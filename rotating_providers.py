"""
rotating_providers.py — Integrated Rotating Proxy Provider Support

Supported providers (all use gateway-based rotation — no manual IP list needed):

  Provider       | Gateway Format                         | Auth Method
  ───────────────┼────────────────────────────────────────┼─────────────────
  BrightData     | brd.superproxy.io:22225                | customer_id + zone
  Oxylabs        | pr.oxylabs.io:7777                    | sub-user credentials
  Smartproxy     | gate.smartproxy.com:7000              | username + password
  Webshare       | p.webshare.io:80                      | username + password
  IPRoyal        | residential.royalproxy.com:3100       | token-based
  Soax           | proxy.soax.com:9132                   | token-based
  NetNut         | proxy.netnut.io:6060                  | username + password
  Proxy-Cheap    | proxy.proxy-cheap.com:3112             | username + password
  StormProxies   | proxy.stormproxies.com:5000            | username + password

Each provider is configured with a dict in config.json under "proxies.rotating_providers":

  {
    "enabled": true,
    "provider": "brightdata",
    "credentials": {
      "username": "...",
      "password": "...",
      "customer_id": "...",   // BrightData only
      "zone": "...",          // BrightData only
      "token": "..."          // IPRoyal / Soax only
    },
    "country": "us",            // optional geo-targeting
    "sticky_session": false,    // keep same IP for session
    "session_ttl_minutes": 10   // how long to keep sticky session
  }

Usage:
  from rotating_providers import get_rotating_proxy, list_providers
  proxy = get_rotating_proxy("brightdata", credentials={...})
  # proxy dict = {"http": "http://user:pass@host:port", "https": "..."}
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests


# ── Provider Definitions ────────────────────────────────────────────────

@dataclass
class RotatingProvider:
    """Definition of a rotating proxy provider."""
    name: str
    slug: str
    description: str
    docs_url: str
    signup_url: str
    supports_sticky: bool = True
    supports_geo: bool = True
    supports_session_ttl: bool = True

    # Gateway defaults
    default_host: str = ""
    default_port: int = 0
    auth_format: str = "user_pass"  # user_pass | customer_zone | token

    def get_proxy_url(self, credentials: dict, country: str = "",
                      sticky: bool = False, session_id: str = "") -> Optional[str]:
        """Build the full proxy URL for this provider's gateway."""
        try:
            if self.auth_format == "customer_zone":
                return self._build_brd(credentials, sticky, session_id)
            elif self.auth_format == "token":
                return self._build_token(credentials, country, sticky, session_id)
            elif self.auth_format == "user_pass":
                return self._build_user_pass(credentials, country, sticky, session_id)
            return None
        except Exception:
            return None

    def _build_brd(self, cred: dict, sticky: bool, sid: str) -> str:
        """Build BrightData proxy URL using customer_id + zone."""
        cid = cred.get("customer_id", "")
        zone = cred.get("zone", "")
        pwd = cred.get("password", "")
        host = cred.get("host", self.default_host)
        port = cred.get("port", self.default_port)
        if not cid or not zone:
            return None
        # Format: brd-customer-{CUSTOMER}-zone-{ZONE}
        user = f"brd-customer-{cid}-zone-{zone}"
        if sticky and sid:
            user += f"-session-{sid}"
        return f"http://{user}:{pwd}@{host}:{port}"

    def _build_token(self, cred: dict, country: str, sticky: bool, sid: str) -> str:
        """Build token-based proxy URL (IPRoyal, Soax)."""
        token = cred.get("token", "")
        host = cred.get("host", self.default_host)
        port = cred.get("port", self.default_port)
        if not token:
            return None
        user = f"token-{token}"
        if sticky and sid:
            user += f"-session-{sid}"
        if country:
            user += f"-country-{country}"
        return f"http://{user}:@{host}:{port}"

    def _build_user_pass(self, cred: dict, country: str, sticky: bool, sid: str) -> str:
        """Build user:pass proxy URL (Oxylabs, Smartproxy, Webshare, etc.)."""
        user = cred.get("username", "")
        pwd = cred.get("password", "")
        host = cred.get("host", self.default_host)
        port = cred.get("port", self.default_port)
        if not user or not pwd:
            return None
        # Append session for sticky
        auth_user = user
        if sticky and sid:
            auth_user = f"{user}-session-{sid}"
        if country:
            # Most providers: country prefix on host
            if host.startswith("pr."):
                host = f"{country}-{host}"
            elif host.startswith("gate."):
                host = f"{country}-{host}"
        return f"http://{auth_user}:{pwd}@{host}:{port}"


# ── All Supported Providers ─────────────────────────────────────────────

PROVIDERS: List[RotatingProvider] = [
    RotatingProvider(
        name="BrightData",
        slug="brightdata",
        description="Bright Data (formerly Luminati) — 72M+ IPs worldwide. "
                     "Residential, datacenter, ISP, mobile.",
        docs_url="https://docs.brightdata.com/api-reference/proxy/rotate_ips",
        signup_url="https://brightdata.com/proxy-types",
        auth_format="customer_zone",
        default_host="brd.superproxy.io",
        default_port=22225,
    ),
    RotatingProvider(
        name="Oxylabs",
        slug="oxylabs",
        description="Oxylabs — 100M+ residential IPs, 99.9% uptime SLA. "
                     "Enterprise-grade proxy network.",
        docs_url="https://developer.oxylabs.io/",
        signup_url="https://oxylabs.io/products/residential-proxy-pool",
        auth_format="user_pass",
        default_host="pr.oxylabs.io",
        default_port=7777,
    ),
    RotatingProvider(
        name="Smartproxy",
        slug="smartproxy",
        description="Smartproxy — 40M+ residential IPs, affordable pricing, "
                     "good for small-medium scale.",
        docs_url="https://docs.smartproxy.com/",
        signup_url="https://smartproxy.com/proxies/residential-proxies",
        auth_format="user_pass",
        default_host="gate.smartproxy.com",
        default_port=7000,
    ),
    RotatingProvider(
        name="Webshare",
        slug="webshare",
        description="Webshare — 100K+ datacenter IPs, free tier available "
                     "(10 proxies). Good for testing.",
        docs_url="https://webshare.io/docs",
        signup_url="https://webshare.io/",
        auth_format="user_pass",
        default_host="p.webshare.io",
        default_port=80,
    ),
    RotatingProvider(
        name="IPRoyal",
        slug="iproyal",
        description="IPRoyal — 33M+ residential IPs, pay-per-IP model, "
                     "royal residential pool.",
        docs_url="https://iproyal.com/docs/residential-proxies",
        signup_url="https://iproyal.com/residential-proxies/",
        auth_format="token",
        default_host="residential.royalproxy.com",
        default_port=3100,
    ),
    RotatingProvider(
        name="Soax",
        slug="soax",
        description="Soax — 8M+ residential IPs, city-level targeting, "
                     "SOCKS5 support.",
        docs_url="https://soax.com/docs",
        signup_url="https://soax.com/residential-proxies",
        auth_format="token",
        default_host="proxy.soax.com",
        default_port=9132,
    ),
    RotatingProvider(
        name="NetNut",
        slug="netnut",
        description="NetNut — ISP-tier proxies integrated directly at the "
                     "backbone level. Very fast.",
        docs_url="https://netnut.io/docs/",
        signup_url="https://netnut.io/residential-proxies/",
        auth_format="user_pass",
        default_host="proxy.netnut.io",
        default_port=6060,
    ),
    RotatingProvider(
        name="Proxy-Cheap",
        slug="proxycheap",
        description="Proxy-Cheap — budget-friendly rotating proxies, "
                     "good for testing and small campaigns.",
        docs_url="https://proxy-cheap.com/docs/",
        signup_url="https://proxy-cheap.com/rotating-proxies/",
        auth_format="user_pass",
        default_host="proxy.proxy-cheap.com",
        default_port=3112,
        supports_geo=False,
    ),
    RotatingProvider(
        name="StormProxies",
        slug="stormproxies",
        description="StormProxies — affordable rotating proxies with "
                     "unlimited bandwidth options.",
        docs_url="https://stormproxies.com/help",
        signup_url="https://stormproxies.com/plans/rotating-proxies",
        auth_format="user_pass",
        default_host="proxy.stormproxies.com",
        default_port=5000,
        supports_geo=False,
    ),
]


# ── Provider Lookup ─────────────────────────────────────────────────────

_PROVIDER_MAP: Dict[str, RotatingProvider] = {p.slug: p for p in PROVIDERS}


def get_provider(slug: str) -> Optional[RotatingProvider]:
    """Get provider definition by slug (e.g. 'brightdata', 'oxylabs')."""
    return _PROVIDER_MAP.get(slug.lower())


def list_providers() -> List[Dict]:
    """Return list of all supported providers with basic info."""
    return [
        {
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "auth_format": p.auth_format,
            "supports_sticky": p.supports_sticky,
            "supports_geo": p.supports_geo,
            "default_host": p.default_host,
            "default_port": p.default_port,
        }
        for p in PROVIDERS
    ]


def list_provider_names() -> List[str]:
    """Return list of provider slugs."""
    return [p.slug for p in PROVIDERS]


# ── Proxy Gateway Connection ────────────────────────────────────────────

@dataclass
class RotatingProxySession:
    """
    Represents an active rotating proxy session.
    - Manages sticky session ID
    - Tracks usage stats
    - Handles reconnection
    """
    provider_slug: str
    proxy_url: str
    session_id: str = ""
    created_at: float = field(default_factory=time.time)
    requests_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_used: float = 0.0
    active: bool = True


class RotatingProxyManager:
    """
    Manages connections to rotating proxy providers.
    Supports multiple providers simultaneously.
    Thread-safe.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.lock = threading.RLock()
        self.sessions: Dict[str, RotatingProxySession] = {}
        self._session_counter = 0

    def get_proxy(self, provider_slug: str,
                  credentials: dict,
                  country: str = "",
                  sticky: bool = False) -> Optional[Dict[str, str]]:
        """
        Get a proxy dict from a rotating provider.

        Args:
            provider_slug: Provider identifier (e.g. 'brightdata', 'oxylabs')
            credentials: Dict with provider-specific credentials
            country: Optional country code (e.g. 'us', 'gb')
            sticky: If True, maintain same IP for this session

        Returns:
            Proxy dict for requests library, or None if failed.
            {"http": "http://...", "https": "http://..."}
        """
        provider = get_provider(provider_slug)
        if not provider:
            return None

        with self.lock:
            # Generate or reuse session ID for sticky sessions
            sid = ""
            if sticky:
                session_key = f"{provider_slug}:{country or 'any'}"
                if session_key in self.sessions:
                    existing = self.sessions[session_key]
                    if existing.active:
                        sid = existing.session_id
                        existing.requests_count += 1
                        existing.last_used = time.time()
                        # Return existing proxy URL
                        return {
                            "http": existing.proxy_url,
                            "https": existing.proxy_url,
                        }
                # Create new sticky session
                self._session_counter += 1
                sid = f"cpabot_{int(time.time())}_{self._session_counter}"

            # Build proxy URL
            proxy_url = provider.get_proxy_url(
                credentials, country=country,
                sticky=sticky, session_id=sid,
            )
            if not proxy_url:
                return None

            # Create session tracking
            if sticky:
                session_key = f"{provider_slug}:{country or 'any'}"
                self.sessions[session_key] = RotatingProxySession(
                    provider_slug=provider_slug,
                    proxy_url=proxy_url,
                    session_id=sid,
                    created_at=time.time(),
                )

            return {
                "http": proxy_url,
                "https": proxy_url,
            }

    def get_proxy_playwright(self, provider_slug: str,
                              credentials: dict,
                              country: str = "",
                              sticky: bool = False) -> Optional[dict]:
        """
        Get proxy config for Playwright from a rotating provider.

        Returns Playwright-compatible proxy dict, or None.
        Format: {"server": "scheme://host:port", "username": "...", "password": "..."}
        """
        proxy_dict = self.get_proxy(provider_slug, credentials, country, sticky)
        if not proxy_dict:
            return None

        http_url = proxy_dict.get("http", "")
        if not http_url:
            return None

        # Parse the proxy URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(http_url)
            if not parsed.hostname:
                return None

            # Build Playwright proxy config
            pw_config = {
                "server": f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port or 80}",
            }
            if parsed.username:
                pw_config["username"] = parsed.username
            if parsed.password:
                pw_config["password"] = parsed.password
            return pw_config
        except Exception:
            return None

    def test_connection(self, provider_slug: str,
                        credentials: dict,
                        country: str = "") -> Tuple[bool, float, str]:
        """
        Test connection to a rotating proxy provider.

        Returns:
            (success: bool, response_time: float, ip: str)
        """
        proxy_dict = self.get_proxy(provider_slug, credentials, country, sticky=False)
        if not proxy_dict:
            return False, 0, "Failed to build proxy URL"

        try:
            start = time.time()
            resp = requests.get(
                "http://httpbin.org/ip",
                proxies=proxy_dict,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                data = resp.json()
                ip = data.get("origin", "unknown")
                return True, elapsed, ip
            return False, elapsed, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, 0, str(e)[:80]

    def mark_failed(self, provider_slug: str, country: str = ""):
        """Mark the current session as failed and force a new IP on next request."""
        with self.lock:
            session_key = f"{provider_slug}:{country or 'any'}"
            if session_key in self.sessions:
                self.sessions[session_key].active = False
                self.sessions[session_key].fail_count += 1

    def mark_success(self, provider_slug: str, country: str = ""):
        """Mark the current session request as successful."""
        with self.lock:
            session_key = f"{provider_slug}:{country or 'any'}"
            if session_key in self.sessions:
                self.sessions[session_key].success_count += 1

    def rotate(self, provider_slug: str, country: str = ""):
        """
        Force rotate to a new IP by invalidating current sticky session.
        Only works with sticky sessions enabled.
        """
        with self.lock:
            session_key = f"{provider_slug}:{country or 'any'}"
            if session_key in self.sessions:
                self.sessions[session_key].active = False
                del self.sessions[session_key]

    def get_stats(self) -> Dict:
        """Get usage statistics for all active sessions."""
        with self.lock:
            return {
                "active_sessions": len(self.sessions),
                "sessions": [
                    {
                        "provider": s.provider_slug,
                        "requests": s.requests_count,
                        "success": s.success_count,
                        "fail": s.fail_count,
                        "age_seconds": int(time.time() - s.created_at),
                        "active": s.active,
                    }
                    for s in self.sessions.values()
                ],
            }


# ── Config Parsing ──────────────────────────────────────────────────────

def load_provider_config(config_data: dict) -> List[Dict]:
    """
    Load rotating proxy provider configurations from config dict.

    Expected format in config.json:
    {
        "proxies": {
            "rotating_providers": [
                {
                    "provider": "brightdata",
                    "enabled": true,
                    "credentials": { ... },
                    "country": "us",
                    "sticky_session": false,
                    "session_ttl_minutes": 10
                },
                ...
            ]
        }
    }

    Returns list of active provider configs.
    """
    providers_config = config_data.get("proxies", {}).get("rotating_providers", [])
    if not providers_config:
        return []

    active = []
    for cfg in providers_config:
        if cfg.get("enabled", False):
            provider_slug = cfg.get("provider", "").lower()
            provider = get_provider(provider_slug)
            if provider:
                active.append(cfg)
    return active


def get_available_providers_text() -> str:
    """Return formatted text of all available providers for CLI display."""
    lines = ["🌐 Rotating Proxy Providers", "═" * 56]
    for p in PROVIDERS:
        lines.append(f"  • [bold]{p.name}[/bold]")
        lines.append(f"    [dim]{p.description}[/dim]")
        lines.append(f"    Gateway: [green]{p.default_host}:{p.default_port}[/green]")
        geo = "🌍 Geo-targeting" if p.supports_geo else ""
        sticky = " 📎 Sticky" if p.supports_sticky else ""
        lines.append(f"    [dim]{geo}{sticky}[/dim]")
        lines.append("")
    return "\n".join(lines)


# ── Quick Test ──────────────────────────────────────────────────────────

def test_quick(provider_slug: str, **kwargs) -> str:
    """
    Quick one-shot test of a provider. Returns a human-readable result.

    Usage:
        from rotating_providers import test_quick
        result = test_quick("brightdata", credentials={...})
    """
    mgr = RotatingProxyManager()
    creds = kwargs.get("credentials", {})
    country = kwargs.get("country", "")
    success, elapsed, info = mgr.test_connection(provider_slug, creds, country)
    if success:
        return f"✅ {provider_slug}: Connected via {info} in {elapsed:.2f}s"
    else:
        return f"❌ {provider_slug}: Failed - {info}"


if __name__ == "__main__":
    # Standalone test
    print("🌐 Rotating Proxy Providers")
    print("=" * 56)
    for p in PROVIDERS:
        print(f"  • {p.name:15s} | {p.default_host:25s}:{p.default_port}")
    print()
    print(f"Total: {len(PROVIDERS)} providers")
