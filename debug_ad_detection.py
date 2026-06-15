#!/usr/bin/env python3
"""
debug_ad_detection.py — CPA Popunder Detection Debugger (Requests-based)

Menganalisis HTML sumber target blog untuk mendeteksi:
1. Semua ad network scripts (src attributes)
2. Inline scripts dengan window.open, location.href, popunder patterns
3. CPA container divs (container-xxx, ad-xxx, pop-xxx)
4. Semua external links (potensi CPA click targets)
5. Data-attribute redirects (data-href, data-url, etc.)
6. Iklan dari Google AdSense / ECPM / dll
7. Menjalankan ad_detector.py terhadap HTML untuk verifikasi

Usage:
    python debug_ad_detection.py <url>
    python debug_ad_detection.py <url> --proxy http://user:pass@host:port
"""

import re
import sys
import time
from collections import Counter
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ─── Ad Network Database ────────────────────────────────────────────────
AD_NETWORKS: Dict[str, str] = {
    # Google
    "googleads": "Google Ads",
    "doubleclick": "DoubleClick",
    "googlesyndication": "Google AdSense",
    "amazon-adsystem": "Amazon Ads",
    # Display / AdX
    "adnxs": "AppNexus",
    "rubiconproject": "Rubicon",
    "openx": "OpenX",
    "pubmatic": "PubMatic",
    "criteo": "Criteo",
    "adform": "AdForm",
    # Native
    "outbrain": "Outbrain",
    "taboola": "Taboola",
    "mgid": "MGID",
    "revcontent": "RevContent",
    "zergnet": "ZergNet",
    # CPA / Popunder Networks
    "effectivecpmnetwork": "ECPM (Effective CPM)",
    "profitableratecpm": "ProfitableRate CPM",
    "adsterra": "Adsterra",
    "popads": "PopAds",
    "propellerads": "PropellerAds",
    "exoclick": "ExoClick",
    "juicyads": "JuicyAds",
    "hilltopads": "HilltopAds",
    "adcash": "AdCash",
    "popcash": "PopCash",
    "bidvertiser": "BidVertiser",
    "cpagrip": "CPAgrip",
    "cpalead": "CPALead",
    "cpabuild": "CPABuild",
    "monetag": "Monetag",
    "monetizus": "Monetizus",
    "adtiming": "AdTiming",
    "publisherdesk": "PublisherDesk",
    "popunder": "PopUnder Network",
    "shorte.st": "Shorte.st",
    "adf.ly": "AdFly",
    "bc.vc": "BC.VC",
}

CPA_SCRIPT_SIGNATURES = [
    r"pl\d+\.(effectivecpmnetwork|profitableratecpm)\.com",
    r"invoke\.js",
    r"popunder\.js",
    r"popads\.net",
    r"adsterra\.com",
    r"propellerads\.com",
    r"exoclick\.com",
    r"juicyads\.com",
    r"hilltopads\.com",
    r"adcash\.com",
    r"popcash\.net",
    r"monetag\.com",
    r"adtiming\.com",
    r"cpagrip\.com",
    r"cpalead\.com",
    r"cpabuild\.com",
    r"trafficjunky\.com",
    r"onclickads",
    r"clickadu",
]

POPUNDER_JS_PATTERNS = [
    (r'''window\.open\s*\(\s*['"]([^'"]+)['"]''', "window.open()"),
    (r'''location\.href\s*=\s*['"]([^'"]+)['"]''', "location.href="),
    (r'''location\.replace\s*\(\s*['"]([^'"]+)['"]''', "location.replace()"),
    (r'''window\.location\s*=\s*['"]([^'"]+)['"]''', "window.location="),
    (r'''document\.location\.href\s*=\s*['"]([^'"]+)['"]''', "document.location.href="),
    (r'''window\.navigate\s*\(\s*['"]([^'"]+)['"]''', "window.navigate()"),
    (r'''window\.open\s*\(\s*[^,]+,\s*['"]_(?:blank|self)['"]''', "window.open(_blank)"),
]

DATA_REDIRECT_ATTRS = [
    "data-href", "data-url", "data-redirect", "data-click-url",
    "data-ad-url", "data-popurl", "data-popup", "data-popunder",
    "data-destination", "data-go", "data-click", "data-dest",
    "data-redirecturl", "data-target-url", "data-link",
]

AD_CLASS_PATTERNS = [
    "ad", "ads", "adsense", "advert", "advertisement",
    "banner", "sponsor", "sponsored", "promo", "promotion",
    "native-ad", "nativead", "in-content-ad",
    "popup", "pop-up", "popunder",
    "leaderboard", "skyscraper", "rectangle",
    "sticky", "floating", "overlay",
    "google-ad", "dfp-ad", "gam-ad",
    "container-", "wrapper-",
]

CPA_CONTAINER_ID_PREFIXES = [
    "container-", "wrapper-", "ad-container",
    "pubs_pop", "banner_place", "ad_zone_",
    "pop-", "popup-", "popunder-",
    "ad_", "_ad", "adblock",
]


def analyze_blog(url: str, proxy: Optional[str] = None):
    """Main analysis function."""
    print("=" * 70)
    print("🔍 CPA POPUNDER DETECTION DEBUGGER (requests-based)")
    print("=" * 70)
    print(f"Target URL: {url}")
    print(f"Proxy: {proxy or 'None (direct)'}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ── Fetch Page ──────────────────────────────────────────────────────
    print("🌐 Fetching page...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    try:
        resp = session.get(url, timeout=30, allow_redirects=True)
        print(f"   Status: {resp.status_code}")
        print(f"   Size: {len(resp.text):,} bytes")
        print(f"   Final URL: {resp.url}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    base_url = resp.url
    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
    base_netloc = parsed_base.netloc

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # ═══════════════════════════════════════════════════════════════════
    # 1. AD SCRIPTS DETECTION
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("📜 SECTION 1: AD NETWORK SCRIPTS (src attributes)")
    print("─" * 56)

    ad_scripts = []
    for script in soup.find_all("script", src=True):
        src = script["src"]
        full_src = urljoin(base_url, src)
        src_lower = full_src.lower()

        for domain, name in sorted(AD_NETWORKS.items(), key=lambda x: -len(x[0])):
            if domain in src_lower:
                ad_scripts.append({
                    "src": full_src,
                    "network": name,
                    "async": script.get("async", False),
                    "defer": script.get("defer", False),
                    "type": script.get("type", ""),
                })
                break
        else:
            # Check CPA script signatures
            for sig in CPA_SCRIPT_SIGNATURES:
                if re.search(sig, src_lower):
                    ad_scripts.append({
                        "src": full_src,
                        "network": "CPA Script",
                        "async": script.get("async", False),
                        "defer": script.get("defer", False),
                        "type": script.get("type", ""),
                    })
                    break

    if ad_scripts:
        for s in ad_scripts:
            async_str = "async" if s["async"] else ""
            defer_str = "defer" if s["defer"] else ""
            flags = f" [{async_str} {defer_str}]".strip() if async_str or defer_str else ""
            print(f"  📦 [{s['network']}]{flags}")
            print(f"      {s['src'][:100]}")
    else:
        print("  ✅ No ad scripts detected (or none matched known networks)")

    # ═══════════════════════════════════════════════════════════════════
    # 2. INLINE SCRIPT POPUNDER ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("🪟 SECTION 2: POPUNDER TRIGGERS IN INLINE SCRIPTS")
    print("─" * 56)

    all_popunders = []
    for script in soup.find_all("script"):
        content = script.string or ""
        if not content.strip():
            continue

        for pattern, label in POPUNDER_JS_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                url_found = m if isinstance(m, str) else m[0] if isinstance(m, tuple) else str(m)
                # Extract context around match
                ctx_match = re.search(pattern, content, re.IGNORECASE)
                start = max(0, ctx_match.start() - 40) if ctx_match else 0
                end = min(len(content), ctx_match.end() + 40) if ctx_match else len(content)
                context = content[start:end].replace("\n", " ").strip()

                all_popunders.append({
                    "url": url_found[:120],
                    "method": label,
                    "context": context[:100],
                })

    if all_popunders:
        for p in all_popunders:
            print(f"  🪟 [{p['method']}]")
            print(f"      URL: {p['url']}")
            print(f"      ctx: ...{p['context']}...")
    else:
        print("  ✅ No popunder triggers found in inline scripts")
        print("     (CPA popunders likely triggered via external invoke.js)")

    # ═══════════════════════════════════════════════════════════════════
    # 3. CPA CONTAINER DIVS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("📦 SECTION 3: CPA CONTAINER DIVS")
    print("─" * 56)

    container_divs = []
    for div in soup.find_all("div", id=True):
        div_id = div.get("id", "")
        div_classes = " ".join(div.get("class", [])) if div.get("class") else ""

        # Check CPA container patterns
        is_container = bool(re.match(r"container-[\da-f]{32}", div_id, re.I))
        is_ad_prefix = any(div_id.lower().startswith(p) for p in CPA_CONTAINER_ID_PREFIXES)
        is_ad_class = any(p in div_classes.lower() for p in AD_CLASS_PATTERNS)

        if is_container or is_ad_prefix or is_ad_class:
            # Find links inside
            links = div.find_all("a", href=True)
            imgs = div.find_all("img")
            scripts_inside = div.find_all("script")
            children = div.find_all(recursive=False)

            container_divs.append({
                "id": div_id,
                "classes": div_classes[:40],
                "tag": div.name,
                "children_count": len(children),
                "total_descendants": len(div.find_all()),
                "has_link": len(links) > 0,
                "link_urls": [urljoin(base_url, a["href"]) for a in links[:3]],
                "has_img": len(imgs) > 0,
                "has_script": len(scripts_inside) > 0,
                "text_length": len(div.get_text(strip=True)),
                "style": div.get("style", "")[:80],
            })

    if container_divs:
        for c in container_divs:
            content_status = "✅ HAS CONTENT" if c["has_link"] or c["has_img"] or c["text_length"] > 0 else "❌ EMPTY"
            print(f"  {'📦' if c['has_link'] or c['has_img'] else '❌'} [{c['id'][:40]}]")
            print(f"      class={c['classes'][:30]} | children={c['children_count']} | style={c['style'][:40]}")
            print(f"      {content_status}")
            if c["has_link"]:
                for link_url in c["link_urls"]:
                    netloc = urlparse(link_url).netloc
                    is_external = netloc != base_netloc
                    ext = "🌐 EXTERNAL" if is_external else "🏠 internal"
                    print(f"      🔗 [{ext}] {link_url[:80]}")
            if c["text_length"] > 0:
                print(f"      text: {div.get_text(strip=True)[:80]}")
    else:
        print("  ✅ No CPA container divs found on page")

    # ═══════════════════════════════════════════════════════════════════
    # 4. EXTERNAL LINKS ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("🔗 SECTION 4: EXTERNAL LINKS (potential CPA click targets)")
    print("─" * 56)

    external_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("javascript:") or href.startswith("#") or href.startswith("mailto:"):
            continue
        full_url = urljoin(base_url, href)
        if urlparse(full_url).netloc != base_netloc:
            rel = a.get("rel", [])
            rel_str = " ".join(rel) if isinstance(rel, list) else str(rel)
            external_links.append({
                "url": full_url,
                "text": a.get_text(strip=True)[:40],
                "rel": rel_str[:20],
                "target": a.get("target", ""),
                "class": " ".join(a.get("class", []))[:30] if a.get("class") else "",
            })

    if external_links:
        # Count by domain
        domain_counts = Counter(urlparse(l["url"]).netloc for l in external_links)
        print(f"  Total: {len(external_links)} external links")
        print(f"  Unique domains: {len(domain_counts)}")
        print()

        # Show top domains
        for domain, count in domain_counts.most_common(10):
            print(f"  🌐 {domain}: {count} links")

        print()
        # Show sponsored/rel links
        sponsored = [l for l in external_links if l["rel"] or "sponsor" in l["class"].lower()]
        if sponsored:
            print(f"  ⭐ SPONSORED links ({len(sponsored)}):")
            for l in sponsored[:5]:
                print(f"      [{l['rel']}] {l['url'][:80]}")
                if l["text"]:
                    print(f"      text: {l['text']}")

        # Show links to known ad networks
        ad_external = []
        for l in external_links:
            for domain in AD_NETWORKS:
                if domain in l["url"].lower():
                    ad_external.append((AD_NETWORKS[domain], l["url"]))
                    break
        if ad_external:
            print(f"\n  📢 Links to known ad networks ({len(ad_external)}):")
            for net, link_url in ad_external[:5]:
                print(f"      [{net}] {link_url[:80]}")
    else:
        print("  ✅ No external links found")

    # ═══════════════════════════════════════════════════════════════════
    # 5. DATA-ATTRIBUTE REDIRECTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("🔗 SECTION 5: DATA-ATTRIBUTE REDIRECTS")
    print("─" * 56)

    data_redirects = []
    for attr in DATA_REDIRECT_ATTRS:
        for tag in soup.find_all(True, attrs={attr: True}):
            val = tag.get(attr, "")
            if val and val.startswith("http"):
                data_redirects.append({
                    "attr": attr,
                    "value": val[:120],
                    "tag": tag.name,
                })

    if data_redirects:
        for d in data_redirects:
            netloc = urlparse(d["value"]).netloc
            is_ad = any(domain in netloc for domain in AD_NETWORKS)
            ad_tag = " 📢 AD!" if is_ad else ""
            print(f"  [{d['attr']}] on <{d['tag']}>{ad_tag}")
            print(f"      {d['value']}")
    else:
        print("  ✅ No data-attribute redirects found")

    # ═══════════════════════════════════════════════════════════════════
    # 6. GOOGLE ADSENSE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("📢 SECTION 6: GOOGLE ADSENSE ANALYSIS")
    print("─" * 56)

    adsense_ins = soup.find_all("ins", class_=re.compile(r"adsbygoogle", re.I))
    adsense_divs = soup.find_all("div", class_=re.compile(r"adsbygoogle", re.I))
    adsense_scripts = [
        s for s in soup.find_all("script", src=True)
        if "adsbygoogle" in s.get("src", "").lower()
        or "pagead/js/adsbygoogle" in s.get("src", "").lower()
    ]

    if adsense_ins:
        print(f"  📢 AdSense <ins> blocks: {len(adsense_ins)}")
        for ins in adsense_ins:
            slot = ins.get("data-ad-slot", "unknown")
            client = ins.get("data-ad-client", "unknown")
            style = ins.get("style", "")
            print(f"      slot={slot} client={client} style={style[:60]}")
    else:
        print("  ❌ No AdSense <ins> blocks found")

    if adsense_scripts:
        print(f"  📜 AdSense scripts: {len(adsense_scripts)}")
        for s in adsense_scripts:
            print(f"      {s['src'][:90]}")

    # ═══════════════════════════════════════════════════════════════════
    # 7. AD DETECTOR ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("🔍 SECTION 7: AD DETECTOR SIMULATION")
    print("─" * 56)

    try:
        from ad_detector import AdDetector
        detector = AdDetector()
        ads = detector.detect_all(html, base_url)
        print(f"  Ad candidates detected: {len(ads)}")
        for ad in ads:
            ad_type = detector.classify_ad_type(ad)
            print(f"  [{ad_type:15s}] [{ad.ad_network:20s}] {ad.url[:70]}")
            if ad.text:
                print(f"      text: {ad.text[:50]}")
    except ImportError:
        print("  ⚠️  ad_detector.py not importable — skipping")
    except Exception as e:
        print(f"  ❌ Error running ad_detector: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # 8. CPA NETWORK META ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 56)
    print("📊 SECTION 8: CPA NETWORK META ANALYSIS")
    print("─" * 56)

    # Count all ad network references
    html_lower = html.lower()
    network_counts = {}
    for domain, name in sorted(AD_NETWORKS.items()):
        count = html_lower.count(domain)
        if count > 0:
            network_counts[name] = count

    if network_counts:
        for name, count in sorted(network_counts.items(), key=lambda x: -x[1]):
            print(f"  🌐 {name}: {count}x references in HTML")
    else:
        print("  ✅ No ad network references found in HTML")

    # ═══════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("📊 FINAL ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"  Ad Network Scripts:   {len(ad_scripts)}")
    print(f"  Inline Popunder Triggers: {len(all_popunders)}")
    print(f"  CPA Container Divs:   {len(container_divs)}")
    print(f"  External Links:       {len(external_links)}")
    print(f"  Data Redirect Attrs:  {len(data_redirects)}")
    print(f"  Ad Networks in HTML:  {len(network_counts)}")

    empty_containers = [c for c in container_divs if not c["has_link"] and not c["has_img"] and c["text_length"] == 0]
    if empty_containers:
        print(f"\n  ❌ {len(empty_containers)}/{len(container_divs)} CPA containers appear EMPTY")
        print(f"     → No <a> tags, no <img> tags, no text content")
        print(f"     → ECPM scripts may return 0-byte (impression tracker only)")
        print(f"     → Creative may need JS execution to render")

    if all_popunders:
        print(f"\n  ✅ {len(all_popunders)} popunder triggers found in inline JS")
        print(f"     → These can be extracted and clicked")
    else:
        print(f"\n  ❌ No inline popunder triggers found")
        print(f"     → The real popunder URL is likely inside external invoke.js")
        print(f"     → Previous investigation showed 92KB obfuscated JS from ECPM")
        print(f"     → Need JavaScript execution to deobfuscate")

    if external_links:
        print(f"\n  ✅ {len(external_links)} external links found")
        print(f"     → Clicking these should trigger CPA click handlers")

    print()
    print("=" * 70)
    print("💡 RECOMMENDATIONS")
    print("=" * 70)
    print("""
  1. ECPM invoke.js returns 0 bytes (impression-only)
     → Fix: Pastikan blog template ECPM container punya min-height dan display:block
     → Fix: Coba aktifkan CAPTCHA solver untuk bypass anti-bot detection

  2. Popunder triggers ada di external JS (bukan inline)
     → Bot sudah punya CPA_POPUNDER_TRIGGER_JS untuk trigger dari page
     → Pastikan exit-intent simulation jalan (mouse sweep ke atas)

  3. External links harus di-click untuk trigger popunder
     → Bot's _click_random_external_links() sudah melakukannya
     → Tingkatkan jumlah external link clicks (max 3-5 per visit)

  4. Jika semua gagal, coba:
     a. Gunakan rotating proxy dari BrightData/Oxylabs (IP segar)
     b. Tambahkan CAPTCHA solver API key
     c. Cek dashboard ECPM — apakah ada kampanye aktif untuk blog ini?
""")

    session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_ad_detection.py <url> [--proxy http://...]")
        sys.exit(1)

    url = sys.argv[1]
    proxy = None
    if "--proxy" in sys.argv:
        idx = sys.argv.index("--proxy")
        if idx + 1 < len(sys.argv):
            proxy = sys.argv[idx + 1]

    analyze_blog(url, proxy)
