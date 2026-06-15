import random
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import Config
from proxy_manager import ProxyManager, Proxy
from user_agent import UserAgentManager
from statistics import StatisticsManager, VisitRecord, AdClickRecord
from ad_detector import AdDetector, AdCandidate
from article_discovery import ArticleDiscovery
from visitor import create_visitor
from logger import logger
from timing import truncated_normal, truncated_normal_int, natural_delay, natural_int


def _soup(html: str):
    """Parse HTML with lxml fallback to html.parser."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


class CampaignTarget:
    def __init__(self, target_dict: dict):
        self.name: str = target_dict.get("name", "Unnamed")
        self.url: str = target_dict["url"]
        self.weight: int = target_dict.get("weight", 1)
        self.click_prob: float = target_dict.get("click_probability", 0.3)
        self.ad_click_prob: float = target_dict.get("ad_click_probability", 0.25)
        self.max_clicks: int = target_dict.get("max_clicks_per_visit", 2)
        self.deep_browse: bool = target_dict.get("deep_browse", True)
        self.keywords: List[str] = target_dict.get("keywords", [])
        self.target_visits: int = target_dict.get("target_visits", 0)
        self.discover_articles: bool = target_dict.get("discover_articles", False)
        self.articles: List[str] = target_dict.get("articles", [])
        self.article_distribution: str = target_dict.get("article_distribution", "random")
        self.article_url_patterns: List[str] = target_dict.get("article_url_patterns", [])
        self.max_articles: int = target_dict.get("max_articles", 50)
        self._completed_visits: int = 0
        self._article_index: int = 0
        self._articles_discovered: bool = False
        self._visit_lock: threading.Lock = threading.Lock()

    @property
    def completed_visits(self) -> int:
        return self._completed_visits

    @completed_visits.setter
    def completed_visits(self, val: int):
        self._completed_visits = val

    @property
    def is_campaign(self) -> bool:
        return self.target_visits > 0

    @property
    def campaign_done(self) -> bool:
        return self.is_campaign and self._completed_visits >= self.target_visits

    @property
    def campaign_progress(self) -> float:
        if not self.is_campaign:
            return 0.0
        return min(100.0, (self._completed_visits / self.target_visits) * 100)

    def get_visit_url(self) -> str:
        if not self.articles:
            return self.url
        if self.article_distribution == "sequential":
            idx = min(self._article_index, len(self.articles) - 1)
            self._article_index = (self._article_index + 1) % len(self.articles)
            return self.articles[idx]
        elif self.article_distribution == "round-robin":
            idx = self._article_index % len(self.articles)
            self._article_index += 1
            return self.articles[idx]
        else:
            return random.choice(self.articles)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "weight": self.weight,
            "click_probability": self.click_prob,
            "ad_click_probability": self.ad_click_prob,
            "max_clicks_per_visit": self.max_clicks,
            "deep_browse": self.deep_browse,
            "keywords": self.keywords,
            "target_visits": self.target_visits if self.is_campaign else 0,
            "discover_articles": self.discover_articles,
            "articles": self.articles,
            "article_distribution": self.article_distribution,
            "article_url_patterns": self.article_url_patterns,
            "max_articles": self.max_articles,
        }


class TrafficBot:
    def __init__(self, config: Config):
        self.config = config
        self.proxy_manager = ProxyManager(config)
        self.ua_manager = UserAgentManager(config)
        self.stats = StatisticsManager(config)
        self.ad_detector = AdDetector()
        self.article_discovery = ArticleDiscovery(timeout=config.timeout)
        self._thread_local = threading.local()
        self._visitors = []
        self._visitors_lock = threading.Lock()
        self.targets: List[CampaignTarget] = [CampaignTarget(t) for t in config.targets]
        self._running = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._thread: Optional[threading.Thread] = None
        self._campaign_complete = threading.Event()
        self._campaign_complete.set()
        self._campaign_done = False
        self._summary_printed = False
        self._state_lock: threading.Lock = threading.Lock()
        self._sticky_proxy_local = threading.local()

    def _build_headers(self, url: str = "", referrer: str = "") -> dict:
        ua = self.ua_manager.get()
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": self.config.get("behavior", "accept_language", default="en-US,en;q=0.9"),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if referrer:
            headers["Referer"] = referrer
        elif self.config.referrer_enabled:
            headers["Referer"] = self._generate_referrer(url)
        if self.config.get("behavior", "dnt", default=False):
            headers["DNT"] = "1"
        if self.config.get("behavior", "sec_fetch_modes", default=True):
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = random.choice(["none", "cross-site", "same-origin"])
            headers["Sec-Fetch-User"] = "?1"
        if random.random() < 0.3:
            headers["Cache-Control"] = "no-cache"
            headers["Pragma"] = "no-cache"
        return headers

    def _generate_referrer(self, url: str) -> str:
        sources = self.config.referrer_sources
        if not sources:
            return "https://google.com/"
        source = random.choice(sources)
        if "{keyword}" in source:
            kws = ["free", "offer", "deal", "discount", "2025", "2026",
                   "best", "top", "review", "how to", "guide", "cheap",
                   "price", "compare", "buy", "shop", "online"]
            kw = random.choice(kws)
            source = source.replace("{keyword}", kw)
        return source

    def _get_target(self) -> Optional[CampaignTarget]:
        if self._campaign_done:
            return None
        active = [t for t in self.targets if not t.campaign_done]
        if not active:
            return None
        total_weight = sum(t.weight for t in active)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for t in active:
            cumulative += t.weight
            if r <= cumulative:
                return t
        return active[0]

    def _random_delay(self, lo: Optional[float] = None, hi: Optional[float] = None):
        lo = lo if lo is not None else self.config.min_delay
        hi = hi if hi is not None else self.config.max_delay
        # Pake natural_delay dengan mean = midpoint, auto-pilih distribusi
        mean = (lo + hi) / 2
        time.sleep(natural_delay(mean, lo, hi))

    def _simulate_visit_duration(self, lo: Optional[int] = None, hi: Optional[int] = None):
        lo = lo if lo is not None else self.config.visit_duration_min
        hi = hi if hi is not None else self.config.visit_duration_max
        mean = (lo + hi) / 2
        duration = natural_int(mean, lo, hi)
        for _ in range(duration):
            if not self._running or not self._pause_event.is_set():
                return
            # Natural 1s pause tapi dengan variasi (bukan sleep 1 exact)
            time.sleep(truncated_normal(1.0, 0.15, 0.5, 1.5))

    def _simulate_scroll(self, html: str):
        if not self.config.get("behavior", "simulate_scroll", default=True):
            return
        try:
            soup = _soup(html)
            paragraphs = len(soup.find_all(["p", "div", "section"]))
            steps = min(natural_int(max(1, paragraphs // 10), 1, 5), 5)
            for _ in range(steps):
                if not self._running or not self._pause_event.is_set():
                    return
                time.sleep(natural_delay(
                    1.5,
                    self.config.get("general", "scroll_wait_min", default=1),
                    self.config.get("general", "scroll_wait_max", default=3),
                ))
        except Exception:
            pass

    def _accept_cookie_consent(self, session: requests.Session, html: str, base_url: str):
        if not self.config.get("behavior", "cookie_consent", default=True):
            return
        try:
            soup = _soup(html)
            patterns = r"accept|agree|allow|consent|cookie|got.?it|i.?understand|accept.?all|accept.?cookies|accept.?and.?continue"
            for tag in soup.find_all(["button", "a", "input", "span"],
                                     text=re.compile(patterns, re.I)):
                if not tag.get_text(strip=True):
                    continue
                parent = tag.find_parent("form")
                action = base_url
                if parent and parent.get("action"):
                    action = urljoin(base_url, parent["action"])
                headers = self._build_headers(action, referrer=base_url)
                try:
                    if tag.name == "input" and tag.get("type") == "submit":
                        data = {}
                        if parent:
                            for inp in parent.find_all("input"):
                                if inp.get("name"):
                                    data[inp["name"]] = inp.get("value", "")
                        session.post(action, data=data, headers=headers, timeout=10)
                    else:
                        href = tag.get("href")
                        if href:
                            session.get(urljoin(base_url, href), headers=headers, timeout=10)
                        elif tag.name == "button" and parent:
                            data = {}
                            for inp in parent.find_all("input"):
                                if inp.get("name"):
                                    data[inp["name"]] = inp.get("value", "")
                            session.post(action, data=data, headers=headers, timeout=10)
                    self._random_delay(0.5, 1.5)
                    break
                except Exception:
                    continue
        except Exception:
            pass

    def _browse_deep(self, session: requests.Session, html: str, base_url: str,
                     max_pages: int) -> List[Tuple[str, int, float]]:
        visited = []
        if not self.config.get("behavior", "multi_page_browsing", default=True):
            return visited
        max_pgs = min(max_pages, self.config.get("general", "max_pages_per_session", default=3))
        cur_html, cur_url = html, base_url
        for _ in range(max_pgs):
            try:
                soup = _soup(cur_html)
                links = []
                for a in soup.find_all("a", href=True):
                    h = a["href"]
                    if any(s in h for s in ["#", "javascript:", "mailto:", "tel:"]):
                        continue
                    t = a.get_text(strip=True)
                    if not t or len(t) <= 5:
                        continue
                    full = urljoin(cur_url, h)
                    if urlparse(full).netloc == urlparse(base_url).netloc:
                        links.append(full)
                if not links:
                    break
                chosen = random.choice(links[:10])
                self._random_delay(1, 3)
                headers = self._build_headers(chosen, referrer=cur_url)
                resp = session.get(chosen, headers=headers, timeout=self.config.timeout)
                if resp.status_code == 200:
                    visited.append((chosen, resp.status_code, 0))
                    cur_html, cur_url = resp.text, chosen
                    self._simulate_scroll(resp.text)
                    self._simulate_visit_duration(2, 8)
                else:
                    break
            except Exception:
                break
        return visited

    def _click_ads(self, session: requests.Session, html: str, base_url: str,
                   target_name: str, click_prob: float, max_clicks: int) -> Tuple[int, int]:
        if not self.config.get("ad_clicking", "enabled", default=True):
            return 0, 0
        if random.random() > click_prob:
            return 0, 0

        ads = self.ad_detector.detect_all(html, base_url)
        if not ads:
            return 0, 0

        ad_cfg = self.config.get("ad_clicking", default={})
        mx = min(ad_cfg.get("max_ads_per_visit", 3), max_clicks)
        pref = ad_cfg.get("preferred_networks", [])
        avoid = ad_cfg.get("avoid_domains", [])
        enabled = ad_cfg.get("ad_types", {})
        log_all = ad_cfg.get("log_all_ads_found", False)

        if log_all:
            logger.info(f"{target_name} | Found {len(ads)} ad(s)")

        filtered = []
        script_ads = []
        for ad in ads:
            tp = self.ad_detector.classify_ad_type(ad)
            if not enabled.get(tp, True):
                continue
            if avoid and any(d in ad.url.lower() for d in avoid):
                continue
            # Separate script_ad for CPA impression handling
            if tp == "script_ad":
                script_ads.append(ad)
                continue
            filtered.append(ad)

        if pref:
            preferred = [a for a in filtered if a.ad_network in pref]
            if preferred:
                filtered = preferred
        if not filtered:
            return 0, 0

        random.shuffle(filtered)
        to_click = filtered[:mx]
        done, total_ads = 0, len(ads)

        for ad in to_click:
            if not self._running or not self._pause_event.is_set():
                break
            tp = self.ad_detector.classify_ad_type(ad)
            url = self.ad_detector.get_ad_click_url(ad, html, base_url)
            self._random_delay(ad_cfg.get("click_delay_min", 2), ad_cfg.get("click_delay_max", 6))
            headers = self._build_headers(url, referrer=base_url)
            try:
                start = time.time()
                resp = session.get(url, headers=headers, timeout=self.config.timeout, allow_redirects=True)
                elapsed = time.time() - start
                ok = resp.status_code == 200
                self.stats.record_ad_click(AdClickRecord(
                    target_name=target_name, page_url=base_url, ad_url=url,
                    ad_type=tp, ad_network=ad.ad_network, response_code=resp.status_code,
                    response_time=elapsed, timestamp=time.time(), success=ok,
                ))
                if ok:
                    done += 1
                    logger.info(f"{target_name} | AD [{tp}/{ad.ad_network}] {resp.status_code} | {url[:60]}...")
                    if ad_cfg.get("click_depth", 1) > 0:
                        self._simulate_visit_duration(2, 6)
                        self._simulate_scroll(resp.text)
                else:
                    logger.fail(f"{target_name} | AD FAIL [{tp}] {resp.status_code}")
            except Exception as e:
                self.stats.record_ad_click(AdClickRecord(
                    target_name=target_name, page_url=base_url, ad_url=url,
                    ad_type=tp, ad_network=ad.ad_network, response_code=0,
                    response_time=0, timestamp=time.time(), success=False, error=str(e)[:100],
                ))
                logger.fail(f"{target_name} | AD ERR [{tp}] {str(e)[:60]}")

        # CPA script ads don't have click URLs - they run in browser context
        for ad in script_ads:
            self.stats.record_ad_click(AdClickRecord(
                target_name=target_name, page_url=base_url, ad_url=ad.url,
                ad_type=ad.element_type, ad_network=ad.ad_network,
                response_code=200, response_time=0,
                timestamp=time.time(), success=True,
            ))
            logger.info(f"{target_name} | CPA IMPRESSION [{ad.ad_network}] | {ad.url[:60]}...")

        return total_ads, done

    def _create_session(self, proxy_dict: Optional[dict]) -> requests.Session:
        s = requests.Session()
        if proxy_dict:
            s.proxies.update(proxy_dict)
        a = requests.adapters.HTTPAdapter(max_retries=0, pool_connections=20, pool_maxsize=20)
        s.mount("http://", a)
        s.mount("https://", a)
        return s

    def _request_with_retry(self, session: requests.Session, url: str,
                            headers: dict) -> Tuple[Optional[requests.Response], float, Optional[Proxy]]:
        last_error = ""
        timeout = self.config.timeout
        max_retries = self.config.max_retries
        proxy = None

        if self.config.proxy_enabled:
            sticky = self.config.get("proxies", "sticky_session", default=False)
            if not sticky or not hasattr(self._sticky_proxy_local, "proxy"):
                proxy = self.proxy_manager.get_proxy()
                if sticky:
                    self._sticky_proxy_local.proxy = proxy
            else:
                proxy = self._sticky_proxy_local.proxy

        proxy_dict = proxy.get_dict() if proxy else None

        for attempt in range(max_retries + 1):
            try:
                start = time.time()
                if proxy_dict:
                    session.proxies.update(proxy_dict)
                resp = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                elapsed = time.time() - start
                if resp.status_code == 200:
                    return resp, elapsed, proxy
                elif resp.status_code in (403, 429):
                    last_error = f"Blocked ({resp.status_code})"
                    if attempt < max_retries:
                        time.sleep(self.config.get("general", "retry_delay", default=1.0) * (attempt + 1) * 2)
                        proxy = self.proxy_manager.get_proxy()
                        proxy_dict = proxy.get_dict() if proxy else None
                        continue
                else:
                    last_error = f"HTTP {resp.status_code}"
                    if attempt < max_retries and resp.status_code >= 500:
                        time.sleep(self.config.get("general", "retry_delay", default=1.0) * (attempt + 1))
                        proxy = self.proxy_manager.get_proxy()
                        proxy_dict = proxy.get_dict() if proxy else None
                        continue
                    break
            except requests.exceptions.ProxyError as e:
                last_error = f"Proxy: {e}"
                if proxy:
                    proxy.mark_failed()
                if attempt < max_retries:
                    time.sleep(self.config.get("general", "retry_delay", default=1.0) * (attempt + 1))
                    proxy = self.proxy_manager.get_proxy()
                    proxy_dict = proxy.get_dict() if proxy else None
                    continue
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_error = f"Conn: {e}"
                if attempt < max_retries:
                    time.sleep(self.config.get("general", "retry_delay", default=1.0) * (attempt + 1))
                    proxy = self.proxy_manager.get_proxy()
                    proxy_dict = proxy.get_dict() if proxy else None
                    continue
                break
            except Exception as e:
                last_error = str(e)
                break
        return None, 0, proxy

    def _discover_articles_for(self, target: CampaignTarget):
        if target._articles_discovered or not target.discover_articles:
            return
        target._articles_discovered = True
        logger.info(f"{target.name} | Discovering articles from {target.url}...")
        try:
            articles = self.article_discovery.discover(
                target.url,
                patterns=target.article_url_patterns or None,
                max_articles=target.max_articles,
            )
            if articles:
                target.articles = articles
                logger.info(f"{target.name} | Discovered {len(articles)} articles")
                # update config
                for t in self.config.data.get("targets", []):
                    if t.get("name") == target.name:
                        t["articles"] = articles
                        break
                self.config.save()
            else:
                logger.warn(f"{target.name} | No articles found, will use base URL")
        except Exception as e:
            logger.error(f"{target.name} | Article discovery error: {e}")

    def _get_visitor(self):
        if not hasattr(self._thread_local, 'visitor'):
            v = create_visitor(self.config)
            self._thread_local.visitor = v
            with self._visitors_lock:
                self._visitors.append(v)
        return self._thread_local.visitor

    def _visit_target(self, target: CampaignTarget):
        """
        Visit a target with full error resilience.
        Never crashes the worker — always catches exceptions.
        """
        self._discover_articles_for(target)

        engine = self.config.get("general", "engine", default="requests")
        try:
            if engine == "playwright":
                self._visit_with_browser(target)
            else:
                self._visit_with_requests(target)
        except Exception as e:
            logger.error(f"{target.name} | VISIT CRASH: {str(e)[:120]}")
            # Never let a visit crash the worker loop

    def _visit_with_browser(self, target: CampaignTarget):
        """
        Browser visit with full error resilience AND proxy retry.
        - If proxy fails (timeout, tunnel error, etc.), tries the next proxy
        - Properly marks bad proxies so they aren't reused
        - Falls back to direct connection if all proxies exhausted
        - Never crashes the worker
        """
        actual_url = target.get_visit_url()
        name = target.name

        # ── Track ad clicks from this visit ─────────────────────────────
        ads_found = 0
        ads_clicked = 0
        pages_visited = 1
        popup_ad_clicked = 0
        final_result = None
        final_proxy_str = "none"

        # ── Retry loop: try different proxies on failure ────────────────
        max_attempts = max(1, self.config.max_retries + 1)
        for attempt in range(max_attempts):
            if not self._running or not self._pause_event.is_set():
                return

            if attempt > 0:
                # Brief delay before retry with new proxy
                time.sleep(natural_delay(1.5, 0.5, 3.0))

            proxy = None
            proxy_str = "none"

            # ── Get proxy (or fallback to direct) ───────────────────────
            if self.config.proxy_enabled:
                proxy = self.proxy_manager.get_proxy()
                proxy_str = str(proxy) if proxy else "none"
                if proxy is None:
                    if attempt == 0:
                        logger.info(f"{name} | Proxy habis, fallback ke direct connection")
                    else:
                        logger.warn(f"{name} | Proxy habis setelah percobaan {attempt}, fallback direct")

            # ── On retry, log that we're trying a different proxy ───────
            if attempt > 0:
                logger.info(f"{name} | Retry #{attempt} dengan proxy: {proxy_str}")

            # ── Track ad clicks from this visit attempt ─────────────────
            ads_found_this = 0
            ads_clicked_this = 0
            popup_ad_clicked_this = 0

            def _on_page_ready(page, context, result):
                nonlocal ads_found_this, ads_clicked_this, popup_ad_clicked_this

                # ── CPA Popup/Popunder Capture (from visit) ─────────────────
                if result.popups_captured > 0:
                    for popup_url in result.popup_urls:
                        popup_ad_clicked_this += 1
                        ads_found_this += 1
                        ads_clicked_this += 1
                        self.stats.record_ad_click(AdClickRecord(
                            target_name=name, page_url=actual_url, ad_url=popup_url,
                            ad_type="popup", ad_network="cpa_popunder",
                            response_code=200, response_time=result.response_time,
                            timestamp=time.time(), success=True,
                        ))
                        logger.success(f"{name} | CPA POPUNDER [{popup_url[:80]}...]")

                # ── Detect ads from HTML ────────────────────────────────────
                if not result.html:
                    return

                try:
                    ads = self.ad_detector.detect_all(result.html, actual_url)
                    detected_ads_count = len(ads)
                    if detected_ads_count > 0:
                        ads_found_this += detected_ads_count

                    if not ads or random.random() >= target.ad_click_prob:
                        return

                    ad_cfg = self.config.get("ad_clicking", default={})
                    enabled = ad_cfg.get("ad_types", {})
                    avoid = ad_cfg.get("avoid_domains", [])

                    filtered = []
                    for ad in ads:
                        tp = self.ad_detector.classify_ad_type(ad)
                        if not enabled.get(tp, True):
                            continue
                        if avoid and any(d in ad.url.lower() for d in avoid):
                            continue
                        if tp == "script_ad":
                            continue
                        filtered.append(ad)

                    random.shuffle(filtered)
                    for ad in filtered[:target.max_clicks]:
                        if not self._running or not self._pause_event.is_set():
                            break
                        try:
                            tp = self.ad_detector.classify_ad_type(ad)
                            click_result = visitor.click_ad_element(
                                page, ad, result.html, actual_url
                            )
                            ok = click_result and click_result.status == "success"
                            self.stats.record_ad_click(AdClickRecord(
                                target_name=name, page_url=actual_url, ad_url=click_result.url if click_result else ad.url,
                                ad_type=tp, ad_network=ad.ad_network,
                                response_code=click_result.response_code if click_result else 0,
                                response_time=click_result.response_time if click_result else 0,
                                timestamp=time.time(), success=ok,
                            ))
                            if ok:
                                ads_clicked_this += 1
                                logger.info(f"{name} | CLICK [{tp}/{ad.ad_network}] | {ad.url[:60]}...")
                            else:
                                err = click_result.error if click_result else "No result"
                                logger.fail(f"{name} | CLICK FAIL [{tp}] {err}")
                        except Exception as e:
                            logger.fail(f"{name} | CLICK ERR [{tp}] {str(e)[:60]}")
                        page.wait_for_timeout(natural_int(3000, 1500, 6000))
                except Exception:
                    pass

            try:
                visitor = self._get_visitor()
                result = visitor.visit(
                    url=actual_url,
                    referrer=self._generate_referrer(actual_url),
                    visit_duration=(self.config.visit_duration_min, self.config.visit_duration_max),
                    proxy=proxy,
                    on_page_ready=_on_page_ready,
                )

                if result.status == "success":
                    # ── SUCCESS: record + break out of retry loop ───────
                    total_ads_clicked = ads_clicked_this + popup_ad_clicked_this
                    ads_found = ads_found_this
                    ads_clicked = total_ads_clicked

                    self.stats.record_visit(VisitRecord(
                        target_name=name, url=actual_url, proxy=proxy_str,
                        user_agent="Playwright/Chromium", status="success",
                        response_time=result.response_time,
                        response_code=result.response_code,
                        timestamp=time.time(), pages_visited=pages_visited,
                        ads_found=ads_found, ads_clicked=ads_clicked,
                    ))

                    al = f" | Ads: {ads_clicked}/{ads_found}" if ads_found > 0 else ""
                    pp = f" | Popups: {result.popups_captured}" if result.popups_captured > 0 else ""
                    logger.success(f"{name} | {result.response_code} | {result.response_time:.2f}s{pp}{al} | [BROWSER]")

                    if not self._campaign_done:
                        with target._visit_lock:
                            target.completed_visits += 1
                            if target.is_campaign:
                                pct = target.campaign_progress
                                logger.info(f"{name} | Campaign: {target.completed_visits}/{target.target_visits} ({pct:.0f}%)")
                                if target.campaign_done:
                                    logger.success(f"{name} | Campaign target reached!")
                                    self._check_campaign_complete()

                    final_result = result
                    final_proxy_str = proxy_str
                    break  # Exit retry loop on success

                else:
                    # ── FAILED: mark bad proxy + try next ───────────────
                    is_proxy_err = ProxyManager._is_proxy_error(str(result.error))
                    if proxy and is_proxy_err:
                        self.proxy_manager.mark_bad(proxy.url)
                        logger.fail(f"{name} | ATTEMPT {attempt+1}/{max_attempts} FAILED — proxy {proxy_str} ditandai bad: {result.error[:80]}")
                    elif proxy:
                        logger.fail(f"{name} | ATTEMPT {attempt+1}/{max_attempts} FAILED — {result.error[:80]} (bukan error proxy)")
                    else:
                        logger.fail(f"{name} | ATTEMPT {attempt+1}/{max_attempts} FAILED — {result.error[:80]} (tanpa proxy)")

                    final_result = result
                    final_proxy_str = proxy_str

                    # ── If not a proxy error, don't retry (waste of time) ──
                    if not is_proxy_err:
                        break

            except Exception as e:
                # ── CRASH: something went terribly wrong ────────────────
                logger.error(f"{name} | ATTEMPT {attempt+1} CRASH: {str(e)[:80]}")
                if proxy and ProxyManager._is_proxy_error(str(e)):
                    self.proxy_manager.mark_bad(proxy.url)
                final_result = None
                final_proxy_str = proxy_str
                # Don't retry on crash — safer to move on
                break

            # ── If no more proxies usable, stop retrying ────────────────
            if self.config.proxy_enabled and not self.proxy_manager.has_alive:
                logger.warn(f"{name} | Tidak ada proxy alive lagi setelah {attempt+1} percobaan")
                break

        # ── If all retries exhausted and still failed, record final failure ──
        if final_result is None or final_result.status != "success":
            err_msg = final_result.error if final_result else "All retries exhausted"
            self.stats.record_visit(VisitRecord(
                target_name=name, url=actual_url, proxy=final_proxy_str,
                user_agent="Playwright/Chromium", status="failed",
                response_time=final_result.response_time if final_result else 0,
                response_code=final_result.response_code if final_result else 0,
                timestamp=time.time(), error=err_msg[:100],
            ))

    def _visit_with_requests(self, target: CampaignTarget):
        actual_url = target.get_visit_url()
        name = target.name

        headers = self._build_headers(actual_url)
        session = self._create_session(None)

        try:
            resp, elapsed, proxy = self._request_with_retry(session, actual_url, headers)
            proxy_str = str(proxy) if proxy else "none"

            if resp is not None:
                pages_visited = 1
                self._simulate_scroll(resp.text)

                if self.config.get("behavior", "cookie_consent", default=True):
                    self._accept_cookie_consent(session, resp.text, actual_url)

                self._simulate_visit_duration()

                ads_found, ads_clicked = 0, 0
                if resp.text and random.random() < target.ad_click_prob:
                    ad_visitor = self._get_visitor()
                    if hasattr(ad_visitor, 'click_ad'):
                        ads = self.ad_detector.detect_all(resp.text, actual_url)
                        ads_found = len(ads)
                        if ads:
                            ad_cfg = self.config.get("ad_clicking", default={})
                            enabled = ad_cfg.get("ad_types", {})
                            avoid = ad_cfg.get("avoid_domains", [])
                            filtered = []
                            for ad in ads:
                                tp = self.ad_detector.classify_ad_type(ad)
                                if not enabled.get(tp, True):
                                    continue
                                if avoid and any(d in ad.url.lower() for d in avoid):
                                    continue
                                if tp == "script_ad":
                                    continue
                                filtered.append(ad)
                            random.shuffle(filtered)
                            for ad in filtered[:target.max_clicks]:
                                tp = self.ad_detector.classify_ad_type(ad)
                                ad_url = self.ad_detector.get_ad_click_url(ad, resp.text, actual_url)
                                time.sleep(natural_delay(4.0, 1.5, 8.0))
                                click_result = ad_visitor.click_ad(
                                    ad_url, referrer=actual_url,
                                    element_type=tp, ad_network=ad.ad_network,
                                )
                                ok = click_result.status == "success"
                                self.stats.record_ad_click(AdClickRecord(
                                    target_name=name, page_url=actual_url, ad_url=ad_url,
                                    ad_type=tp, ad_network=ad.ad_network,
                                    response_code=click_result.response_code,
                                    response_time=click_result.response_time,
                                    timestamp=time.time(), success=ok,
                                ))
                                if ok:
                                    ads_clicked += 1
                                    logger.info(f"{name} | AD [{tp}/{ad.ad_network}] {click_result.response_code} | {ad_url[:60]}...")
                                else:
                                    logger.fail(f"{name} | AD FAIL [{tp}] {click_result.error}")
                    else:
                        ads_found, ads_clicked = self._click_ads(
                            session, resp.text, actual_url, name,
                            target.ad_click_prob, target.max_clicks,
                        )

                if target.deep_browse and random.random() < target.click_prob:
                    deep = self._browse_deep(session, resp.text, actual_url, max_pages=2)
                    pages_visited += len(deep)

                self.stats.record_visit(VisitRecord(
                    target_name=name, url=actual_url, proxy=proxy_str,
                    user_agent=headers.get("User-Agent", ""), status="success",
                    response_time=elapsed, response_code=resp.status_code,
                    timestamp=time.time(), pages_visited=pages_visited,
                    ads_found=ads_found, ads_clicked=ads_clicked,
                ))

                ad_log = f" | Ads: {ads_clicked}/{ads_found}" if ads_found > 0 else ""
                logger.success(
                    f"{name} | {resp.status_code} | {elapsed:.2f}s "
                    f"| {pages_visited}pp{ad_log} | {proxy_str}"
                )

                if not self._campaign_done:
                    with target._visit_lock:
                        target.completed_visits += 1
                        if target.is_campaign:
                            pct = target.campaign_progress
                            logger.info(
                                f"{name} | Campaign: {target.completed_visits}/{target.target_visits} "
                                f"({pct:.0f}%)"
                            )
                            if target.campaign_done:
                                logger.success(f"{name} | Campaign target reached!")
                            self._check_campaign_complete()

                # external link click
                if random.random() < target.click_prob:
                    try:
                        soup = _soup(resp.text)
                        ext = []
                        for a in soup.find_all("a", href=True):
                            h = a["href"]
                            if h.startswith("http") and urlparse(h).netloc != urlparse(actual_url).netloc:
                                ext.append(h)
                        if ext and random.random() < 0.3:
                            chosen = random.choice(ext)
                            logger.info(f"{name} | External -> {chosen[:60]}...")
                            session.get(chosen, headers=self._build_headers(chosen, referrer=actual_url),
                                        timeout=self.config.timeout)
                    except Exception:
                        pass
            else:
                self.stats.record_visit(VisitRecord(
                    target_name=name, url=actual_url, proxy=proxy_str,
                    user_agent=headers.get("User-Agent", ""), status="failed",
                    response_time=elapsed, response_code=0, timestamp=time.time(),
                    error="Unknown",
                ))
                logger.fail(f"{name} | FAILED | {proxy_str}")
        finally:
            session.close()

    def _check_campaign_complete(self):
        with self._state_lock:
            all_done = all(t.campaign_done for t in self.targets if t.is_campaign)
            if all_done and not self._campaign_done:
                self._campaign_done = True
                if not self._summary_printed:
                    self._summary_printed = True
                    logger.success("ALL CAMPAIGNS COMPLETE!")
                    s = self.stats.get_summary()
                    lines = [
                        f"Total visits: {s['total_visits']}",
                        f"Success: {s['successful']} | Fail: {s['failed']}",
                        f"Rate: {s['success_rate']}%",
                        f"Time: {s['elapsed_seconds']:.0f}s",
                        f"Avg response: {s['avg_response_time']}s",
                        f"Ads clicked: {s['total_ads_clicked']}/{s['total_ads_found']}",
                    ]
                    for line in lines:
                        logger.info(f"[SUMMARY] {line}")
            if self._campaign_done:
                self._campaign_complete.set()
                self.stop()

    def _worker_loop(self):
        """
        Main worker loop — never crashes.
        - Catches all exceptions from visits
        - Auto-skips bad proxies
        - Issues warning when proxies are low
        - Continues running until stopped or campaign complete
        """
        try:
            while self._running:
                self._pause_event.wait()
                if not self._running or self._campaign_done:
                    break
                self._random_delay()
                if self._campaign_done:
                    break
                target = self._get_target()
                if target is None:
                    self._check_campaign_complete()
                    break

                self._visit_target(target)

                # Track consecutive failures for proxy health
                try:
                    # Check proxy health periodically
                    if self.config.proxy_enabled and not self.proxy_manager.has_alive:
                        logger.warn("⚠️  Semua proxy mati! Mencoba direct connection...")
                        if self.proxy_manager.need_refresh:
                            logger.warn("🔄 Auto-refresh proxy dari scraper...")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Worker loop error (recovered): {str(e)[:100]}")
        finally:
            v = getattr(self._thread_local, 'visitor', None)
            if v:
                try:
                    v.close()
                except Exception:
                    pass

    def discover_articles(self, target_name: Optional[str] = None):
        for t in self.targets:
            if target_name and t.name != target_name:
                continue
            if t.discover_articles:
                self._discover_articles_for(t)

    def start(self, threads: Optional[int] = None):
        if self._running:
            logger.warn("Already running")
            return
        if not self.targets:
            logger.error("No targets configured")
            return

        self._running = True
        self._pause_event.set()
        self._campaign_complete.clear()
        num_threads = threads or self.config.threads

        # Check campaigns
        for t in self.targets:
            if t.is_campaign:
                logger.info(f"{t.name} | Campaign: {t.completed_visits}/{t.target_visits} visits")
            if t.discover_articles and not t.articles:
                self._discover_articles_for(t)

        # ── CAPTCHA check — warn if enabled but no API key, auto-disable ──
        captcha_cfg = self.config.get("captcha", default={})
        if captcha_cfg.get("enabled", False):
            solvers_list = captcha_cfg.get("solver", [])
            has_key = any(
                s.get("api_key", "").strip() != ""
                for s in solvers_list if isinstance(s, dict)
            )
            if not has_key:
                logger.warning("⚠️  CAPTCHA enabled in config tapi tidak ada API key — otomatis dinonaktifkan")
                logger.warning("   ➤ Set captcha.solver[].api_key di config.json untuk mengaktifkan")
                captcha_cfg["enabled"] = False
                self.config.save()
            else:
                logger.info("🔐 CAPTCHA solver terdeteksi — akan otomatis mendeteksi & menyelesaikan CAPTCHA")

        # ── Proxy check — warn but DON'T block startup ────────────────
        if self.config.proxy_enabled and self.config.test_proxies:
            logger.info("Testing proxies...")
            try:
                alive, total = self.proxy_manager.test_all()
                logger.info(f"Proxies: {alive}/{total} alive")
                if alive == 0 and total > 0:
                    logger.warn("⚠️  Semua proxy mati! Bot akan fallback ke direct connection.")
                    logger.warn("💡 Gunakan fitur Auto Scrape Proxy untuk proxy baru.")
                    # Try auto-refresh from scraper in background
                    if hasattr(self.proxy_manager, '_try_auto_refresh'):
                        self.proxy_manager._try_auto_refresh()
                elif alive == 0:
                    logger.info("🌐 Tidak ada proxy dikonfigurasi. Menggunakan direct connection.")
            except Exception as e:
                logger.warn(f"Proxy check error: {e} — melanjutkan tanpa proxy")

        # ── Log proxy status ────────────────────────────────────────────
        if self.config.proxy_enabled:
            logger.info(f"🌐 Proxy: {self.proxy_manager.alive_count}/{self.proxy_manager.count} alive")
            if self.proxy_manager.alive_count == 0 and self.proxy_manager.count > 0:
                logger.warn("⚠️  Semua proxy dead — auto-refresh akan dicoba")
                # Fire background refresh
                if hasattr(self.proxy_manager, '_try_auto_refresh'):
                    threading.Thread(target=self.proxy_manager._try_auto_refresh, daemon=True).start()

        campaign_info = ", ".join(
            f"{t.name}: {t.completed_visits}/{t.target_visits}" if t.is_campaign else t.name
            for t in self.targets
        )
        logger.info(f"Starting bot | Threads: {num_threads} | Targets: {campaign_info}")
        logger.info(f"Delay: {self.config.min_delay}-{self.config.max_delay}s | "
                     f"Visit: {self.config.visit_duration_min}-{self.config.visit_duration_max}s")
        logger.info(f"Ads: {'ON' if self.config.get('ad_clicking', 'enabled') else 'OFF'}")

        self._executor = ThreadPoolExecutor(max_workers=num_threads)
        self._thread = threading.Thread(target=self._run_workers, daemon=True)
        self._thread.start()

    def _run_workers(self):
        futures = []
        for _ in range(self.config.threads):
            f = self._executor.submit(self._worker_loop)
            futures.append(f)
        try:
            for f in as_completed(futures):
                f.result()
        except Exception as e:
            logger.error(f"Worker error: {e}")

    def stop(self):
        self._running = False
        self._pause_event.set()
        if self._executor:
            self._executor.shutdown(wait=False)
        # Close all visitors first to prevent resource leaks (Playwright browser processes)
        with self._visitors_lock:
            for v in self._visitors:
                try:
                    v.close()
                except Exception:
                    pass
            self._visitors.clear()
        logger.info("Bot stopped")

    def pause(self):
        self._pause_event.clear()
        logger.info("Paused")

    def resume(self):
        self._pause_event.set()
        logger.info("Resumed")

    def add_target(self, name: str, url: str, weight: int = 1,
                   click_prob: float = 0.3, ad_click_prob: Optional[float] = None,
                   keywords: Optional[List[str]] = None,
                   target_visits: int = 0, discover_articles: bool = False,
                   article_distribution: str = "random"):
        t = {
            "name": name, "url": url, "weight": weight,
            "click_probability": click_prob,
            "ad_click_probability": ad_click_prob or self.config.get("ad_clicking", "probability", default=0.25),
            "keywords": keywords or [],
            "deep_browse": self.config.get("behavior", "multi_page_browsing", default=True),
            "max_clicks_per_visit": 2,
            "target_visits": target_visits,
            "discover_articles": discover_articles,
            "articles": [],
            "article_distribution": article_distribution,
            "article_url_patterns": [],
            "max_articles": 50,
        }
        self.targets.append(CampaignTarget(t))
        self.config.data["targets"].append(t)
        self.config.save()
        logger.info(f"Added: {name} -> {url}" +
                    (f" | Campaign: {target_visits} visits" if target_visits else "") +
                    (f" | Article discovery ON" if discover_articles else ""))

    def remove_target(self, name: str) -> bool:
        before = len(self.targets)
        self.targets = [t for t in self.targets if t.name != name]
        self.config.data["targets"] = [t.to_dict() if isinstance(t, CampaignTarget) else t
                                        for t in self.targets]
        self.config.save()
        if len(self.targets) < before:
            logger.info(f"Removed: {name}")
            return True
        return False

    def list_targets(self) -> List[dict]:
        return [t.to_dict() for t in self.targets]

    def get_status(self) -> dict:
        campaigns = []
        for t in self.targets:
            if t.is_campaign:
                campaigns.append({
                    "name": t.name, "target": t.target_visits,
                    "completed": t.completed_visits,
                    "progress": round(t.campaign_progress, 1),
                    "articles": len(t.articles),
                })
        return {
            "running": self._running,
            "paused": not self._pause_event.is_set(),
            "targets": len(self.targets),
            "threads": self.config.threads,
            "proxies": {
                "enabled": self.config.proxy_enabled,
                "total": self.proxy_manager.count,
                "alive": self.proxy_manager.alive_count,
                "playwright_compatible": self.proxy_manager.playwright_usable_count,
            },
            "ad_clicking": self.config.get("ad_clicking", "enabled", default=True),
            "campaigns": campaigns,
            "stats": self.stats.get_summary(),
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()
