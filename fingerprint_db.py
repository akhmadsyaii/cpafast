"""
fingerprint_db.py — Real Browser Fingerprint Database

Provides realistic browser fingerprints collected from actual browsers
(instead of random spoofing). Each fingerprint includes:

- navigator properties (webdriver, plugins, languages, etc.)
- Screen metrics (width, height, colorDepth, pixelRatio)
- WebGL vendor/renderer strings
- Canvas fingerprint noise values
- Installed fonts (OS-specific)
- AudioContext fingerprint
- Hardware concurrency

Fingerprints are organized by:
- Device type: desktop, mobile
- OS: Windows, macOS, Linux, Android, iOS
- Browser: Chrome, Firefox, Edge, Safari

Usage:
    from fingerprint_db import get_fingerprint, random_fingerprint
    fp = random_fingerprint(device="desktop", browser="chrome")
    # Apply fingerprint to Playwright context
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Fingerprint Data Class ──────────────────────────────────────────────

@dataclass
class BrowserFingerprint:
    """Complete browser fingerprint data."""
    name: str
    device: str            # desktop | mobile
    os: str                # windows | macos | linux | android | ios
    browser: str           # chrome | firefox | edge | safari
    version: str

    # Screen
    screen_width: int
    screen_height: int
    screen_color_depth: int = 24
    screen_pixel_ratio: float = 1.0
    available_width: int = 0
    available_height: int = 0

    # Navigator
    platform: str = "Win32"
    vendor: str = "Google Inc."
    language: str = "en-US"
    languages: List[str] = field(default_factory=lambda: ["en-US", "en"])
    hardware_concurrency: int = 8
    device_memory: float = 8
    max_touch_points: int = 0

    # WebGL
    webgl_vendor: str = "Intel Inc."
    webgl_renderer: str = "Intel Iris OpenGL Engine"
    webgl_version: str = "WebGL 2.0"

    # Audio
    audio_context_sample_rate: int = 48000
    audio_context_channel_count: int = 2

    # Fonts (subset of installed fonts)
    fonts: List[str] = field(default_factory=list)

    # Canvas noise values (delta applied to getImageData)
    canvas_noise_min: int = -1
    canvas_noise_max: int = 1

    def to_init_script(self) -> str:
        """Generate JavaScript to apply this fingerprint via Playwright add_init_script."""
        # Escape fonts for JS array
        fonts_js = json.dumps(self.fonts)
        languages_js = json.dumps(self.languages)

        return f"""
// ── Applied Fingerprint: {self.name} ──
// Device: {self.device} | OS: {self.os} | Browser: {self.browser} {self.version}

// Screen
Object.defineProperty(screen, 'width', {{ get: () => {self.screen_width} }});
Object.defineProperty(screen, 'height', {{ get: () => {self.screen_height} }});
Object.defineProperty(screen, 'colorDepth', {{ get: () => {self.screen_color_depth} }});
Object.defineProperty(screen, 'pixelDepth', {{ get: () => {self.screen_color_depth} }});
Object.defineProperty(screen, 'availWidth', {{ get: () => {self.available_width or self.screen_width} }});
Object.defineProperty(screen, 'availHeight', {{ get: () => {self.available_height or self.screen_height} }});

// Navigator overrides
Object.defineProperty(navigator, 'platform', {{ get: () => '{self.platform}' }});
Object.defineProperty(navigator, 'vendor', {{ get: () => '{self.vendor}' }});
Object.defineProperty(navigator, 'language', {{ get: () => '{self.language}' }});
Object.defineProperty(navigator, 'languages', {{ get: () => {languages_js} }});
Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {self.hardware_concurrency} }});
Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {self.device_memory} }});
Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => {self.max_touch_points} }});
Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});

// Chrome runtime
window.chrome = {{
  app: {{ isInstalled: false, InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }}, RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }} }},
  runtime: {{ OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }}, PlatformOs: {{ ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' }}, PlatformArch: {{ ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }}, RequestUpdateCheckStatus: {{ THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' }}, PlatformNaclArch: {{ ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }} }},
  loadTimes: function() {{ return {{}}; }},
  csi: function() {{ return {{}}; }}
}};

// Permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) => (
  params.name === 'notifications' ?
    Promise.resolve({{ state: 'prompt' }}) :
    originalQuery(params)
);

// Plugins (realistic count for {self.browser})
Object.defineProperty(navigator, 'plugins', {{ get: () => [1, 2, 3, 4, 5] }});
Object.defineProperty(navigator, 'mimeTypes', {{ get: () => [1, 2, 3, 4, 5] }});

// Font list (subset to avoid leaking real fonts)
// {fonts_js}

// WebGL spoof
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {{
  if (param === 37445) return '{self.webgl_vendor}';
  if (param === 37446) return '{self.webgl_renderer}';
  return getParameter.call(this, param);
}};
const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
WebGL2RenderingContext.prototype.getParameter = function(param) {{
  if (param === 37445) return '{self.webgl_vendor}';
  if (param === 37446) return '{self.webgl_renderer}';
  return getParameter2.call(this, param);
}};

// Canvas noise (subtle per-pixel variation)
const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
  const imageData = _origGetImageData.call(this, x, y, w, h);
  const noiseMin = {self.canvas_noise_min};
  const noiseMax = {self.canvas_noise_max};
  for (let i = 0; i < imageData.data.length; i += 4) {{
    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (Math.floor(Math.random() * (noiseMax - noiseMin + 1)) + noiseMin)));
  }}
  return imageData;
}};

// AudioContext spoof
const _origAudioContext = window.AudioContext || window.webkitAudioContext;
if (_origAudioContext) {{
  const _origCreateAnalyser = AudioContext.prototype.createAnalyser;
  AudioContext.prototype.createAnalyser = function() {{
    const analyser = _origCreateAnalyser.call(this);
    analyser.fftSize = 2048;
    analyser.frequencyBinCount = 1024;
    analyser.sampleRate = {self.audio_context_sample_rate};
    return analyser;
  }};
}}

// Override toString for detection methods
const _origToString = Function.prototype.toString;
Function.prototype.toString = function() {{
  if (this === navigator.webdriver) return 'function () {{ [native code] }}';
  if (this === window.chrome.runtime) return 'function () {{ [native code] }}';
  return _origToString.call(this);
}};
"""


# ═══════════════════════════════════════════════════════════════════════
#  WEBGL VENDOR DATABASE — realistic GPU strings per OS
# ═══════════════════════════════════════════════════════════════════════

WEBGL_VENDORS: Dict[str, List[tuple]] = {
    "windows": [
        # Intel Integrated
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 620 (0x00005917) Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) HD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) HD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris Plus Graphics 640 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        # NVIDIA
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        # AMD
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 7600 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon(TM) Vega 8 Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ],
    "macos": [
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M1, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M1 Max, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M2, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M2 Pro, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M2 Max, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M3, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M3 Pro, OpenGL 4.1)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple M3 Max, OpenGL 4.1)"),
        # Intel Macs (older)
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris Plus Graphics 640 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon Pro 5500M Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        # Safari non-ANGLE
        ("Apple Inc.", "Apple M1"),
        ("Apple Inc.", "Apple M1 Pro"),
        ("Apple Inc.", "Apple M2"),
        ("Apple Inc.", "Apple M2 Pro"),
        ("Apple Inc.", "Apple M3"),
        ("Apple Inc.", "Apple M3 Pro"),
        ("Apple Inc.", "Apple M3 Max"),
    ],
    "linux": [
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 620 (0x00005917) Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Intel", "Mesa Intel(R) UHD Graphics 620 (KBL GT2)"),
        ("Intel", "Mesa Intel(R) UHD Graphics 630 (CML GT2)"),
        ("Intel", "Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2)"),
        ("AMD", "Mesa AMD Radeon RX 6600 (navi23, LLVM 15.0.7, DRM 3.54)"),
        ("AMD", "Mesa AMD Radeon(TM) Graphics (renoir, LLVM 15.0.7, DRM 3.54)"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3060/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3070/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce GTX 1650/PCIe/SSE2"),
    ],
    "android": [
        ("Google Inc. (Qualcomm)", "ANGLE (Qualcomm, Adreno (TM) 650, OpenGL ES 3.2)"),
        ("Google Inc. (Qualcomm)", "ANGLE (Qualcomm, Adreno (TM) 660, OpenGL ES 3.2)"),
        ("Google Inc. (Qualcomm)", "ANGLE (Qualcomm, Adreno (TM) 730, OpenGL ES 3.2)"),
        ("Google Inc. (Qualcomm)", "ANGLE (Qualcomm, Adreno (TM) 740, OpenGL ES 3.2)"),
        ("Google Inc. (Qualcomm)", "ANGLE (Qualcomm, Adreno (TM) 750, OpenGL ES 3.2)"),
        ("Google Inc. (Samsung)", "ANGLE (Samsung, Mali-G78 MP14, OpenGL ES 3.2)"),
        ("Google Inc. (Samsung)", "ANGLE (Samsung, Mali-G77 MP11, OpenGL ES 3.2)"),
        ("Google Inc. (Samsung)", "ANGLE (Samsung, Xclipse 920, OpenGL ES 3.2)"),
        ("Google Inc. (MediaTek)", "ANGLE (MediaTek, Mali-G610 MC6, OpenGL ES 3.2)"),
        ("Google Inc. (Google)", "ANGLE (Google, Tensor G3 GPU, OpenGL ES 3.2)"),
        ("Google Inc. (Google)", "ANGLE (Google, Tensor G2 GPU, OpenGL ES 3.2)"),
    ],
    "ios": [
        ("Apple Inc.", "Apple A15 GPU"),
        ("Apple Inc.", "Apple A16 Bionic GPU"),
        ("Apple Inc.", "Apple A17 Pro GPU"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple A15 GPU, OpenGL ES 3.2)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple A16 Bionic GPU, OpenGL ES 3.2)"),
        ("Google Inc. (Apple)", "ANGLE (Apple, Apple A17 Pro GPU, OpenGL ES 3.2)"),
    ],
}

# ═══════════════════════════════════════════════════════════════════════
#  FONT POOLS PER OS — realistic installed fonts
# ═══════════════════════════════════════════════════════════════════════

FONT_POOLS: Dict[str, List[str]] = {
    "windows": [
        "Arial", "Arial Black", "Arial Narrow", "Arial Rounded MT Bold",
        "Bahnschrift", "Calibri", "Cambria", "Cambria Math", "Candara",
        "Comic Sans MS", "Consolas", "Constantia", "Corbel",
        "Courier New", "Ebrima", "Franklin Gothic Medium", "Gabriola",
        "Gadugi", "Georgia", "Gill Sans MT", "Gloucester MT Extra Condensed",
        "Goudy Old Style", "Gungsuh", "Impact", "Ink Free",
        "Javanese Text", "Jokerman", "Juice ITC", "Kristen ITC",
        "Leelawadee UI", "Lucida Bright", "Lucida Calligraphy",
        "Lucida Console", "Lucida Fax", "Lucida Handwriting",
        "Lucida Sans", "Lucida Sans Typewriter", "Lucida Sans Unicode",
        "Magneto", "Maiandra GD", "Malgun Gothic", "Microsoft Himalaya",
        "Microsoft JhengHei", "Microsoft New Tai Lue", "Microsoft PhagsPa",
        "Microsoft Sans Serif", "Microsoft Tai Le", "Microsoft YaHei",
        "Microsoft Yi Baiti", "MingLiU-ExtB", "Mongolian Baiti",
        "MSGothic", "MSReferenceSansSerif", "MSReferenceSerif",
        "MT Extra", "MV Boli", "Myanmar Text", "Nirmala UI",
        "OCR A Extended", "Old English Text MT", "Palatino Linotype",
        "Ravie", "Rockwell", "Rockwell Extra Bold", "Script MT Bold",
        "Segoe MDL2 Assets", "Segoe Print", "Segoe Script", "Segoe UI",
        "Segoe UI Emoji", "Segoe UI Historic", "Segoe UI Symbol",
        "Showcard Gothic", "SimSun-ExtB", "Sitka Banner", "Sitka Display",
        "Sitka Heading", "Sitka Small", "Sitka Subheading", "Sitka Text",
        "Snap ITC", "Stencil", "Sylfaen", "Symbol", "Tahoma",
        "Tempus Sans ITC", "Times New Roman", "Trebuchet MS", "Verdana",
        "Webdings", "Wide Latin", "Wingdings", "Wingdings 2", "Wingdings 3",
        "Yu Gothic", "Yu Gothic UI", "Yu Mincho",
    ],
    "macos": [
        "Academy Engraved LET", "Al Bayan", "Al Nile", "Al Tarikh",
        "American Typewriter", "Andale Mono", "Apple Braille",
        "Apple Chancery", "Apple Color Emoji", "Apple SD Gothic Neo",
        "Apple Symbols", "AppleGothic", "AppleMyungjo", "Arial",
        "Arial Black", "Arial Hebrew", "Arial Hebrew Scholar",
        "Arial Narrow", "Arial Rounded MT Bold", "Arial Unicode MS",
        "Avenir", "Avenir Next", "Avenir Next Condensed", "Ayuthaya",
        "Baghdad", "Bangla MN", "Bangla Sangam MN", "Baskerville",
        "Beirut", "Big Caslon", "Bodoni 72", "Bodoni 72 Oldstyle",
        "Bodoni 72 Smallcaps", "Bodoni Ornaments", "Bradley Hand",
        "Brush Script MT", "Chalkboard", "Chalkboard SE", "Chalkduster",
        "Charter", "Cochin", "Comic Sans MS", "Copperplate",
        "Corsiva Hebrew", "Courier", "Courier New", "Damascus",
        "DecoType Naskh", "Devanagari MT", "Devanagari Sangam MN",
        "Didot", "DIN Alternate", "DIN Condensed", "Diwan Kufi",
        "Diwan Thuluth", "Euphemia UCAS", "Farah", "Farisi",
        "Futura", "Galvji", "GB18030 Bitmap", "Geeza Pro", "Geneva",
        "Georgia", "Gill Sans", "Granada", "Gujarati MT",
        "Gujarati Sangam MN", "Gurmukhi MN", "Gurmukhi Sangam MN",
        "Halvetica Neue", "Handwriting Dakota", "Heiti SC", "Heiti TC",
        "Helvetica", "Helvetica Neue", "Herculanum", "Hiragino Kaku Gothic Pro",
        "Hiragino Kaku Gothic ProN", "Hiragino Maru Gothic Pro",
        "Hiragino Mincho ProN", "Hiragino Sans", "Hoefler Text",
        "Impact", "InaiMathi", "ITF Devanagari", "ITF Devanagari Marathi",
        "Kailasa", "Kannada MN", "Kannada Sangam MN", "Kefa",
        "Khmer MN", "Khmer Sangam MN", "Kino", "Kohinoor Bangla",
        "Kohinoor Devanagari", "Kohinoor Gujarati", "Kohinoor Telugu",
        "Kokonor", "Krungthep", "KufiStandardGK", "Lao MN",
        "Lao Sangam MN", "LastResort", "LiHei Pro", "LiSong Pro",
        "Lucida Grande", "Luminari", "Malayalam MN", "Malayalam Sangam MN",
        "Marion", "Marker Felt", "Menlo", "Microsoft Sans Serif",
        "Mishafi", "Mishafi Gold", "Monaco", "Mshtakan",
        "Mukta Mahee", "Myanmar MN", "Myanmar Sangam MN", "Nadeem",
        "New Peninim MT", "Noteworthy", "Noto Nastaliq", "Optima",
        "Oriya MN", "Oriya Sangam MN", "Palatino", "Papyrus",
        "Party LET", "Phosphate", "PingFang HK", "PingFang SC",
        "PingFang TC", "Plantagenet Cherokee", "PSL Orkhon", "Raanana",
        "Sana", "Sathu", "Savoye LET", "SF Pro", "SF Mono",
        "Shree Devanagari 714", "SignPainter", "Silom", "Sinhala MN",
        "Sinhala Sangam MN", "Skia", "Snell Roundhand", "Songti SC",
        "Songti TC", "STFangsong", "STHeiti", "STIXGeneral",
        "STIXIntegralsD", "STIXIntegralsSm", "STIXIntegralsUp",
        "STIXIntegralsUpSm", "STIXNonUnicode", "STIXSizeFiveSym",
        "STIXSizeFourSym", "STIXSizeOneSym", "STIXSizeThreeSym",
        "STIXSizeTwoSym", "STIXVariants", "STKaiti", "STSong",
        "Sukhumvit Set", "Symbol", "Tahoma", "Thonburi", "Times",
        "Times New Roman", "Trebuchet MS", "Verdana", "Webdings",
        "Wingdings", "Wingdings 2", "Wingdings 3", "Zapf Dingbats", "Zapfino",
    ],
    "linux": [
        "Cantarell", "Carlito", "DejaVu Math TeX Gyre", "DejaVu Sans",
        "DejaVu Sans Condensed", "DejaVu Sans Light", "DejaVu Sans Mono",
        "DejaVu Serif", "DejaVu Serif Condensed", "Droid Sans",
        "Droid Sans Fallback", "Droid Sans Mono", "Droid Serif",
        "Fira Code", "Fira Mono", "Fira Sans", "Fira Sans Condensed",
        "FreeMono", "FreeSans", "FreeSerif", "Gentium Basic",
        "Gentium Book Basic", "Liberation Mono", "Liberation Sans",
        "Liberation Sans Narrow", "Liberation Serif", "Lohit Assamese",
        "Lohit Bengali", "Lohit Devanagari", "Lohit Gujarati",
        "Lohit Gurmukhi", "Lohit Kannada", "Lohit Malayalam",
        "Lohit Marathi", "Lohit Odia", "Lohit Tamil", "Lohit Telugu",
        "LKLUG", "M+ 1p", "M+ 1mn", "M+ 2p", "M+ 2m",
        "M+ c", "Meera", "Mukti Narrow", "Nimbus Mono", "Nimbus Mono PS",
        "Nimbus Roman", "Nimbus Roman No9 L", "Nimbus Sans",
        "Nimbus Sans Narrow", "Noto Color Emoji", "Noto Kufi Arabic",
        "Noto Mono", "Noto Naskh Arabic", "Noto Sans", "Noto Sans Arabic",
        "Noto Sans Armenian", "Noto Sans Bengali", "Noto Sans CJG JP",
        "Noto Sans CJK KR", "Noto Sans CJK SC", "Noto Sans CJK TC",
        "Noto Sans Devanagari", "Noto Sans Ethiopic", "Noto Sans Georgian",
        "Noto Sans Gujarati", "Noto Sans Gurmukhi", "Noto Sans Hebrew",
        "Noto Sans Kannada", "Noto Sans Khmer", "Noto Sans Lao",
        "Noto Sans Malayalam", "Noto Sans Myanmar", "Noto Sans Sinhala",
        "Noto Sans Tamil", "Noto Sans Telugu", "Noto Sans Thai",
        "Noto Serif", "Noto Serif Bengali", "Noto Serif Devanagari",
        "Noto Serif Gujarati", "Noto Serif Gurmukhi", "Noto Serif Kannada",
        "Noto Serif Khmer", "Noto Serif Lao", "Noto Serif Malayalam",
        "Noto Serif Sinhala", "Noto Serif Tamil", "Noto Serif Telugu",
        "Noto Serif Thai", "Open Sans", "Oxygen Mono", "Oxygen Sans",
        "Padauk", "Padauk Book", "Phetsarath", "Purisa", "Sawasdee",
        "Science Gothic", "Source Code Pro", "Source Han Sans",
        "Source Han Serif", "Source Sans 3", "Source Sans Pro",
        "Source Serif 4", "Source Serif Pro", "STIX", "STIX Two Math",
        "STIX Two Text", "Symbola", "Tibetan Machine Uni",
        "Tlwg Mono", "Tlwg Typewriter", "Tlwg Typist", "Tlwg Typo",
        "Ubuntu", "Ubuntu Condensed", "Ubuntu Light", "Ubuntu Mono",
        "Umpush", "Waree",
    ],
    "android": [
        "Droid Sans", "Droid Sans Mono", "Droid Serif", "Noto Sans",
        "Noto Sans Bengali", "Noto Sans Devanagari", "Noto Sans Gujarati",
        "Noto Sans Gurmukhi", "Noto Sans Kannada", "Noto Sans Malayalam",
        "Noto Sans Tamil", "Noto Sans Telugu", "Noto Serif",
        "Roboto", "Roboto Black", "Roboto Bold", "Roboto Condensed",
        "Roboto Italic", "Roboto Light", "Roboto Medium", "Roboto Mono",
        "Roboto Thin", "sans-serif", "sans-serif-black",
        "sans-serif-condensed", "sans-serif-condensed-light",
        "sans-serif-light", "sans-serif-medium", "sans-serif-smallcaps",
        "sans-serif-thin", "serif", "serif-condensed", "serif-italic",
        "Source Sans Pro", "Noto Color Emoji", "Noto Sans CJK KR",
        "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans JP",
        "Noto Sans KR", "Noto Sans SC", "Noto Sans TC",
    ],
    "ios": [
        "Academy Engraved LET", "Al Nile", "American Typewriter",
        "Apple Color Emoji", "Apple SD Gothic Neo", "AppleSymbols",
        "Arial", "Arial Hebrew", "Arial Rounded MT Bold", "Avenir",
        "Avenir Next", "Avenir Next Condensed", "Bangla Sangam MN",
        "Baskerville", "Bodoni 72", "Bodoni 72 Oldstyle",
        "Bodoni 72 Smallcaps", "Bradley Hand", "Chalkboard SE",
        "Chalkduster", "Cochin", "Copperplate", "Courier New",
        "Damascus", "Devanagari Sangam MN", "Didot", "DIN Alternate",
        "DIN Condensed", "Euphemia UCAS", "Futura", "Galvji",
        "Geeza Pro", "Georgia", "Gill Sans", "Gujarati Sangam MN",
        "Gurmukhi Sangam MN", "Heiti SC", "Heiti TC", "Helvetica",
        "Helvetica Neue", "Hiragino Kaku Gothic ProN",
        "Hiragino Maru Gothic Pro", "Hiragino Mincho ProN",
        "Hoefler Text", "Impact", "Kailasa", "Kannada Sangam MN",
        "Khmer Sangam MN", "Kohinoor Bangla", "Kohinoor Devanagari",
        "Kohinoor Gujarati", "Kohinoor Telugu", "Lao Sangam MN",
        "Malayalam Sangam MN", "Marker Felt", "Menlo", "Mishafi",
        "Noteworthy", "Noto Nastaliq", "Optima", "Oriya Sangam MN",
        "Palatino", "Papyrus", "Party LET", "PingFang HK", "PingFang SC",
        "PingFang TC", "Savoye LET", "Sinhala Sangam MN", "Skia",
        "Snell Roundhand", "Songti SC", "Songti TC", "STHeiti",
        "STIXGeneral", "Sukhumvit Set", "Symbol", "Tahoma",
        "Thonburi", "Times New Roman", "Trebuchet MS", "Verdana",
        "Zapf Dingbats", "Zapfino",
    ],
}

# ═══════════════════════════════════════════════════════════════════════
#  SCREEN RESOLUTION POOLS per device type
# ═══════════════════════════════════════════════════════════════════════

DESKTOP_RESOLUTIONS: List[tuple] = [
    # Standard (16:9)
    (1280, 720),    # HD
    (1366, 768),    # Most common laptop
    (1440, 900),    # MacBook Air/Pro
    (1536, 864),    # Surface Book / High DPI
    (1600, 900),    # HD+
    (1792, 1120),   # MacBook Pro 14"
    (1920, 1080),   # Full HD — most common desktop
    (1920, 1200),   # WUXGA
    (2048, 1152),   # MacBook Pro 15" native
    (2560, 1080),   # Ultrawide
    (2560, 1440),   # QHD
    (2560, 1600),   # MacBook Pro 16"
    (2880, 1620),   # 3K
    (3024, 1964),   # MacBook Pro 14" high DPI
    (3440, 1440),   # Ultrawide QHD
    (3456, 2234),   # MacBook Pro 16" high DPI
    (3840, 2160),   # 4K UHD
    (3840, 1600),   # Ultrawide 4K
    # Common laptop sizes
    (1920, 1080),   # repeated for weight
    (1366, 768),    # repeated for weight
    (1440, 900),    # repeated for weight
    (1920, 1080),   # repeated for weight
    (1920, 1080),   # repeated for weight
    # Less common but realistic
    (1280, 1024),   # 5:4
    (1680, 1050),   # WSXGA+
]

MOBILE_RESOLUTIONS: List[tuple] = [
    # iPhone
    (390, 844),     # iPhone 14/15 Pro
    (393, 852),     # iPhone 15 Pro Max
    (375, 812),     # iPhone X/11 Pro/12/13 mini
    (414, 896),     # iPhone 11/XR/12/13/14 Plus
    (428, 926),     # iPhone 14/15 Pro Max
    (430, 932),     # iPhone 15 Plus
    # iPad
    (810, 1080),    # iPad 10.2"
    (834, 1194),    # iPad Air 11"
    (820, 1180),    # iPad Pro 11"
    (1024, 1366),   # iPad Pro 12.9"
    (744, 1133),    # iPad mini 6
    # Android phones
    (360, 780),     # Small Android
    (393, 851),     # Google Pixel 8
    (412, 915),     # Samsung Galaxy S24+
    (412, 892),     # Samsung Galaxy S24
    (430, 932),     # OnePlus 12
    (360, 800),     # Xiaomi 14
    (393, 873),     # Google Pixel 8 Pro
    (412, 869),     # Samsung Galaxy S23
    (1080, 2400),   # Samsung Note
    (1080, 2340),   # OnePlus 10
    # Android tablets
    (600, 960),     # Small tablet
    (800, 1280),    # Standard tablet
    (1200, 1920),   # Large tablet
]

# ═══════════════════════════════════════════════════════════════════════
#  Fingerprint Database — 25+ real browser fingerprints
# ═══════════════════════════════════════════════════════════════════════

FINGERPRINTS: List[BrowserFingerprint] = [
    # ══════════════════════════════════════════════════════════════════
    #  Windows 11 + Chrome 124+
    # ══════════════════════════════════════════════════════════════════
    BrowserFingerprint(
        name="Windows 11 - Chrome 124",
        device="desktop", os="windows", browser="chrome", version="124",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1040,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (Intel)", webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 620 (0x00005917) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        fonts=["Arial", "Calibri", "Cambria", "Cambria Math", "Candara",
               "Comic Sans MS", "Consolas", "Courier New", "Ebrima",
               "Franklin Gothic Medium", "Gabriola", "Gadugi",
               "Georgia", "Impact", "Ink Free", "Javanese Text",
               "Leelawadee UI", "Lucida Console", "Lucida Sans Unicode",
               "Malgun Gothic", "Microsoft Himalaya", "Microsoft JhengHei",
               "Microsoft New Tai Lue", "Microsoft PhagsPa",
               "Microsoft Sans Serif", "Microsoft Tai Le",
               "Microsoft YaHei", "Microsoft Yi Baiti",
               "MingLiU-ExtB", "Mongolian Baiti", "MS Gothic",
               "MV Boli", "Myanmar Text", "Nirmala UI",
               "Palatino Linotype", "Segoe MDL2 Assets", "Segoe Print",
               "Segoe Script", "Segoe UI", "Segoe UI Emoji",
               "Segoe UI Historic", "Segoe UI Symbol",
               "SimSun-ExtB", "Sitka", "Sylfaen", "Symbol",
               "Tahoma", "Times New Roman", "Trebuchet MS",
               "Verdana", "Webdings", "Wingdings",
               "Yu Gothic", "Yu Mincho"],
    ),
    BrowserFingerprint(
        name="Windows 11 - Chrome 125",
        device="desktop", os="windows", browser="chrome", version="125",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1040,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=12, device_memory=16, max_touch_points=0,
        webgl_vendor="Google Inc. (NVIDIA)", webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        fonts=["Arial", "Calibri", "Cambria", "Consolas", "Corbel",
               "Courier New", "Georgia", "Impact", "Lucida Console",
               "Microsoft Sans Serif", "Segoe UI", "Tahoma",
               "Times New Roman", "Trebuchet MS", "Verdana"],
    ),
    BrowserFingerprint(
        name="Windows 10 - Chrome 124",
        device="desktop", os="windows", browser="chrome", version="124",
        screen_width=1366, screen_height=768, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1366, available_height=728,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=4, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (Intel)", webgl_renderer="ANGLE (Intel, Intel(R) HD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    BrowserFingerprint(
        name="Windows 11 - Firefox 125",
        device="desktop", os="windows", browser="firefox", version="125",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1040,
        platform="Win32", vendor="",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Intel", webgl_renderer="Intel(R) UHD Graphics 620",
    ),
    BrowserFingerprint(
        name="Windows 11 - Edge 124",
        device="desktop", os="windows", browser="edge", version="124",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1040,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (Intel)", webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    # ── New Windows variants ────────────────────────────────────────
    BrowserFingerprint(
        name="Windows 11 - Chrome 124 - RTX 4090",
        device="desktop", os="windows", browser="chrome", version="124",
        screen_width=3840, screen_height=2160, screen_color_depth=24,
        screen_pixel_ratio=1.5, available_width=3840, available_height=2120,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=16, device_memory=32, max_touch_points=0,
        webgl_vendor="Google Inc. (NVIDIA)", webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    BrowserFingerprint(
        name="Windows 10 - Firefox 124 - AMD",
        device="desktop", os="windows", browser="firefox", version="124",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1040,
        platform="Win32", vendor="",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=16, max_touch_points=0,
        webgl_vendor="Google Inc. (AMD)", webgl_renderer="ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    BrowserFingerprint(
        name="Windows 11 - Edge - UltraWide",
        device="desktop", os="windows", browser="edge", version="125",
        screen_width=3440, screen_height=1440, screen_color_depth=30,
        screen_pixel_ratio=1.0, available_width=3440, available_height=1400,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=12, device_memory=32, max_touch_points=0,
        webgl_vendor="Google Inc. (NVIDIA)", webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    BrowserFingerprint(
        name="Windows 11 - Opera - Chrome 124",
        device="desktop", os="windows", browser="chrome", version="124",
        screen_width=1600, screen_height=900, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1600, available_height=860,
        platform="Win32", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=4, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (Intel)", webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),

    # ══════════════════════════════════════════════════════════════════
    #  macOS + Safari/Chrome
    # ══════════════════════════════════════════════════════════════════
    BrowserFingerprint(
        name="macOS 14 - Chrome 124",
        device="desktop", os="macos", browser="chrome", version="124",
        screen_width=1512, screen_height=982, screen_color_depth=24,
        screen_pixel_ratio=2.0, available_width=1512, available_height=904,
        platform="MacIntel", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (Apple)", webgl_renderer="ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)",
        fonts=["Apple Color Emoji", "Apple SD Gothic Neo", "Apple Symbols",
               "AppleGothic", "AppleMyungjo", "Arial", "Arial Hebrew",
               "Arial Rounded MT Bold", "Arial Unicode MS",
               "Avenir", "Avenir Next", "Avenir Next Condensed",
               "Bangla MN", "Bangla Sangam MN", "Baskerville",
               "Bodoni 72", "Bodoni 72 Oldstyle", "Bodoni 72 Smallcaps",
               "Bodoni Ornaments", "Bradley Hand", "Brush Script MT",
               "Chalkboard", "Chalkboard SE", "Chalkduster",
               "Charter", "Cochin", "Comic Sans MS", "Copperplate",
               "Corsiva Hebrew", "Courier New", "Damascus",
               "DecoType Naskh", "Devanagari MT", "Devanagari Sangam MN",
               "Didot", "DIN Alternate", "DIN Condensed",
               "Euphemia UCAS", "Farah", "Futura", "Galvji",
               "GB18030 Bitmap", "Geeza Pro", "Geneva", "Georgia",
               "Gill Sans", "Granada", "Gujarati MT", "Gujarati Sangam MN",
               "Gurmukhi MN", "Gurmukhi Sangam MN", "Halvetica Neue",
               "Heiti SC", "Heiti TC", "Helvetica", "Helvetica Neue",
               "Herculanum", "Hiragino Kaku Gothic Pro",
               "Hiragino Kaku Gothic ProN", "Hiragino Maru Gothic Pro",
               "Hoefler Text", "Impact", "InaiMathi",
               "ITF Devanagari", "ITF Devanagari Marathi",
               "Kailasa", "Kannada MN", "Kannada Sangam MN",
               "Kefa", "Khmer MN", "Khmer Sangam MN",
               "Kohinoor Bangla", "Kohinoor Devanagari",
               "Kohinoor Gujarati", "Kohinoor Telugu",
               "Kokonor", "Krungthep", "KufiStandardGK",
               "Lao MN", "Lao Sangam MN", "Lucida Grande",
               "Luminari", "Malayalam MN", "Malayalam Sangam MN",
               "Marion", "Marker Felt", "Menlo", "Microsoft Sans Serif",
               "Mishafi", "Mishafi Gold", "Monaco", "Mshtakan",
               "Mukta Mahee", "Myanmar MN", "Myanmar Sangam MN",
               "Nadeem", "New Peninim MT", "Noteworthy",
               "Noto Nastaliq", "Optima", "Oriya MN", "Oriya Sangam MN",
               "Palatino", "Papyrus", "Party LET", "Phosphate",
               "PingFang HK", "PingFang SC", "PingFang TC",
               "Plantagenet Cherokee", "PSL Orkhon", "Raanana",
               "Sana", "Sathu", "Savoye LET", "Shree Devanagari 714",
               "SignPainter", "Silom", "Sinhala MN", "Sinhala Sangam MN",
               "Skia", "Snell Roundhand", "Songti SC", "Songti TC",
               "STHeiti", "STIXGeneral", "STIXIntegralsD",
               "STIXIntegralsSm", "STIXIntegralsUp",
               "STIXIntegralsUpSm", "STIXNonUnicode",
               "STIXSizeFiveSym", "STIXSizeFourSym",
               "STIXSizeOneSym", "STIXSizeThreeSym",
               "STIXSizeTwoSym", "STIXVariants", "Sukhumvit Set",
               "Symbol", "Tahoma", "Thonburi", "Times", "Times New Roman",
               "Trebuchet MS", "Verdana", "Webdings", "Wingdings",
               "Wingdings 2", "Wingdings 3", "Zapf Dingbats",
               "Zapfino"],
    ),
    BrowserFingerprint(
        name="macOS 14 - Safari 17.4",
        device="desktop", os="macos", browser="safari", version="17.4",
        screen_width=1512, screen_height=982, screen_color_depth=24,
        screen_pixel_ratio=2.0, available_width=1512, available_height=904,
        platform="MacIntel", vendor="Apple Computer, Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Apple Inc.", webgl_renderer="Apple M1 Pro",
        fonts=["Arial", "Arial Unicode MS", "Apple Color Emoji",
               "Apple SD Gothic Neo", "Avenir", "Avenir Next",
               "Baskerville", "Chalkboard", "Cochin", "Copperplate",
               "Courier", "Courier New", "Didot", "Futura",
               "Geneva", "Georgia", "Gill Sans", "Helvetica",
               "Helvetica Neue", "Hiragino Kaku Gothic ProN",
               "Hiragino Maru Gothic Pro", "Hoefler Text",
               "Impact", "Lucida Grande", "Marker Felt",
               "Menlo", "Monaco", "Noteworthy", "Optima",
               "Palatino", "Papyrus", "PingFang SC",
               "SF Pro", "SF Mono", "STSongti SC",
               "Skia", "Snell Roundhand", "Tahoma",
               "Times", "Times New Roman", "Trebuchet MS",
               "Verdana", "Zapfino"],
    ),
    # ── New macOS variants ──────────────────────────────────────────
    BrowserFingerprint(
        name="macOS 14 - Chrome - M3 Max",
        device="desktop", os="macos", browser="chrome", version="125",
        screen_width=3456, screen_height=2234, screen_color_depth=24,
        screen_pixel_ratio=2.0, available_width=3456, available_height=2154,
        platform="MacIntel", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=14, device_memory=36, max_touch_points=0,
        webgl_vendor="Google Inc. (Apple)", webgl_renderer="ANGLE (Apple, Apple M3 Max, OpenGL 4.1)",
    ),
    BrowserFingerprint(
        name="macOS 13 - Safari 16.6",
        device="desktop", os="macos", browser="safari", version="16.6",
        screen_width=2560, screen_height=1600, screen_color_depth=24,
        screen_pixel_ratio=2.0, available_width=2560, available_height=1520,
        platform="MacIntel", vendor="Apple Computer, Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=10, device_memory=16, max_touch_points=0,
        webgl_vendor="Apple Inc.", webgl_renderer="Apple M2 Pro",
    ),
    BrowserFingerprint(
        name="macOS 13 - Firefox 124",
        device="desktop", os="macos", browser="firefox", version="124",
        screen_width=1440, screen_height=900, screen_color_depth=24,
        screen_pixel_ratio=2.0, available_width=1440, available_height=822,
        platform="MacIntel", vendor="",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Apple Inc.", webgl_renderer="Apple M1",
    ),
    BrowserFingerprint(
        name="macOS 12 - Chrome - Intel Mac",
        device="desktop", os="macos", browser="chrome", version="123",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1000,
        platform="MacIntel", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=4, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (AMD)", webgl_renderer="ANGLE (AMD, AMD Radeon Pro 5500M Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),

    # ══════════════════════════════════════════════════════════════════
    #  Linux + Chrome/Firefox
    # ══════════════════════════════════════════════════════════════════
    BrowserFingerprint(
        name="Linux (Ubuntu) - Chrome 124",
        device="desktop", os="linux", browser="chrome", version="124",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1053,
        platform="Linux x86_64", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Google Inc. (Intel)", webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 620 (0x00005917) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        fonts=["DejaVu Sans", "DejaVu Sans Mono", "DejaVu Serif",
               "FreeMono", "FreeSans", "FreeSerif", "Liberation Mono",
               "Liberation Sans", "Liberation Serif", "Noto Mono",
               "Noto Sans", "Noto Sans CJK JP", "Noto Serif",
               "Ubuntu", "Ubuntu Condensed", "Ubuntu Light",
               "Ubuntu Mono"],
    ),
    BrowserFingerprint(
        name="Linux (Ubuntu) - Firefox 125",
        device="desktop", os="linux", browser="firefox", version="125",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1053,
        platform="Linux x86_64", vendor="",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=0,
        webgl_vendor="Intel", webgl_renderer="Mesa Intel(R) UHD Graphics 620 (KBL GT2)",
        fonts=["DejaVu Sans", "DejaVu Sans Mono", "DejaVu Serif",
               "FreeMono", "FreeSans", "Noto Sans", "Noto Serif",
               "Ubuntu"],
    ),
    # ── New Linux variants ──────────────────────────────────────────
    BrowserFingerprint(
        name="Linux (Fedora) - Chrome 124",
        device="desktop", os="linux", browser="chrome", version="124",
        screen_width=2560, screen_height=1440, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=2560, available_height=1400,
        platform="Linux x86_64", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=12, device_memory=16, max_touch_points=0,
        webgl_vendor="Google Inc. (NVIDIA)", webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    BrowserFingerprint(
        name="Linux (Arch) - Firefox 126",
        device="desktop", os="linux", browser="firefox", version="126",
        screen_width=1920, screen_height=1080, screen_color_depth=24,
        screen_pixel_ratio=1.0, available_width=1920, available_height=1053,
        platform="Linux x86_64", vendor="",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=16, device_memory=32, max_touch_points=0,
        webgl_vendor="AMD", webgl_renderer="Mesa AMD Radeon RX 6600 (navi23, LLVM 15.0.7, DRM 3.54)",
    ),

    # ══════════════════════════════════════════════════════════════════
    #  Mobile
    # ══════════════════════════════════════════════════════════════════
    BrowserFingerprint(
        name="Android 14 - Chrome 124",
        device="mobile", os="android", browser="chrome", version="124",
        screen_width=412, screen_height=915, screen_color_depth=24,
        screen_pixel_ratio=2.625, available_width=412, available_height=846,
        platform="Linux armv8l", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=5,
        webgl_vendor="Google Inc. (Qualcomm)", webgl_renderer="ANGLE (Qualcomm, Adreno (TM) 730, OpenGL ES 3.2)",
    ),
    BrowserFingerprint(
        name="iPhone 15 Pro - Safari 17.4",
        device="mobile", os="ios", browser="safari", version="17.4",
        screen_width=393, screen_height=852, screen_color_depth=24,
        screen_pixel_ratio=3.0, available_width=393, available_height=734,
        platform="iPhone", vendor="Apple Computer, Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=6, device_memory=8, max_touch_points=5,
        webgl_vendor="Apple Inc.", webgl_renderer="Apple A17 Pro GPU",
    ),
    BrowserFingerprint(
        name="iPhone 14 - Chrome 124",
        device="mobile", os="ios", browser="chrome", version="124",
        screen_width=390, screen_height=844, screen_color_depth=24,
        screen_pixel_ratio=3.0, available_width=390, available_height=726,
        platform="iPhone", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=6, device_memory=8, max_touch_points=5,
        webgl_vendor="Google Inc. (Apple)", webgl_renderer="ANGLE (Apple, Apple A15 GPU, OpenGL ES 3.2)",
    ),
    BrowserFingerprint(
        name="Android 13 - Samsung Chrome",
        device="mobile", os="android", browser="chrome", version="123",
        screen_width=412, screen_height=915, screen_color_depth=24,
        screen_pixel_ratio=2.625, available_width=412, available_height=828,
        platform="Linux armv8l", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=6, max_touch_points=3,
        webgl_vendor="Google Inc. (Samsung)", webgl_renderer="ANGLE (Samsung, Mali-G78 MP14, OpenGL ES 3.2)",
    ),
    # ── New mobile variants ─────────────────────────────────────────
    BrowserFingerprint(
        name="Android 14 - Pixel 8 - Chrome 125",
        device="mobile", os="android", browser="chrome", version="125",
        screen_width=393, screen_height=851, screen_color_depth=24,
        screen_pixel_ratio=2.625, available_width=393, available_height=782,
        platform="Linux armv8l", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=9, device_memory=8, max_touch_points=5,
        webgl_vendor="Google Inc. (Google)", webgl_renderer="ANGLE (Google, Tensor G3 GPU, OpenGL ES 3.2)",
    ),
    BrowserFingerprint(
        name="Android 13 - Samsung S23 - Samsung Browser",
        device="mobile", os="android", browser="samsung", version="23",
        screen_width=412, screen_height=869, screen_color_depth=24,
        screen_pixel_ratio=2.625, available_width=412, available_height=800,
        platform="Linux armv8l", vendor="Google Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=3,
        webgl_vendor="Google Inc. (Samsung)", webgl_renderer="ANGLE (Samsung, Xclipse 920, OpenGL ES 3.2)",
    ),
    BrowserFingerprint(
        name="iPad Pro - Safari 17.4",
        device="mobile", os="ios", browser="safari", version="17.4",
        screen_width=1024, screen_height=1366, screen_color_depth=24,
        screen_pixel_ratio=2.0, available_width=1024, available_height=1298,
        platform="iPad", vendor="Apple Computer, Inc.",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=8, max_touch_points=5,
        webgl_vendor="Apple Inc.", webgl_renderer="Apple M2",
    ),
    BrowserFingerprint(
        name="Android 14 - OnePlus 12 - Firefox",
        device="mobile", os="android", browser="firefox", version="126",
        screen_width=430, screen_height=932, screen_color_depth=24,
        screen_pixel_ratio=2.625, available_width=430, available_height=864,
        platform="Linux armv8l", vendor="",
        language="en-US", languages=["en-US", "en"],
        hardware_concurrency=8, device_memory=12, max_touch_points=5,
        webgl_vendor="Google Inc. (Qualcomm)", webgl_renderer="ANGLE (Qualcomm, Adreno (TM) 750, OpenGL ES 3.2)",
    ),
]


# ═══════════════════════════════════════════════════════════════════════
#  DYNAMIC FINGERPRINT GENERATOR — create fingerprints on-the-fly
#  for infinite variety
# ═══════════════════════════════════════════════════════════════════════

def _random_webgl(os_name: str, browser: str) -> tuple:
    """Get a random WebGL vendor/renderer pair matching the OS and browser."""
    vendors = WEBGL_VENDORS.get(os_name, WEBGL_VENDORS["windows"])
    # Safari on macOS typically uses Apple Inc. vendor
    if browser == "safari" and os_name == "macos":
        safari_vendors = [v for v in vendors if v[0] == "Apple Inc."]
        if safari_vendors:
            return random.choice(safari_vendors)
    # Firefox on Windows uses bare vendor (no Google Inc. prefix)
    if browser == "firefox" and os_name == "windows":
        firefox_vendors = [v for v in vendors if v[0] == "Intel" or v[0].startswith("NVIDIA") or v[0].startswith("AMD")]
        if not firefox_vendors:
            firefox_vendors = [(f"Intel", f"Intel(R) UHD Graphics 620")]
        if firefox_vendors:
            return random.choice(firefox_vendors)
    return random.choice(vendors)


def _random_screen(device: str) -> tuple:
    """Get a random screen resolution and pixel ratio."""
    if device == "mobile":
        w, h = random.choice(MOBILE_RESOLUTIONS)
        # Higher pixel ratio for mobile
        pixel_ratio = random.choice([2.0, 2.625, 3.0])
        return w, h, pixel_ratio
    else:
        w, h = random.choice(DESKTOP_RESOLUTIONS)
        # Standard pixel ratio for desktop (some high DPI)
        pixel_ratio = random.choice([1.0, 1.0, 1.0, 1.0, 1.25, 1.5, 2.0])
        return w, h, pixel_ratio


def _random_fonts(os_name: str, count: Optional[int] = None) -> List[str]:
    """Get a random subset of fonts for the given OS."""
    pool = FONT_POOLS.get(os_name, FONT_POOLS["windows"])
    if count is None:
        count = random.randint(5, min(20, len(pool)))
    else:
        count = min(count, len(pool))
    return random.sample(pool, count)


def _random_hardware(os_name: str) -> tuple:
    """Get random hardware concurrency and device memory."""
    if os_name in ("android", "ios"):
        return random.choice([6, 8]), random.choice([4, 6, 8])
    elif os_name == "macos":
        return random.choice([8, 10, 12, 14]), random.choice([8, 16, 18, 24, 36])
    elif os_name == "linux":
        return random.choice([4, 8, 12, 16]), random.choice([8, 16, 32])
    else:
        return random.choice([4, 8, 12, 16]), random.choice([8, 16, 32])


def _os_to_platform(os_name: str) -> str:
    """Map OS name to navigator.platform string."""
    mapping = {
        "windows": "Win32",
        "macos": "MacIntel",
        "linux": "Linux x86_64",
        "android": "Linux armv8l",
        "ios": random.choice(["iPhone", "iPad"]),
    }
    return mapping.get(os_name, "Win32")


def generate_dynamic_fingerprint(device: str = "desktop",
                                 browser: str = "chrome",
                                 os_name: str = "") -> BrowserFingerprint:
    """
    Generate a fingerprint dynamically with random components.
    This provides infinite variety beyond the static FINGERPRINTS list.

    Args:
        device: "desktop" or "mobile"
        browser: "chrome", "firefox", "edge", "safari"
        os_name: "windows", "macos", "linux", "android", "ios"

    Returns:
        A BrowserFingerprint with randomized but realistic values.
    """
    # Normalize device parameter
    if device in ("android", "ios"):
        device = "mobile"

    # Pick OS if not specified
    if not os_name:
        if device == "mobile":
            os_name = random.choice(["android", "ios"])
        else:
            os_name = random.choice(["windows", "windows", "macos", "linux"])

    # Pick version
    versions = {
        "chrome": random.choice([123, 124, 125, 126]),
        "firefox": random.choice([124, 125, 126]),
        "edge": random.choice([123, 124, 125]),
        "safari": random.choice(["16.6", "17.3", "17.4", "17.5"]),
    }
    version = str(versions.get(browser, "124"))

    # Screen
    sw, sh, px_ratio = _random_screen(device)
    avail_h = sh - random.randint(30, 60)

    # Hardware
    hw_cores, dev_mem = _random_hardware(os_name)
    touch_pts = 5 if device == "mobile" else 0

    # WebGL
    webgl_vendor, webgl_renderer = _random_webgl(os_name, browser)

    # Fonts
    fonts = _random_fonts(os_name)

    # Platform
    platform = _os_to_platform(os_name)

    # Browser vendor
    vendor_map = {
        "chrome": "Google Inc.",
        "edge": "Google Inc.",
        "safari": "Apple Computer, Inc.",
        "firefox": "",
    }
    vendor = vendor_map.get(browser, "Google Inc.")

    # Locale
    locales = ["en-US", "en"]
    if random.random() < 0.3:
        locales = [random.choice(["en-GB", "en-AU", "en-CA", "de-DE", "fr-FR", "ja-JP"])]
        locales.append("en")

    return BrowserFingerprint(
        name=f"Dynamic {os_name.title()} - {browser.title()} {version} (gen)",
        device=device, os=os_name, browser=browser, version=version,
        screen_width=sw, screen_height=sh, screen_color_depth=random.choice([24, 30, 32]),
        screen_pixel_ratio=px_ratio,
        available_width=sw, available_height=avail_h,
        platform=platform, vendor=vendor,
        language=locales[0], languages=locales,
        hardware_concurrency=hw_cores, device_memory=dev_mem, max_touch_points=touch_pts,
        webgl_vendor=webgl_vendor, webgl_renderer=webgl_renderer,
        fonts=fonts,
    )


# ── Fingerprint Selection ───────────────────────────────────────────────

def random_fingerprint(device: str = "desktop",
                       browser: str = "chrome",
                       os_name: str = "",
                       use_dynamic: bool = True) -> BrowserFingerprint:
    """
    Get a random fingerprint matching the given criteria.

    Args:
        device: "desktop" or "mobile" (default: desktop)
        browser: "chrome", "firefox", "edge", "safari" (default: chrome)
        os_name: "windows", "macos", "linux", "android", "ios" (default: any)
        use_dynamic: if True, sometimes generates dynamic fingerprint for variety

    Returns:
        A BrowserFingerprint matching the criteria.
    """
    # 40% chance of dynamic fingerprint for extra variety
    if use_dynamic and random.random() < 0.4:
        return generate_dynamic_fingerprint(device=device, browser=browser, os_name=os_name)

    candidates = FINGERPRINTS

    if device:
        candidates = [f for f in candidates if f.device == device]
    if browser:
        candidates = [f for f in candidates if f.browser == browser]
    if os_name:
        candidates = [f for f in candidates if f.os == os_name]

    if not candidates:
        # Fallback: normalize device and try again
        normalized_device = "mobile" if device in ("android", "ios") else device
        fallback = [f for f in FINGERPRINTS if f.device == normalized_device]
        if fallback:
            return random.choice(fallback)
        return FINGERPRINTS[0]

    return random.choice(candidates)


def get_fingerprint(name: str) -> Optional[BrowserFingerprint]:
    """Get a specific fingerprint by name."""
    for fp in FINGERPRINTS:
        if fp.name == name:
            return fp
    return None


def list_fingerprints() -> List[Dict]:
    """List all available fingerprints."""
    return [
        {
            "name": fp.name,
            "device": fp.device,
            "os": fp.os,
            "browser": fp.browser,
            "version": fp.version,
            "screen": f"{fp.screen_width}x{fp.screen_height}",
            "pixel_ratio": fp.screen_pixel_ratio,
        }
        for fp in FINGERPRINTS
    ]


def generate_init_script(device: str = "desktop",
                         browser: str = "chrome") -> str:
    """
    Generate a complete init script with a random matching fingerprint.
    This combines the fingerprint JS with the standard stealth JS.

    Returns a JavaScript string to be used with page.add_init_script().
    """
    fp = random_fingerprint(device=device, browser=browser)
    return fp.to_init_script()


if __name__ == "__main__":
    # Standalone test
    print("🧬 Browser Fingerprint Database")
    print("=" * 56)
    for fp in FINGERPRINTS:
        print(f"  • {fp.name:40s} {fp.screen_width}x{fp.screen_height} @{fp.screen_pixel_ratio}x")
    print()
    print(f"Total: {len(FINGERPRINTS)} fingerprints")

    print()
    print("Random desktop Chrome fingerprint:")
    fp = random_fingerprint()
    print(f"  {fp.name}")
    print(f"  Screen: {fp.screen_width}x{fp.screen_height} @{fp.screen_pixel_ratio}x")
    print(f"  WebGL: {fp.webgl_renderer[:60]}...")
    print(f"  Fonts: {len(fp.fonts)} installed")
