from __future__ import annotations

import re
import requests
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# ── Comprehensive ad-network domain list (30+ networks) ────────────────────
AD_NETWORK_DOMAINS = [
    # Google
    "googleads", "doubleclick", "googlesyndication",
    "facebook.com/ads", "amazon-adsystem",
    # Display / Ad Exchanges
    "adnxs", "rubiconproject", "openx", "pubmatic",
    "criteo", "adform", "sovrn", "indexexchange",
    "bidswitch", "adroll", "triplelift", "yieldmo",
    "smaato", "inmobi", "chartboost", "contextweb",
    "gumgum", "33across", "smartad", "smartadserver",
    # Native Ads
    "outbrain", "taboola", "mgid", "revcontent", "zergnet",
    "nativo", "playwire",
    # CPA / Traffic / Pop Networks
    "adsterra", "clickadu", "popads", "propellerads",
    "exoclick", "juicyads", "trafficjunky",
    "hilltopads", "adcash", "bidvertiser",
    "popcash", "popunder", "revenuehits",
    "cpagrip", "cpalead", "cpabuild",
    "monetag", "monetizus", "adtiming",
    "vungle", "ironSource",
    # Misc / catch-all
    "adservice", "adserver", "adsrv",
    "ads.", ".ads.", "media.net", "infolinks", "sonobi",
]

# ── Canonical short-name for each domain above ─────────────────────────────
AD_NETWORK_ALIASES = {
    "googleads": "google_ads", "doubleclick": "google_ads",
    "googlesyndication": "google_adsense", "adnxs": "appnexus",
    "rubiconproject": "rubicon", "openx": "openx",
    "pubmatic": "pubmatic", "criteo": "criteo",
    "adform": "adform", "sovrn": "sovrn",
    "indexexchange": "indexexchange", "bidswitch": "bidswitch",
    "adroll": "adroll", "outbrain": "outbrain",
    "taboola": "taboola", "mgid": "mgid",
    "revcontent": "revcontent", "zergnet": "zergnet",
    "adsterra": "adsterra", "clickadu": "clickadu",
    "popads": "popads", "propellerads": "propellerads",
    "exoclick": "exo_click", "juicyads": "juicyads",
    "hilltopads": "hilltop_ads", "adcash": "adcash",
    "bidvertiser": "bidvertiser", "popcash": "popcash",
    "popunder": "popunder", "trafficjunky": "trafficjunky",
    "adservice": "adservice", "adserver": "adserver",
    "adsrv": "adserver", "ads.": "generic_ad",
    ".ads.": "generic_ad", "media.net": "media_net",
    "infolinks": "infolinks", "sonobi": "sonobi",
    "contextweb": "contextweb", "gumgum": "gumgum",
    "33across": "33across", "smartad": "smart_adserver",
    "cpagrip": "cpagrip", "cpalead": "cpalead",
    "cpabuild": "cpabuild", "monetag": "monetag",
    "monetizus": "monetizus", "adtiming": "adtiming",
    "vungle": "vungle", "ironsource": "ironsource",
}

AD_CLASS_PATTERNS = [
    "ad", "ads", "adsense", "advert", "advertisement",
    "banner", "sponsor", "sponsored", "promo", "promotion",
    "native-ad", "nativead", "in-content-ad",
    "recommend", "recommended", "related",
    "popup", "pop-up", "popunder",
    "leaderboard", "skyscraper", "rectangle",
    "sticky", "floating", "overlay",
    "google-ad", "dfp-ad", "gam-ad",
    "prebid", "header-bidder",
]

AD_ID_PATTERNS = [
    "ad-", "-ad", "ads-", "-ads",
    "banner", "sponsor", "promo",
    "popup", "pop-under",
]

AD_REL_PATTERNS = ["sponsored", "tag"]

AD_IMAGE_KEYWORDS = ["ad", "ads", "banner", "sponsor", "promo"]


class AdCandidate:
    def __init__(self, url: str, element_type: str, ad_network: str,
                 selector: str, text: str):
        self.url = url
        self.element_type = element_type
        self.ad_network = ad_network
        self.selector = selector
        self.text = text

    def __repr__(self):
        return f"AdCandidate({self.element_type}, {self.ad_network}, {self.url[:50]})"


class AdDetector:
    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def detect_all(self, html: str, base_url: str) -> List[AdCandidate]:
        ads: List[AdCandidate] = []
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # 1. Iframe-based ads (AdSense, OpenX, Adsterra iframe slots…)
        ads.extend(self._detect_iframes(soup, base_url))

        # 2. <a> tags linking to known ad-network click URLs
        ads.extend(self._detect_ad_links(soup, base_url))

        # 3. Google AdSense <ins class="adsbygoogle">
        ads.extend(self._detect_adsense(soup, base_url))

        # 4. Elements identified by ad-related CSS class / id
        ads.extend(self._detect_class_id_elements(soup, base_url))

        # 5. Elements with data-* ad attributes
        ads.extend(self._detect_data_attributes(soup, base_url))

        # 6. <ampl-amp> / <amp-embed> ads
        ads.extend(self._detect_amp_ads(soup, base_url))

        # 7. General script-based ads (AdSense JS, etc.)
        ads.extend(self._detect_script_based_ads(soup, base_url))

        # 8. CPA-network inline scripts that inject popups/banners
        ads.extend(self._detect_cpa_network_scripts(soup, base_url))

        # 9. Inline script popunder detection (window.open, location.href, etc.)
        ads.extend(self._detect_inline_script_ads(soup, base_url))

        # 10. Data-attribute redirect ads (data-href, data-redirect, etc.)
        ads.extend(self._detect_data_redirect_ads(soup, base_url))

        # 11. Popup / modal / overlay elements
        ads.extend(self._detect_popup_patterns(soup, base_url))

        # 12. Native-ad widgets  (Outbrain, Taboola, Revcontent…)
        ads.extend(self._detect_native_ads(soup, base_url))

        # 13. Image ads (CPA banners in <a><img …>)
        ads.extend(self._detect_image_ads(soup, base_url))

        # Deduplicate by URL
        seen_urls: set = set()
        unique: List[AdCandidate] = []
        for ad in ads:
            if ad.url not in seen_urls:
                seen_urls.add(ad.url)
                unique.append(ad)
        return unique

    def classify_ad_type(self, ad: AdCandidate) -> str:
        t = ad.element_type
        url_l = ad.url.lower()
        text_l = ad.text.lower()

        if any(x in url_l for x in ["popup", "pop-up", "popunder", "pop_under"]):
            return "popup"
        if any(x in text_l for x in ["popup", "pop-up", "popunder"]):
            return "popup"
        if any(x in url_l for x in ["banner"]):
            return "banner"
        if ad.ad_network in ("outbrain", "taboola", "revcontent",
                            "mgid", "zergnet", "nativo"):
            return "native"
        if ad.ad_network in ("google_adsense", "google_ads"):
            return "display"
        if t == "iframe":
            return "display"
        if t in ("ad_link", "class_id", "data_attr"):
            text_low = ad.text.lower()
            if any(x in text_low for x in ["sponsored", "ad ", "promo"]):
                return "sponsored_link"
            return "link"
        return t

    def _identify_ad_network(self, url: str) -> Optional[str]:
        url_lower = url.lower()
        for domain in AD_NETWORK_DOMAINS:
            if domain in url_lower:
                alias = AD_NETWORK_ALIASES.get(domain)
                if alias:
                    return alias
                return domain.split(".")[0].split("/")[0].replace(".", "_")
        return None

    def get_ad_click_url(self, ad: AdCandidate, html: str,
                         base_url: str) -> str:
        """Return the best guess for the *click* URL of *ad*.

        For ``iframe`` / ``amp_ad`` / ``script_ad`` the element URL is
        returned directly — the caller is expected to navigate into it
        (Playwright) or fetch its real ``src`` via HTTP (requests).

        For all other types we re-parse *html* looking for the ``<a>``
        that wraps or matches the saved selector and extract its ``href``.
        """
        if ad.element_type in ("iframe", "amp_ad", "script_ad"):
            return ad.url
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
        try:
            target = soup.select_one(ad.selector)
            if target:
                a_tag = target if target.name == "a" else target.find("a", href=True)
                if a_tag and a_tag.get("href"):
                    href = a_tag["href"]
                    return href if href.startswith("http") else urljoin(base_url, href)
        except Exception:
            pass
        return ad.url

    # ─────────────────────────────────────────────────────────────────────────
    # Internal detectors
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_iframes(self, soup: BeautifulSoup,
                        base_url: str) -> List[AdCandidate]:
        ads = []
        for iframe in soup.find_all(["iframe", "frame"]):
            src = iframe.get("src", "") or iframe.get("data-src", "")
            if not src:
                continue
            full_url = urljoin(base_url, src)
            ad_network = self._identify_ad_network(full_url)
            if ad_network:
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="iframe",
                    ad_network=ad_network,
                    selector="iframe",
                    text=iframe.get("title", "") or "",
                ))
            elif any(re.search(r'\b' + re.escape(x) + r'\b', src.lower())
                     for x in ["ad", "ads", "banner", "sponsor"]):
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="iframe",
                    ad_network="unknown",
                    selector="iframe",
                    text=iframe.get("title", "") or "",
                ))
        return ads

    def _detect_ad_links(self, soup: BeautifulSoup,
                         base_url: str) -> List[AdCandidate]:
        ads = []
        base_netloc = urlparse(base_url).netloc
        for a in soup.find_all("a", href=True):
            href = a["href"]
            rel = a.get("rel", [])
            rel_str = " ".join(rel) if isinstance(rel, list) else str(rel)
            classes = " ".join(a.get("class", []))
            link_text = a.get_text(strip=True)

            # Skip javascript: URLs
            if href.lower().startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)
            full_netloc = urlparse(full_url).netloc

            # Skip internal links - they're navigation, not ads
            if full_netloc == base_netloc:
                continue

            ad_network = self._identify_ad_network(full_url)

            is_sponsored = any(p in rel_str.lower() for p in AD_REL_PATTERNS)
            has_ad_class = any(p in classes.lower() for p in AD_CLASS_PATTERNS)
            is_ad_keyword = bool(re.search(r'\b(ad|ads|banner)\b', href.lower()))

            if ad_network or is_sponsored or has_ad_class or is_ad_keyword:
                network = ad_network or "sponsored_link"
                if not ad_network and is_sponsored:
                    network = "sponsored"
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="ad_link",
                    ad_network=network,
                    selector=f"a[href*='{href[:30]}']",
                    text=link_text,
                ))
        return ads

    def _detect_adsense(self, soup: BeautifulSoup,
                        base_url: str) -> List[AdCandidate]:
        ads = []
        for ins in soup.find_all(
                "ins", class_=re.compile(r"adsbygoogle", re.I)):
            slot = ins.get("data-ad-slot", "")
            client = ins.get("data-ad-client", "")
            if client:
                ads.append(AdCandidate(
                    url=base_url,
                    element_type="adsense",
                    ad_network="google_adsense",
                    selector=f"ins[data-ad-slot='{slot}']" if slot
                             else "ins.adsbygoogle",
                    text=ins.get_text(strip=True) or "Google AdSense",
                ))
        for div in soup.find_all("div",
                                 class_=re.compile(r"adsbygoogle", re.I)):
            ads.append(AdCandidate(
                url=base_url,
                element_type="adsense",
                ad_network="google_adsense",
                selector="div.adsbygoogle",
                text="Google AdSense",
            ))
        return ads

    def _detect_class_id_elements(self, soup: BeautifulSoup,
                                   base_url: str) -> List[AdCandidate]:
        ads = []
        base_netloc = urlparse(base_url).netloc
        for tag in soup.find_all(True):
            classes = tag.get("class", [])
            classes_str = (" ".join(classes)
                           if isinstance(classes, list) else str(classes))
            tag_id = tag.get("id", "") or ""

            if not classes_str and not tag_id:
                continue

            is_ad = any(
                re.search(r'\b' + re.escape(p) + r'\b', classes_str.lower())
                for p in AD_CLASS_PATTERNS)
            if not is_ad:
                is_ad = any(p in tag_id.lower() for p in AD_ID_PATTERNS)

            if is_ad:
                link = (tag.find("a", href=True)
                        if tag.name != "a" else tag)
                if link and link.get("href"):
                    href = link["href"]
                    # Skip javascript: URLs
                    if href.lower().startswith("javascript:"):
                        continue
                    full_url = urljoin(base_url, href)
                    full_netloc = urlparse(full_url).netloc
                    # Skip internal links
                    if full_netloc == base_netloc:
                        continue
                    ads.append(AdCandidate(
                        url=full_url,
                        element_type="class_id",
                        ad_network="contextual",
                        selector=(f".{classes_str.split()[0]}"
                                  if classes_str else f"#{tag_id}"),
                        text=tag.get_text(strip=True)[:100],
                    ))
        return ads

    def _detect_data_attributes(self, soup: BeautifulSoup,
                                base_url: str) -> List[AdCandidate]:
        ads = []
        base_netloc = urlparse(base_url).netloc
        for tag in soup.find_all(True):
            data_attrs = {k: v for k, v in tag.attrs.items()
                          if k.startswith("data-")}
            if not data_attrs:
                continue
            is_ad = any(
                re.search(r'\b' + re.escape(p) + r'\b',
                          f"{an}={av}".lower())
                for an, av in data_attrs.items()
                for p in ["ad", "ads", "banner", "sponsor"]
            )
            if is_ad:
                link = (tag.find("a", href=True)
                        if tag.name != "a" else tag)
                if link and link.get("href"):
                    full_url = urljoin(base_url, link["href"])
                    full_netloc = urlparse(full_url).netloc
                    # Skip internal links
                    if full_netloc == base_netloc:
                        continue
                    ads.append(AdCandidate(
                        url=full_url,
                        element_type="data_attr",
                        ad_network="contextual",
                        selector="[data-*]",
                        text=tag.get_text(strip=True)[:100],
                    ))
        return ads

    def _detect_amp_ads(self, soup: BeautifulSoup,
                        base_url: str) -> List[AdCandidate]:
        ads = []
        for amp in soup.find_all(["amp-ad", "amp-embed"]):
            src = (amp.get("src", "") or amp.get("data-url", "")
                   or amp.get("data-slot", ""))
            w = amp.get("width", "")
            h = amp.get("height", "")
            if src:
                full_url = urljoin(base_url, src)
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="amp_ad",
                    ad_network=(self._identify_ad_network(full_url)
                                or "amp_network"),
                    selector=f"amp-ad[width={w}]" if w else "amp-ad",
                    text=f"AMP Ad ({w}x{h})",
                ))
        return ads

    def _detect_script_based_ads(self, soup: BeautifulSoup,
                                 base_url: str) -> List[AdCandidate]:
        ads = []
        for script in soup.find_all("script"):
            src = script.get("src", "")
            if not src:
                continue
            full_url = urljoin(base_url, src)
            ad_network = self._identify_ad_network(full_url)
            if ad_network:
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="script_ad",
                    ad_network=ad_network,
                    selector=f"script[src*='{src[:30]}']",
                    text=f"Ad script: {ad_network}",
                ))
        return ads

    def _detect_cpa_network_scripts(self, soup: BeautifulSoup,
                                    base_url: str) -> List[AdCandidate]:
        """Detect scripts from CPA/pop/CPM networks that inject creative elements.

        These scripts (ECPM, PopAds, Adsterra, PropellerAds, …) inject
        ``<div><a><img …></a></div>`` into the page or open popups. They
        do **not** return a navigable click URL themselves, so we record
        them for logging purposes and let the caller handle them via
        Playwright evaluate (for on_popunder handlers) or container-navigation.
        """
        CPA_SCRIPT_SIGNATURES = [
            "effectivecpmnetwork.com", "profitableratecpm.com",
            "popads.net", "adsterra.com", "propellerads.com",
            "exoclick.com", "juicyads.com", "hilltopads.com",
            "adcash.com", "bidvertiser.com", "popcash.net",
            "monetag.com", "adtiming.com", "cpagrip.com",
            "cpalead.com", "cpabuild.com", "trafficjunky.com",
            "adxpansion", "trafficfactory",
            "adsterra", "exoclick", "propellerclick",
            "onclickads", "clickadu", "adf.ly", "shorte.st",
            "shrink-service", "bc.vc", "bit.ly",
            "mgid.com", "revcontent", "outbrain",
            "taboola", "nativeads",
            "ad.mo.doublecheck", "ad.xyz",
            "popunder", "popup", "pop_ad",
            "pops", "pop.js", "popunder.js",
        ]
        CPA_CONTAINER_ID_PREFIXES = [
            "container-", "wrapper-", "ad-container",
            "pubs_pop", "banner_place", "ad_zone_",
            "pop-", "popup-", "popunder-",
            "ad_", "_ad", "adblock",
        ]
        ads: List[AdCandidate] = []
        base_netloc = urlparse(base_url).netloc

        for script in soup.find_all("script", src=True):
            src = urljoin(base_url, script["src"])
            if any(sig in src.lower() for sig in CPA_SCRIPT_SIGNATURES):
                net = (self._identify_ad_network(src)
                       or "cpa_network")
                ads.append(AdCandidate(
                    url=src,
                    element_type="script_ad",
                    ad_network=net,
                    selector=f"script[src*='{src[:30]}']",
                    text=f"CPA script: {net}",
                ))

        # Container divs pre-placed by the blog template for CPA networks
        for tag in soup.find_all(["div", "span"],
                                 id=re.compile("|".join(
                                     re.escape(p) for p
                                     in CPA_CONTAINER_ID_PREFIXES), re.I)):
            link = tag.find("a", href=True)
            img = tag.find("img", src=True)
            net = "cpa_widget"
            # Try to identify network from container id
            for sig in CPA_SCRIPT_SIGNATURES:
                short = sig.split(".")[0]
                if short in tag.get("id", "").lower():
                    net = AD_NETWORK_ALIASES.get(sig, short)
                    break
            selector = (f"#{tag.get('id','')}"
                        if tag.get("id") else
                        f".{tag.get('class', [''])[0]}")
            ad_url = ""
            if link and link.get("href"):
                href = link["href"]
                # Skip javascript: URLs
                if not href.lower().startswith("javascript:"):
                    ad_url = urljoin(base_url, href)
            elif img and img.get("src"):
                ad_url = urljoin(base_url, img["src"])
            else:
                ad_url = base_url
            # Skip internal links and javascript in CPA containers
            if not ad_url or ad_url == base_url:
                continue
            if urlparse(ad_url).netloc == base_netloc:
                continue
            ads.append(AdCandidate(
                url=ad_url,
                element_type="class_id",
                ad_network=net,
                selector=selector,
                text=tag.get_text(strip=True)[:100],
            ))
        return ads

    def _detect_inline_script_ads(self, soup: BeautifulSoup,
                                  base_url: str) -> List[AdCandidate]:
        """Detect inline JS that contains window.open() calls for CPA popunders.

        Many CPA networks (ECPM, PopAds, etc.) embed inline scripts with
        window.open(), location.href, or document.location assignments that
        open popup/popunder windows. Extract the URLs from these patterns.
        """
        POPUNDER_PATTERNS = [
            r'''window\.open\s*\(\s*['"]([^'"]+)['"]''',
            r'''(?:window|document|top|parent)\.location(?:\.href)?\s*=\s*['"]([^'"]+)['"]''',
            r'''location\.href\s*=\s*['"]([^'"]+)['"]''',
            r'''location\.replace\(\s*['"]([^'"]+)['"]''',
            r'''window\.navigate\(\s*['"]([^'"]+)['"]''',
        ]
        ads: List[AdCandidate] = []
        base_netloc = urlparse(base_url).netloc

        for script in soup.find_all("script"):
            content = script.string or ""
            if not content.strip():
                continue
            for pattern in POPUNDER_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for m in matches:
                    url = m.strip()
                    if not url.startswith("http"):
                        continue
                    parsed = urlparse(url)
                    if parsed.netloc == base_netloc:
                        continue
                    ad_network = self._identify_ad_network(url) or "inline_popunder"
                    ads.append(AdCandidate(
                        url=url,
                        element_type="popup",
                        ad_network=ad_network,
                        selector="script",
                        text=f"Inline popunder: {url[:60]}",
                    ))
        return ads

    def _detect_data_redirect_ads(self, soup: BeautifulSoup,
                                  base_url: str) -> List[AdCandidate]:
        """Detect ad-related data-* attributes pointing to external URLs.

        CPA networks often embed ad click URLs in data-* attributes
        like data-href, data-url, data-redirect, data-click-url, etc.
        """
        REDIRECT_ATTRS = [
            "data-href", "data-url", "data-redirect",
            "data-click-url", "data-ad-url", "data-destination",
            "data-link", "data-target-url", "data-popurl",
            "data-popup", "data-popunder", "data-redirecturl",
            "data-click", "data-dest", "data-go",
        ]
        ads: List[AdCandidate] = []
        base_netloc = urlparse(base_url).netloc

        for tag in soup.find_all(True):
            for attr in REDIRECT_ATTRS:
                val = tag.get(attr, "")
                if val and val.startswith("http"):
                    parsed = urlparse(val)
                    if parsed.netloc != base_netloc:
                        ad_network = self._identify_ad_network(val) or "data_redirect_ad"
                        ads.append(AdCandidate(
                            url=val,
                            element_type="data_attr",
                            ad_network=ad_network,
                            selector=f"[{attr}]",
                            text=f"Data redirect: {val[:60]}",
                        ))
        return ads

    def _detect_popup_patterns(self, soup: BeautifulSoup,
                               base_url: str) -> List[AdCandidate]:
        ads = []
        base_netloc = urlparse(base_url).netloc
        pat = re.compile(r"popup|pop-up|popunder|overlay|modal", re.I)
        for tag in soup.find_all(True, class_=pat):
            link = tag.find("a", href=True) if tag.name != "a" else tag
            if link and link.get("href"):
                full_url = urljoin(base_url, link["href"])
                full_netloc = urlparse(full_url).netloc
                # Skip internal links
                if full_netloc == base_netloc:
                    continue
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="popup",
                    ad_network="popup",
                    selector=(f".{tag.get('class', [''])[0]}"
                              if tag.get("class") else ""),
                    text=tag.get_text(strip=True)[:100],
                ))
        for tag in soup.find_all(True, id=pat):
            link = tag.find("a", href=True) if tag.name != "a" else tag
            if link and link.get("href"):
                full_url = urljoin(base_url, link["href"])
                full_netloc = urlparse(full_url).netloc
                # Skip internal links
                if full_netloc == base_netloc:
                    continue
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="popup",
                    ad_network="popup",
                    selector=f"#{tag.get('id', '')}",
                    text=tag.get_text(strip=True)[:100],
                ))
        return ads

    def _detect_native_ads(self, soup: BeautifulSoup,
                            base_url: str) -> List[AdCandidate]:
        ads = []
        base_netloc = urlparse(base_url).netloc
        native_sel = [
            {"class": re.compile(
                r"native.?ad|sponsored.?content|recommended.?for.?you|"
                r"promoted|taboola|outbrain", re.I)},
            {"id": re.compile(
                r"native.?ad|sponsored.?content|recommended.?for.?you|"
                r"promoted|taboola|outbrain", re.I)},
        ]
        for sel in native_sel:
            for tag in soup.find_all(True, **sel):
                link = tag.find("a", href=True) if tag.name != "a" else tag
                if link and link.get("href"):
                    full_url = urljoin(base_url, link["href"])
                    full_netloc = urlparse(full_url).netloc
                    # Skip internal links
                    if full_netloc == base_netloc:
                        continue
                    classes = tag.get("class", [])
                    cs = (" ".join(classes)
                          if isinstance(classes, list) else str(classes))
                    ads.append(AdCandidate(
                        url=full_url,
                        element_type="native_ad",
                        ad_network="native",
                        selector=f".{cs.split()[0]}" if cs else "",
                        text=tag.get_text(strip=True)[:100],
                    ))
        return ads

    def _detect_image_ads(self, soup: BeautifulSoup,
                          base_url: str) -> List[AdCandidate]:
        ads = []
        base_netloc = urlparse(base_url).netloc
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            alt = img.get("alt", "") or ""
            classes = (
                " ".join(img.get("class", []))
                if isinstance(img.get("class"), list)
                else str(img.get("class", ""))
            )
            parent = img.find_parent("a")

            is_ad = any(
                re.search(r'\b' + re.escape(p) + r'\b', src.lower())
                for p in AD_IMAGE_KEYWORDS)
            is_ad = is_ad or any(
                re.search(r'\b' + re.escape(p) + r'\b', alt.lower())
                for p in AD_IMAGE_KEYWORDS)
            is_ad = is_ad or any(
                p in classes.lower() for p in AD_CLASS_PATTERNS)

            if is_ad and parent and parent.get("href"):
                full_url = urljoin(base_url, parent["href"])
                full_netloc = urlparse(full_url).netloc
                # Skip internal links
                if full_netloc == base_netloc:
                    continue
                ad_network = (self._identify_ad_network(full_url)
                              or "image_ad")
                ads.append(AdCandidate(
                    url=full_url,
                    element_type="image_ad",
                    ad_network=ad_network,
                    selector=(f"img[alt='{alt[:30]}']"
                              if alt else "img[src*='ad']"),
                    text=alt or "Image Ad",
                ))
        return ads

    # ─── Individual legacy detectors (thin wrappers, kept for compat) ──────

    def _detect_adsterra_tags(self, soup: BeautifulSoup,
                              base_url: str) -> List[AdCandidate]:
        ads = []
        pat = re.compile(r"adsterra", re.I)
        for tag in soup.find_all(True, id=pat):
            link = tag.find("a", href=True) if tag.name != "a" else tag
            if link and link.get("href"):
                ads.append(AdCandidate(
                    url=urljoin(base_url, link["href"]),
                    element_type="ad_link",
                    ad_network="adsterra",
                    selector=f"#{tag.get('id','')}",
                    text=tag.get_text(strip=True)[:100],
                ))
        return ads