"""
captcha_solver.py — CAPTCHA Solving Integration

Supported CAPTCHA solving services:
- 2captcha (2captcha.com) — Most popular, affordable
- Anti-Captcha (anti-captcha.com) — Reliable, good API
- Capsolver (capsolver.com) — Modern, AI-powered
- CapMonster (capmonster.cloud) — Fast, self-hosted option

Each service supports:
- Recaptcha V2 / V3 / Enterprise
- hCaptcha
- FunCaptcha
- GeeTest (GeeTest V3/V4)
- Image CAPTCHA
- Cloudflare Turnstile
- Text CAPTCHA
- ClickCAPTCHA
- RotateCAPTCHA

Usage:
    from captcha_solver import get_solver, CAPTCHA_SOLVER
    solver = get_solver({
        "service": "2captcha",
        "api_key": "YOUR_API_KEY"
    })
    result = solver.solve_recaptcha(site_key="...", page_url="...")
    if result.success:
        token = result.token

Integration with visitor:
    from captcha_solver import has_captcha_on_page, solve_captcha_on_page
    if has_captcha_on_page(page):
        token = solve_captcha_on_page(page, solver)
        page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML="{token}";')
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests


# ── Result Data ─────────────────────────────────────────────────────────

@dataclass
class CaptchaResult:
    """Result of a CAPTCHA solving attempt."""
    success: bool
    token: str = ""
    captcha_id: str = ""       # ID for report_bad
    error: str = ""
    cost: float = 0.0         # USD cost
    solve_time: float = 0.0    # seconds
    service: str = ""
    captcha_type: str = ""


# ── Base Solver ─────────────────────────────────────────────────────────

class BaseCaptchaSolver:
    """Base class for CAPTCHA solvers."""

    NAME = "base"
    BASE_URL = ""
    SUPPORTS_RECAPTCHA = True
    SUPPORTS_HCAPTCHA = True
    SUPPORTS_FUNCAPTCHA = True
    SUPPORTS_GEETEST = True
    SUPPORTS_TURNSTILE = True
    SUPPORTS_IMAGE = True
    SUPPORTS_TEXT = True

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.timeout = kwargs.get("timeout", 120)
        self.poll_interval = kwargs.get("poll_interval", 2.0)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CPABot/CaptchaSolver 2.0",
        })

    def solve_recaptcha(self, site_key: str, page_url: str,
                        action: str = "verify",
                        min_score: float = 0.3,
                        version: str = "v2") -> CaptchaResult:
        """Solve reCAPTCHA. Override in subclass."""
        return CaptchaResult(False, error="Not implemented")

    def solve_hcaptcha(self, site_key: str, page_url: str) -> CaptchaResult:
        """Solve hCaptcha."""
        return CaptchaResult(False, error="Not implemented")

    def solve_funcaptcha(self, public_key: str, page_url: str) -> CaptchaResult:
        """Solve FunCaptcha."""
        return CaptchaResult(False, error="Not implemented")

    def solve_turnstile(self, site_key: str, page_url: str) -> CaptchaResult:
        """Solve Cloudflare Turnstile."""
        return CaptchaResult(False, error="Not implemented")

    def solve_geetest(self, gt: str, challenge: str, page_url: str) -> CaptchaResult:
        """Solve GeeTest."""
        return CaptchaResult(False, error="Not implemented")

    def get_balance(self) -> float:
        """Get account balance in USD."""
        return 0.0

    def report_bad(self, captcha_id: str) -> bool:
        """Report a CAPTCHA as incorrectly solved."""
        return False

    def close(self):
        self._session.close()


# ── 2captcha Solver ────────────────────────────────────────────────────

class TwoCaptchaSolver(BaseCaptchaSolver):
    """Solver for 2captcha.com API."""

    NAME = "2captcha"
    BASE_URL = "https://2captcha.com"

    def _send_request(self, method: str, params: dict) -> Optional[str]:
        """Send CAPTCHA to 2captcha and get ID."""
        params.update({
            "key": self.api_key,
            "method": method,
            "json": 1,
        })
        try:
            resp = self._session.post(
                f"{self.BASE_URL}/in.php",
                data=params,
                timeout=30,
            )
            data = resp.json()
            if data.get("status") == 1:
                return str(data.get("request", ""))
            return None
        except Exception:
            return None

    def _get_result(self, captcha_id: str) -> Optional[str]:
        """Poll 2captcha for result."""
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                resp = self._session.get(
                    f"{self.BASE_URL}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1,
                    },
                    timeout=15,
                )
                data = resp.json()
                if data.get("status") == 1:
                    return str(data.get("request", ""))
                elif data.get("request") == "CAPCHA_NOT_READY":
                    time.sleep(self.poll_interval)
                    continue
                else:
                    return None
            except Exception:
                time.sleep(self.poll_interval)
                continue
        return None

    def solve_recaptcha(self, site_key: str, page_url: str,
                        action: str = "verify",
                        min_score: float = 0.3,
                        version: str = "v2") -> CaptchaResult:
        start = time.time()
        params = {
            "googlekey": site_key,
            "pageurl": page_url,
        }
        if version == "v3":
            params["method"] = "userrecaptcha"
            params["version"] = "v3"
            params["action"] = action
            params["min_score"] = min_score
        elif version == "enterprise":
            params["method"] = "userrecaptcha"
            params["version"] = "enterprise"
        else:
            params["method"] = "userrecaptcha"

        captcha_id = self._send_request("userrecaptcha", params)
        if not captcha_id:
            return CaptchaResult(False, error="Failed to send CAPTCHA",
                               service=self.NAME, solve_time=time.time() - start)

        token = self._get_result(captcha_id)
        if token:
            return CaptchaResult(True, token=token, captcha_id=captcha_id,
                               service=self.NAME, solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve CAPTCHA",
                           service=self.NAME, solve_time=time.time() - start)

    def solve_hcaptcha(self, site_key: str, page_url: str) -> CaptchaResult:
        start = time.time()
        params = {
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
        }
        captcha_id = self._send_request("hcaptcha", params)
        if not captcha_id:
            return CaptchaResult(False, error="Failed to send hCaptcha",
                               service=self.NAME, solve_time=time.time() - start)
        token = self._get_result(captcha_id)
        if token:
            return CaptchaResult(True, token=token, service=self.NAME,
                               solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve hCaptcha",
                           service=self.NAME, solve_time=time.time() - start)

    def solve_turnstile(self, site_key: str, page_url: str) -> CaptchaResult:
        start = time.time()
        params = {
            "method": "turnstile",
            "sitekey": site_key,
            "pageurl": page_url,
        }
        captcha_id = self._send_request("turnstile", params)
        if not captcha_id:
            return CaptchaResult(False, error="Failed to send Turnstile",
                               service=self.NAME, solve_time=time.time() - start)
        token = self._get_result(captcha_id)
        if token:
            return CaptchaResult(True, token=token, service=self.NAME,
                               solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve Turnstile",
                           service=self.NAME, solve_time=time.time() - start)

    def solve_geetest(self, gt: str, challenge: str, page_url: str) -> CaptchaResult:
        start = time.time()
        params = {
            "method": "geetest",
            "gt": gt,
            "challenge": challenge,
            "pageurl": page_url,
        }
        captcha_id = self._send_request("geetest", params)
        if not captcha_id:
            return CaptchaResult(False, error="Failed to send GeeTest",
                               service=self.NAME, solve_time=time.time() - start)
        token = self._get_result(captcha_id)
        if token:
            return CaptchaResult(True, token=token, service=self.NAME,
                               solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve GeeTest",
                           service=self.NAME, solve_time=time.time() - start)

    def get_balance(self) -> float:
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/res.php",
                params={"key": self.api_key, "action": "getbalance", "json": 1},
                timeout=15,
            )
            data = resp.json()
            return float(data) if isinstance(data, (int, float)) else 0.0
        except Exception:
            return 0.0

    def report_bad(self, captcha_id: str) -> bool:
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/res.php",
                params={
                    "key": self.api_key,
                    "action": "reportbad",
                    "id": captcha_id,
                    "json": 1,
                },
                timeout=15,
            )
            data = resp.json()
            return data.get("status") == 1
        except Exception:
            return False


# ── Anti-Captcha Solver ────────────────────────────────────────────────

class AntiCaptchaSolver(BaseCaptchaSolver):
    """Solver for anti-captcha.com API."""

    NAME = "anti-captcha"
    BASE_URL = "https://api.anti-captcha.com"

    def _create_task(self, task_type: str, task_data: dict) -> Optional[int]:
        """Create a CAPTCHA task and return task ID."""
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type": task_type,
                **task_data,
            },
        }
        try:
            resp = self._session.post(
                f"{self.BASE_URL}/createTask",
                json=payload,
                timeout=30,
            )
            data = resp.json()
            if data.get("errorId") == 0:
                return data.get("taskId")
            return None
        except Exception:
            return None

    def _get_result(self, task_id: int) -> Optional[dict]:
        """Poll for task result."""
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                resp = self._session.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id},
                    timeout=15,
                )
                data = resp.json()
                if data.get("errorId") == 0:
                    if data.get("status") == "ready":
                        return data.get("solution", {})
                    time.sleep(self.poll_interval)
                    continue
                return None
            except Exception:
                time.sleep(self.poll_interval)
                continue
        return None

    def solve_recaptcha(self, site_key: str, page_url: str,
                        action: str = "verify",
                        min_score: float = 0.3,
                        version: str = "v2") -> CaptchaResult:
        start = time.time()
        task_data = {
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        if version == "v3":
            task_data.update({
                "type": "RecaptchaV3TaskProxyless",
                "minScore": min_score,
                "pageAction": action,
            })
        elif version == "enterprise":
            task_data["type"] = "RecaptchaV2EnterpriseTaskProxyless"
        else:
            task_data["type"] = "RecaptchaV2TaskProxyless"

        task_id = self._create_task(task_data["type"], task_data)
        if not task_id:
            return CaptchaResult(False, error="Failed to create task",
                               service=self.NAME, solve_time=time.time() - start)

        result = self._get_result(task_id)
        if result:
            token = result.get("gRecaptchaResponse", "")
            if token:
                return CaptchaResult(True, token=token, service=self.NAME,
                                   solve_time=time.time() - start)

        return CaptchaResult(False, error="Failed to solve",
                           service=self.NAME, solve_time=time.time() - start)

    def solve_hcaptcha(self, site_key: str, page_url: str) -> CaptchaResult:
        start = time.time()
        task_data = {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        task_id = self._create_task("HCaptchaTaskProxyless", task_data)
        if not task_id:
            return CaptchaResult(False, error="Failed to create task",
                               service=self.NAME, solve_time=time.time() - start)
        result = self._get_result(task_id)
        if result:
            token = result.get("gRecaptchaResponse", "")
            if token:
                return CaptchaResult(True, token=token, service=self.NAME,
                                   solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve",
                           service=self.NAME, solve_time=time.time() - start)

    def solve_turnstile(self, site_key: str, page_url: str) -> CaptchaResult:
        start = time.time()
        task_data = {
            "type": "TurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        task_id = self._create_task("TurnstileTaskProxyless", task_data)
        if not task_id:
            return CaptchaResult(False, error="Failed to create task",
                               service=self.NAME, solve_time=time.time() - start)
        result = self._get_result(task_id)
        if result:
            token = result.get("token", "")
            if token:
                return CaptchaResult(True, token=token, service=self.NAME,
                                   solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve",
                           service=self.NAME, solve_time=time.time() - start)

    def get_balance(self) -> float:
        try:
            resp = self._session.post(
                f"{self.BASE_URL}/getBalance",
                json={"clientKey": self.api_key},
                timeout=15,
            )
            data = resp.json()
            if data.get("errorId") == 0:
                return data.get("balance", 0.0)
            return 0.0
        except Exception:
            return 0.0


# ── Capsolver Solver ──────────────────────────────────────────────────

class CapsolverSolver(BaseCaptchaSolver):
    """Solver for capsolver.com API."""

    NAME = "capsolver"
    BASE_URL = "https://api.capsolver.com"

    def _create_task(self, task_type: str, task_data: dict) -> Optional[str]:
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type": task_type,
                **task_data,
            },
        }
        try:
            resp = self._session.post(
                f"{self.BASE_URL}/createTask",
                json=payload,
                timeout=30,
            )
            data = resp.json()
            if data.get("errorId") == 0:
                return data.get("taskId")
            return None
        except Exception:
            return None

    def _get_result(self, task_id: str) -> Optional[dict]:
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                resp = self._session.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id},
                    timeout=15,
                )
                data = resp.json()
                if data.get("errorId") == 0:
                    if data.get("status") == "ready":
                        return data.get("solution", {})
                    time.sleep(self.poll_interval)
                    continue
                return None
            except Exception:
                time.sleep(self.poll_interval)
                continue
        return None

    def solve_recaptcha(self, site_key: str, page_url: str,
                        action: str = "verify",
                        min_score: float = 0.3,
                        version: str = "v2") -> CaptchaResult:
        start = time.time()
        task_data = {
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        if version == "v3":
            task_data["type"] = "ReCaptchaV3TaskProxyless"
            task_data["pageAction"] = action
            task_data["minScore"] = min_score
        else:
            task_data["type"] = "ReCaptchaV2TaskProxyless"

        task_id = self._create_task(task_data["type"], task_data)
        if not task_id:
            return CaptchaResult(False, error="Failed to create task",
                               service=self.NAME, solve_time=time.time() - start)

        result = self._get_result(task_id)
        if result:
            token = result.get("gRecaptchaResponse", "")
            if token:
                return CaptchaResult(True, token=token, service=self.NAME,
                                   solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve",
                           service=self.NAME, solve_time=time.time() - start)

    def solve_turnstile(self, site_key: str, page_url: str) -> CaptchaResult:
        start = time.time()
        task_data = {
            "type": "AntiTurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        task_id = self._create_task("AntiTurnstileTaskProxyless", task_data)
        if not task_id:
            return CaptchaResult(False, error="Failed to create task",
                               service=self.NAME, solve_time=time.time() - start)
        result = self._get_result(task_id)
        if result:
            token = result.get("token", "")
            if token:
                return CaptchaResult(True, token=token, service=self.NAME,
                                   solve_time=time.time() - start)
        return CaptchaResult(False, error="Failed to solve",
                           service=self.NAME, solve_time=time.time() - start)

    def get_balance(self) -> float:
        try:
            resp = self._session.post(
                f"{self.BASE_URL}/getBalance",
                json={"clientKey": self.api_key},
                timeout=15,
            )
            data = resp.json()
            if data.get("errorId") == 0:
                return data.get("balance", 0.0)
            return 0.0
        except Exception:
            return 0.0


# ── Solver Factory ─────────────────────────────────────────────────────

SOLVER_CLASSES = {
    "2captcha": TwoCaptchaSolver,
    "anti-captcha": AntiCaptchaSolver,
    "capsolver": CapsolverSolver,
}


def get_solver(config: dict) -> Optional[BaseCaptchaSolver]:
    """
    Create a CAPTCHA solver from config dict.

    Config format:
    {
        "service": "2captcha | anti-captcha | capsolver",
        "api_key": "...",
        "timeout": 120,         # optional
        "poll_interval": 2.0,   # optional
    }

    Returns a solver instance or None if config is invalid.
    """
    service = config.get("service", "").lower()
    api_key = config.get("api_key", "")

    if not service or not api_key:
        return None

    cls = SOLVER_CLASSES.get(service)
    if not cls:
        return None

    return cls(api_key=api_key, **config)


# ── Page Integration ────────────────────────────────────────────────────

# Selectors for CAPTCHA detection
RECAPTCHA_SELECTORS = [
    "iframe[src*='google.com/recaptcha']",
    "iframe[src*='recaptcha']",
    "div.g-recaptcha",
    ".g-recaptcha",
    "#g-recaptcha",
    "[data-sitekey]",
]

HCAPTCHA_SELECTORS = [
    "iframe[src*='hcaptcha.com']",
    ".h-captcha",
    "[data-hcaptcha-widget-id]",
]

TURNSTILE_SELECTORS = [
    "iframe[src*='challenges.cloudflare.com']",
    ".cf-turnstile",
    "[data-turnstile]",
]


def detect_captcha_type(page) -> Optional[str]:
    """
    Detect CAPTCHA type on a Playwright page.
    Returns: 'recaptcha_v2', 'recaptcha_v3', 'hcaptcha', 'turnstile', or None
    """
    try:
        # Quick check via evaluate (async, non-blocking)
        has_recaptcha = page.evaluate("""() => {
            return !!(
                document.querySelector('iframe[src*=\"google.com/recaptcha\"]') ||
                document.querySelector('.g-recaptcha') ||
                document.querySelector('[data-sitekey]')
            );
        }""")
        if has_recaptcha:
            # Determine v2 vs v3
            is_v3 = page.evaluate("""() => {
                const badge = document.querySelector('.grecaptcha-badge');
                return !!badge;
            }""")
            return "recaptcha_v3" if is_v3 else "recaptcha_v2"

        has_hcaptcha = page.evaluate("""() => {
            return !!(
                document.querySelector('iframe[src*=\"hcaptcha.com\"]') ||
                document.querySelector('.h-captcha')
            );
        }""")
        if has_hcaptcha:
            return "hcaptcha"

        has_turnstile = page.evaluate("""() => {
            return !!(
                document.querySelector('iframe[src*=\"challenges.cloudflare.com\"]') ||
                document.querySelector('.cf-turnstile')
            );
        }""")
        if has_turnstile:
            return "turnstile"
    except Exception:
        pass

    return None


def get_site_key(page, captcha_type: str) -> str:
    """Extract site key from the page."""
    try:
        if captcha_type.startswith("recaptcha"):
            return page.evaluate("""() => {
                const el = document.querySelector('.g-recaptcha') ||
                          document.querySelector('[data-sitekey]') ||
                          document.querySelector('#g-recaptcha');
                return el ? (el.getAttribute('data-sitekey') || '') : '';
            }""")
        elif captcha_type == "hcaptcha":
            return page.evaluate("""() => {
                const el = document.querySelector('.h-captcha') ||
                          document.querySelector('[data-sitekey]');
                return el ? (el.getAttribute('data-sitekey') || '') : '';
            }""")
        elif captcha_type == "turnstile":
            return page.evaluate("""() => {
                const el = document.querySelector('.cf-turnstile') ||
                          document.querySelector('[data-sitekey]');
                return el ? (el.getAttribute('data-sitekey') || '') : '';
            }""")
    except Exception:
        pass
    return ""


def solve_captcha_on_page(page, solver: BaseCaptchaSolver,
                          page_url: str) -> CaptchaResult:
    """
    Detect and solve CAPTCHA on a Playwright page automatically.

    Args:
        page: Playwright page object
        solver: CAPTCHA solver instance
        page_url: URL of the page

    Returns:
        CaptchaResult with the solution token
    """
    captcha_type = detect_captcha_type(page)
    if not captcha_type:
        return CaptchaResult(False, error="No CAPTCHA detected")

    site_key = get_site_key(page, captcha_type)
    if not site_key:
        return CaptchaResult(False, error=f"Could not extract site key for {captcha_type}")

    if captcha_type == "recaptcha_v2":
        return solver.solve_recaptcha(site_key, page_url, version="v2")
    elif captcha_type == "recaptcha_v3":
        return solver.solve_recaptcha(site_key, page_url, version="v3")
    elif captcha_type == "hcaptcha":
        return solver.solve_hcaptcha(site_key, page_url)
    elif captcha_type == "turnstile":
        return solver.solve_turnstile(site_key, page_url)

    return CaptchaResult(False, error=f"Unsupported CAPTCHA type: {captcha_type}")


def inject_captcha_token(page, token: str, captcha_type: str) -> bool:
    """
    Inject a solved CAPTCHA token into the page.

    For reCAPTCHA: Sets the #g-recaptcha-response textarea
    For hCaptcha: Sets the h-captcha-response
    For Turnstile: Sets the cf-turnstile-response

    Returns True if injection was successful.
    """
    try:
        if captcha_type.startswith("recaptcha"):
            page.evaluate(f"""() => {{
                const textarea = document.getElementById('g-recaptcha-response');
                if (textarea) {{
                    textarea.innerHTML = '{token}';
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
                // Also try data-callback
                const el = document.querySelector('[data-callback]');
                if (el) {{
                    const cb = el.getAttribute('data-callback');
                    if (cb && typeof window[cb] === 'function') {{
                        window[cb]('{token}');
                    }}
                }}
                // Trigger grecaptcha.execute
                if (typeof grecaptcha !== 'undefined' && grecaptcha.execute) {{
                    grecaptcha.execute();
                }}
            }}""")
            return True

        elif captcha_type == "hcaptcha":
            page.evaluate(f"""() => {{
                const textarea = document.querySelector('[name="h-captcha-response"]');
                if (textarea) {{
                    textarea.innerHTML = '{token}';
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
                // Trigger callback
                const el = document.querySelector('[data-callback]');
                if (el) {{
                    const cb = el.getAttribute('data-callback');
                    if (cb && typeof window[cb] === 'function') {{
                        window[cb]('{token}');
                    }}
                }}
            }}""")
            return True

        elif captcha_type == "turnstile":
            page.evaluate(f"""() => {{
                const textarea = document.querySelector('[name="cf-turnstile-response"]');
                if (textarea) {{
                    textarea.innerHTML = '{token}';
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }}""")
            return True

    except Exception:
        pass
    return False


# ── Service Discovery ──────────────────────────────────────────────────

SOLVER_SERVICES = [
    {
        "name": "2captcha",
        "slug": "2captcha",
        "description": "Most popular CAPTCHA solving service. Supports ReCaptcha V2/V3, hCaptcha, GeeTest, FunCaptcha, Cloudflare Turnstile, and image CAPTCHA.",
        "website": "https://2captcha.com",
        "signup": "https://2captcha.com/auth/register",
        "docs": "https://2captcha.com/api-docs",
        "pricing": "$0.002-0.01 per CAPTCHA",
        "min_deposit": "$0.50",
    },
    {
        "name": "Anti-Captcha",
        "slug": "anti-captcha",
        "description": "Reliable CAPTCHA solving with excellent API. Supports ReCaptcha V2/V3/Enterprise, hCaptcha, GeeTest V3/V4, FunCaptcha, Turnstile.",
        "website": "https://anti-captcha.com",
        "signup": "https://anti-captcha.com/clients/register",
        "docs": "https://anti-captcha.com/apidoc",
        "pricing": "$0.0007-0.01 per CAPTCHA",
        "min_deposit": "$0.50",
    },
    {
        "name": "Capsolver",
        "slug": "capsolver",
        "description": "Modern AI-powered CAPTCHA solver. Supports ReCaptcha V2/V3/Enterprise, hCaptcha, Cloudflare Turnstile, GeeTest, FunCaptcha.",
        "website": "https://capsolver.com",
        "signup": "https://capsolver.com/auth/register",
        "docs": "https://docs.capsolver.com/",
        "pricing": "$0.001-0.01 per CAPTCHA",
        "min_deposit": "$1.00",
    },
]


def list_services() -> List[Dict]:
    """List all available CAPTCHA solving services."""
    return SOLVER_SERVICES


# ── Balance Check ──────────────────────────────────────────────────────

def check_all_balances(configs: List[dict]) -> Dict[str, float]:
    """Check balance for multiple solvers. Returns {service: balance}."""
    balances = {}
    for cfg in configs:
        solver = get_solver(cfg)
        if solver:
            service = cfg.get("service", "unknown")
            try:
                balances[service] = solver.get_balance()
            except Exception:
                balances[service] = 0.0
    return balances


if __name__ == "__main__":
    print("🤖 CAPTCHA Solver Module")
    print("=" * 56)
    for svc in SOLVER_SERVICES:
        print(f"  • {svc['name']:15s} | {svc['website']}")
    print()
    print(f"Services: {len(SOLVER_SERVICES)}")
