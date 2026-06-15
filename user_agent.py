"""
user_agent.py — Enhanced User Agent Manager

Provides realistic user agent rotation with:
- Desktop: Windows, macOS, Linux — Chrome, Firefox, Edge, Opera
- Mobile: iOS Safari, Android Chrome, Samsung Browser
- Mixed mode: random desktop/mobile per session
- No duplicate consecutive agents
- Agent version diversity (minor version variations)
"""

import random
from typing import List, Optional


class UserAgentManager:
    # ═════════════════════════════════════════════════════════════════════
    #  DESKTOP USER AGENTS (60 diverse agents)
    # ═════════════════════════════════════════════════════════════════════

    # -- Windows + Chrome (most common + locale diversity) --
    WIN_CHROME = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.60 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.105 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.129 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.185 Safari/537.36",
        # Locale-diverse
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36",  # en-GB
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36",  # de-DE
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36",  # fr-FR
    ]

    # -- Windows + Chrome (non-English locales) --
    WIN_CHROME_LOCALE = [
        # en-GB
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        # de-DE
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36",
        # fr-FR
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.60 Safari/537.36",
        # nl-NL
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    # -- Windows + Firefox --
    WIN_FIREFOX = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    ]

    # -- Windows + Edge (Chromium-based) --
    WIN_EDGE = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    ]

    # -- Windows + Opera --
    WIN_OPERA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/109.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/108.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/107.0.0.0",
    ]

    # -- Windows 11 specific --
    WIN11_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    ]

    # -- macOS + Safari --
    MAC_SAFARI = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    ]

    # -- macOS + Chrome --
    MAC_CHROME = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    # -- macOS + Firefox --
    MAC_FIREFOX = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) Gecko/20100101 Firefox/126.0",
    ]

    # -- Linux + Chrome --
    LINUX_CHROME = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    ]

    # -- Linux + Firefox --
    LINUX_FIREFOX = [
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    ]

    DESKTOP_AGENTS = (
        WIN_CHROME + WIN_FIREFOX + WIN_EDGE + WIN_OPERA +
        MAC_SAFARI + MAC_CHROME + MAC_FIREFOX +
        LINUX_CHROME + LINUX_FIREFOX
    )

    # ═════════════════════════════════════════════════════════════════════
    #  MOBILE USER AGENTS (20+ diverse agents)
    # ═════════════════════════════════════════════════════════════════════

    # -- iOS Safari (iPhone) --
    IOS_SAFARI = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    ]

    # -- iOS Chrome --
    IOS_CHROME = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/124.0.6367.71 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/125.0.6422.51 Mobile/15E148 Safari/604.1",
    ]

    # -- Android Chrome (Samsung, Pixel, Xiaomi, etc.) --
    ANDROID_CHROME = [
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6327.4 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6327.4 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-A536B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6327.4 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Xiaomi 14 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; OnePlus 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; M2012K11AG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6327.4 Mobile Safari/537.36",
    ]

    # -- Android Firefox --
    ANDROID_FIREFOX = [
        "Mozilla/5.0 (Android 14; Mobile; rv:126.0) Gecko/126.0 Firefox/126.0",
        "Mozilla/5.0 (Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0",
    ]

    # -- Samsung Internet Browser --
    ANDROID_SAMSUNG = [
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/122.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/23.0 Chrome/120.0.0.0 Mobile Safari/537.36",
    ]

    MOBILE_AGENTS = (
        IOS_SAFARI + IOS_CHROME +
        ANDROID_CHROME + ANDROID_FIREFOX + ANDROID_SAMSUNG
    )

    # ═════════════════════════════════════════════════════════════════════
    #  FULL AGENT CATEGORIES for weighted selection
    # ═════════════════════════════════════════════════════════════════════

    AGENT_CATEGORIES = {
        "win_chrome": {"agents": WIN_CHROME, "weight": 30},
        "win_firefox": {"agents": WIN_FIREFOX, "weight": 8},
        "win_edge": {"agents": WIN_EDGE, "weight": 6},
        "win_opera": {"agents": WIN_OPERA, "weight": 3},
        "mac_safari": {"agents": MAC_SAFARI, "weight": 10},
        "mac_chrome": {"agents": MAC_CHROME, "weight": 8},
        "mac_firefox": {"agents": MAC_FIREFOX, "weight": 3},
        "linux_chrome": {"agents": LINUX_CHROME, "weight": 4},
        "linux_firefox": {"agents": LINUX_FIREFOX, "weight": 2},
        "ios_safari": {"agents": IOS_SAFARI, "weight": 8},
        "ios_chrome": {"agents": IOS_CHROME, "weight": 3},
        "android_chrome": {"agents": ANDROID_CHROME, "weight": 10},
        "android_firefox": {"agents": ANDROID_FIREFOX, "weight": 2},
        "android_samsung": {"agents": ANDROID_SAMSUNG, "weight": 3},
    }

    def __init__(self, config):
        self.config = config
        self.last_ua: Optional[str] = None
        self._session_agent_pool: Optional[List[str]] = None

    def get(self, force_desktop: bool = False, force_mobile: bool = False) -> str:
        """
        Get a realistic User-Agent string.
        
        Args:
            force_desktop: Force desktop agent only
            force_mobile: Force mobile agent only
            
        Returns:
            A User-Agent string that won't repeat consecutively
        """
        if not self.config.rotate_ua:
            return self.DESKTOP_AGENTS[0]

        if force_desktop:
            pool = self.DESKTOP_AGENTS
        elif force_mobile:
            pool = self.MOBILE_AGENTS
        else:
            pool = self._get_pool()

        if not pool:
            pool = self.DESKTOP_AGENTS

        ua = random.choice(pool)
        while ua == self.last_ua and len(pool) > 1:
            ua = random.choice(pool)
        self.last_ua = ua
        return ua

    def get_with_accept_language(self, force_desktop: bool = False,
                                 force_mobile: bool = False) -> str:
        """
        Get a User-Agent with matching Accept-Language header hint.
        Returns just the UA string (caller sets Accept-Language separately).
        """
        return self.get(force_desktop=force_desktop, force_mobile=force_mobile)

    def _get_pool(self) -> List[str]:
        """Get agent pool based on device_type config.

        - "mobile": mobile agents only
        - "mixed": desktop + mobile (roughly 65/35 desktop bias)
        - "desktop": desktop agents only
        - default (any other value): weighted random selection across
          all categories using realistic market-share weights
        """
        device = self.config.device_type

        if device == "mobile":
            return self.MOBILE_AGENTS
        elif device == "mixed":
            # Roughly 65/35 desktop/mobile by duplicating desktop pool
            pool = list(self.DESKTOP_AGENTS) * 2 + list(self.MOBILE_AGENTS)
            random.shuffle(pool)
            return pool
        elif device == "desktop":
            return self.DESKTOP_AGENTS
        else:
            # Weighted random selection by category
            if self._session_agent_pool is None or random.random() < 0.05:
                self._session_agent_pool = self._build_weighted_pool()
            return self._session_agent_pool

    def _build_weighted_pool(self) -> List[str]:
        """Build a weighted agent pool for realistic traffic distribution."""
        pool = []
        for name, cat in self.AGENT_CATEGORIES.items():
            count = max(1, min(cat["weight"] // 2, len(cat["agents"])))
            pool.extend(random.sample(cat["agents"], count))
        random.shuffle(pool)
        return pool

    def get_random_os_match(self) -> dict:
        """
        Return OS/browser metadata matching the last UA for consistent fingerprinting.
        Used to keep platform/language consistent with User-Agent.
        """
        if not self.last_ua:
            return {"os": "windows", "browser": "chrome", "is_mobile": False}

        ua_lower = self.last_ua.lower()
        is_mobile = "mobile" in ua_lower or "android" in ua_lower
        is_iphone = "iphone" in ua_lower
        is_ipad = "ipad" in ua_lower

        if "windows nt" in ua_lower:
            return {"os": "windows", "browser": self._detect_browser(ua_lower), "is_mobile": False}
        elif "mac os x" in ua_lower and not is_mobile:
            return {"os": "macos", "browser": self._detect_browser(ua_lower), "is_mobile": False}
        elif "linux" in ua_lower and not "android" in ua_lower:
            return {"os": "linux", "browser": self._detect_browser(ua_lower), "is_mobile": False}
        elif "android" in ua_lower:
            return {"os": "android", "browser": self._detect_browser(ua_lower), "is_mobile": True}
        elif is_iphone or is_ipad:
            return {"os": "ios", "browser": self._detect_browser(ua_lower), "is_mobile": True}
        return {"os": "windows", "browser": "chrome", "is_mobile": False}

    @staticmethod
    def _detect_browser(ua_lower: str) -> str:
        """Detect browser type from user-agent string."""
        if "edg/" in ua_lower:
            return "edge"
        elif "opr/" in ua_lower or "opera" in ua_lower:
            return "opera"
        elif "firefox" in ua_lower:
            return "firefox"
        elif "crios" in ua_lower:
            return "chrome"
        elif "samsungbrowser" in ua_lower:
            return "samsung"
        elif "version/" in ua_lower and "safari" in ua_lower:
            return "safari"
        elif "chrome" in ua_lower:
            return "chrome"
        return "chrome"
