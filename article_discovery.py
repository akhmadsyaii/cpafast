import random
import re
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from logger import logger


ARTICLE_URL_PATTERNS = [
    r"/blog/", r"/blogs/",
    r"/article/", r"/articles/",
    r"/post/", r"/posts/",
    r"/news/",
    r"/story/", r"/stories/",
    r"/entry/",
    r"/content/",
    r"/p/",
    r"/\d{4}/\d{2}/",    # date-based: /2024/01/
    r"/\d{4}/\d{2}/\d{2}/",  # /2024/01/15/
    r"/\d{4}/\d{2}/.+",
    r"/\d{8}/",           # /20240115/
    r"-article$",
    r"-news$",
    r"-guide$",
    r"-review$",
    r"-tutorial$",
    r"-tips$",
    r"-story$",
    r".html$", r".htm$", r".php$",
    r"/page/", r"/pages/",
    r"/topic/",
    r"/category/",
    r"/tag/",
    r"/author/",
    r"/profile/",
    r"/listing/",
    r"/item/", r"/items/",
    r"/product/", r"/products/",
    r"/detail/",
    r"/view/",
    r"/read/",
    r"/amp/",
]

SKIP_EXTENSIONS = [
    ".css", ".js", ".json", ".xml", ".rss", ".atom",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz",
    ".mp4", ".avi", ".mov",
    ".woff", ".woff2", ".ttf", ".eot",
    ".ico",
]

SKIP_KEYWORDS = [
    "login", "logout", "signup", "register",
    "cart", "checkout", "basket",
    "account", "profile", "settings",
    "admin", "wp-admin", "dashboard",
    "#", "javascript:", "mailto:", "tel:",
    "facebook.com", "twitter.com", "instagram.com",
    "youtube.com", "linkedin.com",
    "tag/", "category/", "author/",
    "page/2", "page/3",
    "feed", "rss", "atom",
    "comments", "reply",
    "share?", "share/",
    "privacy", "terms", "contact",
    "print", "print/",
    "amp/", "/amp",
]


class ArticleDiscovery:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ArticleDiscovery/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def discover(self, base_url: str, patterns: Optional[List[str]] = None,
                 max_articles: int = 50) -> List[str]:
        found: Set[str] = set()
        parsed = urlparse(base_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        urls_from_sitemap = self._from_sitemap(base_url)
        found.update(urls_from_sitemap)
        if urls_from_sitemap:
            logger.info(f"ArticleDiscovery | Sitemap: {len(urls_from_sitemap)} URLs found")

        robots_sitemaps = self._from_robots(base_domain)
        for sm in robots_sitemaps:
            if len(found) >= max_articles:
                break
            sm_urls = self._parse_sitemap(sm)
            found.update(sm_urls)

        # From HTML homepage
        if len(found) < max_articles:
            html_urls = self._from_html(base_url)
            found.update(html_urls)
            logger.info(f"ArticleDiscovery | Homepage: {len(html_urls)} URLs found")

        custom_patterns = patterns or ARTICLE_URL_PATTERNS
        filtered = self._filter_articles(list(found), custom_patterns, max_articles)

        random.shuffle(filtered)
        logger.info(f"ArticleDiscovery | Total articles discovered: {len(filtered)}")
        return filtered[:max_articles]

    def discover_from_sitemap(self, base_url: str, max_articles: int = 50) -> List[str]:
        found = self._from_sitemap(base_url)
        if not found:
            parsed = urlparse(base_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            robots = self._from_robots(base)
            for sm in robots:
                found.extend(self._parse_sitemap(sm))
        filtered = self._filter_articles(found, max_articles=max_articles)
        random.shuffle(filtered)
        return filtered[:max_articles]

    def discover_from_homepage(self, base_url: str, max_articles: int = 50) -> List[str]:
        found = self._from_html(base_url)
        filtered = self._filter_articles(found, max_articles=max_articles)
        random.shuffle(filtered)
        return filtered[:max_articles]

    def _from_sitemap(self, base_url: str) -> List[str]:
        urls = []
        sitemap_urls = [f"{base_url.rstrip('/')}/sitemap.xml"]

        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        sitemap_urls.append(f"{base}/sitemap.xml")
        sitemap_urls.append(f"{base}/sitemap_index.xml")
        sitemap_urls.append(f"{base}/wp-sitemap.xml")

        for sm_url in sitemap_urls:
            found = self._parse_sitemap(sm_url)
            urls.extend(found)
            if found:
                break

        return urls

    def _parse_sitemap(self, url: str) -> List[str]:
        urls = []
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.content, "lxml-xml")
            locs = soup.find_all("loc")
            if not locs:
                return []

            sub_sitemaps = []
            article_urls = []
            for loc in locs:
                text = loc.get_text(strip=True)
                if not text:
                    continue
                if "sitemap" in text.lower() and text.endswith(".xml"):
                    sub_sitemaps.append(text)
                else:
                    article_urls.append(text)

            if sub_sitemaps:
                for sub in sub_sitemaps[:5]:
                    urls.extend(self._parse_sitemap(sub))
            urls.extend(article_urls)
        except Exception:
            pass
        return urls

    def _from_robots(self, base_domain: str) -> List[str]:
        sitemaps = []
        try:
            resp = self.session.get(
                f"{base_domain}/robots.txt", timeout=self.timeout
            )
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sm = line.split(":", 1)[1].strip()
                        if sm:
                            sitemaps.append(sm)
        except Exception:
            pass
        return sitemaps

    def _from_html(self, url: str) -> List[str]:
        urls = set()
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                full = urljoin(url, href)
                parsed = urlparse(full)
                if parsed.scheme in ("http", "https") and parsed.netloc:
                    urls.add(full)

            # Also check structured data
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json as _json
                    data = _json.loads(script.string)
                    if isinstance(data, dict):
                        if data.get("@type") in ("Article", "BlogPosting", "NewsArticle"):
                            if data.get("url"):
                                urls.add(data["url"])
                        elif data.get("mainEntity"):
                            me = data["mainEntity"]
                            if isinstance(me, dict) and me.get("url"):
                                urls.add(me["url"])
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("@type") in (
                                "Article", "BlogPosting", "NewsArticle"
                            ):
                                if item.get("url"):
                                    urls.add(item["url"])
                except Exception:
                    pass
        except Exception:
            pass
        return list(urls)

    def _filter_articles(self, urls: List[str],
                         patterns: Optional[List[str]] = None,
                         max_articles: int = 50) -> List[str]:
        result = []
        patterns = patterns or ARTICLE_URL_PATTERNS
        compiled = [re.compile(p, re.I) for p in patterns]

        for url in urls:
            parsed = urlparse(url)
            path = parsed.path
            if not path or path == "/":
                continue

            ext = path.split("?")[0].rsplit(".", 1)[-1].lower() if "." in path else ""
            if f".{ext}" in SKIP_EXTENSIONS:
                continue

            url_lower = url.lower()
            if any(sk in url_lower for sk in SKIP_KEYWORDS):
                continue

            matched = False
            for cp in compiled:
                if cp.search(path):
                    matched = True
                    break
            if not matched:
                continue

            if url not in result:
                result.append(url)
                if len(result) >= max_articles:
                    break

        return result

    def close(self):
        self.session.close()
