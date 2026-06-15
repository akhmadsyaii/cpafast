import json
import os
import random
import time
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from ad_detector import AdDetector
from config import Config
from logger import logger
from proxy_manager import Proxy

# Optional CAPTCHA solver (gracefully skip if no API key configured)
try:
    from captcha_solver import (
        detect_captcha_type, solve_captcha_on_page,
        inject_captcha_token, get_solver,
    )
    _HAS_CAPTCHA_SOLVER = True
except ImportError:
    _HAS_CAPTCHA_SOLVER = False


# ── Stealth JavaScript: masking automation fingerprints ──────────────────
STEALTH_JS = """
// ═════════════════════════════════════════════════════════════════════
//  Core Stealth JS — v3.0 (Phase 7: Maximum Realism)
// ═════════════════════════════════════════════════════════════════════

// === navigator.webdriver (WAJIB) ===
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// === navigator.userAgentData (Chrome 90+) — KRITIS ===
// Headless Chrome punya nilai berbeda di sini. Ini yang paling
// sering dicek anti-bot modern (Cloudflare, Akamai, DataDome).
Object.defineProperty(navigator, 'userAgentData', {
  get: () => ({
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not?A_Brand', version: '99' },
    ],
    mobile: false,
    platform: 'Windows',
    getHighEntropyValues: function(hints) {
      return Promise.resolve({
        platform: 'Windows',
        platformVersion: '15.0.0',
        architecture: 'x86',
        model: '',
        uaFullVersion: '124.0.6367.118',
        bitness: '64',
        fullVersionList: [
          { brand: 'Chromium', version: '124.0.6367.118' },
          { brand: 'Google Chrome', version: '124.0.6367.118' },
          { brand: 'Not?A_Brand', version: '99.0.0.0' },
        ],
        wow64: false,
        formFactor: 'Desktop',
      });
    },
    toJSON: function() {
      return {
        brands: [
          { brand: 'Chromium', version: '124' },
          { brand: 'Google Chrome', version: '124' },
          { brand: 'Not?A_Brand', version: '99' },
        ],
        mobile: false,
        platform: 'Windows',
      };
    },
  })
});

// === Chrome runtime (realistik) ===
window.chrome = {
  app: { isInstalled: false },
  runtime: {
    OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
    OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
    PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
    PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
    connect: function() { return {}; },
    connectNative: function() { return {}; },
    sendMessage: function() {},
    getManifest: function() { return { version: '124.0.6367.118' }; },
    id: 'nmmhkkegccagdldgiimedpiccmgmieda',
  },
  loadTimes: function() {
    return {
      requestTime: performance.now() / 1000,
      startLoadTime: performance.now() / 1000,
      commitLoadTime: performance.now() / 1000,
      finishDocumentLoadTime: performance.now() / 1000,
      finishLoadTime: performance.now() / 1000,
      firstPaintTime: performance.now() / 1000,
      firstPaintAfterLoadTime: performance.now() / 1000,
      navigationType: 'Reload',
      wasFetchedViaSpdy: false,
      wasNpnNegotiated: false,
      npnNegotiatedProtocol: 'http/1.1',
      wasAlternateProtocolAvailable: false,
      connectionInfo: 'http/1.1',
    };
  },
  csi: function() {
    return {
      onloadT: performance.now(),
      startE: performance.now(),
      pageT: Date.now(),
      tran: Math.floor(Math.random() * 100),
    };
  },
};

// === Permissions (realistik) ===
const _origPermissionsQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) => {
  const permissions = {
    'notifications': 'prompt',
    'geolocation': 'prompt',
    'midi': 'prompt',
    'camera': 'prompt',
    'microphone': 'prompt',
    'background-sync': 'granted',
    'clipboard-read': 'granted',
    'clipboard-write': 'granted',
    'persistent-storage': 'granted',
    'storage-access': 'granted',
    'local-fonts': 'prompt',
    'window-management': 'prompt',
  };
  return Promise.resolve({ state: permissions[params.name] || 'prompt' });
};

// === Plugins & MIME types (realistik) ===
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
  ]
});
Object.defineProperty(navigator, 'mimeTypes', {
  get: () => [
    { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: true },
    { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: true },
  ]
});

// == Languages (akan dioverride oleh fingerprint) ===
Object.defineProperty(navigator, 'languages', {
  get: () => ['en-US', 'en']
});

// === Performance & Resource Timing API (kritis!) ===
// Headless Chrome sering punya performance.memory yang nilainya beda.
// Anti-bot cek juga performance.getEntriesByType('navigation') untuk
// lihat type='prerender' yang cuma muncul di automated Chrome.
try {
  if (performance && performance.getEntriesByType) {
    const _origGetEntriesByType = performance.getEntriesByType.bind(performance);
    performance.getEntriesByType = function(type) {
      const entries = _origGetEntriesByType(type);
      if (type === 'navigation' && entries && entries.length > 0) {
        // Hapus type='prerender' yang cuma ada di automated Chrome
        entries[0].type = 'navigate';
      }
      return entries;
    };
  }
} catch(e) {}

// === Memory info (Real Chrome expose ini, headless nilainya beda) ===
if (performance && performance.memory) {
  Object.defineProperty(performance, 'memory', {
    get: () => ({
      jsHeapSizeLimit: 2172649472,
      totalJSHeapSize: Math.floor(Math.random() * 50000000) + 20000000,
      usedJSHeapSize: Math.floor(Math.random() * 30000000) + 10000000,
    })
  });
}

// === Spoof canvas fingerprint (subtle, variable noise) ===
const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
  const imageData = _origGetImageData.call(this, x, y, w, h);
  // Noise lebih subtle: hanya 1 dari 16 pixel, variasi -1 sampai 1
  const noiseStep = Math.floor(Math.random() * 8) + 12;  // 12-20 (variabel)
  for (let i = 0; i < imageData.data.length; i += noiseStep) {
    const delta = Math.floor(Math.random() * 3) - 1;  // -1, 0, atau 1
    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + delta));
  }
  return imageData;
};

// === Spoof WebGL fingerprint ===
const _getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {
  if (param === 37445) return 'Intel Inc.';  // UNMASKED_VENDOR_WEBGL
  if (param === 37446) return 'Intel Iris OpenGL Engine';  // UNMASKED_RENDERER_WEBGL
  return _getParameter.call(this, param);
};

// === Spoof WebGL2 ===
const _getParameter2 = WebGL2RenderingContext.prototype.getParameter;
if (_getParameter2) {
  WebGL2RenderingContext.prototype.getParameter = function(param) {
    if (param === 37445) return 'Intel Inc.';
    if (param === 37446) return 'Intel Iris OpenGL Engine';
    return _getParameter2.call(this, param);
  };
}

// === Spoof WEBGL_debug_renderer_info extension ===
// Anti-bot scripts sering cek extension ini buat dapet GPU asli
const _origGetExtension = WebGLRenderingContext.prototype.getExtension;
WebGLRenderingContext.prototype.getExtension = function(ext) {
  if (ext === 'WEBGL_debug_renderer_info') {
    return {
      UNMASKED_VENDOR_WEBGL: 37445,
      UNMASKED_RENDERER_WEBGL: 37446,
    };
  }
  return _origGetExtension.call(this, ext);
};

// === Override toString untuk anti-detection methods ===
const _origToString = Function.prototype.toString;
Function.prototype.toString = function() {
  if (this === navigator.webdriver || this === window.chrome.runtime) {
    return 'function () { [native code] }';
  }
  return _origToString.call(this);
};
"""

# ── CPA Popunder Trigger Script (passive — no synthetic events) ───────
CPA_POPUNDER_TRIGGER_JS = """
(() => {
  const results = [];

  // 1. Collect window.open URLs from inline scripts (passive extraction)
  const scripts = document.querySelectorAll('script:not([src])');
  scripts.forEach(script => {
    const content = script.textContent || '';
    const matches = content.match(/window\.open\s*\(\s*['"]([^'"]+)['"]/g);
    if (matches) {
      matches.forEach(m => {
        const url = m.match(/['"]([^'"]+)['"]/)?.[1];
        if (url && url.startsWith('http')) results.push(url);
      });
    }
  });

  // 2. Find data-* attributes containing ad URLs
  document.querySelectorAll('[data-href], [data-url], [data-redirect], [data-click-url], [data-popurl]').forEach(el => {
    const url = el.getAttribute('data-href') || el.getAttribute('data-url') ||
                el.getAttribute('data-redirect') || el.getAttribute('data-click-url') ||
                el.getAttribute('data-popurl');
    if (url && url.startsWith('http')) results.push(url);
  });

  return results;
})();
"""

# ── OS→Fingerprint consistency mapping ─────────────────────────────────
# Cocokkan locale, timezone, dan geolocation dengan User-Agent
_OS_FINGERPRINT_MAP: Dict[str, Dict] = {
    "windows": {
        "locales": [["en-US", "en"], ["en-US", "en"], ["en-GB", "en"], ["de-DE", "en"], ["fr-FR", "en"]],
        "timezones": ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Europe/Berlin"],
        "geos": [
            {"latitude": 40.7128, "longitude": -74.0060},   # NYC
            {"latitude": 41.8781, "longitude": -87.6298},   # Chicago
            {"latitude": 34.0522, "longitude": -118.2437},  # LA
            {"latitude": 51.5074, "longitude": -0.1278},    # London
            {"latitude": 52.5200, "longitude": 13.4050},    # Berlin
        ],
    },
    "macos": {
        "locales": [["en-US", "en"], ["en-US", "en"], ["en-GB", "en"], ["de-DE", "en"], ["fr-FR", "en"]],
        "timezones": ["America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "Europe/Berlin"],
        "geos": [
            {"latitude": 40.7128, "longitude": -74.0060},
            {"latitude": 37.7749, "longitude": -122.4194},  # San Francisco
            {"latitude": 51.5074, "longitude": -0.1278},
            {"latitude": 48.8566, "longitude": 2.3522},    # Paris
        ],
    },
    "linux": {
        "locales": [["en-US", "en"], ["en-GB", "en"], ["de-DE", "en"], ["fr-FR", "en"]],
        "timezones": ["Europe/London", "Europe/Berlin", "Europe/Paris", "America/New_York"],
        "geos": [
            {"latitude": 51.5074, "longitude": -0.1278},
            {"latitude": 52.5200, "longitude": 13.4050},
            {"latitude": 48.8566, "longitude": 2.3522},
            {"latitude": 40.7128, "longitude": -74.0060},
        ],
    },
    "android": {
        "locales": [["en-US", "en"], ["en-GB", "en"], ["ja-JP", "en"], ["ko-KR", "en"]],
        "timezones": ["Asia/Jakarta", "Asia/Bangkok", "Asia/Singapore", "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai"],
        "geos": [
            {"latitude": -6.2088, "longitude": 106.8456},   # Jakarta
            {"latitude": 13.7563, "longitude": 100.5018},   # Bangkok
            {"latitude": 1.3521, "longitude": 103.8198},    # Singapore
            {"latitude": 35.6762, "longitude": 139.6503},   # Tokyo
            {"latitude": 37.5665, "longitude": 126.9780},   # Seoul
        ],
    },
    "ios": {
        "locales": [["en-US", "en"], ["en-GB", "en"], ["ja-JP", "en"]],
        "timezones": ["America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "Asia/Tokyo"],
        "geos": [
            {"latitude": 40.7128, "longitude": -74.0060},
            {"latitude": 34.0522, "longitude": -118.2437},
            {"latitude": 51.5074, "longitude": -0.1278},
            {"latitude": 35.6762, "longitude": 139.6503},
        ],
    },
}

# ── Natural timing distributions — v3.0 ────────────────────────────────
# Real humans DON'T have uniform timing. Mereka pakai berbagai distribusi
# natural: truncated normal, log-normal, bimodal, Pareto.
#
# timing.py punya 4 distribusi + 1 fungsi PINTAR yang auto-pilih:
#   natural_delay(mean, min, max) → pilih distribusi terbaik berdasarkan mean
#   truncated_normal(mean, std, lo, hi) → cluster di sekitar mean
#   lognormal_delay(mean, max) → miring ke kanan (sering pendek, jarang panjang)
#   bimodal_delay(peak1, peak2) → dua kecepatan (cepet + lambat)
#   pareto_delay(scale, alpha) → heavy tail (beberapa SANGAT lambat)
#
# 🔬 Kenapa gak uniform?
#   random.randint(5, 30) → SEMUA nilai 5-30 punya probabilitas SAMA.
#   Ini TIDAK NATURAL. Real user: 60% visit 10-20 detik, 20% < 10,
#   20% > 20 detik. Distribusi normal/log-normal mencerminkan ini.
from timing import (
    natural_delay, natural_int,
    truncated_normal, truncated_normal_int,
    bimodal_delay, bimodal_int,
    pareto_int,
)


class VisitResult:
    def __init__(self):
        self.url: str = ""
        self.status: str = "failed"
        self.response_code: int = 0
        self.response_time: float = 0.0
        self.html: str = ""
        self.error: str = ""
        self.proxy: Optional[Proxy] = None
        self.popup_urls: list = []
        self.popups_captured: int = 0


class RequestsVisitor:
    def __init__(self, config: Config):
        self.config = config
        self._session: Optional[requests.Session] = None

    def _ensure_session(self, proxy_dict: Optional[dict] = None) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            a = requests.adapters.HTTPAdapter(
                max_retries=0, pool_connections=20, pool_maxsize=20
            )
            self._session.mount("http://", a)
            self._session.mount("https://", a)
        if proxy_dict:
            self._session.proxies.update(proxy_dict)
        return self._session

    def _build_headers(self, url: str, referrer: str = "") -> dict:
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if referrer:
            headers["Referer"] = referrer
        if random.random() < 0.3:
            headers["Cache-Control"] = "no-cache"
            headers["Pragma"] = "no-cache"
        return headers

    def visit(self, url: str, referrer: str = "",
              proxy_dict: Optional[dict] = None,
              on_scroll: Optional[Callable] = None,
              on_consent: Optional[Callable] = None,
              visit_duration: Tuple[int, int] = (5, 30)) -> VisitResult:
        result = VisitResult()
        result.url = url

        session = self._ensure_session(proxy_dict)
        headers = self._build_headers(url, referrer)
        max_retries = self.config.max_retries
        timeout = self.config.timeout

        for attempt in range(max_retries + 1):
            try:
                start = time.time()
                resp = session.get(
                    url, headers=headers, timeout=timeout, allow_redirects=True
                )
                elapsed = time.time() - start
                result.response_time = elapsed
                result.response_code = resp.status_code

                if resp.status_code == 200:
                    result.status = "success"
                    result.html = resp.text

                    if on_scroll:
                        on_scroll(resp.text)
                    if on_consent:
                        on_consent(session, resp.text, url)

                    dur = natural_int(
                        (visit_duration[0] + visit_duration[1]) / 2,
                        visit_duration[0], visit_duration[1],
                    )
                    for _ in range(dur):
                        time.sleep(1)
                    break
                elif resp.status_code in (403, 429):
                    result.error = f"Blocked ({resp.status_code})"
                    if attempt < max_retries:
                        time.sleep(
                            truncated_normal(
                                self.config.get("general", "retry_delay", default=1.0) * (attempt + 1) * 2,
                                0.5, 0.5, 10.0,
                            )
                        )
                        continue
                    else:
                        result.status = "failed"
                    break
                else:
                    result.error = f"HTTP {resp.status_code}"
                    result.status = "failed"
                    if attempt < max_retries and resp.status_code >= 500:
                        time.sleep(
                            truncated_normal(
                                self.config.get("general", "retry_delay", default=1.0) * (attempt + 1),
                                0.5, 0.5, 8.0,
                            )
                        )
                        continue
                    break

            except Exception as e:
                result.error = str(e)[:100]
                result.status = "failed"
                if attempt < max_retries:
                    time.sleep(
                        truncated_normal(
                            self.config.get("general", "retry_delay", default=1.0) * (attempt + 1),
                            0.5, 0.5, 8.0,
                        )
                    )
                    continue
                break

        return result

    def close(self):
        if self._session:
            self._session.close()
            self._session = None


class PlaywrightVisitor:
    def __init__(self, config: Config):
        self.config = config
        self._browser = None
        self._playwright = None
        self._popup_urls: list = []
        self._user_agent_mgr = None
        self._launch_args = [
            # ── Essential flags (Chrome tetap jalan) ────────────────
            "--no-sandbox",
            "--disable-dev-shm-usage",
            # ── Benign flags (real Chrome punya ini atau ga ngaruh) ─
            "--disable-background-networking",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-session-crashed-bubble",
            "--no-first-run",
            "--disable-default-apps",
            # ── ⚠️ FLAGS YANG DIHAPUS:
            #    --disable-blink-features=AutomationControlled
            #      → Flag ini justru DIDETEKSI anti-bot karena tidak
            #        ada di Chrome asli. Anti-bot cek startup command
            #        line dan lihat flag ini = langsung flagged.
            #    --disable-web-security
            #      → Red flag besar. Real Chrome gak pernah matiin ini.
            #    --disable-automation / --disable-blink-test-automation
            #      → Sama seperti di atas, gak ada di Chrome asli.
            #    --user-agent=...
            #      → Bentrok dengan user-agent di browser context.
            #        Anti-bot cek kesamaan launch arg UA vs navigator.UA.
            #        Kalau beda = flagged.
            #    --start-maximized
            #      → Bentrok dengan --window-size. Pilih salah satu.
            #
            # ── Rahasia: MAKIN SEDIKIT FLAGS = MAKIN AMAN ──────────
            #    Real user jalanin Chrome tanpa flags aneh-aneh.
            #    Tujuan kita: bikin Chrome kita terlihat seperti
            #    Chrome yang di-double-click dari desktop.
        ]
        # ── Random window-size flag (dipake nanti di _ensure_browser) ─
        self._random_window_size = f"--window-size={random.choice([1366, 1440, 1536, 1600, 1920])},{random.choice([768, 800, 864, 900, 1080])}"
        # ── Sticky UA: pake UA yang sama untuk beberapa visit ────────────
        self._current_ua = None
        self._ua_visits_remaining = 0
        # ── Session-level consistency: fingerprint tetap untuk beberapa visit ─
        self._session_fingerprint = None
        self._session_fp_remaining = 0
        self._sticky_viewport = None

    def _random_viewport(self) -> dict:
        """Get a random viewport size from 25+ realistic desktop/mobile sizes."""
        DESKTOP_VP = [
            (1366, 768), (1920, 1080), (1440, 900), (1536, 864),
            (1600, 900), (1280, 720), (1280, 800), (1792, 1120),
            (1920, 1200), (2048, 1152), (2560, 1440), (2560, 1600),
            (2560, 1080), (2880, 1620), (3024, 1964), (3456, 2234),
            (3840, 2160), (3440, 1440),
        ]
        weighted = DESKTOP_VP * 2 + [(1920, 1080)] * 4 + [(1366, 768)] * 3
        w, h = random.choice(weighted)
        return {"width": w, "height": h}

    def _ensure_browser(self):
        if self._browser:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")

        self._playwright = sync_playwright().start()

        # ── Deteksi Xvfb: kalau DISPLAY environment ada, jalankan dengan headed ──
        # Xvfb = virtual display, jadi Chrome berjalan seolah-olah ada monitor
        # Ini cara PALING EFEKTIF untuk menghindari headless detection
        xvfb_cfg = self.config.get("behavior", "xvfb", default={})
        use_xvfb = xvfb_cfg.get("enabled", True) and os.environ.get("DISPLAY") is not None

        if use_xvfb:
            # ── Xvfb mode: Chrome seperti REAL USER ──────────────────
            xvfb_args = list(self._launch_args)
            # Tanpa --window-size, pake --start-maximized biar full display
            xvfb_args.append("--start-maximized")
            self._browser = self._playwright.chromium.launch(
                headless=False,
                args=xvfb_args,
            )
            logger.info("[XVFB] Xvfb terdeteksi — Chrome berjalan dengan DISPLAY (headed mode)")
            logger.info("[XVFB] =====================================================")
            logger.info("[XVFB] Mode ini PALING SULIT dideteksi — seperti real user!")
            logger.info("[XVFB] =====================================================")
        else:
            # ── Headless mode: pake new headless Chrome 112+ ─────────
            headless_args = list(self._launch_args)
            headless_args.append(self._random_window_size)
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=headless_args + ["--headless=new"],  # Chrome 112+ new headless mode
            )
            if not hasattr(self.__class__, '_headless_warned'):
                self.__class__._headless_warned = True
                logger.info("[STEALTH] Chrome headless=new mode — lebih sulit dideteksi")
                logger.info("[STEALTH] Untuk hasil maksimal, jalankan dengan: xvfb-run python main.py tui")

    def _proxy_to_playwright(self, proxy: Proxy) -> Optional[dict]:
        if not proxy or not proxy.alive:
            return None
        scheme = proxy.scheme
        if scheme == "socks5h":
            scheme = "socks5"
        if scheme == "socks4":
            logger.warning(f"SOCKS4 not supported by Playwright, skipping proxy {proxy.host}:{proxy.port}")
            return None
        pw_proxy = {"server": f"{scheme}://{proxy.host}:{proxy.port}"}
        if proxy.auth:
            pw_proxy["username"] = proxy.auth[0]
            pw_proxy["password"] = proxy.auth[1]
        return pw_proxy

    def _os_from_ua(self, ua: str) -> str:
        """Detect OS from user-agent string for consistent fingerprinting."""
        ua_lower = ua.lower()
        if "windows nt" in ua_lower:
            return "windows"
        elif "mac os x" in ua_lower and "mobile" not in ua_lower:
            return "macos"
        elif "android" in ua_lower:
            return "android"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            return "ios"
        elif "linux" in ua_lower:
            return "linux"
        return "windows"

    def _browser_from_ua(self, ua: str) -> str:
        """Detect browser from user-agent string."""
        ua_lower = ua.lower()
        if "edg/" in ua_lower:
            return "edge"
        elif "opr/" in ua_lower or "opera" in ua_lower:
            return "chrome"  # Opera is Chromium-based
        elif "firefox" in ua_lower:
            return "firefox"
        elif "version/" in ua_lower and "safari" in ua_lower and "chrome" not in ua_lower:
            return "safari"
        elif "crios" in ua_lower:
            return "chrome"
        else:
            return "chrome"

    def _consistent_fingerprint(self, os_name: str) -> tuple:
        """
        Dapatkan locale, timezone, geolocation yang KONSISTEN dengan OS.
        Tidak merandom semuanya secara independen — semua cocok.
        """
        fp_map = _OS_FINGERPRINT_MAP.get(os_name, _OS_FINGERPRINT_MAP["windows"])
        # Pilih index random, lalu semua atribut pakai index yang SAMA
        idx = random.randint(0, min(len(fp_map["timezones"]), len(fp_map["geos"])) - 1)
        locale_list = random.choice(fp_map["locales"])
        timezone = fp_map["timezones"][idx % len(fp_map["timezones"])]
        geo = fp_map["geos"][idx % len(fp_map["geos"])]
        return locale_list[0], locale_list, timezone, geo

    def visit(self, url: str, referrer: str = "",
              proxy_dict: Optional[dict] = None,
              on_scroll: Optional[Callable] = None,
              on_consent: Optional[Callable] = None,
              visit_duration: Tuple[int, int] = (5, 30),
              proxy: Optional[Proxy] = None,
              on_page_ready: Optional[Callable] = None) -> VisitResult:
        result = VisitResult()
        result.url = url
        self._ensure_browser()
        self._popup_urls = []

        pw_proxy = self._proxy_to_playwright(proxy) if proxy else None

        # ── Dapatkan User-Agent dulu (sumber kebenaran fingerprint) ─────
        if self._user_agent_mgr is None:
            from user_agent import UserAgentManager
            self._user_agent_mgr = UserAgentManager(self.config)

        # ── Sticky UA: pake UA yang SAMA untuk beberapa visit ──────────
        # Real user gak ganti browser tiap kali buka halaman
        sticky_cfg = self.config.get("behavior", "sticky_ua", default={})
        if sticky_cfg.get("enabled", True):
            if self._current_ua is None or self._ua_visits_remaining <= 0:
                self._current_ua = self._user_agent_mgr.get()
                self._ua_visits_remaining = truncated_normal_int(
                    (sticky_cfg.get("min_visits", 5) + sticky_cfg.get("max_visits", 30)) / 2,
                    5, sticky_cfg.get("min_visits", 5), sticky_cfg.get("max_visits", 30),
                )
                logger.info(f"[STICKY UA] UA baru untuk {self._ua_visits_remaining} visit ke depan")
            self._ua_visits_remaining -= 1
            ua = self._current_ua
        else:
            ua = self._user_agent_mgr.get()

        # ── Deteksi OS & browser dari UA ────────────────────────────────
        fp_os = self._os_from_ua(ua)
        fp_browser = self._browser_from_ua(ua)

        # ── Session-level fingerprint consistency ────────────────────
        # Viewport, geolocation, timezone tetap SAMA untuk beberapa visit
        # Real user gak ganti layar & lokasi setiap 2 menit!
        stealth_config = self.config.get("stealth", default={})
        session_fp = self.config.get("behavior", "session_fingerprint", default={})

        if session_fp.get("enabled", True):
            if self._session_fingerprint is None or self._session_fp_remaining <= 0:
                # Generate fresh session fingerprint
                locale_str, locale_list, timezone_id, geo = self._consistent_fingerprint(fp_os)
                self._session_fingerprint = {
                    "locale": locale_str,
                    "locale_list": locale_list,
                    "timezone_id": timezone_id,
                    "geo": geo,
                }
                self._sticky_viewport = self._random_viewport()
                self._session_fp_remaining = truncated_normal_int(
                    (session_fp.get("min_visits", 3) + session_fp.get("max_visits", 15)) / 2,
                    3, session_fp.get("min_visits", 3), session_fp.get("max_visits", 15),
                )
                logger.info(f"[SESSION FP] Fingerprint baru untuk {self._session_fp_remaining} visit ke depan")
            self._session_fp_remaining -= 1
            locale_str = self._session_fingerprint["locale"]
            locale_list = self._session_fingerprint["locale_list"]
            timezone_id = self._session_fingerprint["timezone_id"]
            geo = self._session_fingerprint["geo"]
            viewport = self._sticky_viewport
        else:
            # Non-sticky mode: random setiap visit (seperti sebelumnya)
            locale_str, locale_list, timezone_id, geo = self._consistent_fingerprint(fp_os)
            viewport = self._random_viewport()

        context_kwargs = {
            "viewport": viewport,
            "locale": locale_str,
            "timezone_id": timezone_id,
            "java_script_enabled": True,
            "ignore_https_errors": True,
            "bypass_csp": True,
            "user_agent": ua,
        }

        if stealth_config.get("randomize_geolocation", True):
            context_kwargs["geolocation"] = geo
            context_kwargs["permissions"] = ["geolocation"]

        if pw_proxy:
            context_kwargs["proxy"] = pw_proxy

        context = self._browser.new_context(**context_kwargs)
        page = context.new_page()

        # ── Network throttle: simulasi koneksi lambat via route ──
        #    (tidak pakai CDP biar lebih aman dari deteksi)
        self._apply_network_throttle(page, context)

        # ── Inject stealth JS (dengan fingerprint yang cocok dengan UA) ──
        if stealth_config.get("enabled", True):
            use_fingerprint_db = stealth_config.get("use_fingerprint_db", True)
            use_enhanced_stealth = stealth_config.get("use_enhanced_stealth", True)

            if use_fingerprint_db:
                try:
                    from fingerprint_db import random_fingerprint
                    fp = random_fingerprint(device="mobile" if fp_os in ("android", "ios") else "desktop",
                                           browser=fp_browser,
                                           os_name=fp_os)
                    page.add_init_script(fp.to_init_script())
                    logger.info(f"[FINGERPRINT] Applied: {fp.name} (matched to UA OS: {fp_os})")
                except Exception:
                    try:
                        if use_enhanced_stealth:
                            page.add_init_script(self._get_enhanced_stealth_js())
                        else:
                            page.add_init_script(STEALTH_JS)
                    except Exception:
                        page.add_init_script(STEALTH_JS)
            elif use_enhanced_stealth:
                page.add_init_script(self._get_enhanced_stealth_js())
            else:
                page.add_init_script(STEALTH_JS)

        # ── CPA Popunder Capture ────────────────────────────────────────
        _captured_popups = []

        def _on_popup(new_page):
            try:
                new_page.wait_for_load_state("commit", timeout=3000)
                popup_url = new_page.url
                if popup_url and popup_url != "about:blank":
                    _captured_popups.append(popup_url)
                    self._popup_urls.append(popup_url)
            except Exception:
                try:
                    pu = new_page.url
                    if pu and pu != "about:blank":
                        _captured_popups.append(pu)
                        self._popup_urls.append(pu)
                except Exception:
                    pass
            finally:
                try:
                    new_page.close()
                except Exception:
                    pass

        context.on("page", _on_popup)

        try:
            if referrer:
                page.set_extra_http_headers({"Referer": referrer})

            start = time.time()
            resp = page.goto(url, wait_until="domcontentloaded",
                             timeout=self.config.timeout * 1000)
            elapsed = time.time() - start
            result.response_time = elapsed

            if resp:
                result.response_code = resp.status
                if resp.status == 200:
                    result.status = "success"

                    # ── Cookie Consent (wait 1s for dialogs to render) ──
                    page.wait_for_timeout(1000)
                    self._handle_consent_dialogs(page)

                    # ── Bounce simulation: 35% visit cuma bentar ──────────
                    # Real user sering bounce — buka, liat dikit, langsung cabut
                    bounce_cfg = self.config.get("behavior", "bounce", default={})
                    if bounce_cfg.get("enabled", True) and random.random() < bounce_cfg.get("probability", 0.35):
                        bounce_dur = natural_int(
                            (bounce_cfg.get("min_seconds", 3) + bounce_cfg.get("max_seconds", 15)) / 2,
                            bounce_cfg.get("min_seconds", 3),
                            bounce_cfg.get("max_seconds", 15),
                        )
                        # Quick scroll like real user who just glances
                        try:
                            page.evaluate(f"window.scrollBy(0, {natural_int(120, 30, 250)})")
                            page.wait_for_timeout(natural_int(800, 300, 2000))
                        except Exception:
                            pass
                        # Wait remaining bounce time (max with 0 to prevent negative timeout)
                        page.wait_for_timeout(max(0, bounce_dur * 1000 - 1500))
                        result.html = page.content()
                        logger.info(f"[BOUNCE] Visit cuma {bounce_dur}s — seperti real user")
                        page.close()
                        context.close()
                        return result

                    # ── Wait for CPA scripts to execute & open popups ────
                    for _ in range(5):
                        page.wait_for_timeout(1000)
                        if _captured_popups:
                            break

                    # ── Varied flow: tiap langkah punya probability sendiri ──
                    # Real user gak selalu ngelakuin SEMUA hal tiap visit
                    step_prob = self.config.get("behavior", "step_probabilities", default={})

                    # ── Simulate organic mouse movement (Bezier curves) ──
                    if random.random() < step_prob.get("mouse_movement", 0.7):
                        self._simulate_organic_mouse_movement(page)

                    # ── Inject CPA popunder trigger JS ─────────────────
                    if random.random() < step_prob.get("cpa_trigger", 0.8):
                        try:
                            popunder_urls = page.evaluate(CPA_POPUNDER_TRIGGER_JS)
                            if popunder_urls:
                                for pu_url in popunder_urls:
                                    if pu_url.startswith("called:"):
                                        logger.info(f"[STEALTH] Called popunder function: {pu_url}")
                        except Exception:
                            pass

                    # ── Exit-intent ──────────────────────────────────────
                    if random.random() < step_prob.get("exit_intent", 0.4):
                        self._simulate_exit_intent(page)

                    # ── Human emulation: reading pattern ────────────────
                    if (self.config.get("behavior", "simulate_reading", default=True)
                            and random.random() < step_prob.get("reading_pattern", 0.55)):
                        self._simulate_reading_pattern(page)

                    # ── Human emulation: tab switching ──────────────────
                    if (self.config.get("behavior", "simulate_tab_switching", default=False)
                            and random.random() < step_prob.get("tab_switching", 0.3)):
                        self._simulate_tab_switching(page, url)

                    # ── Natural scrolling (bimodal timing: fast & slow readers) ──
                    num_scrolls = bimodal_int(2, 6, 1, 2, 0.7, 1, 8)
                    for _ in range(num_scrolls):
                        scroll_amount = truncated_normal_int(350, 150, 50, 1000)
                        direction = 1 if random.random() < 0.85 else -1
                        page.evaluate(f"window.scrollBy(0, {scroll_amount * direction})")
                        # Natural pause: bimodal — 70% cepat, 30% lambat (lagi baca)
                        pause_ms = int(bimodal_delay(2.0, 6.0, 0.8, 2.0, 0.7, 0.5, 10.0) * 1000)
                        page.wait_for_timeout(pause_ms)
                        if random.random() < 0.25:
                            page.wait_for_timeout(int(bimodal_delay(3.0, 8.0, 1.0, 3.0, 0.6, 0.5, 12.0) * 1000))

                    dur_mean = (visit_duration[0] + visit_duration[1]) / 2
                    dur = natural_int(dur_mean, 3, visit_duration[1])

                    # ── Detect & solve CAPTCHA (optional) ──────────────────
                    cap_data = self._detect_and_solve_captcha(page, url)
                    if cap_data:
                        cap_result = cap_data.get("result")
                        if cap_result and cap_result.success:
                            logger.info(f"[CAPTCHA] Solved via {cap_result.service} ({cap_result.solve_time:.1f}s)")

                    # ── External link clicks ─────────────────────────────
                    if random.random() < step_prob.get("external_clicks", 0.6):
                        config_click_min = self.config.get("behavior", "link_click_min", default=0)
                        config_click_max = self.config.get("behavior", "link_click_max", default=2)
                        max_link_clicks = random.randint(config_click_min, config_click_max)
                        self._click_random_external_links(page, url, max_link_clicks)

                    # ── Click ads inside iframes ─────────────────────────
                    if random.random() < step_prob.get("iframe_ads", 0.5):
                        self._click_ads_in_iframes(page, url)

                    # ── Random distraction (ngopi, ke toilet, dll) ───────
                    # 25% chance tiap visit, kadang 2x biar makin natural
                    if self._simulate_distraction(page):
                        # Kalau udah distraction sekali, 15% chance distraction lagi
                        if random.random() < 0.15:
                            self._simulate_distraction(page)

                    # ── Remaining visit duration (natural pauses) ─────────
                    remaining = max(2, dur - 6)
                    for _ in range(remaining):
                        wait_ms = natural_int(1500, 500, 4000)
                        page.wait_for_timeout(wait_ms)
                        if random.random() < 0.25:
                            page.evaluate(f"window.scrollBy(0, {natural_int(130, 30, 300)})")

                    result.html = page.content()

                    # ── On-page ad click callback ───────────────────────
                    if on_page_ready:
                        try:
                            on_page_ready(page, context, result)
                        except Exception:
                            pass
                else:
                    result.status = "failed"
                    result.error = f"HTTP {resp.status}"
            else:
                result.status = "failed"
                result.error = "No response"

        except Exception as e:
            result.status = "failed"
            result.error = str(e)[:120]

        finally:
            result.popup_urls = list(_captured_popups)
            result.popups_captured = len(_captured_popups)
            page.close()
            context.close()

        return result

    # ─────────────────────────────────────────────────────────────────────
    # CAPTCHA Detection & Solving (optional — skip gracefully if no API)
    # ─────────────────────────────────────────────────────────────────────

    # Class-level flag: only warn about missing CAPTCHA API key once per session
    _captcha_warned_no_api = False

    def _detect_and_solve_captcha(self, page, page_url: str) -> Optional[dict]:
        """
        Detect CAPTCHA on the current page and solve it if a solver is available.

        Returns CaptchaResult if solved, None if:
        - No CAPTCHA detected
        - No solver configured
        - CAPTCHA solving is disabled in config
        - Module not available

        This never blocks the bot — always returns gracefully.
        Only warns about missing API key ONCE per session.
        """
        captcha_cfg = self.config.get("captcha", default={})
        if not captcha_cfg.get("enabled", False):
            return None
        if not _HAS_CAPTCHA_SOLVER:
            logger.warning("[CAPTCHA] captcha_solver.py not available")
            return None

        # Get solver from config (first service with API key)
        solvers_cfg = captcha_cfg.get("solver", [])
        solver = None
        solver_name = ""
        for scfg in solvers_cfg:
            s = get_solver(scfg)
            if s is not None:
                solver = s
                solver_name = scfg.get("service", "unknown")
                break

        if solver is None:
            if not PlaywrightVisitor._captcha_warned_no_api:
                logger.warning("[CAPTCHA] Enabled in config tapi tidak ada API key — otomatis dinonaktifkan")
                logger.warning("   ➤ Set captcha.solver[].api_key di config.json untuk mengaktifkan")
                PlaywrightVisitor._captcha_warned_no_api = True
            # Auto-disable in memory so we don't re-check every visit
            captcha_cfg["enabled"] = False
            return None

        # Detect CAPTCHA on page
        try:
            cap_type = detect_captcha_type(page)
            if not cap_type:
                return None  # No CAPTCHA on this page

            logger.info(f"[CAPTCHA] Detected {cap_type} on {page_url[:50]}...")

            # Solve
            result = solve_captcha_on_page(page, solver, page_url)
            if result is None or not result.success:
                logger.warning(f"[CAPTCHA] Solve failed: {result.error if result else 'unknown'}")
                return None

            # Inject the token
            success = inject_captcha_token(page, result.token, cap_type)
            if success:
                logger.success(f"[CAPTCHA] {cap_type} solved via {solver_name} ({result.solve_time:.1f}s)")
                # Wait a moment for the form to process
                page.wait_for_timeout(1000)
            else:
                logger.warning(f"[CAPTCHA] Token obtained but injection failed")

            return {"result": result, "type": cap_type}

        except Exception as e:
            logger.warning(f"[CAPTCHA] Error: {str(e)[:80]} — skipped")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # CPA Popunder trigger methods
    # ─────────────────────────────────────────────────────────────────────

    def _click_random_external_links(self, page, base_url, max_clicks=2):
        """Click external links to trigger CPA popunders.

        Strategy:
        1. Click real external links (strongest CPA trigger)
        2. If no external links, click any visible internal links
           (some CPA scripts attach handlers to ALL links)
        3. If zero links at all, click CPA ad containers directly

        Without click events, CPA networks see only impressions = 0 clicks.
        """
        clicked = 0
        try:
            base_netloc = urlparse(base_url).netloc

            # ── Collect ALL click targets ────────────────────────────────
            all_targets = page.evaluate("""(baseHost) => {
                const anchors = document.querySelectorAll('a[href]');
                const results = [];
                for (const a of anchors) {
                    try {
                        const url = new URL(a.href);
                        if (url.protocol.startsWith('javascript:') ||
                            url.protocol.startsWith('mailto:') ||
                            url.protocol.startsWith('tel:')) continue;
                        results.push({
                            href: a.href,
                            isExternal: url.hostname !== baseHost,
                            visible: a.offsetParent !== null,
                        });
                    } catch(e) {}
                }
                // External + visible first
                return results.sort((a,b) => {
                    const score = (x) => (x.isExternal ? 100 : 0) + (x.visible ? 10 : 0);
                    return score(b) - score(a);
                });
            }""", base_netloc)

            # ── Strategy 1: Click links (external first) ─────────────────
            if all_targets:
                random.shuffle(all_targets)
                targets_to_click = [t for t in all_targets if t['visible']][:max_clicks]
                for link in targets_to_click:
                    try:
                        href = link['href']
                        escaped = href.replace('"', '%22')
                        loc = page.locator(f'a[href="{escaped}"]').first

                        if loc.is_visible(timeout=1000):
                            loc.scroll_into_view_if_needed(timeout=2000)
                            # Natural pause before click (user mikir bentar)
                            page.wait_for_timeout(natural_int(450, 200, 1000))
                            loc.click(timeout=5000)
                            # Natural pause after click (loading + baca bentar)
                            page.wait_for_timeout(natural_int(3000, 1500, 6000))
                            clicked += 1
                            # Navigate back
                            try:
                                page.go_back(wait_until='domcontentloaded', timeout=10000)
                                page.wait_for_timeout(1000)
                            except Exception:
                                pass
                    except Exception:
                        continue
                return clicked

            # ── No clickable links — skip instead of forcing agresif clicks ──
            logger.info(f"[CPA] No external links found on page — skipping")
            return 0

        except Exception as e:
            logger.warning(f"[CPA] Link click error: {e}")
            return 0

    # _click_cpa_containers dihapus — terlalu agresif, mudah dideteksi

    def _simulate_organic_mouse_movement(self, page):
        """Simulate organic, human-like mouse movement across the page.

        Uses Bezier curves for realistic trajectories instead of straight
        lines. This avoids detection patterns used by anti-bot systems.

        NOTE: No random click at the end — clicking nowhere is suspicious.
        Only move the mouse naturally as if reading/scrolling.
        """
        try:
            viewport_size = page.evaluate("({w: window.innerWidth, h: window.innerHeight})")
            vw, vh = viewport_size["w"], viewport_size["h"]
            if vw < 100 or vh < 100:
                return

            # Move in Bezier-curved paths with varying speeds
            points = truncated_normal_int(4, 1, 2, 7)
            prev_x = random.randint(100, vw - 100)
            prev_y = random.randint(100, vh - 100)

            for _ in range(points):
                target_x = random.randint(50, vw - 50)
                target_y = random.randint(100, vh - 100)
                steps = truncated_normal_int(12, 4, 5, 25)

                # Use Bezier curve from previous position to target
                self._bezier_mouse_move(page, prev_x, prev_y, target_x, target_y, steps=steps)
                prev_x, prev_y = target_x, target_y

                page.wait_for_timeout(truncated_normal_int(60, 25, 20, 200))
        except Exception:
            pass

    def _simulate_exit_intent(self, page):
        """Simulate exit-intent mouse movement.

        Single subtle upward sweep — not multiple aggressive sweeps.
        Natural users don't rapidly move to the top multiple times.
        Only 50% chance to avoid pattern detection.
        """
        try:
            vs = page.evaluate("({w: window.innerWidth, h: window.innerHeight})")
            vw, vh = vs["w"], vs["h"]
            if vw < 200 or vh < 200:
                return

            if random.random() < 0.5:
                start_x = random.randint(100, vw - 200)
                start_y = random.randint(vh // 2, vh - 50)

                page.mouse.move(start_x, start_y, steps=8)
                page.wait_for_timeout(natural_int(500, 200, 1000))

                end_x = random.randint(start_x - 50, start_x + 50)
                end_y = random.randint(100, vh // 3)
                page.mouse.move(end_x, end_y, steps=10)
                page.wait_for_timeout(natural_int(1400, 600, 3000))

                page.mouse.move(end_x, random.randint(vh // 2, vh - 50), steps=12)
                page.wait_for_timeout(natural_int(900, 400, 2000))
        except Exception:
            pass

    def _click_ads_in_iframes(self, page, base_url):
        """Find and click ad elements inside iframes on the page.

        Two strategies:
        1. If the iframe src is from a known ad network (e.g. googleads,
           doubleclick, adsterra), navigate to it in a new context and
           click any links found (counts as ad click).
        2. If the iframe is same-origin, switch to its content frame
           and click visible external links inside.
        """
        clicked = 0
        try:
            base_netloc = urlparse(base_url).netloc
            AD_IFRAME_DOMAINS = [
                'googleads', 'doubleclick', 'googlesyndication',
                'adsterra', 'propellerads', 'popads', 'exoclick',
                'effectivecpm', 'profitableratecpm'
            ]

            # Get all iframes with their src attributes
            iframe_data = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('iframe[src]')).map(f => ({
                    src: f.src,
                    id: f.id || '',
                    className: f.className || ''
                }));
            }""")

            for ifd in iframe_data:
                src = ifd['src']
                if not src or src == 'about:blank':
                    if clicked >= 2:
                        break
                    continue
                is_ad_iframe = any(d in src.lower() for d in AD_IFRAME_DOMAINS)
                if is_ad_iframe:
                    try:
                        # Open the ad iframe URL directly - this registers as
                        # an ad view/click in the network's system
                        ad_page = page.context.new_page()
                        ad_page.goto(src, wait_until='domcontentloaded',
                                     timeout=10000)
                        ad_page.wait_for_timeout(1000)

                        # Try to click any link in the ad page
                        ad_links = ad_page.locator('a[href]').all()
                        for link in ad_links[:3]:
                            try:
                                href = link.get_attribute('href')
                                if href and not href.startswith(('javascript:', '#')):
                                    if link.is_visible(timeout=500):
                                        link.click(timeout=3000)
                                        ad_page.wait_for_timeout(1000)
                                        clicked += 1
                                        break
                            except Exception:
                                continue
                        ad_page.close()
                    except Exception:
                        try:
                            ad_page.close()
                        except Exception:
                            pass
                    continue

                # Strategy 2: Try same-origin iframe content frame
                try:
                    frame = page.frame_locator(f'iframe[src="{src}"]')
                    frame_links = frame.locator('a[href]').all()
                    for link in frame_links[:3]:
                        try:
                            href = link.get_attribute('href')
                            if href and not href.startswith(('javascript:', '#')):
                                parsed = urlparse(href)
                                if parsed.netloc and parsed.netloc != base_netloc:
                                    if link.is_visible(timeout=500):
                                        link.click(timeout=3000)
                                        page.wait_for_timeout(2000)
                                        clicked += 1
                                        break
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
        return clicked

    def _handle_consent_dialogs(self, page):
        consent_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('Accept Cookies')",
            "button:has-text('Allow')",
            "button:has-text('Allow All')",
            "button:has-text('I Agree')",
            "button:has-text('Got it')",
            "button:has-text('OK')",
            "a:has-text('Accept')",
            "a:has-text('Accept Cookies')",
            ".fc-cta-consent",
            ".cookie-consent-accept",
            "#cookie-accept",
            ".accept-cookies",
            "[aria-label*='cookie' i][aria-label*='accept' i]",
        ]
        for sel in consent_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000):
                    btn.click(timeout=2000)
                    page.wait_for_timeout(500)
                    break
            except Exception:
                continue

    def click_ad(self, url: str, referrer: str = "",
                 visit_duration: Tuple[int, int] = (60, 80),
                 proxy: Optional[Proxy] = None,
                 element_type: Optional[str] = None,
                 ad_network: Optional[str] = None) -> VisitResult:
        result = VisitResult()
        result.url = url
        self._ensure_browser()

        pw_proxy = self._proxy_to_playwright(proxy) if proxy else None
        context_kwargs = {
            "viewport": {
                "width": random.choice([1366, 1440, 1536, 1920]),
                "height": random.choice([768, 900, 864, 1080]),
            },
            "locale": "en-US",
            "java_script_enabled": True,
            "ignore_https_errors": True,
            "bypass_csp": True,
        }
        if pw_proxy:
            context_kwargs["proxy"] = pw_proxy
        context = self._browser.new_context(**context_kwargs)
        page = context.new_page()

        popup_urls: list = []

        def _on_new_page(new_pg):
            if new_pg != page:
                try:
                    new_pg.wait_for_load_state("commit", timeout=3000)
                    pu = new_pg.url
                    if pu and pu != "about:blank":
                        popup_urls.append(pu)
                except Exception:
                    try:
                        pu = new_pg.url
                        if pu and pu != "about:blank":
                            popup_urls.append(pu)
                    except Exception:
                        pass
                try:
                    new_pg.close()
                except Exception:
                    pass

        context.on("page", _on_new_page)

        try:
            if referrer:
                page.set_extra_http_headers({"Referer": referrer})

            start = time.time()

            if element_type == "iframe" and _is_iframe_url(url):
                resolved_url = self._resolve_iframe_click_url(
                    page, url, referrer, ad_network or ""
                )
                elapsed = time.time() - start
                result.response_time = elapsed
                if resolved_url:
                    start2 = time.time()
                    resp2 = page.goto(resolved_url,
                                      wait_until="domcontentloaded",
                                      timeout=self.config.timeout * 1000)
                    elapsed2 = time.time() - start2
                    result.response_time = (elapsed + elapsed2) / 2
                    if resp2:
                        result.response_code = resp2.status
                        if resp2.status in (200, 301, 302, 303, 307, 308):
                            result.status = "success"
                        else:
                            result.status = "failed"
                            result.error = f"HTTP {resp2.status}"
                    else:
                        result.status = "failed"
                        result.error = "No response"
                else:
                    result.status = "failed"
                    result.error = "No click URL found in iframe"

            elif element_type == "script_ad":
                try:
                    resp = page.goto(url, wait_until="domcontentloaded",
                                     timeout=self.config.timeout * 1000)
                    elapsed = time.time() - start
                    result.response_time = elapsed
                    if resp:
                        result.response_code = resp.status
                        if resp.status == 200:
                            result.status = "success"
                        else:
                            result.status = "failed"
                            result.error = f"HTTP {resp.status}"
                    else:
                        result.status = "success"
                        result.response_code = 200
                except Exception:
                    result.status = "success"
                    result.response_code = 200
                    result.response_time = time.time() - start

                if popup_urls:
                    result.url = popup_urls[0]
                    result.response_code = 200
                    result.status = "success"
                    result.popup_urls = list(popup_urls)
                    result.popups_captured = len(popup_urls)
            else:
                resp = page.goto(url, wait_until="domcontentloaded",
                                 timeout=self.config.timeout * 1000)
                elapsed = time.time() - start
                result.response_time = elapsed

                if resp:
                    result.response_code = resp.status
                    if resp.status in (200, 301, 302, 303, 307, 308):
                        result.status = "success"
                        # Simulate mouse interaction for CPA popunders
                        try:
                            page.mouse.move(random.randint(200, 1500), random.randint(200, 800), steps=10)
                            page.mouse.click(random.randint(400, 1200), random.randint(300, 600))
                            page.wait_for_timeout(500)
                        except Exception:
                            pass
                        for _ in range(truncated_normal_int(2, 0.7, 1, 3)):
                            page.evaluate(
                                f"window.scrollBy(0, {truncated_normal_int(250, 80, 50, 500)})"
                            )
                            page.wait_for_timeout(natural_int(1500, 800, 3000))
                        dur = natural_int(
                            (visit_duration[0] + visit_duration[1]) / 2,
                            visit_duration[0], visit_duration[1],
                        )
                        for _ in range(dur):
                            page.wait_for_timeout(1000)
                    else:
                        result.status = "failed"
                        result.error = f"HTTP {resp.status}"
                else:
                    result.status = "failed"
                    result.error = "No response"

            if popup_urls:
                result.url = popup_urls[0]
                result.response_code = 200
                result.status = "success"
                result.popup_urls = list(popup_urls)
                result.popups_captured = len(popup_urls)

        except Exception as e:
            result.status = "failed"
            result.error = str(e)[:120]
        finally:
            page.close()
            context.close()

        return result

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _resolve_iframe_click_url(self, page, iframe_url: str,
                                  referrer: str,
                                  ad_network: str) -> Optional[str]:
        try:
            if referrer:
                page.set_extra_http_headers({"Referer": referrer})

            resp = page.goto(iframe_url, wait_until="domcontentloaded",
                             timeout=self.config.timeout * 1000)
            if not resp or resp.status != 200:
                return None

            page.wait_for_timeout(1000)

            try:
                anchor = page.locator("a[href]").first
                href = anchor.get_attribute("href", timeout=1000)
                if href and not href.startswith("javascript"):
                    return href
            except Exception:
                pass

            found = page.evaluate("""() => {
                const a = document.querySelector('a[target="_blank"]');
                if (a && a.href && !a.href.startsWith('javascript:'))
                    return a.href;
                const all = document.querySelectorAll('a[href]');
                for (const el of all) {
                    if (el.href && !el.href.startsWith('javascript:') &&
                        !el.href.includes(window.location.hostname))
                        return el.href;
                }
                return '';
            }""")
            if found:
                return found

            onclick_url = page.evaluate("""() => {
                const els = document.querySelectorAll('[onclick]');
                for (const el of els) {
                    const fn = String(el.onclick || '');
                    const m = fn.match(/['"](https?:\\/\\/[^'"]+click[^'"]*|https?:\\/\\/[^'"]+ad[^'"]*)['"]/i);
                    if (m) return m[1];
                }
                return '';
            }""")
            if onclick_url:
                return onclick_url
        except Exception:
            pass
        return None

    def _resolve_script_click_url(self, page, script_url: str,
                                   ad_network: str) -> Optional[str]:
        try:
            page.goto(script_url, wait_until="domcontentloaded",
                      timeout=self.config.timeout * 1000)
            page.wait_for_timeout(2000)
        except Exception:
            pass
        return None

    def close(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._playwright = None

    def click_ad_element(self, page, ad_candidate, html: str, base_url: str) -> Optional[VisitResult]:
        """Click an ad element ON the current page using Playwright.

        Unlike click_ad() which opens a new page and navigates to the ad URL,
        this method finds the actual ad element in the current page's DOM and
        performs a real user-like click on it. This triggers the ad network's
        click-tracking JavaScript (which is attached via event listeners on
        the element), causing the click to be registered in the CPA dashboard.

        Why this matters:
          - CPA networks (Adsterra, ECPM, PropellerAds, etc.) attach click
            tracking via "click" event listeners on <a> / <img> elements.
          - Navigating to the ad URL directly bypasses these listeners.
          - Only clicking the element ON the publisher's page fires them.
        """
        detector = AdDetector()

        click_url = detector.get_ad_click_url(ad_candidate, html, base_url)
        selector = ad_candidate.selector

        result = VisitResult()
        result.url = click_url

        # ── Strategy 1: Click by CSS selector ───────────────────────────
        try:
            # Try various selector strategies to find the element
            element = None

            if selector and selector not in ("script", "iframe"):
                try:
                    element = page.locator(selector).first
                    if not element.is_visible(timeout=1000):
                        element = None
                except Exception:
                    element = None

            # If selector failed, try finding by URL match
            if element is None and click_url:
                # Try to find <a> with matching href
                try:
                    # URL could be relative, try partial match
                    url_part = click_url.split("?")[0].split("#")[0][:60]
                    sel = f'a[href*="{url_part}"]'
                    el = page.locator(sel).first
                    if el.is_visible(timeout=500):
                        element = el
                except Exception:
                    pass

            # If still nothing, try any visible external link
            if element is None:
                try:
                    el = page.locator("a[href^='http']:visible").first
                    if el.is_visible(timeout=500):
                        element = el
                except Exception:
                    pass

            if element is None:
                result.status = "failed"
                result.error = "Element not found on page"
                return result

            # ── Click the element ───────────────────────────────────────
            element.scroll_into_view_if_needed(timeout=3000)
            page.wait_for_timeout(500)

            start = time.time()
            element.click(timeout=5000)
            elapsed = time.time() - start
            result.response_time = elapsed

            # Wait briefly for any tracking redirect or popup (natural timing)
            page.wait_for_timeout(natural_int(2500, 1500, 4000))

            result.response_code = 200
            result.status = "success"

            return result

        except Exception as e:
            result.status = "failed"
            result.error = str(e)[:120]
            return result

    # ─────────────────────────────────────────────────────────────────────
    # Phase 3: Human Emulation Enhancement
    # ─────────────────────────────────────────────────────────────────────

    def _bezier_mouse_move(self, page, start_x: int, start_y: int,
                           end_x: int, end_y: int,
                           steps: int = 20,
                           jitter: float = 0.3) -> None:
        """
        Move mouse using a cubic Bezier curve with random control points.
        This produces organic, human-like mouse movement instead of
        straight-line movement which is easily detected by anti-bot systems.

        The curve uses 2 random control points to create:
        - Slight arcs (not perfectly straight)
        - Variable speed (faster in middle, slower at start/end)
        - Natural overshoot and correction
        """
        try:
            # Generate 2 random control points for cubic Bezier
            cp1_x = start_x + (end_x - start_x) * 0.3 + random.randint(-50, 50)
            cp1_y = start_y + (end_y - start_y) * 0.2 + random.randint(-30, 30)
            cp2_x = start_x + (end_x - start_x) * 0.7 + random.randint(-50, 50)
            cp2_y = start_y + (end_y - start_y) * 0.8 + random.randint(-30, 30)

            for i in range(steps + 1):
                t = i / steps
                # Cubic Bezier formula
                x = (1 - t) ** 3 * start_x + 3 * (1 - t) ** 2 * t * cp1_x + \
                    3 * (1 - t) * t ** 2 * cp2_x + t ** 3 * end_x
                y = (1 - t) ** 3 * start_y + 3 * (1 - t) ** 2 * t * cp1_y + \
                    3 * (1 - t) * t ** 2 * cp2_y + t ** 3 * end_y

                # Add small random jitter (human hand tremor)
                if jitter > 0:
                    x += random.uniform(-jitter, jitter)
                    y += random.uniform(-jitter, jitter)

                page.mouse.move(x, y, steps=1)

                # Variable delay: slower at edges (easing), faster in middle
                ease = 1 - abs(2 * t - 1) ** 2  # parabolic ease
                delay = truncated_normal(6, 2, 2, 12) * (0.3 + ease * 0.7)
                page.wait_for_timeout(int(delay))

        except Exception:
            # Fallback to straight line
            page.mouse.move(end_x, end_y, steps=steps)

    def _simulate_typing(self, page, selector: str, text: str) -> None:
        """
        Simulate human typing into an input field.
        Types character by character with variable speed:
        - Fast typists: 30-80ms per character
        - Slow typists: 80-200ms per character
        - Random pauses after punctuation (200-500ms)
        - Random mistakes and corrections (10% chance)
        """
        try:
            # Click the element first
            locator = page.locator(selector)
            if not locator.is_visible(timeout=2000):
                return

            # Click with bezier movement
            try:
                box = locator.bounding_box(timeout=1000)
                if box:
                    from_x = random.randint(100, 500)
                    from_y = random.randint(100, 500)
                    to_x = box["x"] + box["width"] / 2
                    to_y = box["y"] + box["height"] / 2
                    self._bezier_mouse_move(page, from_x, from_y, to_x, to_y, steps=15)
            except Exception:
                pass

            locator.click(timeout=3000)
            page.wait_for_timeout(natural_int(300, 150, 600))

            # Clear existing text
            locator.fill("")
            page.wait_for_timeout(natural_int(180, 80, 400))

            # Type character by character
            for i, char in enumerate(text):
                # Random typo (5% chance)
                make_typo = random.random() < 0.05 and i > 0 and i < len(text) - 1
                if make_typo:
                    # Type wrong character
                    wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                    page.keyboard.type(wrong_char)
                    page.wait_for_timeout(natural_int(120, 60, 250))
                    # Backspace to correct
                    page.keyboard.press("Backspace")
                    page.wait_for_timeout(natural_int(180, 80, 400))

                # Type the actual character
                page.keyboard.type(char)

                # Variable delay per character (truncated normal)
                if char in ".!?":
                    delay = truncated_normal_int(320, 80, 150, 600)
                elif char == " ":
                    delay = truncated_normal_int(70, 20, 30, 150)
                elif char.isupper():
                    delay = truncated_normal_int(95, 25, 40, 200)
                else:
                    delay = truncated_normal_int(55, 15, 20, 120)

                page.wait_for_timeout(delay)

        except Exception:
            # Fallback: just fill directly
            try:
                page.locator(selector).fill(text, timeout=2000)
            except Exception:
                pass

    def _simulate_tab_switching(self, page, base_url: str,
                                num_tabs: int = 2) -> List[str]:
        """
        Simulate natural tab-switching behavior:
        1. Open additional tabs
        2. Switch between tabs (like a real user browsing)
        3. Close extra tabs

        Returns list of URLs visited in additional tabs.
        """
        opened_urls = []
        try:
            context = page.context
            num_new = truncated_normal_int(1.5, 0.7, 1, min(num_tabs, 3))

            for _ in range(num_new):
                new_page = context.new_page()
                # Navigate to a common site (social media, search, etc.)
                sites = [
                    "https://google.com",
                    "https://facebook.com",
                    "https://twitter.com",
                    "https://youtube.com",
                    "https://reddit.com",
                    "https://instagram.com",
                ]
                target = random.choice(sites)
                try:
                    new_page.goto(target, wait_until="domcontentloaded",
                                 timeout=10000)
                    opened_urls.append(target)
                    # Do a quick scroll on the new tab
                    for _ in range(natural_int(2, 1, 4)):
                        new_page.evaluate(f"window.scrollBy(0, {truncated_normal_int(200, 80, 50, 500)})")
                        new_page.wait_for_timeout(natural_int(800, 300, 2000))
                except Exception:
                    pass

                # Switch back to original page
                page.bring_to_front()
                page.wait_for_timeout(natural_int(1000, 400, 2500))

            # Close extra tabs
            for p in context.pages:
                if p != page:
                    try:
                        p.close()
                    except Exception:
                        pass

        except Exception:
            pass

        return opened_urls

    def _apply_network_throttle(self, page, context):
        """
        Simulasi koneksi internet lambat (3G/4G) via page.route (bukan CDP).

        Latency sekarang pakai truncated normal — tidak uniform.
        Kebanyakan nilai di sekitar 60ms, kadang 120ms (lebih realistik).
        """
        try:
            throttle_cfg = self.config.get("behavior", "network_throttle", default={})
            if not throttle_cfg.get("enabled", True):
                return
            if random.random() > throttle_cfg.get("probability", 0.15):
                return

            latency_ms = int(truncated_normal(60, 20, 20, 150))
            logger.info(f"[THROTTLE] Simulasi latency {latency_ms}ms via route")

            def _throttle(route):
                time.sleep(latency_ms / 1000.0)
                route.continue_()

            page.route(("**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,css}"), _throttle)

        except Exception:
            pass

    def _simulate_distraction(self, page) -> bool:
        """
        Simulasi user yang lagi distractionsi — ngopi, ke toilet, scroll HP, dll.

        Random long pause (1-10 menit) seperti real user yang lagi
        sibuk bentar. Ini penting karena bot yang tanpa jeda sama
        sekali itu tidak natural — real user pasti kadang ngopi,
        ngecek HP, atau ngobrol bentar.

        Returns:
            True jika distraction terjadi, False jika skip
        """
        try:
            dist_cfg = self.config.get("behavior", "distraction", default={})
            if not dist_cfg.get("enabled", True):
                return False

            probability = dist_cfg.get("probability", 0.25)
            if random.random() > probability:
                return False

            mean_sec = dist_cfg.get("mean_seconds", 180)
            max_sec = dist_cfg.get("max_seconds", 600)

            # Pilih alasan distraction secara acak (biar lognya lucu)
            reasons = [
                "☕ Ngopi bentar...",
                "🚬 Ke luar bentar...",
                "🚽 Ke kamar mandi...",
                "📱 Ngecek HP...",
                "🍕 Makan cemilan...",
                "💬 Balas chat...",
                "🛋️  Ngambil minum...",
                "😴 Microsleep...",
                "🐱 Ngusir kucing...",
                "📺 Nonton video bentar...",
                "🎵 Ganti lagu...",
                "☎️  Angkat telpon...",
            ]
            reason = random.choice(reasons)

            # Durasi pake Pareto — kebanyakan pendek, tapi ada yang panjang banget
            delay_sec = pareto_int(mean_sec * 0.4, 2.0, 30, int(max_sec))
            delay_min = delay_sec / 60.0

            logger.info(f"[DISTRACTION] {reason} ({delay_min:.1f} menit)...")

            # Selama distraction, kadang-kadang gerakin mouse dikit
            elapsed = 0
            chunk = min(30.0, delay_sec / 3)
            while elapsed < delay_sec:
                wait = min(chunk, delay_sec - elapsed)
                page.wait_for_timeout(int(wait * 1000))
                elapsed += wait

                # Tiap ~30 detik, gerakin mouse sedikit (user masih "ada")
                if random.random() < 0.3 and elapsed < delay_sec * 0.8:
                    try:
                        vs = page.evaluate("({w: window.innerWidth, h: window.innerHeight})")
                        page.mouse.move(
                            truncated_normal_int(vs["w"] / 2, vs["w"] / 4, 50, vs["w"] - 50),
                            truncated_normal_int(vs["h"] / 2, vs["h"] / 4, 100, vs["h"] - 100),
                            steps=truncated_normal_int(5, 2, 2, 10)
                        )
                        page.wait_for_timeout(natural_int(400, 150, 1000))
                    except Exception:
                        pass

            logger.info(f"[DISTRACTION] Kembali! (\ud83d\udd52 {delay_min:.1f} menit)")

            # Setelah distraction, scroll sedikit kayak user nyari posisi baca lagi
            try:
                scroll_px = truncated_normal_int(50, 100, -300, 400)
                page.evaluate(f"window.scrollBy(0, {scroll_px})")
                page.wait_for_timeout(natural_int(800, 300, 2000))
            except Exception:
                pass

            return True

        except Exception:
            return False

    def _simulate_reading_pattern(self, page) -> None:
        """
        Simulate realistic reading patterns:
        - Select text as if reading
        - Copy text occasionally
        - Hover over links
        - Right-click for context menu (then dismiss)
        """
        try:
            # Find text paragraphs
            paragraphs = page.evaluate("""() => {
                const paragraphs = [];
                document.querySelectorAll('p, article p, .content p, .post p').forEach(p => {
                    const text = p.textContent.trim();
                    if (text.length > 50 && p.offsetParent !== null) {
                        paragraphs.push({
                            text: text.substring(0, 100),
                            x: p.getBoundingClientRect().x,
                            y: p.getBoundingClientRect().y,
                            width: p.getBoundingClientRect().width,
                            height: p.getBoundingClientRect().height
                        });
                    }
                });
                return paragraphs.slice(0, 5);
            }""")

            if not paragraphs:
                return

            # Select random paragraph and simulate reading
            para = random.choice(paragraphs)
            if para.get("height", 0) > 0:
                mid_x = para["x"] + para["width"] / 2
                mid_y = para["y"] + para["height"] / 2
                page.mouse.move(mid_x, mid_y, steps=5)
                page.wait_for_timeout(natural_int(800, 300, 2000))

            # Occasionally select text (like reading with cursor)
            if random.random() < 0.3 and paragraphs:
                para = random.choice(paragraphs)
                try:
                    page.mouse.click(para["x"] + 20, para["y"] + 5, click_count=2)
                    page.wait_for_timeout(natural_int(300, 150, 600))
                    for _ in range(natural_int(3, 2, 5)):
                        page.mouse.move(
                            truncated_normal_int(para["x"] + para["width"] / 2, para["width"] / 4,
                                                  int(para["x"]), int(para["x"] + para["width"])),
                            truncated_normal_int(para["y"] + para["height"] / 2, para["height"] / 4,
                                                  int(para["y"]), int(para["y"] + para["height"])),
                            steps=3
                        )
                        page.wait_for_timeout(natural_int(180, 80, 400))
                except Exception:
                    pass

            # Occasionally copy text (Ctrl+C)
            if random.random() < 0.15:
                try:
                    page.keyboard.press("Control+c")
                    page.wait_for_timeout(natural_int(500, 200, 1000))
                except Exception:
                    pass

            # Hover over a link
            try:
                links = page.locator("a[href^='http']")
                count = links.count()
                if count > 0:
                    idx = min(count - 1, truncated_normal_int(2, 1.5, 0, min(count - 1, 5)))
                    link = links.nth(idx)
                    if link.is_visible(timeout=500):
                        box = link.bounding_box(timeout=500)
                        if box:
                            page.mouse.move(
                                box["x"] + box["width"] / 2,
                                box["y"] + box["height"] / 2,
                                steps=10
                            )
                            page.wait_for_timeout(natural_int(1500, 800, 3000))
            except Exception:
                pass

            # Occasionally right-click (context menu) then dismiss
            if random.random() < 0.1:
                try:
                    page.mouse.click(
                        truncated_normal_int(500, 200, 100, 900),
                        truncated_normal_int(400, 150, 100, 700),
                        button="right"
                    )
                    page.wait_for_timeout(natural_int(500, 200, 900))
                    page.mouse.click(
                        truncated_normal_int(200, 60, 50, 400),
                        truncated_normal_int(150, 40, 50, 300),
                    )
                    page.wait_for_timeout(natural_int(300, 150, 600))
                except Exception:
                    pass

        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Phase 6: Headless Detection Bypass Enhancement
    # ─────────────────────────────────────────────────────────────────────

    def _get_enhanced_stealth_js(self) -> str:
        """
        Generate enhanced stealth JavaScript that patches more
        headless detection vectors than the basic STEALTH_JS.

        Additional patches:
        - navigator.connection (network info)
        - navigator.deviceMemory
        - navigator.hardwareConcurrency
        - Screen orientation
        - MediaDevices (webcam/mic presence)
        - Battery API
        - Service worker detection
        - PDF viewer enabled
        - Fullscreen API
        - Presentation API
        - Navigator credentials
        - Speech recognition
        - Gamepad API
        - Virtual keyboard
        - Web Bluetooth
        - Web USB
        - Web Serial
        - WebGPU
        - File System Access API
        - Window management API
        - Detect language
        - Do Not Track
        """
        return """
// ═════════════════════════════════════════════════════════════════════
//  Enhanced Stealth JS — v3.0 Headless Detection Bypass
// ═════════════════════════════════════════════════════════════════════

// ── CORE OVERRIDES ───────────────────────────────────────────────────
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, '__webdriver', { get: () => undefined });
Object.defineProperty(navigator, '__selenium', { get: () => undefined });
Object.defineProperty(navigator, '__driver_evaluate', { get: () => undefined });
Object.defineProperty(navigator, '__fxdriver_unwrapped', { get: () => undefined });

// ── CRITICAL: navigator.userAgentData (Chrome 90+) ───────────────────
// Anti-bot modern (Cloudflare Turnstile, DataDome, Akamai) cek ini
Object.defineProperty(navigator, 'userAgentData', {
  get: () => ({
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not?A_Brand', version: '99' },
    ],
    mobile: false,
    platform: 'Windows',
    getHighEntropyValues: function(hints) {
      return Promise.resolve({
        platform: 'Windows',
        platformVersion: '15.0.0',
        architecture: 'x86',
        model: '',
        uaFullVersion: '124.0.6367.118',
        bitness: '64',
        fullVersionList: [
          { brand: 'Chromium', version: '124.0.6367.118' },
          { brand: 'Google Chrome', version: '124.0.6367.118' },
          { brand: 'Not?A_Brand', version: '99.0.0.0' },
        ],
        wow64: false,
        formFactor: 'Desktop',
      });
    },
    toJSON: function() {
      return {
        brands: [
          { brand: 'Chromium', version: '124' },
          { brand: 'Google Chrome', version: '124' },
          { brand: 'Not?A_Brand', version: '99' },
        ],
        mobile: false,
        platform: 'Windows',
      };
    },
  })
});

// ── CHROME RUNTIME (realistik — matches real Chrome) ─────────────────
window.chrome = {
  app: {
    isInstalled: false,
    InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
    RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
  },
  runtime: {
    OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
    OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
    PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
    PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
    PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
    RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
    connect: function() { return {}; },
    connectNative: function() { return {}; },
    sendMessage: function() {},
    getManifest: function() { return { version: '124.0.6367.118' }; },
    id: 'nmmhkkegccagdldgiimedpiccmgmieda',
  },
  loadTimes: function() {
    return {
      requestTime: performance.now() / 1000,
      startLoadTime: performance.now() / 1000,
      commitLoadTime: performance.now() / 1000,
      finishDocumentLoadTime: performance.now() / 1000,
      finishLoadTime: performance.now() / 1000,
      firstPaintTime: performance.now() / 1000,
      firstPaintAfterLoadTime: performance.now() / 1000,
      navigationType: 'Reload',
      wasFetchedViaSpdy: false,
      wasNpnNegotiated: false,
      npnNegotiatedProtocol: 'http/1.1',
      wasAlternateProtocolAvailable: false,
      connectionInfo: 'http/1.1'
    };
  },
  csi: function() {
    return {
      onloadT: performance.now(),
      startE: performance.now(),
      pageT: Date.now(),
      tran: Math.floor(Math.random() * 100)
    };
  }
};

// ── PERMISSIONS (realistik — response sesuai Chrome asli) ────────────
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) => {
  const permissions = {
    'notifications': 'prompt',
    'geolocation': 'prompt',
    'midi': 'prompt',
    'midi-sysex': 'prompt',
    'camera': 'prompt',
    'microphone': 'prompt',
    'background-sync': 'granted',
    'ambient-light-sensor': 'denied',
    'accelerometer': 'denied',
    'gyroscope': 'denied',
    'magnetometer': 'denied',
    'clipboard-read': 'granted',
    'clipboard-write': 'granted',
    'payment-handler': 'prompt',
    'persistent-storage': 'granted',
    'storage-access': 'granted',
    'display-capture': 'prompt',
    'top-level-storage-access': 'prompt',
    'local-fonts': 'prompt',
  };
  return Promise.resolve({ state: permissions[params.name] || 'prompt' });
};

// ── PLUGINS & MIME TYPES (realistik) ─────────────────────────────────
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
  ]
});
Object.defineProperty(navigator, 'mimeTypes', {
  get: () => [
    { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: true },
    { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: true },
  ]
});

// ── NAVIGATOR EXTRAS ─────────────────────────────────────────────────
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
Object.defineProperty(navigator, 'pdfViewerEnabled', { get: () => true });
Object.defineProperty(navigator, 'cookieEnabled', { get: () => true });
Object.defineProperty(navigator, 'onLine', { get: () => true });

// ── PERFORMANCE & RESOURCE TIMING (kritis untuk Cloudflare) ─────────
try {
  if (performance && performance.getEntriesByType) {
    const _origGetEntriesByType = performance.getEntriesByType.bind(performance);
    performance.getEntriesByType = function(type) {
      const entries = _origGetEntriesByType(type);
      if (type === 'navigation' && entries && entries.length > 0) {
        // Hapus 'prerender' type yang cuma muncul di automated Chrome
        // Anti-bot modern cek ini!
        Object.defineProperty(entries[0], 'type', { get: () => 'navigate' });
      }
      return entries;
    };
  }
} catch(e) {}

// ── PERFORMANCE.MEMORY (real Chrome expose ini, headless nilainya beda) ─
if (performance && performance.memory) {
  Object.defineProperty(performance, 'memory', {
    get: () => ({
      jsHeapSizeLimit: 2172649472,
      totalJSHeapSize: Math.floor(Math.random() * 50000000) + 20000000,
      usedJSHeapSize: Math.floor(Math.random() * 30000000) + 10000000,
    })
  });
}

// ── NETWORK INFORMATION ──────────────────────────────────────────────
try {
  if (navigator.connection) {
    Object.defineProperty(navigator.connection, 'effectiveType', { get: () => '4g' });
    Object.defineProperty(navigator.connection, 'rtt', { get: () => Math.floor(Math.random() * 50) + 50 });
    Object.defineProperty(navigator.connection, 'downlink', { get: () => Math.random() * 10 + 5 });
    Object.defineProperty(navigator.connection, 'saveData', { get: () => false });
  }
} catch(e) {}

// ── SCREEN ───────────────────────────────────────────────────────────
Object.defineProperty(screen, 'isExtended', { get: () => Math.random() > 0.7 });
if (screen.orientation) {
  Object.defineProperty(screen.orientation, 'type', { get: () => 'landscape-primary' });
  Object.defineProperty(screen.orientation, 'angle', { get: () => 0 });
}

// ── WINDOW SCHEDULER ─────────────────────────────────────────────────
Object.defineProperty(window, 'scheduler', { get: () => ({
  postTask: function() { return Promise.resolve(); },
  yield: function() { return Promise.resolve(); }
}) });

// ── WEBGL SPOOFING (lengkap dengan WebGL2) ───────────────────────────
const _getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {
  if (param === 37445) return 'Google Inc. (Intel)';
  if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)';
  if (param === 7936) return 'WebKit';
  if (param === 7937) return 'WebKit WebGL';
  if (param === 3415) return 1;
  if (param === 3414) return 1;
  if (param === 34047) return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
  return _getParameter.call(this, param);
};

// ── WebGL2 ───────────────────────────────────────────────────────────
const _getParameter2 = WebGL2RenderingContext.prototype.getParameter;
if (_getParameter2) {
  WebGL2RenderingContext.prototype.getParameter = function(param) {
    if (param === 37445) return 'Google Inc. (Intel)';
    if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    if (param === 7936) return 'WebKit';
    if (param === 7937) return 'WebKit WebGL';
    if (param === 3415) return 1;
    if (param === 3414) return 2;
    if (param === 34047) return 'WebGL 2.0 (OpenGL ES 3.0 Chromium)';
    return _getParameter2.call(this, param);
  };
}

// ── WEBGL_debug_renderer_info EXTENSION SPOOF ────────────────────────
// Anti-bot scripts sering cek extension ini buat dapet GPU asli
const _origGetExtension = WebGLRenderingContext.prototype.getExtension;
WebGLRenderingContext.prototype.getExtension = function(ext) {
  if (ext === 'WEBGL_debug_renderer_info') {
    return {
      UNMASKED_VENDOR_WEBGL: 37445,
      UNMASKED_RENDERER_WEBGL: 37446,
    };
  }
  return _origGetExtension.call(this, ext);
};

// ── CANVAS NOISE (subtle, variabel) ─────────────────────────────────
const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
  const imageData = _origGetImageData.call(this, x, y, w, h);
  const noiseStep = Math.floor(Math.random() * 8) + 12;
  for (let i = 0; i < imageData.data.length; i += noiseStep) {
    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (Math.floor(Math.random() * 3) - 1)));
  }
  return imageData;
};

// ── AUDIO CONTEXT SPOOF ──────────────────────────────────────────────
const _origAudioContext = window.AudioContext || window.webkitAudioContext;
if (_origAudioContext) {
  AudioContext.prototype.getChannelData = function() { return new Float32Array(1024); };
  const _origCreateAnalyser = AudioContext.prototype.createAnalyser;
  AudioContext.prototype.createAnalyser = function() {
    const a = _origCreateAnalyser.call(this);
    a.fftSize = 2048;
    a.frequencyBinCount = 1024;
    a.minDecibels = -100;
    a.maxDecibels = -30;
    a.smoothingTimeConstant = 0.8;
    return a;
  };
}

// ── MEDIADEVICES ─────────────────────────────────────────────────────
if (navigator.mediaDevices) {
  navigator.mediaDevices.enumerateDevices = function() {
    return Promise.resolve([
      { deviceId: '', groupId: '', kind: 'audioinput', label: '', toJSON: () => ({}) },
      { deviceId: '', groupId: '', kind: 'audiooutput', label: '', toJSON: () => ({}) },
    ]);
  };
}

// ── BATTERY API ──────────────────────────────────────────────────────
if (navigator.getBattery) {
  navigator.getBattery = function() {
    return Promise.resolve({
      charging: true,
      chargingTime: 0,
      dischargingTime: Infinity,
      level: Math.random() * 0.3 + 0.7
    });
  };
}

// ── SPEECH RECOGNITION ───────────────────────────────────────────────
if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
  window.SpeechRecognition = function() {};
  window.webkitSpeechRecognition = function() {};
}

// ── CREDENTIALS API ──────────────────────────────────────────────────
if (navigator.credentials) {
  navigator.credentials.get = function() { return Promise.resolve(null); };
}

// ── FILE SYSTEM ACCESS API ───────────────────────────────────────────
if (!window.showOpenFilePicker) window.showOpenFilePicker = function() { return Promise.resolve([]); };
if (!window.showSaveFilePicker) window.showSaveFilePicker = function() { return Promise.resolve(); };
if (!window.showDirectoryPicker) window.showDirectoryPicker = function() { return Promise.resolve(); };

// ── CLIPBOARD API ────────────────────────────────────────────────────
if (navigator.clipboard) {
  navigator.clipboard.read = function() { return Promise.resolve([]); };
  navigator.clipboard.write = function(data) { return Promise.resolve(); };
  navigator.clipboard.readText = function() { return Promise.resolve(''); };
  navigator.clipboard.writeText = function(text) { return Promise.resolve(); };
}

// ── WEB BLUETOOTH ────────────────────────────────────────────────────
if (!navigator.bluetooth) {
  navigator.bluetooth = {};
  navigator.bluetooth.requestDevice = function() { return Promise.reject(new Error('User cancelled')); };
  navigator.bluetooth.getDevices = function() { return Promise.resolve([]); };
}

// ── WEB USB ──────────────────────────────────────────────────────────
if (!navigator.usb) {
  navigator.usb = {};
  navigator.usb.requestDevice = function() { return Promise.reject(new Error('User cancelled')); };
  navigator.usb.getDevices = function() { return Promise.resolve([]); };
}

// ── WEB SERIAL ───────────────────────────────────────────────────────
if (!navigator.serial) {
  navigator.serial = {};
  navigator.serial.requestPort = function() { return Promise.reject(new Error('User cancelled')); };
  navigator.serial.getPorts = function() { return Promise.resolve([]); };
}

// ── GAMEPAD API ──────────────────────────────────────────────────────
if (!navigator.getGamepads) {
  navigator.getGamepads = function() { return [null, null, null, null]; };
}

// ── KEYBOARD LOCK ────────────────────────────────────────────────────
navigator.keyboard = navigator.keyboard || {};
navigator.keyboard.lock = function() { return Promise.resolve(); };
navigator.keyboard.unlock = function() {};

// ── VIRTUAL KEYBOARD ─────────────────────────────────────────────────
if (!navigator.virtualKeyboard) {
  navigator.virtualKeyboard = { boundingRect: {}, overlaysContent: false };
}

// ── WINDOW CONTROLS OVERLAY ──────────────────────────────────────────
if (!navigator.windowControlsOverlay) {
  navigator.windowControlsOverlay = {};
  navigator.windowControlsOverlay.visible = false;
  navigator.windowControlsOverlay.getTitlebarAreaRect = function() { return { x: 0, y: 0, width: 0, height: 0 }; };
  navigator.windowControlsOverlay.addEventListener = function() {};
  navigator.windowControlsOverlay.removeEventListener = function() {};
}

// ── SECURITY & INTEGRITY ─────────────────────────────────────────────
const _origToString = Function.prototype.toString;
Function.prototype.toString = function() {
  if (this === navigator.webdriver || this === window.chrome.runtime) {
    return 'function () { [native code] }';
  }
  return _origToString.call(this);
};

// ── ERROR STACK TRACE NORMALIZATION (Hapus semua jejak Headless) ─────
const _origCaptureStackTrace = Error.captureStackTrace;
if (_origCaptureStackTrace) {
  Error.captureStackTrace = function(obj, fn) {
    _origCaptureStackTrace(obj, fn);
    if (obj.stack) {
      obj.stack = obj.stack
        .replace(/HeadlessChrome/g, 'Chrome')
        .replace(/Headless/g, '');
    }
  };
}

// ── Object.prototype.toString (biar PluginArray/MimeTypeArray real) ──
const _origObjToString = Object.prototype.toString;
Object.prototype.toString = function() {
  if (this === navigator.plugins) return '[object PluginArray]';
  if (this === navigator.mimeTypes) return '[object MimeTypeArray]';
  return _origObjToString.call(this);
};
"""

    def get_captured_popups(self) -> list:
        return list(self._popup_urls)


def _is_iframe_url(url: str) -> bool:
    u = url.lower()
    return (u.startswith("http")
            and not any(u.endswith(ext) for ext in [".js", ".css", ".png",
                                                      ".jpg", ".svg", ".woff"])
            and ("googleads" in u or "doubleclick" in u
            or "adsterra" in u or "exoclick" in u
            or "juicyads" in u or "propellerads" in u
            or "hilltopads" in u or "adcash" in u
            or "popcash" in u or "popads" in u))


def create_visitor(config: Config):
    mode = config.get("general", "engine", default="requests")
    if mode == "playwright":
        try:
            return PlaywrightVisitor(config)
        except Exception as e:
            logger.warning(f"Playwright unavailable ({e}), falling back to requests")
            return RequestsVisitor(config)
    return RequestsVisitor(config)
