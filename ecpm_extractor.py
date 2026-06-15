"""
ecpm_extractor.py — ECPM / CPA Network URL Extractor

Mendownload dan menganalisis skrip ECPM invoke.js yang di-obfuscate
untuk mengekstrak URL popunder, pixel tracking, dan konfigurasi.

⚠️  BATASAN:
ECPM invoke.js membangun URL popunder sesungguhnya secara RUNTIME
menggunakan JavaScript evaluation (string concatenation + eval).
Ekstraktor ini hanya bisa menemukan:
  - String parsial yang digunakan untuk membangun URL
  - URL statis (pixel, script, ad content)
  - Pola konfigurasi dan placement key
  - Array char codes yang mungkin membentuk URL

Untuk URL popunder lengkap, diperlukan eksekusi JS sesungguhnya
(Node.js/sandbox) atau ekstraksi dari browser session.

Usage:
    python ecpm_extractor.py <blog_url_or_js_url>
    python ecpm_extractor.py invoke_ecpm.js  # analyze local file
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger("CPABot.ECPMExtractor")


# ── Hex decoder ─────────────────────────────────────────────────────────

def decode_hex_strings(content: str) -> str:
    """Decode all \\xNN hex sequences in the content."""
    def _replace(match):
        try:
            return chr(int(match.group(1), 16))
        except (ValueError, OverflowError):
            return match.group(0)
    return re.sub(r'\\x([0-9a-fA-F]{2})', _replace, content)


# ── Extract URLs from decoded content ──────────────────────────────────

def extract_urls(content: str) -> List[str]:
    """Extract all http/https URLs from content."""
    urls = re.findall(r'https?://[^\s"\'`)>;,}\]]+', content)
    cleaned = []
    for u in urls:
        u = u.rstrip('.,;:!?)\'"]')
        if u.startswith('http'):
            cleaned.append(u)
    return list(set(cleaned))


# ── Extract char-code arrays that might encode URLs ─────────────────────

def decode_number_arrays(content: str) -> List[str]:
    """
    Find arrays of numbers that look like character codes
    and try to decode them into strings.
    """
    decoded_strings = []
    number_arrays = re.findall(r'\[(\d+(?:,\s*\d+)+)\]', content)

    for arr_str in number_arrays:
        try:
            nums = [int(x.strip()) for x in arr_str.split(',')]
            if 5 < len(nums) < 300:
                # Decode ALL values — don't filter printable-only
                # Obfuscated URLs often use XOR/encoded bytes
                decoded = ''.join(chr(n % 256) for n in nums)
                # Only keep if it has meaningful content
                if decoded and len(decoded) > 8:
                    # Check if it looks like a URL, function call, or meaningful string
                    if any(x in decoded for x in ['http', '.com', 'www', '://',
                                                   'window', 'open', 'click',
                                                   'location', 'document']):
                        decoded_strings.append(decoded)
        except (ValueError, OverflowError):
            continue

    return decoded_strings


# ── Categorize URLs ─────────────────────────────────────────────────────

def categorize_url(url: str) -> str:
    """Categorize a URL by its purpose."""
    url_lower = url.lower()

    if 'pixel' in url_lower or '/pixel/' in url_lower:
        return 'pixel'
    if 'pop' in url_lower or 'popunder' in url_lower:
        return 'popunder'
    if 'click' in url_lower or '/click/' in url_lower:
        return 'click'
    if 'redirect' in url_lower:
        return 'redirect'
    if 'ad' in url_lower or '/ad/' in url_lower:
        return 'ad_content'
    if 'stats' in url_lower or 'stat' in url_lower:
        return 'stats'
    if url_lower.endswith('.js') or 'invoke' in url_lower:
        return 'script'
    if url_lower.endswith('.html') or url_lower.endswith('.htm'):
        return 'html_content'
    return 'other'


# ── Find obfuscated window.open calls ──────────────────────────────────

def find_open_calls(content: str) -> List[str]:
    """Find window.open and similar patterns in decoded content."""
    patterns = [
        r'open\s*\(\s*["\']([^"\']+)["\']',
        r'window\[["\']open["\']\]\s*\(\s*["\']([^"\']+)["\']',
        r'\[["\']open["\']\]\s*\(\s*["\']([^"\']+)["\']',
    ]
    urls = []
    for pat in patterns:
        matches = re.findall(pat, content, re.IGNORECASE)
        for m in matches:
            if m.startswith('http'):
                urls.append(m)
    return list(set(urls))


# ── Find ECPM-specific config keys ─────────────────────────────────────

def find_config_keys(content: str) -> List[Tuple[str, str]]:
    """Find configuration key-value pairs related to CPA/ad placement."""
    patterns = [
        (r'["\'](\w+Key\w*)["\']\s*[=:]\s*["\']([^"\']+)["\']', 'key'),
        (r'["\'](\w+[Uu]rl)["\']\s*[=:]\s*["\']([^"\']+)["\']', 'url'),
        (r'["\'](\w+[Dd]omain)["\']\s*[=:]\s*["\']([^"\']+)["\']', 'domain'),
        (r'["\'](\w+[Ee]nabled)["\']\s*[=:]\s*(true|false)', 'flag'),
        (r'["\'](\w+[Tt]imeout|\w+[Dd]elay|\w+[Pp]eriod)["\']\s*[=:]\s*(\d+)', 'number'),
    ]
    results = []
    for pat, typ in patterns:
        matches = re.findall(pat, content, re.IGNORECASE)
        for m in matches:
            key, val = m[0], m[1]
            if any(x in key.lower() for x in ['ad', 'pop', 'click', 'redirect',
                                               'pixel', 'placement', 'url',
                                               'domain', 'target', 'callback']):
                results.append((key, val, typ))
    return results


# ── Main extraction function ───────────────────────────────────────────

def extract_from_js_content(js_content: str) -> Dict:
    """
    Analyze ECPM invoke.js content and extract all URLs and patterns.

    Returns dict with categorized URLs, config keys, and structure info.
    """
    result: Dict = {
        "all_urls": [],
        "pixel_urls": [],
        "popunder_urls": [],
        "redirect_urls": [],
        "ad_content_urls": [],
        "script_urls": [],
        "stats_urls": [],
        "other_urls": [],
        "config_keys": [],
        "decoded_arrays": [],
        "injection_patterns": {},
        "runtime_only_warning": True,
    }

    # 1. Decode hex strings
    decoded = decode_hex_strings(js_content)
    result["decoded_size"] = len(decoded)

    # 2. Extract all URLs
    urls = extract_urls(decoded)
    result["all_urls"] = urls

    # 3. Categorize URLs
    for url in urls:
        cat = categorize_url(url)
        key = f"{cat}_urls"
        if key in result:
            result[key].append(url)

    # 4. Find window.open calls
    open_urls = find_open_calls(decoded)
    for u in open_urls:
        if u not in result["popunder_urls"]:
            result["popunder_urls"].append(u)

    # 5. Decode number arrays
    decoded_arrays = decode_number_arrays(decoded)
    result["decoded_arrays"] = decoded_arrays

    # 6. Extract config keys
    config_pairs = find_config_keys(decoded)
    result["config_keys"] = config_pairs

    # 7. Find injection patterns
    result["injection_patterns"] = {
        "appendChild": len(re.findall(r'appendChild', decoded)),
        "createElement": len(re.findall(r'createElement', decoded)),
        "innerHTML": len(re.findall(r'\.innerHTML\s*=', decoded)),
        "insertBefore": len(re.findall(r'insertBefore', decoded)),
        "eval_or_function": len(re.findall(r'eval\s*\(|new\s+Function', decoded)),
        "document_write": len(re.findall(r'document\.write', decoded)),
    }

    return result


def extract_ecpm_urls(script_url: str,
                      timeout: int = 15,
                      proxy: Optional[str] = None) -> Optional[Dict]:
    """
    Download and extract URLs from an ECPM invoke.js script.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }

    try:
        resp = requests.get(script_url, headers=headers,
                           timeout=timeout,
                           proxies={"http": proxy, "https": proxy} if proxy else None)

        if resp.status_code != 200 or len(resp.content) == 0:
            logger.warning(f"ECPM: {resp.status_code} / {len(resp.content)}b — {script_url[:80]}")
            return None

        result = extract_from_js_content(resp.text)
        result["source_url"] = script_url
        result["size_bytes"] = len(resp.content)
        result["status_code"] = resp.status_code
        return result

    except Exception as e:
        logger.error(f"ECPM extract error: {e}")
        return None


def extract_from_file(filepath: str) -> Optional[Dict]:
    """Read a local JS file and extract URLs."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        result = extract_from_js_content(content)
        result["source_url"] = f"file://{filepath}"
        result["size_bytes"] = len(content)
        return result
    except Exception as e:
        logger.error(f"File read error: {e}")
        return None


def find_ecpm_scripts(html: str, base_url: str) -> List[str]:
    """Find ECPM invoke.js script URLs in HTML content."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    scripts = []
    for s in soup.find_all("script", src=True):
        src = s["src"]
        full_url = urljoin(base_url, src)
        if "effectivecpmnetwork" in full_url.lower() and "invoke" in full_url.lower():
            scripts.append(full_url)

    return scripts


def extract_from_blog(url: str, proxy: Optional[str] = None) -> Optional[Dict]:
    """
    Full pipeline: fetch blog HTML → find ECPM scripts → extract URLs.
    """
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20,
                          proxies={"http": proxy, "https": proxy} if proxy else None)
        if resp.status_code != 200:
            return None

        ecpm_scripts = find_ecpm_scripts(resp.text, resp.url)
        if not ecpm_scripts:
            return {"error": "No ECPM scripts found", "source_url": url}

        # Extract from each script
        results = []
        for script_url in ecpm_scripts:
            extracted = extract_ecpm_urls(script_url, proxy=proxy)
            if extracted:
                results.append(extracted)

        if not results:
            return {"error": "Failed to extract from scripts", "ecpm_scripts": ecpm_scripts, "source_url": url}

        # Merge results from multiple scripts
        merged: Dict = {
            "source_url": url,
            "ecpm_scripts": ecpm_scripts,
            "all_urls": [],
            "pixel_urls": [], "popunder_urls": [],
            "redirect_urls": [], "ad_content_urls": [],
            "script_urls": [], "stats_urls": [], "other_urls": [],
            "config_keys": [],
            "injection_patterns": {},
        }

        for r in results:
            for key in ["all_urls", "pixel_urls", "popunder_urls", "redirect_urls",
                       "ad_content_urls", "script_urls", "stats_urls", "other_urls"]:
                merged[key].extend(r.get(key, []))
            merged["config_keys"].extend(r.get("config_keys", []))

            for k, v in r.get("injection_patterns", {}).items():
                merged["injection_patterns"][k] = merged["injection_patterns"].get(k, 0) + v

        for key in ["all_urls", "pixel_urls", "popunder_urls", "redirect_urls",
                   "ad_content_urls", "script_urls", "stats_urls", "other_urls"]:
            merged[key] = list(set(merged[key]))

        return merged

    except Exception as e:
        logger.error(f"Blog extraction error: {e}")
        return None


# ── Print formatted report ─────────────────────────────────────────────

def print_report(result: Dict):
    """Pretty-print extraction results."""
    print("=" * 70)
    print("🔍 ECPM URL EXTRACTION REPORT")
    print("=" * 70)
    print(f"Source: {result.get('source_url', 'N/A')}")
    print(f"Size:   {result.get('size_bytes', 0):,} bytes")
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    sections = [
        ("📡 Pixel URLs", "pixel_urls"),
        ("🪟 Popunder URLs", "popunder_urls"),
        ("🔗 Redirect URLs", "redirect_urls"),
        ("📦 Ad Content URLs", "ad_content_urls"),
        ("📜 Script URLs", "script_urls"),
        ("📊 Stats URLs", "stats_urls"),
        ("📋 Other URLs", "other_urls"),
    ]

    for title, key in sections:
        urls = result.get(key, [])
        if urls:
            print(f"\n{title} ({len(urls)}):")
            for u in urls:
                print(f"  • {u}")

    config_pairs = result.get("config_keys", [])
    if config_pairs:
        print(f"\n⚙️  Configuration ({len(config_pairs)}):")
        for k, v, typ in config_pairs[:15]:
            print(f"  • {k} = {v[:50]}  [{typ}]")

    decoded_arrays = result.get("decoded_arrays", [])
    if decoded_arrays:
        print(f"\n🔢 Decoded string arrays ({len(decoded_arrays)}):")
        for s in decoded_arrays[:10]:
            print(f"  • {s[:100]}")

    inj = result.get("injection_patterns", {})
    if inj:
        print(f"\n💉 Injection Patterns:")
        for k, v in inj.items():
            if v > 0:
                print(f"  • {k}: {v}x")

    # Limitation warning
    print(f"\n⚠️  DISCLAIMER:")
    print(f"   Popunder URLs are typically built at RUNTIME by JavaScript.")
    print(f"   For complete popunder URLs, you need to execute the JS in")
    print(f"   a browser (Playwright) and capture window.open() calls.")


# ── Standalone ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg.endswith('.js') and '/' not in arg:
            # Local file
            result = extract_from_file(arg)
        elif arg.startswith('http'):
            result = extract_from_blog(arg)
        else:
            result = extract_from_file(arg)

        if result:
            print_report(result)
        else:
            print("❌ Extraction failed")
    else:
        # Default: test against saved invoke.js if it exists
        import os
        if os.path.exists("invoke_ecpm.js"):
            print("📂 Testing against saved invoke_ecpm.js...\n")
            result = extract_from_file("invoke_ecpm.js")
            if result:
                print_report(result)
        else:
            print("Usage: python ecpm_extractor.py <blog_url_or_js_file>")
            print()
            print("Examples:")
            print("  python ecpm_extractor.py https://likhita.my.id")
            print("  python ecpm_extractor.py invoke_ecpm.js")
