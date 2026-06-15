#!/usr/bin/env python3
"""
proxy_scraper.py — Auto-Scrape Proxy Gratis dari Internet

Fitur:
- Scrape dari 10+ sumber proxy gratis
- Parse HTML tables, raw text lists, JSON API
- Deduplikasi otomatis (multi-source)
- Parallel testing (cepat)
- Filter berdasarkan protocol (HTTP/HTTPS/SOCKS4/SOCKS5)
- Progress callback untuk GUI/TUI
"""

import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("CPABot.ProxyScraper")

# ─── SOURCE DEFINITIONS ────────────────────────────────────────────────
# Each source has: url, parser type, protocol hint, and weight (reliability)

RAW_SOURCES = [
    # ═══════════════════════════════════════════════════════════════════
    #  GitHub RAW — fastest & most reliable (auto-updated daily)
    # ═══════════════════════════════════════════════════════════════════

    # -- TheSpeedX (large lists, frequently updated) --
    {
        "name": "TheSpeedX HTTP",
        "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 5,
    },
    {
        "name": "TheSpeedX SOCKS5",
        "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 5,
    },
    {
        "name": "TheSpeedX SOCKS4",
        "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "parser": "raw_list",
        "types": {"socks4"},
        "weight": 4,
    },

    # -- Monosans (clean lists, good variety) --
    {
        "name": "Monosans HTTP",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 5,
    },
    {
        "name": "Monosans SOCKS5",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 4,
    },
    {
        "name": "Monosans SOCKS4",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "parser": "raw_list",
        "types": {"socks4"},
        "weight": 4,
    },

    # -- ShiftyTR (good backup) --
    {
        "name": "ShiftyTR HTTP",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 4,
    },
    {
        "name": "ShiftyTR SOCKS5",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 4,
    },
    {
        "name": "ShiftyTR SOCKS4",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "parser": "raw_list",
        "types": {"socks4"},
        "weight": 4,
    },

    # -- RoosterKid (focused on HTTPS) --
    {
        "name": "RoosterKid HTTPS",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "parser": "raw_list",
        "types": {"https"},
        "weight": 4,
    },
    {
        "name": "RoosterKid SOCKS5",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },

    # -- New: Proxifly (updates every 5 minutes, very fresh!) --
    {
        "name": "Proxifly HTTP",
        "url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 5,
    },
    {
        "name": "Proxifly SOCKS5",
        "url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/socks5/data.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 4,
    },
    {
        "name": "Proxifly SOCKS4",
        "url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/socks4/data.txt",
        "parser": "raw_list",
        "types": {"socks4"},
        "weight": 4,
    },

    # -- New: gfpcom (clean lists) --
    {
        "name": "GFPCom HTTP",
        "url": "https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 4,
    },
    {
        "name": "GFPCom SOCKS5",
        "url": "https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },

    # -- New: vakhov (fresh proxy list) --
    {
        "name": "Vakhov HTTP",
        "url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 4,
    },
    {
        "name": "Vakhov SOCKS5",
        "url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },
    {
        "name": "Vakhov SOCKS4",
        "url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
        "parser": "raw_list",
        "types": {"socks4"},
        "weight": 3,
    },

    # -- New: jetkai (good variety) --
    {
        "name": "JetKai HTTP",
        "url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online/proxies/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 4,
    },
    {
        "name": "JetKai SOCKS5",
        "url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online/proxies/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },
    {
        "name": "JetKai SOCKS4",
        "url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online/proxies/socks4.txt",
        "parser": "raw_list",
        "types": {"socks4"},
        "weight": 3,
    },

    # -- New: mmpx12 --
    {
        "name": "MMPX12 HTTP",
        "url": "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },
    {
        "name": "MMPX12 SOCKS5",
        "url": "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },

    # -- New: Hookzof SOCKS5 --
    {
        "name": "Hookzof SOCKS5",
        "url": "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },

    # -- New: Ercinmert --
    {
        "name": "Ercinmert HTTP",
        "url": "https://raw.githubusercontent.com/Ercinmert/Proxy-List/main/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },

    # -- New: Zaeem20 --
    {
        "name": "Zaeem20 HTTP",
        "url": "https://raw.githubusercontent.com/Zaeem20/Fresh_Proxy_List/main/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },

    # -- New: sunny9577 --
    {
        "name": "Sunny9577",
        "url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },

    # -- New: ObcbO --
    {
        "name": "ObcbO HTTP",
        "url": "https://raw.githubusercontent.com/ObcbO/Proxy-List/main/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },
    {
        "name": "ObcbO SOCKS5",
        "url": "https://raw.githubusercontent.com/ObcbO/Proxy-List/main/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },

    # -- New: Anonym0usWork1221 --
    {
        "name": "Anonym0us HTTP",
        "url": "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },
    {
        "name": "Anonym0us SOCKS5",
        "url": "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },

    # -- New: sagirilmi --
    {
        "name": "Sagirilmi HTTP",
        "url": "https://raw.githubusercontent.com/sagirilmi/proxy-list/main/proxy-list/data.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },

    # ═══════════════════════════════════════════════════════════════════
    #  API Services
    # ═══════════════════════════════════════════════════════════════════

    {
        "name": "ProxyScrape API",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 5,
    },
    {
        "name": "ProxyScrape SOCKS5",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 4,
    },
    {
        "name": "ProxyList Download HTTP",
        "url": "https://www.proxy-list.download/api/v1/get?type=http",
        "parser": "raw_list",
        "types": {"http"},
        "weight": 4,
    },
    {
        "name": "ProxyList Download HTTPS",
        "url": "https://www.proxy-list.download/api/v1/get?type=https",
        "parser": "raw_list",
        "types": {"https"},
        "weight": 4,
    },
    {
        "name": "ProxyList Download SOCKS5",
        "url": "https://www.proxy-list.download/api/v1/get?type=socks5",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },
    {
        "name": "Geonode API",
        "url": "https://proxylist.geonode.com/api/proxy?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps",
        "parser": "geonode_api",
        "types": {"http", "https"},
        "weight": 4,
    },

    # ═══════════════════════════════════════════════════════════════════
    #  Text-based sources
    # ═══════════════════════════════════════════════════════════════════

    {
        "name": "Spys.me",
        "url": "https://spys.me/proxy.txt",
        "parser": "spys_txt",
        "types": {"http", "https", "socks4", "socks5"},
        "weight": 3,
    },
    {
        "name": "OpenProxyList",
        "url": "https://openproxylist.xyz/http.txt",
        "parser": "raw_list",
        "types": {"http", "https"},
        "weight": 3,
    },
    {
        "name": "OpenProxyList SOCKS5",
        "url": "https://openproxylist.xyz/socks5.txt",
        "parser": "raw_list",
        "types": {"socks5"},
        "weight": 3,
    },
    {
        "name": "ProxyDB",
        "url": "https://www.proxy-list.download/HTTP-Proxy/",
        "parser": "table_ip_port",
        "table_index": 1,
        "types": {"http", "https"},
        "weight": 2,
    },
]

HTML_SOURCES = [
    {
        "name": "Free-Proxy-List",
        "url": "https://free-proxy-list.net/",
        "parser": "table_ip_port",
        "table_index": 0,
        "types": {"http", "https"},
        "weight": 4,
    },
    {
        "name": "SSL Proxies",
        "url": "https://www.sslproxies.org/",
        "parser": "table_ip_port",
        "table_index": 0,
        "types": {"https"},
        "weight": 4,
    },
    {
        "name": "US Proxy",
        "url": "https://www.us-proxy.org/",
        "parser": "table_ip_port",
        "table_index": 0,
        "types": {"http", "https"},
        "weight": 3,
    },
    {
        "name": "ProxyNova",
        "url": "https://www.proxynova.com/proxy-server-list/",
        "parser": "proxynova",
        "types": {"http", "https", "socks4", "socks5"},
        "weight": 2,
    },
    {
        "name": "HideMyName",
        "url": "https://hidemy.name/en/proxy-list/",
        "parser": "hidemy_name",
        "types": {"http", "https", "socks4", "socks5"},
        "weight": 2,
    },
]

# Combine all sources
ALL_SOURCES = RAW_SOURCES + HTML_SOURCES

# ─── TESTING CONFIG ─────────────────────────────────────────────────────
TEST_TIMEOUT = 5          # seconds per proxy test
TEST_CONCURRENCY = 30     # parallel test threads
FETCH_TIMEOUT = 15        # seconds per source fetch
FETCH_MAX_WORKERS = 15    # parallel fetch threads (increased for 48 sources)
TEST_URLS = [
    "http://httpbin.org/ip",
    "http://ip-api.com/json",
    "http://ifconfig.me/ip",
]
TEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_proxy_line(line: str) -> Optional[Dict]:
    """Parse a proxy line like 'ip:port' or 'protocol://ip:port' or 'ip:port:user:pass'."""
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("//"):
        return None

    # Skip non-proxy lines (e.g. headers like "Last Update: ...")
    if re.match(r'^[A-Za-z]', line) and ':' not in line.split()[0] if line.split() else True:
        # Check if it looks like a date or label
        if re.search(r'(Last|Update|Updated|Date|Proxy|List|http|socks)', line, re.I):
            return None

    # Try protocol://ip:port format
    if "://" in line:
        try:
            parsed = urlparse(line)
            if parsed.hostname and parsed.port:
                # Determine scheme
                scheme = parsed.scheme
                if scheme in ("http", "https", "socks4", "socks5", "socks5h"):
                    return {
                        "ip": parsed.hostname,
                        "port": parsed.port,
                        "protocol": scheme,
                        "url": f"{scheme}://{parsed.hostname}:{parsed.port}",
                        "auth": (parsed.username, parsed.password) if parsed.username else None,
                    }
        except Exception:
            pass

    # Try ip:port format
    parts = line.split(":")
    if len(parts) == 2:
        ip, port = parts[0].strip(), parts[1].strip()
        if _is_valid_ip(ip) and port.isdigit():
            return {
                "ip": ip,
                "port": int(port),
                "protocol": "http",
                "url": f"http://{ip}:{port}",
                "auth": None,
            }

    # Try ip:port:user:pass format
    if len(parts) == 4:
        ip, port, user, pwd = [p.strip() for p in parts]
        if _is_valid_ip(ip) and port.isdigit():
            return {
                "ip": ip,
                "port": int(port),
                "protocol": "http",
                "url": f"http://{user}:{pwd}@{ip}:{port}",
                "auth": (user, pwd),
            }

    return None


def _is_valid_ip(ip: str) -> bool:
    """Quick IPv4 validation."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit() or not 0 <= int(p) <= 255:
            return False
    return True


# ─── SOURCE-SPECIFIC PARSERS ────────────────────────────────────────────

def parse_raw_list(text: str) -> List[str]:
    """Parse a simple newline-separated proxy list (most common format)."""
    proxies = []
    for line in text.splitlines():
        p = parse_proxy_line(line)
        if p:
            proxies.append(p["url"])
    return proxies


def parse_spys_txt(text: str) -> List[str]:
    """Parse spys.me proxy list format."""
    proxies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        # Skip header lines
        if re.match(r'^[A-Za-z\s]+\s+[A-Za-z]', line):
            continue
        if ":" in line:
            # Format: ip:port protocol ...
            parts = line.split()
            addr = parts[0] if parts else ""
            p = parse_proxy_line(addr)
            if p:
                # Detect protocol from rest of line
                rest = " ".join(parts[1:]).lower()
                if "socks5" in rest or "s5" in rest:
                    p["url"] = p["url"].replace("http://", "socks5://")
                elif "socks4" in rest or "s4" in rest:
                    p["url"] = p["url"].replace("http://", "socks4://")
                proxies.append(p["url"])
    return proxies


def parse_table_ip_port(soup: BeautifulSoup, table_index: int = 0) -> List[str]:
    """Parse HTML tables with ip:port columns (common format)."""
    proxies = []
    tables = soup.find_all("table")
    if table_index >= len(tables):
        return proxies

    table = tables[table_index]
    rows = table.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            ip = cols[0].get_text(strip=True)
            port = cols[1].get_text(strip=True)
            if _is_valid_ip(ip) and port.isdigit():
                proxies.append(f"http://{ip}:{port}")

                # Check subsequent columns for HTTPS/SOCKS support
                full_text = row.get_text().lower()
                if len(cols) >= 7:
                    https_td = cols[6].get_text(strip=True).lower()
                    if "yes" in https_td or "y" == https_td:
                        proxies.append(f"https://{ip}:{port}")

    return proxies


def parse_proxynova(soup: BeautifulSoup) -> List[str]:
    """Parse ProxyNova format."""
    proxies = []
    table = soup.find("table", id="tbl_proxy_list")
    if not table:
        # Try generic table
        tables = soup.find_all("table")
        if tables:
            table = tables[0]
        else:
            return proxies

    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            ip_text = cols[0].get_text(strip=True)
            # ProxyNova sometimes has extra text
            ip = ip_text.split()[0] if ip_text else ""
            port = cols[1].get_text(strip=True)
            if _is_valid_ip(ip) and port.isdigit():
                proxies.append(f"http://{ip}:{port}")
    return proxies


def parse_geonode_api(text: str) -> List[str]:
    """Parse Geonode API JSON response."""
    proxies = []
    try:
        data = json.loads(text)
        # Geonode returns: {"data": [{...}], "total": ...}
        results = data.get("data", [])
        for item in results:
            ip = item.get("ip", "")
            port = item.get("port", "")
            protocols = item.get("protocols", [])
            if _is_valid_ip(ip) and port:
                # Add each protocol separately
                if not protocols:
                    protocols = ["http"]
                for proto in protocols:
                    if proto in ("http", "https", "socks4", "socks5"):
                        proxies.append(f"{proto}://{ip}:{port}")
    except Exception:
        pass
    return proxies


def parse_hidemy_name(soup: BeautifulSoup) -> List[str]:
    """Parse HideMy.name format."""
    proxies = []
    table = soup.find("table")
    if not table:
        return proxies

    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            ip = cols[0].get_text(strip=True)
            port = cols[1].get_text(strip=True)
            if _is_valid_ip(ip) and port.isdigit():
                # Detect protocol
                protocol = "http"
                if len(cols) >= 5:
                    type_text = cols[4].get_text(strip=True).lower()
                    if "socks5" in type_text:
                        protocol = "socks5"
                    elif "socks4" in type_text:
                        protocol = "socks4"
                    elif "https" in type_text:
                        protocol = "https"

                proxy_url = f"{protocol}://{ip}:{port}"
                proxies.append(proxy_url)

                # If it supports HTTPS, add both
                if protocol == "http" and len(cols) >= 6:
                    https_text = cols[5].get_text(strip=True).lower()
                    if "yes" in https_text or "y" == https_text:
                        proxies.append(f"https://{ip}:{port}")

    return proxies


# ─── FETCH & PARSE ─────────────────────────────────────────────────────

def fetch_source(source: Dict) -> Tuple[str, List[str]]:
    """Fetch a proxy source and return (source_name, proxy_urls)."""
    name = source["name"]
    url = source["url"]
    parser = source["parser"]

    try:
        resp = requests.get(url, headers=TEST_HEADERS, timeout=FETCH_TIMEOUT)
        if resp.status_code != 200:
            return name, []

        text = resp.text

        if parser == "raw_list":
            proxies = parse_raw_list(text)

        elif parser == "spys_txt":
            proxies = parse_spys_txt(text)

        elif parser == "table_ip_port":
            soup = BeautifulSoup(text, "html.parser")
            proxies = parse_table_ip_port(soup, source.get("table_index", 0))

        elif parser == "geonode_api":
            proxies = parse_geonode_api(text)

        elif parser == "proxynova":
            soup = BeautifulSoup(text, "html.parser")
            proxies = parse_proxynova(soup)

        elif parser == "hidemy_name":
            soup = BeautifulSoup(text, "html.parser")
            proxies = parse_hidemy_name(soup)

        else:
            return name, []

        return name, proxies

    except Exception as e:
        logger.debug(f"Fetch error [{name}]: {e}")
        return name, []


def fetch_all_sources(sources: List[Dict],
                      progress_callback: Optional[Callable] = None) -> Tuple[Set[str], Dict[str, int]]:
    """Fetch all proxy sources in parallel and return deduplicated proxy URLs + stats."""
    all_proxies: Set[str] = set()
    stats: Dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=FETCH_MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_source, src): src for src in sources}

        for future in as_completed(futures):
            src = futures[future]
            try:
                name, proxies = future.result()
                if proxies:
                    count_before = len(all_proxies)
                    all_proxies.update(proxies)
                    new_count = len(all_proxies) - count_before
                    stats[name] = len(proxies)
                    if progress_callback:
                        progress_callback(
                            f"  ✅ {name}: {len(proxies)} proxy (baru: {new_count})",
                            "success",
                        )
                else:
                    stats[name] = 0
                    if progress_callback:
                        progress_callback(f"  ⚠️  {name}: 0 proxy ditemukan", "warn")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"  ❌ {src['name']}: {e}", "error")

    return all_proxies, stats


# ─── PROXY TESTING ─────────────────────────────────────────────────────

def test_single_proxy(proxy_url: str, timeout: int = TEST_TIMEOUT) -> Tuple[str, bool, float]:
    """Test a single proxy. Returns (url, alive, response_time)."""
    scheme = proxy_url.split("://")[0] if "://" in proxy_url else "http"
    test_url = random.choice(TEST_URLS)

    # Determine proxy dict format
    proxy_dict = {
        "http": proxy_url,
        "https": proxy_url,
    }

    start = time.time()
    try:
        resp = requests.get(
            test_url,
            proxies=proxy_dict,
            timeout=timeout,
            headers=TEST_HEADERS,
        )
        elapsed = time.time() - start
        if resp.status_code == 200:
            return proxy_url, True, elapsed
        else:
            return proxy_url, False, elapsed
    except Exception:
        elapsed = time.time() - start
        return proxy_url, False, elapsed


def test_proxies_parallel(proxy_list: List[str],
                          max_workers: int = TEST_CONCURRENCY,
                          min_alive: int = 1,
                          progress_callback: Optional[Callable] = None
                          ) -> List[Tuple[str, float]]:
    """Test all proxies in parallel. Returns [(alive_url, response_time), ...] sorted by speed."""
    if not proxy_list:
        return []

    alive_proxies: List[Tuple[str, float]] = []
    total = len(proxy_list)
    tested = 0

    if progress_callback:
        progress_callback(f"  🧪 Testing {total} proxy dengan {max_workers} thread...", "info")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_proxy, p): p for p in proxy_list}

        for future in as_completed(futures):
            proxy_url = futures[future]
            tested += 1
            try:
                url, alive, elapsed = future.result()
                if alive:
                    alive_proxies.append((url, elapsed))
            except Exception:
                pass

            if progress_callback and tested % 10 == 0:
                pct = (tested / total) * 100
                progress_callback(
                    f"  🔍 Testing {tested}/{total} ({pct:.0f}%) | Alive: {len(alive_proxies)}",
                    "info",
                )

    # Sort by response time (fastest first)
    alive_proxies.sort(key=lambda x: x[1])

    if progress_callback:
        progress_callback(
            f"  ✅ {len(alive_proxies)}/{total} proxy alive (tercepat: {alive_proxies[0][1]:.2f}s)" if alive_proxies
            else f"  ❌ 0/{total} proxy alive!",
            "success" if alive_proxies else "error",
        )

    return alive_proxies


# ─── FILTER BY PROTOCOL ────────────────────────────────────────────────

def filter_by_protocol(proxy_urls: Set[str], protocols: Set[str]) -> List[str]:
    """Filter proxy URLs by protocol type."""
    filtered = []
    for url in proxy_urls:
        scheme = url.split("://")[0] if "://" in url else "http"
        if scheme in protocols:
            filtered.append(url)
    return filtered


def get_playwright_compatible_protocols() -> Set[str]:
    """Return protocols that are compatible with Playwright browser.
    Playwright supports: HTTP, HTTPS, SOCKS5.
    Playwright does NOT support: SOCKS4.
    """
    return {"http", "https", "socks5"}


def _strip_socks4(protocols: Set[str]) -> Set[str]:
    """Remove SOCKS4 from a set of protocols (not Playwright-compatible)."""
    return {p for p in protocols if p != "socks4"}


# ─── MAIN SCRAPE FUNCTION ──────────────────────────────────────────────

def scrape_proxies(
    protocols: Set[str] = None,
    sources: List[str] = None,
    min_proxies: int = 20,
    test: bool = True,
    max_workers: int = TEST_CONCURRENCY,
    progress_callback: Optional[Callable] = None,
    skip_socks4: bool = False,
) -> List[str]:
    """
    Main function: scrape, filter, test, and return alive proxy URLs.

    Args:
        protocols: Set of protocols to include (e.g. {"http", "https", "socks5"})
        sources: List of source names to scrape (None = all)
        min_proxies: Minimum desired proxies (will scrape more if needed)
        test: Whether to test proxies before returning
        max_workers: Parallel test threads
        progress_callback: fn(message, level) for progress updates
        skip_socks4: If True, remove SOCKS4 protocols (not Playwright-compatible)

    Returns:
        List of alive proxy URLs (fastest first)
    """
    if protocols is None:
        protocols = {"http", "https"}

    # Auto-exclude SOCKS4 for Playwright compatibility
    if skip_socks4:
        before = len(protocols)
        protocols = _strip_socks4(protocols)
        if len(protocols) < before and progress_callback:
            progress_callback("  ℹ️  SOCKS4 dilewati (tidak kompatibel dengan Playwright)", "info")

    # Select sources
    if sources:
        active_sources = [s for s in ALL_SOURCES if s["name"] in sources]
    else:
        active_sources = ALL_SOURCES

    if not active_sources:
        if progress_callback:
            progress_callback("  ❌ Tidak ada sumber proxy yang dipilih!", "error")
        return []

    if progress_callback:
        protocol_str = ", ".join(sorted(protocols))
        progress_callback(
            f"  📡 Scraping {len(active_sources)} sumber proxy untuk {protocol_str}...",
            "info",
        )

    # Fetch all sources
    all_proxies, stats = fetch_all_sources(active_sources, progress_callback)

    if not all_proxies:
        if progress_callback:
            progress_callback("  ❌ Tidak ada proxy ditemukan dari semua sumber!", "error")
        return []

    if progress_callback:
        progress_callback(
            f"  📊 Total: {len(all_proxies)} proxy unik (sebelum filter)",
            "info",
        )

    # Filter by protocol
    filtered = filter_by_protocol(all_proxies, protocols)
    if not filtered:
        if progress_callback:
            progress_callback(
                f"  ❌ Tidak ada proxy untuk protocol {protocols}",
                "error",
            )
        return []

    if progress_callback:
        progress_callback(
            f"  🔎 Setelah filter protocol: {len(filtered)} proxy",
            "info",
        )

    # If not testing, return all filtered
    if not test:
        # Shuffle for randomness
        random.shuffle(filtered)
        return filtered[:max(min_proxies * 5, len(filtered))]

    # Test proxies
    alive = test_proxies_parallel(
        filtered,
        max_workers=max_workers,
        min_alive=min_proxies,
        progress_callback=progress_callback,
    )

    if not alive:
        if progress_callback:
            progress_callback("  ❌ Tidak ada proxy yang alive!", "error")
        return []

    # Return just URLs, fastest first + some random slower ones for variety
    result = [url for url, _ in alive]

    # Ensure minimum count
    if len(result) < min_proxies and progress_callback:
        progress_callback(
            f"  ⚠️  Hanya {len(result)} proxy alive (target: {min_proxies})",
            "warn",
        )

    return result


def scrape_and_save(
    protocols: Set[str] = None,
    output_file: str = "proxy.txt",
    min_proxies: int = 50,
    progress_callback: Optional[Callable] = None,
    skip_socks4: bool = False,
) -> int:
    """
    Scrape, test, and save alive proxies to a file.

    Args:
        protocols: Set of protocols to include
        output_file: File to save proxies to
        min_proxies: Minimum desired proxies
        progress_callback: fn(message, level) for progress updates
        skip_socks4: If True, remove SOCKS4 protocols (not Playwright-compatible)

    Returns:
        Number of alive proxies saved.
    """
    alive = scrape_proxies(
        protocols=protocols,
        min_proxies=min_proxies,
        test=True,
        progress_callback=progress_callback,
        skip_socks4=skip_socks4,
    )

    if not alive:
        return 0

    # Save to file
    try:
        with open(output_file, "w") as f:
            f.write(f"# Auto-scraped proxies ({len(alive)} alive)\n")
            f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Protocols: {', '.join(sorted(protocols or {'http', 'https'}))}\n")
            f.write(f"# Sources: All\n")
            f.write("# ========================================\n")
            for url in alive:
                f.write(url + "\n")

        if progress_callback:
            progress_callback(
                f"  💾 Tersimpan: {len(alive)} proxy ke {output_file}",
                "success",
            )
    except Exception as e:
        if progress_callback:
            progress_callback(f"  ❌ Gagal menyimpan: {e}", "error")
        return 0

    return len(alive)


# ─── QUICK SCRAPE (no callbacks, returns data) ─────────────────────────

def quick_scrape(protocols: Set[str] = None, min_alive: int = 20,
                  skip_socks4: bool = False) -> List[str]:
    """
    Quick one-shot scrape. Good for TUI/non-GUI usage.
    Returns list of alive proxy URLs.

    Args:
        protocols: Set of protocols to include
        min_alive: Minimum desired proxies
        skip_socks4: If True, remove SOCKS4 protocols (not Playwright-compatible)
    """
    return scrape_proxies(
        protocols=protocols,
        min_proxies=min_alive,
        test=True,
        max_workers=20,
        skip_socks4=skip_socks4,
    )


# ─── SOURCE INFO ───────────────────────────────────────────────────────

def get_source_names() -> List[str]:
    """Get list of available source names."""
    return [s["name"] for s in ALL_SOURCES]


def get_protocol_options() -> List[str]:
    """Get available protocol options."""
    all_types = set()
    for s in ALL_SOURCES:
        all_types.update(s["types"])
    return sorted(all_types)


# ─── STANDALONE TESTING ────────────────────────────────────────────────

def _console_callback(message: str, level: str = "info"):
    """Print callback for console testing."""
    icons = {"success": "✅", "info": "ℹ️", "warn": "⚠️", "error": "❌"}
    icon = icons.get(level, "•")
    print(f"{icon} {message}")


if __name__ == "__main__":
    import sys

    print("🌐 Proxy Scraper — Standalone Test")
    print("=" * 50)
    print(f"Sumber tersedia: {len(ALL_SOURCES)}")
    for s in ALL_SOURCES:
        print(f"  • {s['name']:30s} | {', '.join(s['types']):20s} | {s['parser']}")
    print()

    # Parse args
    protocols = {"http", "https"}
    if len(sys.argv) > 1:
        protocols = set(sys.argv[1].split(","))

    print(f"📡 Scraping untuk protocol: {', '.join(sorted(protocols))}")
    print()

    alive = scrape_proxies(
        protocols=protocols,
        min_proxies=20,
        progress_callback=_console_callback,
    )

    print()
    print(f"{'='*50}")
    print(f"Hasil: {len(alive)} proxy alive")
    if alive:
        print(f"Contoh (5 tercepat):")
        for url in alive[:5]:
            print(f"  • {url}")
