"""
proxy_manager.py — Enhanced Proxy Manager

Fitur baru:
- Health tracking per proxy (success/fail ratio, latency, score)
- Auto-refresh dari proxy_scraper jika semua proxy mati
- Smart filtering: skip proxy rusak, prioritaskan yang cepat
- Graceful degradation: jika proxy habis, fallback ke direct connection
- Thread-safe dengan lock yang lebih granular
"""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests

# ── Parallel test constants ──────────────────────────────────────────
TEST_CONCURRENCY = 30        # Max parallel proxy tests
TEST_TIMEOUT = 10            # Seconds per proxy test timeout

# ── Import scraper (optional — graceful fallback) ─────────────────────
try:
    from proxy_scraper import scrape_proxies
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False

# ── Import rotating providers (optional) ────────────────────────────────
try:
    from rotating_providers import (
        RotatingProxyManager, load_provider_config,
        list_providers, get_provider, test_quick,
    )
    HAS_ROTATING = True
except ImportError:
    HAS_ROTATING = False


class Proxy:
    """Single proxy with health tracking."""

    # ── Health scoring constants ─────────────────────────────────────
    MAX_FAILS = 5                # Max consecutive fails before marked dead
    RECOVERY_SUCCESSES = 3       # Successes needed to fully revive
    MAX_LATENCY = 15.0           # Max acceptable latency in seconds
    SCORE_DECAY_MINUTES = 30     # Score decays over time if unused

    def __init__(self, url: str):
        self.url = url.strip()
        self.scheme = "http"
        self.host = ""
        self.port = 0
        self.auth: Optional[Tuple[str, str]] = None
        self.alive = True                     # Whether proxy is usable
        self.fail_count = 0                   # Consecutive fail count
        self.max_fails = self.MAX_FAILS       # Max fails before dead
        self.success_count = 0                # Total successes
        self.total_fails = 0                  # Total failures
        self.last_success_time = 0.0          # Timestamp of last success
        self.last_fail_time = 0.0             # Timestamp of last fail
        self.last_latency = 0.0               # Last measured response time
        self.avg_latency = 0.0                # Running average latency
        self._latency_samples: List[float] = []
        self._recovery_successes = 0          # Successes since last fail
        self._parse()

    SOCKS_SCHEMES = ("socks4", "socks5", "socks5h")

    def _parse(self):
        parsed = urlparse(self.url)
        self.scheme = parsed.scheme or "http"
        self.host = parsed.hostname or ""
        self.port = parsed.port or 0
        if parsed.username and parsed.password:
            self.auth = (parsed.username, parsed.password)

    def get_dict(self) -> dict:
        if self.scheme in self.SOCKS_SCHEMES:
            auth_part = f"{self.auth[0]}:{self.auth[1]}@" if self.auth else ""
            return {
                "http": f"{self.scheme}://{auth_part}{self.host}:{self.port}",
                "https": f"{self.scheme}://{auth_part}{self.host}:{self.port}",
            }
        return {
            "http": self.url,
            "https": self.url,
        }

    def mark_failed(self, latency: float = 0.0):
        """Mark a failure, potentially marking proxy as dead."""
        self.fail_count += 1
        self.total_fails += 1
        self.last_fail_time = time.time()
        self.last_latency = latency
        self._recovery_successes = 0

        if self.fail_count >= self.max_fails:
            self.alive = False

    def mark_success(self, latency: float = 0.0):
        """Mark a success. Revives proxy if it was dead."""
        self.fail_count = 0
        self.success_count += 1
        self.last_success_time = time.time()
        self.last_latency = latency

        # Track latency for average
        if latency > 0:
            self._latency_samples.append(latency)
            if len(self._latency_samples) > 10:
                self._latency_samples = self._latency_samples[-10:]
            self.avg_latency = sum(self._latency_samples) / len(self._latency_samples)

        # Recovery: if proxy was dead but starts working again
        self._recovery_successes += 1
        if not self.alive and self._recovery_successes >= self.RECOVERY_SUCCESSES:
            self.alive = True
            self.fail_count = 0
            self.max_fails = max(3, self.MAX_FAILS - self.total_fails // 5)

    @property
    def health_score(self) -> float:
        """
        Calculate health score 0.0–1.0.
        Based on: success rate, latency, recency.
        """
        if self.success_count + self.total_fails == 0:
            return 0.5  # Neutral for untested

        # Success rate
        total = self.success_count + self.total_fails
        success_rate = self.success_count / max(total, 1)

        # Latency score (1.0 for fast, 0.0 for slow)
        if self.avg_latency > 0:
            latency_score = max(0.0, 1.0 - (self.avg_latency / self.MAX_LATENCY))
        else:
            latency_score = 0.5

        # Combine
        score = (success_rate * 0.6) + (latency_score * 0.4)

        # Bonus for many successes (proven reliability)
        if self.success_count > 50:
            score = min(1.0, score + 0.1)
        elif self.success_count > 20:
            score = min(1.0, score + 0.05)

        return max(0.0, min(1.0, score))

    def reset(self):
        """Reset proxy health stats (not URL)."""
        self.alive = True
        self.fail_count = 0
        self.success_count = 0
        self.total_fails = 0
        self.last_latency = 0.0
        self.avg_latency = 0.0
        self._latency_samples = []
        self._recovery_successes = 0
        self.max_fails = self.MAX_FAILS

    def __str__(self):
        auth_str = "***:***@" if self.auth else ""
        return f"{self.scheme}://{auth_str}{self.host}:{self.port}"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        if isinstance(other, Proxy):
            return self.url == other.url
        return self.url == str(other)


class ProxyManager:
    """
    Enhanced Proxy Manager with:
    - Health tracking per proxy
    - Smart proxy selection (weighted by health score)
    - Auto-refresh from scraper when proxies run out
    - Graceful degradation (fallback to direct)
    - Thread-safe operations
    """

    # ── Auto-refresh thresholds ──────────────────────────────────────
    AUTO_REFRESH_MIN_ALIVE = 3        # Auto-refresh when alive count drops below this
    AUTO_REFRESH_COOLDOWN = 120       # Seconds between auto-refresh attempts
    SCRAPE_MIN_ALIVE_TARGET = 30      # Target number of alive proxies when scraping

    def __init__(self, config):
        self.config = config
        self.proxies: List[Proxy] = []
        self.lock = threading.RLock()  # Reentrant lock for nested calls
        self.current_index = 0

        # ── Health tracking ──────────────────────────────────────────
        self._proxy_stats: Dict[str, Dict] = {}  # url -> stats dict
        self._last_auto_refresh = 0.0
        self._refresh_in_progress = False
        self._used_proxies: Set[str] = set()
        self._bad_proxies: Set[str] = set()

        # ── Grace period config ──────────────────────────────────────
        self._grace_until = 0.0
        self._grace_mode = False
        self._max_grace_seconds = 30

        # ── Rotating gateways from rotating.txt ──────────────────────
        self._rotating_gateways: List[Dict] = []  # entries from rotating.txt

        # ── Rotating provider manager (from config.json) ────────────────
        self._rotating_mgr: Optional[RotatingProxyManager] = None
        self._rotating_active: List[Dict] = []
        if HAS_ROTATING:
            self._rotating_mgr = RotatingProxyManager()
            self._rotating_active = load_provider_config(config.data if hasattr(config, 'data') else {})

        self._load_proxies()
        self._load_rotating_gateways()

    # ── LOADING ────────────────────────────────────────────────────────

    # ── Playwright-compatible proxy schemes ───────────────────────────
    PLAYWRIGHT_SCHEMES = ("http", "https", "socks5", "socks5h")
    SOCKS4_SCHEMES = ("socks4",)

    @staticmethod
    def _is_proxy_error(error_str: str) -> bool:
        """Check if an error string indicates a bad proxy (Playwright or requests)."""
        if not error_str:
            return False
        err = error_str.lower()
        patterns = [
            "proxy",
            "timed_out", "timeout",
            "connection_failed", "connection_reset", "connection refused",
            "tunnel_connection_failed", "tunnel",
            "socks_connection_failed", "socks",
            "proxyerror", "proxyerror",
            "err_timed_out", "err_connection", "err_tunnel", "err_socks",
            "name_not_resolved", "dns",
            "eof", "reset by peer", "connection aborted",
            "unreachable", "network is unreachable",
            "socket hang up", "socket closed",
        ]
        return any(p in err for p in patterns)

    @staticmethod
    def _proxy_scheme_is_playwright_compatible(scheme: str) -> bool:
        """Check if proxy scheme is compatible with Playwright browser.
        Playwright supports: HTTP, HTTPS, SOCKS5.
        Playwright does NOT support: SOCKS4.
        """
        return scheme.lower() in ProxyManager.PLAYWRIGHT_SCHEMES

    def _load_proxies(self):
        """Load proxies from config list and proxy file.
        SOCKS4 proxies are automatically excluded because Playwright
        does not support them and they waste time during testing.
        """
        self.proxies = []
        seen: Set[str] = set()
        socks4_skipped = 0

        def _add_proxy(p_str: str):
            nonlocal socks4_skipped
            p_str = p_str.strip()
            if not p_str or p_str in seen:
                return
            # Check SOCKS4 — Playwright doesn't support it
            scheme = p_str.split("://")[0].lower() if "://" in p_str else "http"
            if scheme in ProxyManager.SOCKS4_SCHEMES:
                socks4_skipped += 1
                return
            self.proxies.append(Proxy(p_str))
            seen.add(p_str)

        # From config list
        for p in self.config.proxy_list:
            _add_proxy(p)

        # From proxy_file
        proxy_file = self.config.proxy_file
        if proxy_file:
            try:
                with open(proxy_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            _add_proxy(line)
            except FileNotFoundError:
                pass
            except Exception:
                pass

        random.shuffle(self.proxies)
        self.current_index = 0
        self._used_proxies.clear()
        self._bad_proxies.clear()

        if socks4_skipped > 0:
            import logging
            logging.getLogger("bot").warning(
                f"⚠️  {socks4_skipped} SOCKS4 proxy dilewati (tidak kompatibel dengan Playwright)"
            )

    def load_from_file(self, filepath: str):
        """Load/replace proxies from a file."""
        with self.lock:
            self.config.data.setdefault("proxies", {})
            self.config.data["proxies"]["file"] = filepath
            self._load_proxies()
            # Re-test all newly loaded proxies
            threading.Thread(target=self._background_test, daemon=True).start()

    def _background_test(self):
        """Test all proxies in background (parallel)."""
        with self.lock:
            proxies = list(self.proxies)
        with ThreadPoolExecutor(max_workers=TEST_CONCURRENCY) as executor:
            # Consume iterator so results are collected and exceptions surface
            list(executor.map(self.test_proxy, proxies))

    def load_from_scraper(self, alive_proxies: List[str]):
        """Load proxies from scraper results."""
        with self.lock:
            # Clear existing
            self.proxies = []
            seen: Set[str] = set()

            for url in alive_proxies:
                if url not in seen:
                    proxy = Proxy(url)
                    # Mark as already tested (scraper already tested it)
                    proxy.mark_success(latency=0.5)  # Assume tested
                    self.proxies.append(proxy)
                    seen.add(url)

            random.shuffle(self.proxies)
            self.current_index = 0
            self._used_proxies.clear()
            self._bad_proxies.clear()
            self._last_auto_refresh = time.time()

            # Save to proxy file
            try:
                filepath = self.config.proxy_file or "proxy.txt"
                with open(filepath, "w") as f:
                    f.write(f"# Auto-scraped proxies ({len(alive_proxies)} total)\n")
                    f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("# =========================================\n")
                    for url in alive_proxies:
                        f.write(url + "\n")
            except Exception:
                pass

    # ── ROTATING.TXT GATEWAY LOADER ──────────────────────────────────

    @staticmethod
    def _parse_rotating_line(line: str) -> Optional[Dict]:
        """
        Parse satu baris dari rotating.txt.

        Format:
          http://user:pass@host:port  |country=id  |sticky=true

        Returns dict {"url": str, "country": str, "sticky": bool} atau None.
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        # Split by whitespace after URL to separate options
        # URL bisa mengandung spasi? Tidak. Tapi options dipisah dengan spasi+|
        # Format: URL [ |key=val [ |key=val ...]]
        parts = line.split()
        if not parts:
            return None

        raw_url = parts[0]

        # Remove trailing | and parse options from remaining parts
        country = ""
        sticky = False

        for p in parts[1:]:
            p = p.strip().lstrip("|")
            if not p:
                continue
            if p.startswith("country="):
                country = p.split("=", 1)[1].strip().lower()
            elif p.startswith("sticky="):
                val = p.split("=", 1)[1].strip().lower()
                sticky = val in ("true", "yes", "1", "on")

        # Pastikan URL valid
        if "://" not in raw_url:
            raw_url = f"http://{raw_url}"

        parsed = urlparse(raw_url)
        if not parsed.hostname or not parsed.port:
            return None

        return {
            "url": raw_url,
            "country": country,
            "sticky": sticky,
        }

    def _load_rotating_gateways(self):
        """
        Load rotating proxy gateways dari rotating.txt.
        File ini berisi URL gateway rotating proxy provider,
        satu per baris, dengan opsi inline |country=XX |sticky=true.
        """
        self._rotating_gateways = []
        rotating_file = self.config.rotating_file
        if not rotating_file:
            return

        try:
            with open(rotating_file, "r") as f:
                for line in f:
                    entry = self._parse_rotating_line(line)
                    if entry:
                        self._rotating_gateways.append(entry)
        except FileNotFoundError:
            pass  # rotating.txt optional — fallback ke proxy.txt
        except Exception:
            pass

        if self._rotating_gateways:
            import logging
            logging.getLogger("bot").info(
                f"🌐 Loaded {len(self._rotating_gateways)} rotating gateway(s) from {rotating_file}"
            )

    # ── TESTING ────────────────────────────────────────────────────────

    def test_proxy(self, proxy: Proxy) -> bool:
        """Test a single proxy. Returns True if alive.
        Tests with both HTTP and HTTPS to ensure the proxy works for both.
        """
        try:
            test_url = self.config.proxy_test_url  # Default: http://httpbin.org/ip
            # Also test an HTTPS URL to ensure TLS works
            https_test_url = "https://httpbin.org/ip"
            start = time.time()
            resp = requests.get(
                test_url,
                proxies=proxy.get_dict(),
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                # Quick HTTPS test — many proxies handle HTTP but fail HTTPS
                try:
                    https_resp = requests.get(
                        https_test_url,
                        proxies=proxy.get_dict(),
                        timeout=8,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    if https_resp.status_code != 200:
                        # HTTPS failed — mark as slower (HTTPS is more important for browsers)
                        elapsed *= 1.5
                except Exception:
                    # HTTPS failed completely — proxy is weak
                    elapsed *= 2.0
                proxy.mark_success(elapsed)
                return True
        except Exception:
            pass
        proxy.mark_failed()
        return False

    def test_all(self) -> Tuple[int, int]:
        """Test all proxies in parallel. Returns (alive_count, total_count)."""
        proxies = list(self.proxies)
        if not proxies:
            return 0, 0

        with ThreadPoolExecutor(max_workers=TEST_CONCURRENCY) as executor:
            results = list(executor.map(self.test_proxy, proxies))
            alive_count = sum(1 for r in results if r)
        return alive_count, len(proxies)

    def test_fast(self, sample: int = 10) -> Tuple[int, int]:
        """Quick test of a sample. Returns (alive_in_sample, sample_size)."""
        with self.lock:
            to_test = random.sample(self.proxies, min(sample, len(self.proxies))) if self.proxies else []
        alive = sum(1 for p in to_test if self.test_proxy(p))
        return alive, len(to_test)

    # ── PROXY SELECTION (smart) ────────────────────────────────────────

    def get_proxy(self, prefer_rotating: bool = True) -> Optional[Proxy]:
        """
        Get the best available proxy.
        Priority:
        1. Rotating gateways dari rotating.txt (always fresh, no testing needed)
        2. Rotating providers dari config.json (BrightData, Oxylabs, dll)
        3. Static proxy list dari proxy.txt (dengan health tracking)
        4. None (direct connection — graceful degradation)
        """
        if not self.config.proxy_enabled:
            return None

        # ══════════════════════════════════════════════════════════════════
        #  PRIORITY 1: Rotating gateways dari rotating.txt
        # ══════════════════════════════════════════════════════════════════
        if prefer_rotating and self._rotating_gateways:
            entry = random.choice(self._rotating_gateways)
            proxy = Proxy(entry["url"])
            # Gateway selalu fresh — jangan ditandai mati
            proxy.alive = True
            proxy.mark_success(latency=0.3)
            # Tambah metadata untuk logging
            proxy._is_rotating_gateway = True
            proxy._rotating_country = entry.get("country", "")
            proxy._rotating_sticky = entry.get("sticky", False)
            return proxy

        # ══════════════════════════════════════════════════════════════════
        #  PRIORITY 2: Rotating providers dari config.json
        # ══════════════════════════════════════════════════════════════════
        if prefer_rotating and HAS_ROTATING and self._rotating_mgr and self._rotating_active:
            # Randomly pick an active rotating provider
            cfg = random.choice(self._rotating_active)
            slug = cfg.get("provider", "")
            creds = cfg.get("credentials", {})
            country = cfg.get("country", "")
            sticky = cfg.get("sticky_session", False)

            proxy_dict = self._rotating_mgr.get_proxy(
                slug, creds, country=country, sticky=sticky
            )
            if proxy_dict:
                # Wrap rotating provider URL as a Proxy object
                http_url = proxy_dict.get("http", "")
                if http_url:
                    proxy = Proxy(http_url)
                    # Mark as alive — rotating providers are always fresh
                    proxy.alive = True
                    proxy.mark_success(latency=0.5)
                    proxy._is_rotating_gateway = True
                    return proxy

        # ══════════════════════════════════════════════════════════════════
        #  PRIORITY 3: Static proxy list dari proxy.txt
        # ══════════════════════════════════════════════════════════════════
        if not self.proxies:
            return None

        with self.lock:
            alive = [p for p in self.proxies if p.alive and p.url not in self._bad_proxies]

            if not alive:
                alive = [p for p in self.proxies if p.alive]

            if not alive:
                # Try auto-refresh from scraper
                self._try_auto_refresh()
                return None

            if self.config.rotate_every_request:
                scores = [(p, p.health_score) for p in alive]
                weights = [
                    max(0.1, s + (0.3 if p.success_count == 0 and p.total_fails == 0 else 0.0))
                    for p, s in scores
                ]
                total_w = sum(weights)
                if total_w > 0:
                    weights = [w / total_w for w in weights]
                    proxy = random.choices(alive, weights=weights, k=1)[0]
                else:
                    proxy = random.choice(alive)
            else:
                proxy = alive[self.current_index % len(alive)]
                self.current_index += 1

            self._used_proxies.add(proxy.url)
            return proxy

    def get_proxy_dict(self, prefer_rotating: bool = True) -> Optional[dict]:
        """Get proxy dict for requests library."""
        proxy = self.get_proxy(prefer_rotating=prefer_rotating)
        if proxy:
            return proxy.get_dict()
        return None

    def get_rotating_proxy(self) -> Optional[dict]:
        """Get a proxy from a rotating provider only (no fallback)."""
        if not HAS_ROTATING or not self._rotating_mgr or not self._rotating_active:
            return None
        cfg = random.choice(self._rotating_active)
        return self._rotating_mgr.get_proxy(
            cfg.get("provider", ""),
            cfg.get("credentials", {}),
            country=cfg.get("country", ""),
            sticky=cfg.get("sticky_session", False),
        )

    def validate_on_fail(self, proxy: Optional[Proxy]):
        """Validate a proxy after a failure."""
        if proxy and self.config.test_proxies:
            self.test_proxy(proxy)

    # ── AUTO-REFRESH ──────────────────────────────────────────────────

    def _try_auto_refresh(self):
        """
        Auto-refresh proxies from scraper when running low.
        Only triggers if:
        - Scraper module is available
        - Enough time has passed since last refresh (cooldown)
        - No refresh is already in progress
        """
        if not HAS_SCRAPER:
            return

        with self.lock:
            alive_count = self.alive_count
            now = time.time()

            # Don't refresh if we still have enough
            if alive_count >= self.AUTO_REFRESH_MIN_ALIVE:
                return

            # Don't refresh too often
            if now - self._last_auto_refresh < self.AUTO_REFRESH_COOLDOWN:
                return

            # Don't overlap refreshes
            if self._refresh_in_progress:
                return

            self._refresh_in_progress = True

        # Fire-and-forget background refresh
        threading.Thread(target=self._do_auto_refresh, daemon=True).start()

    def _do_auto_refresh(self):
        """Background auto-refresh from scraper."""
        try:
            alive = scrape_proxies(
                protocols={"http", "https"},
                min_proxies=self.SCRAPE_MIN_ALIVE_TARGET,
                test=True,
                max_workers=20,
            )
            if alive:
                self.load_from_scraper(alive)
        except Exception:
            pass
        finally:
            with self.lock:
                self._refresh_in_progress = False

    # ── REPORTING ─────────────────────────────────────────────────────

    def get_report(self) -> dict:
        """Get detailed proxy report."""
        with self.lock:
            alive = [p for p in self.proxies if p.alive]
            dead = [p for p in self.proxies if not p.alive]
            untested = [p for p in self.proxies if p.success_count == 0 and p.total_fails == 0]

            # Sort alive by health score
            alive_sorted = sorted(alive, key=lambda p: p.health_score, reverse=True)

            # Separate by Playwright compatibility
            pw_compatible = [p for p in alive if self._proxy_scheme_is_playwright_compatible(p.scheme)]
            not_pw = [p for p in alive if not self._proxy_scheme_is_playwright_compatible(p.scheme)]

            return {
                "total": len(self.proxies),
                "alive": len(alive),
                "dead": len(dead),
                "untested": len(untested),
                "playwright_compatible": len(pw_compatible),
                "playwright_incompatible": len(not_pw),
                "enabled": self.config.proxy_enabled,
                "rotation": "per request" if self.config.rotate_every_request else "sequential",
                "avg_latency": sum(p.avg_latency for p in alive) / max(len(alive), 1),
                "top_proxies": [
                    {
                        "url": str(p),
                        "score": round(p.health_score, 2),
                        "latency": round(p.avg_latency, 3),
                        "successes": p.success_count,
                        "fails": p.total_fails,
                    }
                    for p in alive_sorted[:5]
                ],
                "bad_proxies_count": len(self._bad_proxies),
                "auto_refresh_available": HAS_SCRAPER,
            }

    # ── MANAGEMENT ────────────────────────────────────────────────────

    def reload(self):
        """Reload proxies from disk config (proxy.txt + rotating.txt)."""
        self._load_proxies()
        self._load_rotating_gateways()

    def add_proxy(self, url: str):
        """Add a single proxy."""
        with self.lock:
            # Avoid duplicates
            for p in self.proxies:
                if p.url == url:
                    return
            self.proxies.append(Proxy(url))

    def remove_proxy(self, url: str):
        """Remove a specific proxy."""
        with self.lock:
            self.proxies = [p for p in self.proxies if p.url != url]
            self._bad_proxies.discard(url)
            self._used_proxies.discard(url)

    def mark_bad(self, url: str):
        """Permanently mark a proxy as bad (won't be retried this session)."""
        with self.lock:
            self._bad_proxies.add(url)
            for p in self.proxies:
                if p.url == url:
                    p.alive = False
                    break

    def mark_good(self, url: str):
        """Remove a proxy from the bad list."""
        with self.lock:
            self._bad_proxies.discard(url)
            for p in self.proxies:
                if p.url == url:
                    p.alive = True
                    p.fail_count = 0
                    break

    # ── MANUAL PROXY MANAGEMENT ────────────────────────────────────────

    def add_manual(self, proxy_url: str) -> bool:
        """
        Add a single proxy manually. Validates format first.
        Returns True if added successfully.
        """
        proxy_url = proxy_url.strip()
        if not proxy_url:
            return False

        # Validate format
        if "://" not in proxy_url:
            proxy_url = f"http://{proxy_url}"

        # Check for duplicates
        with self.lock:
            for p in self.proxies:
                if p.url == proxy_url:
                    return False  # Already exists

            proxy = Proxy(proxy_url)
            self.proxies.append(proxy)

            # Save to proxy file
            try:
                filepath = self.config.proxy_file or "proxy.txt"
                with open(filepath, "a") as f:
                    f.write(f"{proxy_url}\n")
            except Exception:
                pass

            return True

    def add_manual_bulk(self, proxy_urls: List[str]) -> Tuple[int, int]:
        """
        Add multiple proxies at once.
        Returns (added_count, duplicate_count).
        """
        added = 0
        duplicates = 0
        for url in proxy_urls:
            if self.add_manual(url):
                added += 1
            else:
                duplicates += 1
        return added, duplicates

    def remove_manual(self, proxy_url: str) -> bool:
        """Remove a proxy by URL."""
        with self.lock:
            before = len(self.proxies)
            self.proxies = [p for p in self.proxies if p.url != proxy_url]
            self._bad_proxies.discard(proxy_url)
            self._used_proxies.discard(proxy_url)
            if len(self.proxies) < before:
                # Also remove from proxy file
                try:
                    filepath = self.config.proxy_file or "proxy.txt"
                    with open(filepath, "r") as f:
                        lines = f.readlines()
                    with open(filepath, "w") as f:
                        for line in lines:
                            if line.strip() != proxy_url:
                                f.write(line)
                except Exception:
                    pass
                return True
            return False

    def list_manual(self) -> List[Dict]:
        """List all manually added proxies with status."""
        with self.lock:
            return [
                {
                    "url": str(p),
                    "alive": p.alive,
                    "latency": round(p.avg_latency, 3),
                    "successes": p.success_count,
                    "fails": p.total_fails,
                    "score": round(p.health_score, 2),
                    "last_used": p.last_success_time,
                }
                for p in self.proxies
            ]

    def test_single(self, proxy_url: str) -> Tuple[bool, float]:
        """Test a single proxy URL."""
        proxy = Proxy(proxy_url)
        alive = self.test_proxy(proxy)
        return alive, proxy.avg_latency

    # ── ROTATING PROVIDER MANAGEMENT ──────────────────────────────────

    def get_rotating_status(self) -> Dict:
        """Get status of all configured rotating providers."""
        if not HAS_ROTATING:
            return {"available": False, "providers": []}

        result = {
            "available": True,
            "active_count": len(self._rotating_active),
            "providers": [],
        }
        for cfg in self._rotating_active:
            slug = cfg.get("provider", "unknown")
            provider = get_provider(slug) if HAS_ROTATING else None
            result["providers"].append({
                "name": provider.name if provider else slug,
                "slug": slug,
                "country": cfg.get("country", "any"),
                "sticky": cfg.get("sticky_session", False),
            })

        if self._rotating_mgr:
            result["sessions"] = self._rotating_mgr.get_stats()

        return result

    def add_rotating_provider(self, config_dict: dict) -> bool:
        """Add a rotating provider configuration."""
        if not HAS_ROTATING:
            return False

        slug = config_dict.get("provider", "").lower()
        if not get_provider(slug):
            return False

        with self.lock:
            # Remove existing config for same provider
            self._rotating_active = [
                c for c in self._rotating_active
                if c.get("provider", "").lower() != slug
            ]
            self._rotating_active.append(config_dict)

            # Save to config
            self.config.data.setdefault("proxies", {})
            self.config.data["proxies"]["rotating_providers"] = [
                c for c in self._rotating_active
            ]
            self.config.save()

            return True

    def remove_rotating_provider(self, slug: str) -> bool:
        """Remove a rotating provider configuration."""
        if not HAS_ROTATING:
            return False

        with self.lock:
            before = len(self._rotating_active)
            self._rotating_active = [
                c for c in self._rotating_active
                if c.get("provider", "").lower() != slug.lower()
            ]
            if len(self._rotating_active) < before:
                # Save to config
                self.config.data.setdefault("proxies", {})
                self.config.data["proxies"]["rotating_providers"] = [
                    c for c in self._rotating_active
                ]
                self.config.save()
                return True
            return False

    def test_rotating_provider(self, slug: str) -> Tuple[bool, float, str]:
        """Test connection to a rotating provider."""
        if not HAS_ROTATING or not self._rotating_mgr:
            return False, 0, "Rotating providers not available"

        for cfg in self._rotating_active:
            if cfg.get("provider", "").lower() == slug.lower():
                return self._rotating_mgr.test_connection(
                    slug,
                    cfg.get("credentials", {}),
                    country=cfg.get("country", ""),
                )
        return False, 0, f"Provider '{slug}' not configured"

    def clear_bad_list(self):
        """Reset all bad proxy marks."""
        with self.lock:
            self._bad_proxies.clear()
            for p in self.proxies:
                if not p.alive and p.total_fails < p.MAX_FAILS * 2:
                    p.alive = True
                    p.fail_count = 0

    def clear_all(self):
        """Remove all proxies."""
        with self.lock:
            self.proxies.clear()
            self._bad_proxies.clear()
            self._used_proxies.clear()
            self.current_index = 0

    # ── PROPERTIES ────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self.proxies) + len(self._rotating_gateways)

    @property
    def alive_count(self) -> int:
        """Jumlah proxy hidup = static proxy alive + rotating gateways.
        Rotating gateways selalu dianggap hidup (gateway auto-rotate).
        """
        static_alive = sum(1 for p in self.proxies if p.alive)
        return static_alive + len(self._rotating_gateways)

    @property
    def dead_count(self) -> int:
        return sum(1 for p in self.proxies if not p.alive)

    @property
    def has_alive(self) -> bool:
        """Quick check if any alive proxy exists (incl. rotating gateways)."""
        return any(p.alive for p in self.proxies) or len(self._rotating_gateways) > 0

    @property
    def playwright_usable_count(self) -> int:
        """Count of proxies that are both alive AND Playwright-compatible."""
        return sum(1 for p in self.proxies if p.alive and self._proxy_scheme_is_playwright_compatible(p.scheme))

    @property
    def need_refresh(self) -> bool:
        """Whether proxies need refreshing from scraper."""
        return self.alive_count < self.AUTO_REFRESH_MIN_ALIVE and HAS_SCRAPER
