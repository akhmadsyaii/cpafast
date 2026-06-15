#!/usr/bin/env python3
"""
CPA Traffic Bot — Desktop GUI
Modern, user-friendly interface built with CustomTkinter.
"""

import json
import logging
import os
import queue
import random
import sys
import threading
import time
import urllib.request
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ── Pre-import to fix any PIL issues ────────────────────────────────
try:
    from PIL import Image
except ImportError:
    Image = None

import customtkinter as ctk

# ── Set theme defaults ──────────────────────────────────────────────
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ──── Project imports ────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config
from traffic_bot import TrafficBot, CampaignTarget
from logger import logger
from scheduler import Scheduler

# ── Proxy scraper import (optional) ─────────────────────────────────
try:
    from proxy_scraper import scrape_proxies, get_source_names
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False


# ═════════════════════════════════════════════════════════════════════
#  FUTURISTIC COLOR PALETTE — Cyberpunk / Neo-cyber theme
# ═════════════════════════════════════════════════════════════════════

# -- Deep space backgrounds --
C_BG = "#0a0e17"          # Deep cosmic void
C_CARD = "#131a2b"        # Dark navy card
C_CARD2 = "#1a2338"       # Slightly lighter card
C_CARD_HOVER = "#1f2a42"  # Card hover state

# -- Neon accent spectrum --
C_CYAN = "#00e5ff"        # Primary neon cyan
C_PURPLE = "#b388ff"      # Cyber purple
C_PINK = "#ff4081"        # Neon pink
C_GREEN = "#00e676"       # Matrix green
C_RED = "#ff1744"         # Alert red
C_ORANGE = "#ff9100"      # Warning orange
C_YELLOW = "#ffd600"      # Golden yellow
C_TEAL = "#1de9b6"        # Teal accent
C_BLUE = "#2979ff"        # Vibrant blue

# -- Neutral tones --
C_GRAY = "#546e7a"        # Muted gray
C_TEXT = "#e0e0e0"        # Primary text — bright
C_TEXT_SEC = "#8892b0"    # Secondary text — muted
C_BORDER = "#2a3a5c"      # Subtle border

# -- Gradient helpers (for future use) --
GRADIENT_CYAN_PURPLE = ["#00e5ff", "#b388ff"]
GRADIENT_GREEN_TEAL = ["#00e676", "#1de9b6"]
GRADIENT_ORANGE_PINK = ["#ff9100", "#ff4081"]
GRADIENT_PURPLE_PINK = ["#b388ff", "#ff4081"]


# ═════════════════════════════════════════════════════════════════════
#  TYPOGRAPHY SYSTEM — Font families & helpers
# ═════════════════════════════════════════════════════════════════════

# -- Font families (cross-platform) --
FONT_UI = "Roboto"                     # Primary UI font (clean, modern, highly readable)
FONT_MONO = "Noto Sans Mono"          # Monospace for data/logs (replaces Courier)

# -- Convenience helper --
# Usage:  make_font(13, "bold")  or  make_font(11, family=FONT_MONO)
def make_font(size=11, weight="normal", family=None):
    """Create a CTkFont with consistent typography."""
    return ctk.CTkFont(size=size, weight=weight, family=family or FONT_UI)


# ═════════════════════════════════════════════════════════════════════
#  Log handler — captures logs into a queue for the GUI
# ═════════════════════════════════════════════════════════════════════

class GUILogHandler(logging.Handler):
    """Custom logging handler that pushes records to a queue for the GUI."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            pass



# ═════════════════════════════════════════════════════════════════════
#  Animated counter widget
# ═════════════════════════════════════════════════════════════════════

class AnimatedNumber(ctk.CTkLabel):
    """A label that animates counting up to a target value."""
    def __init__(self, master, start_val=0, duration=0.3, **kwargs):
        super().__init__(master, **kwargs)
        self._target = start_val
        self._current = float(start_val)
        self._start_val = float(start_val)
        self._animating = False
        self._duration = duration
        self._last_update = 0

    def set(self, value, animate=True):
        self._target = float(value)
        if not animate or abs(self._target - self._current) < 1:
            self._current = self._target
            text = self._format_value()
            self.configure(text=text)
            return
        self._start_val = self._current
        self._anim_start = time.time()
        if not self._animating:
            self._animating = True
            self._animate()

    def _animate(self):
        elapsed = time.time() - self._anim_start
        progress = min(1.0, elapsed / self._duration)
        eased = 1 - (1 - progress) ** 3  # ease-out cubic
        self._current = self._start_val + (self._target - self._start_val) * eased
        self.configure(text=self._format_value())
        if progress < 1.0:
            self.after(16, self._animate)
        else:
            self._current = self._target
            self.configure(text=self._format_value())
            self._animating = False

    def _format_value(self) -> str:
        if abs(self._target) >= 1000000:
            return f"{self._current / 1e6:.1f}M"
        elif abs(self._target) >= 1000:
            return f"{self._current:,.0f}"
        return f"{int(self._current)}"


# ═════════════════════════════════════════════════════════════════════
#  Stat card widget
# ═════════════════════════════════════════════════════════════════════

class StatCard(ctk.CTkFrame):
    """A compact card for displaying a single metric."""
    def __init__(self, master, title: str, value: str = "0",
                 icon: str = "", color: str = C_BLUE,
                 subtitle: str = "", width: int = 180, height: int = 110,
                 **kwargs):
        super().__init__(master, width=width, height=height,
                        fg_color=C_CARD, corner_radius=12, **kwargs)
        self.pack_propagate(False)

        # Accent bar on top
        self._accent = ctk.CTkFrame(self, height=3, fg_color=color,
                                    corner_radius=0)
        self._accent.pack(fill="x", side="top")
        self._accent.pack_propagate(False)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=12, pady=(8, 10))

        # Icon + title row
        title_row = ctk.CTkFrame(inner, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 2))

        if icon:
            icon_lbl = ctk.CTkLabel(title_row, text=icon,
                                    font=make_font(14), text_color=color)
            icon_lbl.pack(side="left", padx=(0, 4))

        title_lbl = ctk.CTkLabel(title_row, text=title,
                                 font=make_font(11, "bold"),
                                 text_color=C_TEXT_SEC)
        title_lbl.pack(side="left")

        # Value
        self._value_label = ctk.CTkLabel(
            inner, text=value,
            font=make_font(26, "bold"),
            text_color=color,
        )
        self._value_label.pack(anchor="w", pady=(2, 0))

        # Subtitle
        if subtitle:
            self._subtitle = ctk.CTkLabel(inner, text=subtitle,
                                          font=make_font(10),
                                          text_color=C_TEXT_SEC)
            self._subtitle.pack(anchor="w")

    def set_value(self, value: str, color: Optional[str] = None):
        self._value_label.configure(text=value)
        if color:
            self._value_label.configure(text_color=color)


# ═════════════════════════════════════════════════════════════════════
#  Progress bar with label
# ═════════════════════════════════════════════════════════════════════

class LabeledProgress(ctk.CTkFrame):
    """A horizontal progress bar with left/right labels."""
    def __init__(self, master, label: str = "", max_val: float = 100,
                 color: str = C_GREEN, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Label on left
        self._label = ctk.CTkLabel(self, text=label,
                                   font=make_font(12),
                                   text_color=C_TEXT_SEC, anchor="w")
        self._label.pack(fill="x", pady=(0, 2))

        # Progress bar
        self._progress = ctk.CTkProgressBar(
            self, height=8, corner_radius=4,
            fg_color=C_CARD, progress_color=color,
        )
        self._progress.pack(fill="x")
        self._progress.set(0)

        # Value on right
        self._value = ctk.CTkLabel(self, text="0%",
                                   font=make_font(11, "bold"),
                                   text_color=color, anchor="e")
        self._value.pack(fill="x", pady=(1, 0))

    def set_progress(self, pct: float, text: Optional[str] = None):
        self._progress.set(min(1.0, max(0.0, pct / 100)))
        self._value.configure(text=text or f"{pct:.0f}%")

    def set_label(self, text: str):
        self._label.configure(text=text)


# ═════════════════════════════════════════════════════════════════════
#  Main GUI Application
# ═════════════════════════════════════════════════════════════════════

class CPABotGUI(ctk.CTk):
    TITLE = "CPA Traffic Bot"
    MIN_W = 1200
    MIN_H = 780

    def __init__(self):
        super().__init__()
        self.title(self.TITLE)
        self.minsize(self.MIN_W, self.MIN_H)
        self.geometry("1400x850")

        # ── State ──────────────────────────────────────────────────────
        self.config: Optional[Config] = None
        self.bot: Optional[TrafficBot] = None
        self.scheduler: Optional[Scheduler] = None
        self._bot_thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._polling = True
        self._log_queue: queue.Queue = queue.Queue()
        self._log_handler: Optional[GUILogHandler] = None
        self._stats_cache: Dict[str, Any] = {}
        self._last_stats_time: float = 0
        self._auto_scroll_log = True
        self._tips = [
            "🌐 Proxy aktif = visitor dari banyak IP berbeda",
            "⏱️ Visit duration 30-80 detik biar gak kena banned",
            "🖱️ Bot auto-detect & klik iklan yang relevan",
            "📰 Article discovery otomatis dari sitemap.xml",
            "🎯 Campaign mode: set target visit, bot stop otomatis",
            "🧵 Multi-threading: makin banyak thread makin cepat",
            "📊 Export report CSV/JSON buat analisis",
            "🔁 Proxy rotation tiap request biar makin natural",
            "🛡️ Cookie consent otomatis biar gak dicurigai",
            "📱 User-Agent rotation desktop & mobile",
        ]

        # ── Initialize config ──────────────────────────────────────────
        self._load_config()

        # ── Build UI ───────────────────────────────────────────────────
        self._build_ui()

        # ── Restore theme ──────────────────────────────────────────────
        self._restore_theme()

        # ── Keyboard shortcuts ─────────────────────────────────────────
        self.bind("<space>", lambda e: self._on_start() if not self._running else self._on_stop())
        self.bind("<Control-p>", lambda e: self._on_pause())
        self.bind("<Control-r>", lambda e: self._on_resume())
        self.bind("<Control-q>", lambda e: self._on_close())
        self.bind("<Control-Tab>", lambda e: self._cycle_tab())

        # ── Start pollers ──────────────────────────────────────────────
        self.after(100, self._poll_stats)
        self.after(200, self._poll_logs)
        self._update_tip()

        # ── Graceful shutdown ──────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────────────
    #  Config helpers
    # ─────────────────────────────────────────────────────────────────

    def _load_config(self, path: str = "config.json"):
        try:
            self.config = Config(path)
            self.bot = TrafficBot(self.config)
            self.scheduler = Scheduler(self.config)
            logger.setup(self.config)
        except Exception as e:
            self.config = None
            self.bot = None

    def _save_config(self):
        if self.config:
            try:
                self.config.save()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────
    #  UI construction
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=0)   # top bar
        self.grid_rowconfigure(1, weight=1)   # content
        self.grid_rowconfigure(2, weight=0)   # status
        self.grid_columnconfigure(0, weight=1)

        # ── Top bar ────────────────────────────────────────────────────
        self._top_bar = self._build_top_bar()
        self._top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        # ── Tab view ───────────────────────────────────────────────────
        self._tab_view = ctk.CTkTabview(
            self, fg_color=C_BG, segmented_button_fg_color=C_CARD,
            segmented_button_selected_color=C_BLUE,
            segmented_button_selected_hover_color="#2980b9",
            segmented_button_unselected_color=C_CARD2,
            segmented_button_unselected_hover_color=C_CARD,
            text_color=C_TEXT, corner_radius=0,
        )
        self._tab_view.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # Create tabs
        self._tab_dashboard = self._tab_view.add("📊 Dashboard")
        self._tab_targets = self._tab_view.add("🎯 Targets")
        self._tab_config = self._tab_view.add("⚙️ Config")
        self._tab_logs = self._tab_view.add("📋 Logs")
        self._tab_reports = self._tab_view.add("📈 Reports")

        self._build_dashboard()
        self._build_targets()
        self._build_config()
        self._build_logs()
        self._build_reports()

        # ── Status bar ─────────────────────────────────────────────────
        self._status_bar = self._build_status_bar()
        self._status_bar.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))

    # ── Top Bar ────────────────────────────────────────────────────────

    def _build_top_bar(self):
        frame = ctk.CTkFrame(self, fg_color=C_CARD, height=52, corner_radius=0)
        frame.pack_propagate(False)

        # Title
        title = ctk.CTkLabel(frame, text="  CPA Traffic Bot",
                             font=make_font(18, "bold"),
                             text_color=C_CYAN)
        title.pack(side="left", padx=(16, 10))

        # Separator
        sep = ctk.CTkLabel(frame, text="|", font=make_font(16),
                           text_color=C_GRAY)
        sep.pack(side="left", padx=4)

        # Version / mode
        mode_lbl = ctk.CTkLabel(frame, text="v2.0 • Desktop",
                                font=make_font(11),
                                text_color=C_TEXT_SEC)
        mode_lbl.pack(side="left", padx=4)

        # ── Loading indicator ──────────────────────────────────────────
        self._loading_label = ctk.CTkLabel(
            frame, text="",
            font=make_font(11, "bold"),
            text_color=C_YELLOW,
        )
        self._loading_label.pack(side="left", padx=8)

        # ── Current action indicator ────────────────────────────────────
        self._action_indicator = ctk.CTkLabel(
            frame, text="",
            font=make_font(11),
            text_color=C_TEAL,
        )
        self._action_indicator.pack(side="left", padx=4)

        # ── Control buttons ────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=(0, 12), pady=6)

        self._btn_start = self._make_btn(btn_frame, "▶ Start", C_GREEN,
                                         self._on_start)
        self._btn_start.pack(side="left", padx=3)

        self._btn_stop = self._make_btn(btn_frame, "⏹ Stop", C_RED,
                                        self._on_stop, state="disabled")
        self._btn_stop.pack(side="left", padx=3)

        self._btn_pause = self._make_btn(btn_frame, "⏸ Pause", C_ORANGE,
                                         self._on_pause, state="disabled")
        self._btn_pause.pack(side="left", padx=3)

        self._btn_resume = self._make_btn(btn_frame, "▶ Resume", C_GREEN,
                                          self._on_resume, state="disabled")
        self._btn_resume.pack(side="left", padx=3)

        # Status indicator
        self._status_indicator = ctk.CTkLabel(
            btn_frame, text=" ● STOPPED",
            font=make_font(13, "bold"),
            text_color=C_RED,
        )
        self._status_indicator.pack(side="left", padx=(10, 0))

        # Elapsed timer
        self._elapsed_label = ctk.CTkLabel(
            btn_frame, text="⏱ 00:00:00",
            font=make_font(12),
            text_color=C_TEXT_SEC,
        )
        self._elapsed_label.pack(side="left", padx=(10, 0))

        # Theme switch
        self._theme_switch = ctk.CTkSwitch(
            btn_frame, text="☀️",
            font=make_font(10),
            progress_color=C_BLUE, button_color=C_YELLOW,
            command=self._toggle_theme, onvalue="Light", offvalue="Dark",
        )
        self._theme_switch.pack(side="left", padx=(12, 0))

        # Action buttons
        self._qs_btn = self._make_btn(btn_frame, "⚡ Quick Setup", C_PURPLE,
                                      self._on_quick_setup)
        self._qs_btn.pack(side="left", padx=3)

        self._scrape_btn = self._make_btn(btn_frame, "🌐 Auto Scrape", C_CYAN,
                                          self._on_auto_scrape, width=120)
        self._scrape_btn.pack(side="left", padx=3)

        return frame

    def _make_btn(self, master, text: str, color: str,
                  cmd: Callable, state: str = "normal",
                  width: int = 90, height: int = 32) -> ctk.CTkButton:
        return ctk.CTkButton(
            master, text=text, command=cmd,
            fg_color=color, hover_color=self._darken(color),
            text_color="#ffffff", font=make_font(11, "bold"),
            corner_radius=6, border_width=0,
            width=width, height=height,
            state=state,
        )

    def _darken(self, hex_color: str, factor: float = 0.8) -> str:
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            r, g, b = int(r * factor), int(g * factor), int(b * factor)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    # ── Dashboard ──────────────────────────────────────────────────────

    def _build_dashboard(self):
        parent = self._tab_dashboard
        parent.grid_rowconfigure(0, weight=0)  # stats row
        parent.grid_rowconfigure(1, weight=0)  # overall progress
        parent.grid_rowconfigure(2, weight=0)  # campaign row
        parent.grid_rowconfigure(3, weight=1)  # bottom panels
        parent.grid_columnconfigure(0, weight=1)

        # ── Top stats row ──────────────────────────────────────────────
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.grid(row=0, column=0, sticky="ew", pady=(10, 4), padx=10)
        for i in range(6):
            stats_frame.columnconfigure(i, weight=1)

        self._card_visits = StatCard(stats_frame, "Total Visits", "0",
                                     icon="📥", color=C_CYAN)
        self._card_visits.grid(row=0, column=0, padx=4, pady=2, sticky="ew")

        self._card_ok = StatCard(stats_frame, "Successful", "0",
                                 icon="✅", color=C_GREEN)
        self._card_ok.grid(row=0, column=1, padx=4, pady=2, sticky="ew")

        self._card_fail = StatCard(stats_frame, "Failed", "0",
                                   icon="❌", color=C_RED)
        self._card_fail.grid(row=0, column=2, padx=4, pady=2, sticky="ew")

        self._card_rate = StatCard(stats_frame, "Success Rate", "0%",
                                   icon="📈", color=C_GREEN)
        self._card_rate.grid(row=0, column=3, padx=4, pady=2, sticky="ew")

        self._card_vpm = StatCard(stats_frame, "Visits/min", "0",
                                  icon="🚀", color=C_ORANGE)
        self._card_vpm.grid(row=0, column=4, padx=4, pady=2, sticky="ew")

        self._card_ads = StatCard(stats_frame, "Ads Clicked", "0/0",
                                  icon="🖱️", color=C_YELLOW)
        self._card_ads.grid(row=0, column=5, padx=4, pady=2, sticky="ew")

        # ── Overall Campaign Progress Bar ──────────────────────────────
        progress_frame = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=12)
        progress_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 4))

        progress_top = ctk.CTkFrame(progress_frame, fg_color="transparent")
        progress_top.pack(fill="x", padx=16, pady=(10, 2))

        self._overall_progress_label = ctk.CTkLabel(
            progress_top, text="📊 Overall Progress",
            font=make_font(13, "bold"),
            text_color=C_TEXT,
        )
        self._overall_progress_label.pack(side="left")

        self._overall_progress_pct = ctk.CTkLabel(
            progress_top, text="0%",
            font=make_font(16, "bold"),
            text_color=C_CYAN,
        )
        self._overall_progress_pct.pack(side="right")

        # Big animated progress bar
        self._overall_progress_bar = ctk.CTkProgressBar(
            progress_frame, height=12, corner_radius=6,
            fg_color=C_CARD2, progress_color=C_TEAL,
            border_width=0,
        )
        self._overall_progress_bar.pack(fill="x", padx=16, pady=(4, 6))
        self._overall_progress_bar.set(0)

        # Subtitle showing visits completed / total
        self._overall_progress_sub = ctk.CTkLabel(
            progress_frame,
            text="No active campaigns — running in unlimited mode",
            font=make_font(10),
            text_color=C_TEXT_SEC,
        )
        self._overall_progress_sub.pack(fill="x", padx=16, pady=(0, 8))

        # ── Campaign / Progress ────────────────────────────────────────
        camp_frame = ctk.CTkFrame(parent, fg_color="transparent")
        camp_frame.grid(row=2, column=0, sticky="ew", pady=2, padx=10)

        # ── Scheduler status ───────────────────────────────────────────

        self._camp_panel = ctk.CTkFrame(camp_frame, fg_color=C_CARD,
                                        corner_radius=10)
        self._camp_panel.pack(fill="x", expand=True)

        self._camp_header = ctk.CTkLabel(
            self._camp_panel, text="  🎯 Campaign Progress",
            font=make_font(13, "bold"), text_color=C_TEXT,
            anchor="w",
        )
        self._camp_header.pack(fill="x", padx=14, pady=(10, 4))

        self._camp_container = ctk.CTkScrollableFrame(
            self._camp_panel, fg_color="transparent",
            height=80, scrollbar_button_color=C_CARD2,
        )
        self._camp_container.pack(fill="x", padx=10, pady=(0, 4))

        self._camp_progress_bars: List[LabeledProgress] = []

        # ── Scheduler status ───────────────────────────────────────────
        self._scheduler_panel = ctk.CTkFrame(
            self._camp_panel, fg_color="transparent", height=24
        )
        self._scheduler_panel.pack(fill="x", padx=14, pady=(0, 8))

        self._scheduler_status = ctk.CTkLabel(
            self._scheduler_panel, text="⏰ Scheduler: OFF",
            font=make_font(10),
            text_color=C_TEXT_SEC,
        )
        self._scheduler_status.pack(side="left")

        self._scheduler_next = ctk.CTkLabel(
            self._scheduler_panel, text="",
            font=make_font(10),
            text_color=C_GRAY,
        )
        self._scheduler_next.pack(side="right")

        # ── Bottom panels ──────────────────────────────────────────────
        bottom_frame = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)
        bottom_frame.grid_rowconfigure(0, weight=1)

        # Left panel: Performance + Ad Activity
        left_panel = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left_panel.grid_rowconfigure(0, weight=0)
        left_panel.grid_rowconfigure(1, weight=1)

        # Performance panel
        perf_frame = ctk.CTkFrame(left_panel, fg_color=C_CARD,
                                  corner_radius=10)
        perf_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(perf_frame, text="  📊 Performance",
                     font=make_font(13, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(10, 4))

        self._perf_ok = LabeledProgress(perf_frame, "Success Rate",
                                        color=C_GREEN)
        self._perf_ok.pack(fill="x", padx=14, pady=2)

        self._perf_ad = LabeledProgress(perf_frame, "Ad Click Rate",
                                        color=C_YELLOW)
        self._perf_ad.pack(fill="x", padx=14, pady=2)

        self._perf_vpm = LabeledProgress(perf_frame, "Visits/min",
                                         color=C_ORANGE, max_val=100)
        self._perf_vpm.pack(fill="x", padx=14, pady=(2, 10))

        # Ad Activity panel
        ad_frame = ctk.CTkFrame(left_panel, fg_color=C_CARD,
                                corner_radius=10)
        ad_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        ctk.CTkLabel(ad_frame, text="  📢 Ad Activity",
                     font=make_font(13, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(10, 4))

        self._ad_table = ctk.CTkTextbox(ad_frame, fg_color="transparent",
                                        font=make_font(11),
                                        text_color=C_TEXT_SEC,
                                        activate_scrollbars=False,
                                        state="disabled", height=120)
        self._ad_table.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # Right panel: Per Target
        right_panel = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        target_frame = ctk.CTkFrame(right_panel, fg_color=C_CARD,
                                    corner_radius=10)
        target_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(target_frame, text="  🌐 Per Target Stats",
                     font=make_font(13, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(10, 4))

        self._target_table = ctk.CTkTextbox(target_frame, fg_color="transparent",
                                            font=make_font(11),
                                            text_color=C_TEXT_SEC,
                                            activate_scrollbars=False,
                                            state="disabled")
        self._target_table.pack(fill="both", expand=True, padx=14, pady=(0, 10))

    def _update_dashboard(self, s: dict):
        """Update dashboard with latest stats."""
        self._card_visits.set_value(f"{s.get('total_visits', 0):,}")
        self._card_ok.set_value(f"{s.get('successful', 0):,}", C_GREEN)
        self._card_fail.set_value(f"{s.get('failed', 0):,}",
                                  C_RED if s.get('failed', 0) > 0 else C_GRAY)

        rate = s.get('success_rate', 0)
        rate_color = C_GREEN if rate >= 80 else C_ORANGE if rate >= 50 else C_RED
        self._card_rate.set_value(f"{rate:.1f}%", rate_color)

        vpm = s.get('visits_per_minute', 0)
        self._card_vpm.set_value(f"{vpm:.1f}")

        ads_found = s.get('total_ads_found', 0)
        ads_clicked = s.get('total_ads_clicked', 0)
        self._card_ads.set_value(f"{ads_clicked}/{ads_found}", C_YELLOW)

        # Performance bars
        self._perf_ok.set_progress(rate, f"{rate:.1f}%")
        ad_rate = s.get('ad_click_rate', 0)
        self._perf_ad.set_progress(ad_rate, f"{ad_rate:.1f}%")
        self._perf_vpm.set_progress(min(100, vpm * 5), f"{vpm:.1f}/min")

        # Overall campaign progress bar (0-100%)
        campaigns = self._stats_cache.get("campaigns", [])
        self._update_campaigns(campaigns)

        # Update overall progress bar
        if campaigns:
            total_target = sum(c.get("target", 0) for c in campaigns)
            total_completed = sum(c.get("completed", 0) for c in campaigns)
            if total_target > 0:
                overall_pct = (total_completed / total_target) * 100
                self._overall_progress_pct.configure(text=f"{overall_pct:.1f}%")
                self._overall_progress_bar.set(min(1.0, overall_pct / 100))
                self._overall_progress_sub.configure(
                    text=f"{total_completed}/{total_target} visits completed across {len(campaigns)} campaigns"
                )
            else:
                # Unlimited mode — show visits only
                total_visits = s.get('total_visits', 0)
                self._overall_progress_pct.configure(text=f"{total_visits:,} v")
                self._overall_progress_sub.configure(
                    text="Unlimited mode — no target set, running indefinitely"
                )
        elif self._running:
            total_visits = s.get('total_visits', 0)
            self._overall_progress_pct.configure(text=f"{total_visits:,} v")
            self._overall_progress_sub.configure(
                text="Running without campaigns — progress measured by total visits"
            )

        # Ad activity text
        ad_types = s.get("ad_type_stats", {})
        ad_networks = s.get("ad_network_stats", {})
        ad_lines = []
        if ad_types:
            ad_lines.append("By Type:")
            for k, v in sorted(ad_types.items(), key=lambda x: -x[1])[:6]:
                ico = {"display": "🖥", "native": "📰", "banner": "🎪",
                       "popup": "🪟", "image_ad": "🖼", "iframe": "📦",
                       "link": "🔗", "script_ad": "📜"}.get(k, "📌")
                ad_lines.append(f"  {ico} {k[:12]:12s}  {v}")
        if ad_networks:
            ad_lines.append("\nBy Network:")
            for k, v in sorted(ad_networks.items(), key=lambda x: -x[1])[:6]:
                ad_lines.append(f"  🌐 {k[:18]:18s}  {v}")
        if not ad_lines:
            ad_lines = ["  No ad activity yet"]

        self._ad_table.configure(state="normal")
        self._ad_table.delete("0.0", "end")
        self._ad_table.insert("0.0", "\n".join(ad_lines))
        self._ad_table.configure(state="disabled")

        # Target stats
        targets = s.get("targets", {})
        target_lines = []
        if targets:
            for name, td in sorted(targets.items()):
                total = td["total"]
                rate2 = (td["success"] / total * 100) if total > 0 else 0
                ads_str = f"ads {td.get('ads_clicked', 0)}/{td.get('ads_found', 0)}" if td.get('ads_found', 0) > 0 else ""
                target_lines.append(
                    f"  {name[:18]:18s}  "
                    f"{td['success']} OK / {td['fail']} Fail  "
                    f"({rate2:.1f}%)  "
                    f"{ads_str}"
                )
        else:
            target_lines = ["  No targets configured"]

        self._target_table.configure(state="normal")
        self._target_table.delete("0.0", "end")
        self._target_table.insert("0.0", "\n".join(target_lines))
        self._target_table.configure(state="disabled")

    def _update_campaigns(self, campaigns: List[dict]):
        # Clear existing bars
        for bar in self._camp_progress_bars:
            bar.pack_forget()
        self._camp_progress_bars.clear()

        if not campaigns:
            lbl = ctk.CTkLabel(self._camp_container, text="  No active campaigns",
                               font=make_font(11), text_color=C_TEXT_SEC)
            lbl.pack(anchor="w", padx=4, pady=4)
            self._camp_progress_bars.append(lbl)
            return

        for c in campaigns:
            pct = c.get("progress", 0)
            bar = LabeledProgress(
                self._camp_container,
                label=f"  {c['name'][:20]:20s}  {c['completed']}/{c['target']}",
                color=C_CYAN,
            )
            bar.pack(fill="x", padx=4, pady=2)
            bar.set_progress(pct, f"{pct:.0f}%  [{c['completed']}/{c['target']}]")
            self._camp_progress_bars.append(bar)

    # ── Targets Tab ────────────────────────────────────────────────────

    def _build_targets(self):
        parent = self._tab_targets
        parent.grid_rowconfigure(0, weight=0)  # toolbar
        parent.grid_rowconfigure(1, weight=1)  # list + form
        parent.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(parent, fg_color="transparent", height=40)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(10, 4), padx=10)

        self._btn_add_target = self._make_btn(toolbar, "➕ Add", C_GREEN,
                                              self._show_add_target, width=100)
        self._btn_add_target.pack(side="left", padx=3)

        self._btn_edit_target = self._make_btn(toolbar, "✏️ Edit", C_BLUE,
                                               self._on_edit_target, width=100)
        self._btn_edit_target.pack(side="left", padx=3)

        self._btn_remove_target = self._make_btn(toolbar, "🗑 Remove", C_RED,
                                                 self._on_remove_target, width=100)
        self._btn_remove_target.pack(side="left", padx=3)

        self._btn_discover = self._make_btn(toolbar, "📡 Auto-Discover", C_ORANGE,
                                            self._on_discover_articles, width=140)
        self._btn_discover.pack(side="left", padx=3)

        self._btn_refresh_targets = self._make_btn(toolbar, "🔄 Refresh", C_GRAY,
                                                   self._refresh_targets_list, width=100)
        self._btn_refresh_targets.pack(side="right", padx=3)

        # Main area: target list + form
        main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Target list (left)
        list_frame = ctk.CTkFrame(main_frame, fg_color=C_CARD, corner_radius=10)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        ctk.CTkLabel(list_frame, text="  Target List",
                     font=make_font(13, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(10, 4))

        columns = ("Name", "URL", "Visits", "Articles", "Ads")
        self._target_tree = ctk.CTkTextbox(
            list_frame, fg_color="transparent",
            font=make_font(11, family=FONT_MONO),
            text_color=C_TEXT, state="disabled",
        )
        self._target_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._selected_target_name: Optional[str] = None

        # Target form (right)
        form_frame = ctk.CTkFrame(main_frame, fg_color=C_CARD, corner_radius=10)
        form_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self._form_title = ctk.CTkLabel(form_frame, text="  Add New Target",
                                        font=make_font(13, "bold"),
                                        text_color=C_TEXT)
        self._form_title.pack(anchor="w", padx=14, pady=(10, 6))

        # Form fields
        self._form_name = self._add_form_field(form_frame, "Name", "My Blog")
        self._form_url = self._add_form_field(form_frame, "URL", "https://")
        self._form_visits = self._add_form_field(form_frame, "Target Visits", "0")
        self._form_threads = self._add_form_field(form_frame, "Threads", "10")

        # Checkboxes
        self._form_discover = ctk.CTkCheckBox(form_frame, text="Auto-Discover Articles",
                                              font=make_font(11),
                                              text_color=C_TEXT, fg_color=C_BLUE,
                                              border_color=C_TEXT_SEC, onvalue=True, offvalue=False)
        self._form_discover.pack(anchor="w", padx=14, pady=3)

        self._form_ad_click = ctk.CTkCheckBox(form_frame, text="Click Ads",
                                              font=make_font(11),
                                              text_color=C_TEXT, fg_color=C_BLUE,
                                              border_color=C_TEXT_SEC, onvalue=True, offvalue=False)
        self._form_ad_click.select()
        self._form_ad_click.pack(anchor="w", padx=14, pady=3)

        # Duration sliders
        ctk.CTkLabel(form_frame, text="Visit Duration (seconds):",
                     font=make_font(10), text_color=C_TEXT_SEC
                     ).pack(anchor="w", padx=14, pady=(8, 0))

        dur_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        dur_frame.pack(fill="x", padx=14, pady=2)

        self._dur_min = ctk.CTkSlider(dur_frame, from_=5, to=120,
                                       number_of_steps=23,
                                       progress_color=C_BLUE,
                                       button_color=C_BLUE)
        self._dur_min.set(30)
        self._dur_min.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._dur_min_lbl = ctk.CTkLabel(dur_frame, text="30s",
                                         font=make_font(10),
                                         text_color=C_TEXT, width=30)
        self._dur_min_lbl.pack(side="left", padx=(0, 6))
        self._dur_min.configure(command=lambda v: self._dur_min_lbl.configure(text=f"{int(v)}s"))

        self._dur_max = ctk.CTkSlider(dur_frame, from_=5, to=120,
                                       number_of_steps=23,
                                       progress_color=C_ORANGE,
                                       button_color=C_ORANGE)
        self._dur_max.set(80)
        self._dur_max.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._dur_max_lbl = ctk.CTkLabel(dur_frame, text="80s",
                                         font=make_font(10),
                                         text_color=C_TEXT, width=30)
        self._dur_max_lbl.pack(side="left")
        self._dur_max.configure(command=lambda v: self._dur_max_lbl.configure(text=f"{int(v)}s"))

        # Save / Clear buttons
        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(10, 14))

        self._btn_form_save = self._make_btn(btn_row, "💾 Save", C_GREEN,
                                             self._on_form_save, width=120)
        self._btn_form_save.pack(side="left", padx=3)

        self._btn_form_clear = self._make_btn(btn_row, "🗑 Clear", C_GRAY,
                                              self._clear_form, width=100)
        self._btn_form_clear.pack(side="left", padx=3)

        self._form_editing_name: Optional[str] = None

        self._refresh_targets_list()

    def _add_form_field(self, parent, label: str, placeholder: str = "") -> ctk.CTkEntry:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=3)

        ctk.CTkLabel(row, text=label + ":",
                     font=make_font(11),
                     text_color=C_TEXT_SEC, width=100, anchor="w"
                     ).pack(side="left")

        entry = ctk.CTkEntry(row, placeholder_text=placeholder,
                             font=make_font(11),
                             fg_color=C_CARD2, border_color=C_TEXT_SEC,
                             text_color=C_TEXT)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        return entry

    def _refresh_targets_list(self):
        """Refresh the targets list display."""
        if not self.bot:
            return

        self._target_tree.configure(state="normal")
        self._target_tree.delete("0.0", "end")

        targets = self.bot.list_targets()
        if not targets:
            self._target_tree.insert("0.0", "  No targets configured.\n  Add one using the form on the right.")
        else:
            # Header
            header = f"  {'Name':<18}{'URL':<40}{'Visits':<10}{'Articles':<10}{'Ads':<10}\n"
            header += f"  {'─'*18} {'─'*38} {'─'*8} {'─'*8} {'─'*8}\n"
            self._target_tree.insert("0.0", header)

            for i, t in enumerate(targets):
                url_str = t["url"][:38] + ".." if len(t["url"]) > 38 else t["url"]
                visits = str(t.get("target_visits", 0)) or "-"
                arts = str(len(t.get("articles", []))) if t.get("discover_articles") else "-"
                ads = "✅" if t.get("ad_click_probability", 0) > 0 else "❌"
                line = f"  {t['name'][:18]:<18}{url_str:<40}{visits:<10}{arts:<10}{ads:<10}\n"
                self._target_tree.insert("end", line)

        self._target_tree.configure(state="disabled")

    def _show_add_target(self):
        """Reset form for adding a new target."""
        self._form_title.configure(text="  Add New Target")
        self._clear_form()
        self._form_editing_name = None
        self._btn_form_save.configure(text="💾 Save")

    def _clear_form(self):
        self._form_name.delete(0, "end")
        self._form_url.delete(0, "end")
        self._form_url.insert(0, "https://")
        self._form_visits.delete(0, "end")
        self._form_visits.insert(0, "0")
        self._form_threads.delete(0, "end")
        self._form_threads.insert(0, "10")
        self._form_discover.deselect()
        self._form_ad_click.select()
        self._dur_min.set(30)
        self._dur_min_lbl.configure(text="30s")
        self._dur_max.set(80)
        self._dur_max_lbl.configure(text="80s")
        self._form_editing_name = None
        self._btn_form_save.configure(text="💾 Save")

    def _on_form_save(self):
        """Save or update a target."""
        if not self.bot:
            messagebox.showerror("Error", "Bot not initialized")
            return

        name = self._form_name.get().strip()
        url = self._form_url.get().strip()
        visits_str = self._form_visits.get().strip()
        threads_str = self._form_threads.get().strip()

        if not name:
            messagebox.showerror("Error", "Target name is required")
            return
        if not url.startswith("http"):
            messagebox.showerror("Error", "URL must start with http:// or https://")
            return

        visits = int(visits_str) if visits_str.isdigit() else 0
        discover = bool(self._form_discover.get())
        ad_click = bool(self._form_ad_click.get())
        dur_min = int(self._dur_min.get())
        dur_max = int(self._dur_max.get())

        editing = self._form_editing_name
        if editing:
            # Remove old target first
            self.bot.remove_target(editing)

        self.bot.add_target(
            name=name, url=url, weight=1,
            click_prob=0.3, ad_click_prob=0.25 if ad_click else 0.0,
            target_visits=visits, discover_articles=discover,
            article_distribution="random",
        )

        # Update config duration
        if self.config:
            self.config.data.setdefault("general", {})
            self.config.data["general"]["visit_duration_min"] = dur_min
            self.config.data["general"]["visit_duration_max"] = dur_max
            if threads_str.isdigit():
                self.config.data["general"]["threads"] = int(threads_str)
            self.config.save()

        self._refresh_targets_list()
        self._show_add_target()
        self._add_log(f"Target '{name}' saved", "info")

    def _show_target_selector(self, action: str = "edit"):
        """Show a popup to select a target for editing or removal."""
        if not self.bot:
            return
        targets = self.bot.list_targets()
        if not targets:
            messagebox.showinfo("Info", "No targets to " + action)
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Select Target to {action.title()}")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        main = ctk.CTkFrame(dialog, fg_color=C_BG)
        main.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(main, text=f"Select a target to {action}:",
                     font=make_font(12, "bold"),
                     text_color=C_TEXT).pack(anchor="w", pady=(0, 8))

        # Scrollable list of targets
        list_frame = ctk.CTkScrollableFrame(
            main, fg_color=C_CARD, corner_radius=8,
            scrollbar_button_color=C_CARD2,
        )
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        selected_name = ctk.StringVar()

        for i, t in enumerate(targets):
            name = t["name"]
            url = t["url"][:50] + ".." if len(t["url"]) > 50 else t["url"]
            visits = t.get("target_visits", 0) or "∞"

            card = ctk.CTkFrame(list_frame, fg_color=C_CARD2 if i % 2 == 0 else C_CARD,
                                corner_radius=6)
            card.pack(fill="x", padx=4, pady=2)

            rb = ctk.CTkRadioButton(card, text="", variable=selected_name,
                                    value=name, fg_color=C_BLUE,
                                    border_color=C_TEXT_SEC)
            rb.pack(side="left", padx=(8, 4))

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=4, pady=6)

            ctk.CTkLabel(info, text=name,
                         font=make_font(12, "bold"),
                         text_color=C_TEXT).pack(anchor="w")
            ctk.CTkLabel(info, text=f"{url}  •  Visits: {visits}",
                         font=make_font(10),
                         text_color=C_TEXT_SEC).pack(anchor="w")

        # Select first by default
        if targets:
            selected_name.set(targets[0]["name"])

        def confirm():
            name = selected_name.get()
            if not name:
                return
            dialog.destroy()
            if action == "edit":
                self._load_target_into_form(name)
            elif action == "remove":
                self._confirm_remove_target(name)

        def do_cancel():
            dialog.destroy()

        btn_row = ctk.CTkFrame(main, fg_color="transparent")
        btn_row.pack(fill="x")

        action_color = C_BLUE if action == "edit" else C_RED
        action_label = "✏️ Edit" if action == "edit" else "🗑 Remove"
        ctk.CTkButton(btn_row, text=action_label, command=confirm,
                      fg_color=action_color,
                      hover_color=self._darken(action_color),
                      font=make_font(11, "bold"),
                      corner_radius=6, width=120).pack(side="left", padx=3)
        ctk.CTkButton(btn_row, text="Cancel", command=do_cancel,
                      fg_color=C_GRAY,
                      font=make_font(11),
                      corner_radius=6, width=100).pack(side="left", padx=3)

    def _load_target_into_form(self, target_name: str):
        """Load a target's data into the edit form."""
        if not self.bot:
            return
        for t in self.bot.targets:
            if t.name == target_name:
                break
        else:
            messagebox.showerror("Error", f"Target '{target_name}' not found")
            return

        self._form_title.configure(text=f"  Edit Target: {t.name}")
        self._form_name.delete(0, "end")
        self._form_name.insert(0, t.name)
        self._form_url.delete(0, "end")
        self._form_url.insert(0, t.url)
        self._form_visits.delete(0, "end")
        self._form_visits.insert(0, str(t.target_visits or 0))
        self._form_threads.delete(0, "end")
        self._form_threads.insert(0, str(self.config.threads if self.config else 10))
        self._form_discover.select() if t.discover_articles else self._form_discover.deselect()
        self._form_ad_click.select() if t.ad_click_prob > 0 else self._form_ad_click.deselect()
        self._form_editing_name = t.name
        self._btn_form_save.configure(text="💾 Update")

    def _on_edit_target(self):
        """Show target selector popup for editing."""
        self._show_target_selector("edit")

    def _on_remove_target(self):
        """Show target selector popup for removal."""
        self._show_target_selector("remove")

    def _confirm_remove_target(self, target_name: str):
        """Confirm and remove a specific target."""
        if not self.bot:
            return
        if messagebox.askyesno("Confirm", f"Remove target '{target_name}'?"):
            self.bot.remove_target(target_name)
            self._refresh_targets_list()
            self._add_log(f"Target '{target_name}' removed", "warn")
            self._show_add_target()

    def _on_discover_articles(self):
        if not self.bot:
            return
        if not self.bot.targets:
            messagebox.showinfo("Info", "No targets")
            return
        self._add_log("Discovering articles...", "info")
        threading.Thread(target=self._do_discover, daemon=True).start()

    def _do_discover(self):
        try:
            for t in self.bot.targets:
                if t.discover_articles:
                    self.bot._discover_articles_for(t)
                    self.after(0, lambda t=t: self._add_log(
                        f"  {t.name}: {len(t.articles)} articles found", "info"
                    ))
            self.after(0, self._refresh_targets_list)
        except Exception as e:
            self.after(0, lambda e=e: self._add_log(f"Discover error: {e}", "error"))

    # ── Config Tab ─────────────────────────────────────────────────────

    def _build_config(self):
        parent = self._tab_config
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # Scrollable config area
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                        scrollbar_button_color=C_CARD2)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # ── General Settings ────────────────────────────────────────────
        self._build_config_section(scroll, "⚙️ General Settings", 0, [
            ("threads", "Threads", "5"),
            ("engine", "Engine", "playwright"),
            ("timeout", "Timeout (s)", "30"),
            ("max_retries", "Max Retries", "3"),
        ])

        # Duration
        dur_frame = ctk.CTkFrame(scroll, fg_color=C_CARD, corner_radius=10)
        dur_frame.grid(row=1, column=0, sticky="ew", pady=4)

        ctk.CTkLabel(dur_frame, text="  ⏱ Visit Duration (seconds)",
                     font=make_font(12, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(8, 2))

        dur_row = ctk.CTkFrame(dur_frame, fg_color="transparent")
        dur_row.pack(fill="x", padx=14, pady=(4, 10))

        ctk.CTkLabel(dur_row, text="Min:", font=make_font(10),
                     text_color=C_TEXT_SEC).pack(side="left", padx=(0, 4))
        self._cfg_dur_min = ctk.CTkEntry(dur_row, width=60,
                                         font=make_font(11),
                                         fg_color=C_CARD2, border_color=C_TEXT_SEC,
                                         text_color=C_TEXT)
        self._cfg_dur_min.insert(0, "15")
        self._cfg_dur_min.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(dur_row, text="Max:", font=make_font(10),
                     text_color=C_TEXT_SEC).pack(side="left", padx=(0, 4))
        self._cfg_dur_max = ctk.CTkEntry(dur_row, width=60,
                                         font=make_font(11),
                                         fg_color=C_CARD2, border_color=C_TEXT_SEC,
                                         text_color=C_TEXT)
        self._cfg_dur_max.insert(0, "30")
        self._cfg_dur_max.pack(side="left")

        # ── Proxy Settings ──────────────────────────────────────────────
        proxy_frame = ctk.CTkFrame(scroll, fg_color=C_CARD, corner_radius=10)
        proxy_frame.grid(row=2, column=0, sticky="ew", pady=4)

        ctk.CTkLabel(proxy_frame, text="  🌐 Proxy Settings",
                     font=make_font(12, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(8, 4))

        proxy_entries = {}
        for key, label, default in [
            ("proxy_enabled", "Enabled", "false"),
            ("proxy_type", "Type", "http"),
            ("proxy_test_url", "Test URL", "http://httpbin.org/ip"),
            ("proxy_file", "File", "proxy.txt"),
        ]:
            row2 = ctk.CTkFrame(proxy_frame, fg_color="transparent")
            row2.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row2, text=label + ":",
                         font=make_font(10),
                         text_color=C_TEXT_SEC, width=130, anchor="w"
                         ).pack(side="left")
            entry = ctk.CTkEntry(row2, font=make_font(11),
                                 fg_color=C_CARD2, border_color=C_TEXT_SEC,
                                 text_color=C_TEXT)
            entry.insert(0, default)
            entry.pack(side="right", fill="x", expand=True, padx=(8, 0))
            proxy_entries[key] = entry

        # Proxy Test button + result label
        proxy_btn_row = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_btn_row.pack(fill="x", padx=14, pady=(6, 10))

        self._btn_test_proxies = self._make_btn(
            proxy_btn_row, "🔍 Test Proxies", C_PURPLE,
            self._on_test_proxies, width=120, height=28,
        )
        self._btn_test_proxies.pack(side="left", padx=3)

        self._proxy_test_result = ctk.CTkLabel(
            proxy_btn_row, text="",
            font=make_font(10),
            text_color=C_TEXT_SEC,
        )
        self._proxy_test_result.pack(side="left", padx=(8, 0))

        if not hasattr(self, "_config_entries"):
            self._config_entries: Dict[str, ctk.CTkEntry] = {}
        self._config_entries.update(proxy_entries)

        # ── Ad Clicking ─────────────────────────────────────────────────
        self._build_config_section(scroll, "📢 Ad Clicking", 3, [
            ("ad_enabled", "Enabled", "true"),
            ("ad_probability", "Probability", "1.0"),
            ("ad_max_per_visit", "Max Ads/Visit", "5"),
            ("ad_click_delay_min", "Click Delay Min (s)", "2.0"),
            ("ad_click_delay_max", "Click Delay Max (s)", "5.0"),
        ])

        # ── Behavior Settings ───────────────────────────────────────────
        self._build_config_section(scroll, "🧠 Behavior", 4, [
            ("cookie_consent", "Cookie Consent", "true"),
            ("multi_page", "Multi-Page Browsing", "true"),
            ("simulate_scroll", "Simulate Scroll", "true"),
            ("form_interaction", "Form Interaction", "false"),
        ])

        # ── Scheduler Settings ──────────────────────────────────────────
        sched_frame = ctk.CTkFrame(scroll, fg_color=C_CARD, corner_radius=10)
        sched_frame.grid(row=5, column=0, sticky="ew", pady=4)

        ctk.CTkLabel(sched_frame, text="  ⏰ Scheduler Settings",
                     font=make_font(12, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(8, 4))

        sched_entries = {}
        for key, label, default in [
            ("sched_enabled", "Enabled", "false"),
            ("sched_mode", "Mode (interval/daily)", "interval"),
            ("sched_interval", "Interval (minutes)", "60"),
            ("sched_daily_time", "Daily Time (HH:MM)", "09:00"),
            ("sched_daily_runs", "Daily Runs", "10"),
            ("sched_run_duration", "Run Duration (min)", "30"),
        ]:
            row2 = ctk.CTkFrame(sched_frame, fg_color="transparent")
            row2.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row2, text=label + ":",
                         font=make_font(10),
                         text_color=C_TEXT_SEC, width=130, anchor="w"
                         ).pack(side="left")
            entry = ctk.CTkEntry(row2, font=make_font(11),
                                 fg_color=C_CARD2, border_color=C_TEXT_SEC,
                                 text_color=C_TEXT)
            entry.insert(0, default)
            entry.pack(side="right", fill="x", expand=True, padx=(8, 0))
            sched_entries[key] = entry

        self._config_entries.update(sched_entries)

        # ── Save Button ────────────────────────────────────────────────
        self._btn_save_config = self._make_btn(
            scroll, "💾 Save All Settings", C_GREEN,
            self._on_save_config, width=200, height=40,
        )
        self._btn_save_config.grid(row=6, column=0, pady=(12, 20))

        self._load_config_into_form()

    def _build_config_section(self, parent, title: str, row: int,
                              fields: List[Tuple[str, str, str]]):
        """Build a config section card with fields."""
        frame = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10)
        frame.grid(row=row, column=0, sticky="ew", pady=4)

        ctk.CTkLabel(frame, text=f"  {title}",
                     font=make_font(12, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(8, 4))

        entries = {}
        for key, label, default in fields:
            row2 = ctk.CTkFrame(frame, fg_color="transparent")
            row2.pack(fill="x", padx=14, pady=2)

            ctk.CTkLabel(row2, text=label + ":",
                         font=make_font(10),
                         text_color=C_TEXT_SEC, width=130, anchor="w"
                         ).pack(side="left")

            entry = ctk.CTkEntry(row2, font=make_font(11),
                                 fg_color=C_CARD2, border_color=C_TEXT_SEC,
                                 text_color=C_TEXT)
            entry.insert(0, default)
            entry.pack(side="right", fill="x", expand=True, padx=(8, 0))
            entries[key] = entry

        # Save entries reference
        if not hasattr(self, "_config_entries"):
            self._config_entries: Dict[str, ctk.CTkEntry] = {}
        self._config_entries.update(entries)

    def _load_config_into_form(self):
        if not self.config:
            return

        cfg = self.config
        map = {
            "threads": lambda: str(cfg.threads),
            "engine": lambda: cfg.get("general", "engine", default="playwright"),
            "timeout": lambda: str(cfg.timeout),
            "max_retries": lambda: str(cfg.max_retries),
            "proxy_enabled": lambda: str(cfg.proxy_enabled).lower(),
            "proxy_type": lambda: cfg.proxy_type,
            "proxy_test_url": lambda: cfg.proxy_test_url,
            "proxy_file": lambda: cfg.proxy_file or "proxy.txt",
            "ad_enabled": lambda: str(cfg.get("ad_clicking", "enabled", default=True)).lower(),
            "ad_probability": lambda: str(cfg.get("ad_clicking", "probability", default=1.0)),
            "ad_max_per_visit": lambda: str(cfg.get("ad_clicking", "max_ads_per_visit", default=5)),
            "ad_click_delay_min": lambda: str(cfg.get("ad_clicking", "click_delay_min", default=2.0)),
            "ad_click_delay_max": lambda: str(cfg.get("ad_clicking", "click_delay_max", default=5.0)),
            "cookie_consent": lambda: str(cfg.get("behavior", "cookie_consent", default=True)).lower(),
            "multi_page": lambda: str(cfg.get("behavior", "multi_page_browsing", default=True)).lower(),
            "simulate_scroll": lambda: str(cfg.get("behavior", "simulate_scroll", default=True)).lower(),
            "form_interaction": lambda: str(cfg.get("behavior", "form_interaction", default=False)).lower(),
            "sched_enabled": lambda: str(cfg.get("scheduler", "enabled", default=False)).lower(),
            "sched_mode": lambda: cfg.get("scheduler", "mode", default="interval"),
            "sched_interval": lambda: str(cfg.get("scheduler", "interval_minutes", default=60)),
            "sched_daily_time": lambda: cfg.get("scheduler", "daily_time", default="09:00"),
            "sched_daily_runs": lambda: str(cfg.get("scheduler", "daily_runs", default=10)),
            "sched_run_duration": lambda: str(cfg.get("scheduler", "run_duration_minutes", default=30)),
        }

        for key, entry in self._config_entries.items():
            if key in map:
                try:
                    val = map[key]()
                    entry.delete(0, "end")
                    entry.insert(0, val)
                except Exception:
                    pass

        # Duration fields
        if hasattr(self, "_cfg_dur_min"):
            self._cfg_dur_min.delete(0, "end")
            self._cfg_dur_min.insert(0, str(cfg.visit_duration_min))
            self._cfg_dur_max.delete(0, "end")
            self._cfg_dur_max.insert(0, str(cfg.visit_duration_max))

    def _on_save_config(self):
        if not self.config:
            return

        cfg = self.config
        try:
            # General
            cfg.data.setdefault("general", {})
            if "threads" in self._config_entries:
                cfg.data["general"]["threads"] = int(self._config_entries["threads"].get())
            if "engine" in self._config_entries:
                cfg.data["general"]["engine"] = self._config_entries["engine"].get().strip()
            if "timeout" in self._config_entries:
                cfg.data["general"]["timeout"] = int(self._config_entries["timeout"].get())
            if "max_retries" in self._config_entries:
                cfg.data["general"]["max_retries"] = int(self._config_entries["max_retries"].get())
            if hasattr(self, "_cfg_dur_min"):
                cfg.data["general"]["visit_duration_min"] = int(self._cfg_dur_min.get())
                cfg.data["general"]["visit_duration_max"] = int(self._cfg_dur_max.get())

            # Proxies
            cfg.data.setdefault("proxies", {})
            if "proxy_enabled" in self._config_entries:
                cfg.data["proxies"]["enabled"] = self._config_entries["proxy_enabled"].get().strip().lower() == "true"
            if "proxy_type" in self._config_entries:
                cfg.data["proxies"]["type"] = self._config_entries["proxy_type"].get().strip()
            if "proxy_test_url" in self._config_entries:
                cfg.data["proxies"]["test_url"] = self._config_entries["proxy_test_url"].get().strip()
            if "proxy_file" in self._config_entries:
                cfg.data["proxies"]["file"] = self._config_entries["proxy_file"].get().strip()

            # Ad clicking
            cfg.data.setdefault("ad_clicking", {})
            if "ad_enabled" in self._config_entries:
                cfg.data["ad_clicking"]["enabled"] = self._config_entries["ad_enabled"].get().strip().lower() == "true"
            if "ad_probability" in self._config_entries:
                cfg.data["ad_clicking"]["probability"] = float(self._config_entries["ad_probability"].get())
            if "ad_max_per_visit" in self._config_entries:
                cfg.data["ad_clicking"]["max_ads_per_visit"] = int(self._config_entries["ad_max_per_visit"].get())
            if "ad_click_delay_min" in self._config_entries:
                cfg.data["ad_clicking"]["click_delay_min"] = float(self._config_entries["ad_click_delay_min"].get())
            if "ad_click_delay_max" in self._config_entries:
                cfg.data["ad_clicking"]["click_delay_max"] = float(self._config_entries["ad_click_delay_max"].get())

            # Behavior
            cfg.data.setdefault("behavior", {})
            if "cookie_consent" in self._config_entries:
                cfg.data["behavior"]["cookie_consent"] = self._config_entries["cookie_consent"].get().strip().lower() == "true"
            if "multi_page" in self._config_entries:
                cfg.data["behavior"]["multi_page_browsing"] = self._config_entries["multi_page"].get().strip().lower() == "true"
            if "simulate_scroll" in self._config_entries:
                cfg.data["behavior"]["simulate_scroll"] = self._config_entries["simulate_scroll"].get().strip().lower() == "true"
            if "form_interaction" in self._config_entries:
                cfg.data["behavior"]["form_interaction"] = self._config_entries["form_interaction"].get().strip().lower() == "true"
            # ── Save Scheduler settings ────────────────────────────────
            cfg.data.setdefault("scheduler", {})
            if "sched_enabled" in self._config_entries:
                cfg.data["scheduler"]["enabled"] = self._config_entries["sched_enabled"].get().strip().lower() == "true"
            if "sched_mode" in self._config_entries:
                cfg.data["scheduler"]["mode"] = self._config_entries["sched_mode"].get().strip()
            if "sched_interval" in self._config_entries:
                cfg.data["scheduler"]["interval_minutes"] = int(self._config_entries["sched_interval"].get())
            if "sched_daily_time" in self._config_entries:
                cfg.data["scheduler"]["daily_time"] = self._config_entries["sched_daily_time"].get().strip()
            if "sched_daily_runs" in self._config_entries:
                cfg.data["scheduler"]["daily_runs"] = int(self._config_entries["sched_daily_runs"].get())
            if "sched_run_duration" in self._config_entries:
                cfg.data["scheduler"]["run_duration_minutes"] = int(self._config_entries["sched_run_duration"].get())

            cfg.save()
            self._add_log("Config saved successfully", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    # ── Proxy Test ────────────────────────────────────────────────────

    def _on_test_proxies(self):
        """Test proxy connectivity in a background thread."""
        self._proxy_test_result.configure(text="🔄 Testing...", text_color=C_YELLOW)
        self._btn_test_proxies.configure(state="disabled")
        threading.Thread(target=self._do_test_proxies, daemon=True).start()

    def _do_test_proxies(self):
        try:
            proxy_file = self.config.proxy_file if self.config else "proxy.txt"
            if not os.path.exists(proxy_file):
                self.after(0, lambda pf=proxy_file: self._proxy_test_result.configure(
                    text=f"❌ File not found: {pf}", text_color=C_RED
                ))
                self.after(0, lambda: self._btn_test_proxies.configure(state="normal"))
                return

            test_url = self.config.proxy_test_url if self.config else "http://httpbin.org/ip"
            proxy_type = self.config.proxy_type if self.config else "http"

            # Read proxies
            with open(proxy_file) as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

            if not lines:
                self.after(0, lambda: self._proxy_test_result.configure(
                    text="⚠️ No proxies in file", text_color=C_ORANGE
                ))
                self.after(0, lambda: self._btn_test_proxies.configure(state="normal"))
                return

            # Test first 5 proxies
            alive = 0
            tested = min(5, len(lines))
            for i, proxy_str in enumerate(lines[:tested]):
                try:
                    proxy_handler = urllib.request.ProxyHandler({
                        proxy_type: proxy_str
                    })
                    opener = urllib.request.build_opener(proxy_handler)
                    opener.open(test_url, timeout=5)
                    alive += 1
                except Exception:
                    pass

            result = f"✅ {alive}/{tested} proxies alive ({len(lines)} total)"
            color = C_GREEN if alive > 0 else C_RED
            self.after(0, lambda: self._proxy_test_result.configure(
                text=result, text_color=color
            ))
            self.after(0, lambda: self._add_log(result, "success" if alive > 0 else "warn"))
        except Exception as e:
            self.after(0, lambda: self._proxy_test_result.configure(
                text=f"❌ Test error: {e}", text_color=C_RED
            ))
        finally:
            self.after(0, lambda: self._btn_test_proxies.configure(state="normal"))

    # ── Logs Tab ───────────────────────────────────────────────────────

    def _build_logs(self):
        parent = self._tab_logs
        parent.grid_rowconfigure(0, weight=0)  # toolbar
        parent.grid_rowconfigure(1, weight=1)  # log area
        parent.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(10, 4), padx=10)

        ctk.CTkLabel(toolbar, text="  📋 Real-time Logs",
                     font=make_font(13, "bold"),
                     text_color=C_TEXT).pack(side="left", padx=(0, 10))

        self._log_filter_var = ctk.StringVar(value="ALL")
        self._log_filter = ctk.CTkOptionMenu(
            toolbar, variable=self._log_filter_var,
            values=["ALL", "SUCCESS", "INFO", "WARN", "ERROR"],
            font=make_font(11),
            fg_color=C_CARD2, button_color=C_BLUE,
            text_color=C_TEXT, dropdown_fg_color=C_CARD,
            width=130,
        )
        self._log_filter.pack(side="left", padx=5)
        self._log_filter_var.trace_add("write", lambda *a: self._apply_log_filter())

        # Auto-scroll toggle
        self._auto_scroll_var = ctk.BooleanVar(value=True)
        self._auto_scroll_toggle = ctk.CTkSwitch(
            toolbar, text="Auto-Scroll",
            variable=self._auto_scroll_var,
            onvalue=True, offvalue=False,
            font=make_font(10),
            progress_color=C_BLUE, button_color=C_CYAN,
            command=self._toggle_auto_scroll,
        )
        self._auto_scroll_toggle.pack(side="left", padx=8)
        self._auto_scroll_toggle.select()

        self._btn_clear_logs = self._make_btn(toolbar, "🗑 Clear", C_GRAY,
                                              self._clear_logs, width=90)
        self._btn_clear_logs.pack(side="right", padx=3)

        self._btn_export_logs = self._make_btn(toolbar, "💾 Export", C_BLUE,
                                               self._export_logs, width=90)
        self._btn_export_logs.pack(side="right", padx=3)

        # Log text area (FIXED: moved inside _build_logs, not in _toggle_auto_scroll)
        log_frame = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10)
        log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self._log_text = ctk.CTkTextbox(
            log_frame, fg_color="transparent",
            font=make_font(11, family=FONT_MONO),
            text_color=C_TEXT, wrap="word",
        )
        self._log_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Buffer for log lines with levels
        self._log_lines: List[Tuple[str, str]] = []  # (level, text)
        self._log_max_lines = 1000

    def _toggle_auto_scroll(self):
        self._auto_scroll_log = self._auto_scroll_var.get()

    def _add_log(self, msg: str, level: str = "info"):
        """Add a log message from the GUI thread."""
        now = datetime.now().strftime("%H:%M:%S")
        level_upper = level.upper()
        prefix = {"success": "[SUCCESS]", "info": "[INFO]",
                  "warn": "[WARN]", "error": "[ERROR]"}.get(level, "[INFO]")
        line = f"{now} {prefix} {msg}"
        self._log_lines.append((level_upper, line))
        if len(self._log_lines) > self._log_max_lines:
            self._log_lines = self._log_lines[-self._log_max_lines:]

        # Apply filter
        filter_val = self._log_filter_var.get()
        if filter_val == "ALL" or filter_val == level_upper:
            self._insert_log_line(line, level)

    def _insert_log_line(self, line: str, level: str):
        color_map = {"success": C_GREEN, "info": C_TEXT,
                     "warn": C_ORANGE, "error": C_RED}
        tag = f"log_{level}"
        self._log_text.insert("end", line + "\n", tag)
        self._log_text.tag_config(tag, foreground=color_map.get(level, C_TEXT))
        if self._auto_scroll_log:
            try:
                self._log_text.see("end")
            except Exception:
                pass

    def _apply_log_filter(self):
        filter_val = self._log_filter_var.get()
        self._log_text.delete("0.0", "end")
        for level, line in self._log_lines:
            if filter_val == "ALL" or level == filter_val:
                self._insert_log_line(line, level.lower())

    def _clear_logs(self):
        self._log_text.delete("0.0", "end")
        self._log_lines.clear()

    def _export_logs(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, "w") as f:
                    for _, line in self._log_lines:
                        f.write(line + "\n")
                self._add_log(f"Logs exported to {path}", "info")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")

    # ── Reports Tab ────────────────────────────────────────────────────

    def _build_reports(self):
        parent = self._tab_reports
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=0)  # controls
        parent.grid_rowconfigure(1, weight=1)  # preview
        parent.grid_rowconfigure(2, weight=0)  # tip

        # Controls
        ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl.grid(row=0, column=0, sticky="ew", pady=(10, 4), padx=10)

        ctk.CTkLabel(ctrl, text="  📊 Reports & Statistics",
                     font=make_font(13, "bold"),
                     text_color=C_TEXT).pack(side="left", padx=(0, 14))

        self._btn_export_csv = self._make_btn(ctrl, "📄 Export CSV", C_GREEN,
                                              self._on_export_csv, width=120)
        self._btn_export_csv.pack(side="left", padx=3)

        self._btn_export_json = self._make_btn(ctrl, "📋 Export JSON", C_BLUE,
                                               self._on_export_json, width=120)
        self._btn_export_json.pack(side="left", padx=3)

        self._btn_reset_stats = self._make_btn(ctrl, "🔄 Reset Stats", C_ORANGE,
                                               self._on_reset_stats, width=120)
        self._btn_reset_stats.pack(side="left", padx=3)

        self._btn_refresh_report = self._make_btn(ctrl, "🔄 Refresh", C_GRAY,
                                                  self._refresh_report, width=100)
        self._btn_refresh_report.pack(side="right", padx=3)

        # Report preview
        preview_frame = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10)
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

        ctk.CTkLabel(preview_frame, text="  Summary Report",
                     font=make_font(12, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(10, 4))

        self._report_text = ctk.CTkTextbox(
            preview_frame, fg_color="transparent",
            font=make_font(11, family=FONT_MONO),
            text_color=C_TEXT, state="disabled",
        )
        self._report_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Bottom tip
        tip_frame = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=8)
        tip_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        self._report_tip = ctk.CTkLabel(
            tip_frame, text="💡 Export reports periodically to track performance over time.",
            font=make_font(11), text_color=C_TEXT_SEC,
        )
        self._report_tip.pack(padx=14, pady=8)

        self._refresh_report()

    def _refresh_report(self):
        """Update the report preview with current stats."""
        if not self.bot:
            return

        try:
            status = self.bot.get_status()
        except Exception:
            return

        s = status.get("stats", {})

        lines = []
        lines.append("=" * 56)
        lines.append("  CPA TRAFFIC BOT — SUMMARY REPORT")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 56)
        lines.append("")
        lines.append(f"  Status:       {'▶ Running' if status.get('running') else '⏹ Stopped'}")
        if status.get('paused'):
            lines.append("  [PAUSED]")
        lines.append(f"  Targets:      {status.get('targets', 0)}")
        lines.append(f"  Threads:      {status.get('threads', 0)}")
        lines.append(f"  Proxies:      {status.get('proxies', {}).get('alive', 0)}/{status.get('proxies', {}).get('total', 0)}")
        lines.append(f"  Ad Clicking:  {'ON' if status.get('ad_clicking') else 'OFF'}")
        lines.append("")
        lines.append("─" * 56)
        lines.append("  VISIT STATISTICS")
        lines.append("─" * 56)
        lines.append(f"  Total Visits:    {s.get('total_visits', 0):,}")
        lines.append(f"  Successful:      {s.get('successful', 0):,}")
        lines.append(f"  Failed:          {s.get('failed', 0):,}")
        lines.append(f"  Success Rate:    {s.get('success_rate', 0):.1f}%")
        lines.append(f"  Visits/min:      {s.get('visits_per_minute', 0):.1f}")
        lines.append(f"  Avg Response:    {s.get('avg_response_time', 0):.3f}s")
        lines.append(f"  Pages Viewed:    {s.get('total_pages_visited', 0):,}")
        lines.append(f"  Elapsed:         {s.get('elapsed_seconds', 0):.0f}s")
        lines.append("")
        lines.append("─" * 56)
        lines.append("  AD STATISTICS")
        lines.append("─" * 56)
        lines.append(f"  Ads Found:       {s.get('total_ads_found', 0):,}")
        lines.append(f"  Ads Clicked:     {s.get('total_ads_clicked', 0):,}")
        lines.append(f"  Click Rate:      {s.get('ad_click_rate', 0):.1f}%")
        lines.append(f"  Clicks OK:       {s.get('ad_clicks_success', 0):,}")
        lines.append(f"  Clicks Failed:   {s.get('ad_clicks_failed', 0):,}")

        ad_types = s.get("ad_type_stats", {})
        if ad_types:
            lines.append("")
            lines.append(f"  By Type:")
            for k, v in sorted(ad_types.items(), key=lambda x: -x[1]):
                lines.append(f"    {k:16s}: {v}")

        ad_networks = s.get("ad_network_stats", {})
        if ad_networks:
            lines.append("")
            lines.append(f"  By Network:")
            for k, v in sorted(ad_networks.items(), key=lambda x: -x[1]):
                lines.append(f"    {k:24s}: {v}")

        targets = s.get("targets", {})
        if targets:
            lines.append("")
            lines.append("─" * 56)
            lines.append("  PER TARGET")
            lines.append("─" * 56)
            for name, td in sorted(targets.items()):
                total = td["total"]
                rate2 = (td["success"] / total * 100) if total > 0 else 0
                lines.append(f"  {name}")
                lines.append(f"    Visits: {td['success']} OK / {td['fail']} Fail ({rate2:.1f}%)")
                if td.get('ads_found', 0) > 0:
                    lines.append(f"    Ads: {td.get('ads_clicked', 0)}/{td.get('ads_found', 0)}")

        campaigns = status.get("campaigns", [])
        if campaigns:
            lines.append("")
            lines.append("─" * 56)
            lines.append("  CAMPAIGNS")
            lines.append("─" * 56)
            for c in campaigns:
                lines.append(f"  {c['name']}: {c['completed']}/{c['target']} ({c['progress']:.0f}%)")

        self._report_text.configure(state="normal")
        self._report_text.delete("0.0", "end")
        self._report_text.insert("0.0", "\n".join(lines))
        self._report_text.configure(state="disabled")

    def _on_export_csv(self):
        if not self.bot:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            try:
                self.bot.stats.export_csv(path)
                self._add_log(f"CSV report exported to {path}", "success")
                messagebox.showinfo("Success", f"Report exported to:\n{path}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")

    def _on_export_json(self):
        if not self.bot:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                self.bot.stats.export_json(path)
                self._add_log(f"JSON report exported to {path}", "success")
                messagebox.showinfo("Success", f"Report exported to:\n{path}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")

    def _on_reset_stats(self):
        if not self.bot:
            return
        if messagebox.askyesno("Confirm", "Reset all statistics? This cannot be undone."):
            self.bot.stats.reset()
            self._add_log("Statistics reset", "warn")
            self._refresh_report()

    # ── Status Bar ─────────────────────────────────────────────────────

    def _build_status_bar(self):
        frame = ctk.CTkFrame(self, fg_color=C_CARD, height=32, corner_radius=8)
        frame.pack_propagate(False)

        # Tip text
        self._tip_label = ctk.CTkLabel(
            frame, text="",
            font=make_font(10),
            text_color=C_TEXT_SEC,
        )
        self._tip_label.pack(side="left", padx=(14, 0))

        # Right side info
        self._status_right = ctk.CTkLabel(
            frame, text="",
            font=make_font(10),
            text_color=C_GRAY,
        )
        self._status_right.pack(side="right", padx=(0, 14))

        return frame

    def _update_tip(self):
        if hasattr(self, '_tip_label') and self._tip_label.winfo_exists():
            tip = random.choice(self._tips)
            self._tip_label.configure(text=tip)
        self.after(8000, self._update_tip)

    # ── Theme ──────────────────────────────────────────────────────────

    def _restore_theme(self):
        """Restore saved theme from config."""
        if not self.config:
            return
        saved_theme = self.config.get("gui", "theme", default="Dark")
        ctk.set_appearance_mode(saved_theme)
        try:
            if hasattr(self, '_theme_switch') and self._theme_switch.winfo_exists():
                if saved_theme == "Light":
                    self._theme_switch.select()
                else:
                    self._theme_switch.deselect()
        except Exception:
            pass

    def _toggle_theme(self):
        mode = self._theme_switch.get()
        ctk.set_appearance_mode(mode)
        # Save to config
        if self.config:
            self.config.data.setdefault("gui", {})
            self.config.data["gui"]["theme"] = mode
            self._save_config()

    # ── Auto Scrape Dialog ────────────────────────────────────────────

    def _on_auto_scrape(self):
        """Open the Auto Scrape Proxy dialog."""
        if not HAS_SCRAPER:
            messagebox.showerror(
                "Scraper Tidak Tersedia",
                "Modul proxy_scraper.py tidak ditemukan.\n"
                "Pastikan file proxy_scraper.py ada di folder yang sama."
            )
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("🌐 Auto Scrape Proxy")
        dialog.geometry("600x520")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        main = ctk.CTkFrame(dialog, fg_color=C_BG)
        main.pack(fill="both", expand=True, padx=16, pady=16)

        # Title
        ctk.CTkLabel(main, text="Auto Scrape Proxy",
                     font=make_font(16, "bold"),
                     text_color=C_CYAN).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(main,
                     text="Scrape proxy gratis dari " + str(len(get_source_names())) + " sumber internet.",
                     font=make_font(11), text_color=C_TEXT_SEC
                     ).pack(anchor="w", pady=(0, 12))

        # Protocol selection
        proto_frame = ctk.CTkFrame(main, fg_color=C_CARD, corner_radius=8)
        proto_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(proto_frame, text="  Pilih Protocol:",
                     font=make_font(11, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=12, pady=(8, 2))

        proto_row = ctk.CTkFrame(proto_frame, fg_color="transparent")
        proto_row.pack(fill="x", padx=12, pady=(2, 8))

        cb_http = ctk.CTkCheckBox(proto_row, text="HTTP", font=make_font(11),
                                   text_color=C_TEXT, fg_color=C_BLUE,
                                   border_color=C_TEXT_SEC)
        cb_http.select()
        cb_http.pack(side="left", padx=(0, 12))

        cb_https = ctk.CTkCheckBox(proto_row, text="HTTPS", font=make_font(11),
                                    text_color=C_TEXT, fg_color=C_GREEN,
                                    border_color=C_TEXT_SEC)
        cb_https.select()
        cb_https.pack(side="left", padx=(0, 12))

        cb_socks5 = ctk.CTkCheckBox(proto_row, text="SOCKS5", font=make_font(11),
                                     text_color=C_TEXT, fg_color=C_PURPLE,
                                     border_color=C_TEXT_SEC)
        cb_socks5.pack(side="left", padx=(0, 12))

        # Min proxy count
        count_frame = ctk.CTkFrame(main, fg_color=C_CARD, corner_radius=8)
        count_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(count_frame, text="  Minimum Proxy:",
                     font=make_font(11, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=12, pady=(8, 4))

        slider_frame = ctk.CTkFrame(count_frame, fg_color="transparent")
        slider_frame.pack(fill="x", padx=12, pady=(0, 10))

        min_proxy_slider = ctk.CTkSlider(slider_frame, from_=10, to=200,
                                           number_of_steps=19,
                                           progress_color=C_TEAL,
                                           button_color=C_TEAL)
        min_proxy_slider.set(50)
        min_proxy_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        min_proxy_lbl = ctk.CTkLabel(slider_frame, text="50",
                                      font=make_font(11, "bold"),
                                      text_color=C_TEAL, width=40)
        min_proxy_lbl.pack(side="left")
        min_proxy_slider.configure(
            command=lambda v: min_proxy_lbl.configure(text=str(int(v)))
        )

        # Progress area
        progress_frame = ctk.CTkFrame(main, fg_color=C_CARD, corner_radius=8)
        progress_frame.pack(fill="both", expand=True, pady=4)

        ctk.CTkLabel(progress_frame, text="  Progress:",
                     font=make_font(11, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=12, pady=(8, 2))

        progress_text = ctk.CTkTextbox(progress_frame, fg_color="transparent",
                                       font=make_font(11),
                                       text_color=C_TEXT,
                                       height=140, state="disabled")
        progress_text.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Progress bar
        progress_bar = ctk.CTkProgressBar(progress_frame, height=6,
                                           corner_radius=3,
                                           fg_color=C_CARD2,
                                           progress_color=C_CYAN)
        progress_bar.pack(fill="x", padx=12, pady=(0, 4))
        progress_bar.set(0)

        # Button row
        btn_row = ctk.CTkFrame(main, fg_color="transparent")
        btn_row.pack(fill="x", pady=(8, 0))

        start_btn = ctk.CTkButton(btn_row, text="▶ Mulai Scrape",
                                   command=lambda: self._start_scrape_thread(
                                       dialog, cb_http, cb_https, cb_socks5,
                                       min_proxy_slider, progress_text,
                                       progress_bar, start_btn
                                   ),
                                   fg_color=C_GREEN,
                                   hover_color=self._darken(C_GREEN),
                                   font=make_font(12, "bold"),
                                   corner_radius=6, height=34)
        start_btn.pack(side="left", padx=3)

        ctk.CTkButton(btn_row, text="Tutup",
                       command=dialog.destroy,
                       fg_color=C_GRAY,
                       font=make_font(11),
                       corner_radius=6, height=34).pack(side="left", padx=3)

    def _do_scrape(self, dialog, cb_http, cb_https, cb_socks5,
                     min_proxy_slider, progress_text, progress_bar, start_btn):
        """Run proxy scraping in background thread."""
        # Get selected protocols
        protocols = set()
        if cb_http.get():
            protocols.add("http")
        if cb_https.get():
            protocols.add("https")
        if cb_socks5.get():
            protocols.add("socks5")
        if not protocols:
            protocols = {"http", "https"}

        min_proxies = int(min_proxy_slider.get())

        def update_progress(msg, level="info"):
            """Update progress text from background thread."""
            self.after(0, lambda: self._append_scrape_progress(
                progress_text, msg, level, progress_bar
            ))

        start_btn.configure(state="disabled", text="⏳ Scraping...")
        update_progress(f"📡 Scraping {len(get_source_names())} sumber proxy...", "info")

        try:
            from proxy_scraper import scrape_and_save
            count = scrape_and_save(
                protocols=protocols,
                output_file=self.config.proxy_file or "proxy.txt",
                min_proxies=min_proxies,
                progress_callback=update_progress,
            )

            if count > 0:
                update_progress(f"\n✅ Scrape selesai! {count} proxy siap digunakan.", "success")
                # Reload proxy manager
                if self.bot:
                    self.bot.proxy_manager.load_from_file(
                        self.config.proxy_file or "proxy.txt"
                    )
                    # Enable proxies
                    self.config.data.setdefault("proxies", {})
                    self.config.data["proxies"]["enabled"] = True
                    self.config.save()
                update_progress("✅ Proxy enabled & siap dipakai!", "success")

                self._add_log(f"✅ Auto-scrape: {count} proxy siap", "success")
            else:
                update_progress("\n❌ Tidak ada proxy yang alive!", "error")

        except Exception as e:
            update_progress(f"\n❌ Error: {str(e)[:100]}", "error")
        finally:
            self.after(0, lambda: start_btn.configure(
                state="normal", text="▶ Mulai Scrape"
            ))

    def _append_scrape_progress(self, textbox, msg, level, progress_bar):
        """Append a line to the scrape progress textbox."""
        colors = {"success": C_GREEN, "info": C_TEXT, "warn": C_ORANGE, "error": C_RED}
        color = colors.get(level, C_TEXT)
        try:
            textbox.configure(state="normal")
            textbox.insert("end", msg + "\n")
            textbox.see("end")
            textbox.configure(state="disabled")
        except Exception:
            pass

    # ── Quick Setup Dialog ─────────────────────────────────────────────

    def _on_quick_setup(self):
        """Open a quick setup dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚡ Quick Setup")
        dialog.geometry("520x520")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        main = ctk.CTkFrame(dialog, fg_color=C_BG)
        main.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(main, text="Quick Setup",
                     font=make_font(16, "bold"),
                     text_color=C_CYAN).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(main, text="Isi data di bawah untuk memulai bot:",
                     font=make_font(11), text_color=C_TEXT_SEC
                     ).pack(anchor="w", pady=(0, 12))

        # Form fields
        fields_frame = ctk.CTkFrame(main, fg_color="transparent")
        fields_frame.pack(fill="x")

        def add_row(label, placeholder, default="", show=None):
            r = ctk.CTkFrame(fields_frame, fg_color="transparent")
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, font=make_font(11),
                         text_color=C_TEXT_SEC, width=120, anchor="w"
                         ).pack(side="left")
            e = ctk.CTkEntry(r, placeholder_text=placeholder,
                             font=make_font(11),
                             fg_color=C_CARD2, border_color=C_TEXT_SEC,
                             text_color=C_TEXT, show=show)
            e.insert(0, default)
            e.pack(side="right", fill="x", expand=True, padx=(8, 0))
            return e

        e_url = add_row("Target URL", "https://teknodill.blogspot.com")
        e_name = add_row("Name", "My Blog", "")
        e_visits = add_row("Visits", "500", "600")
        e_threads = add_row("Threads", "10", "10")

        # Checkboxes
        cb_discover = ctk.CTkCheckBox(main, text="Auto-Discover Articles",
                                      font=make_font(11),
                                      text_color=C_TEXT, fg_color=C_BLUE,
                                      border_color=C_TEXT_SEC)
        cb_discover.select()
        cb_discover.pack(anchor="w", padx=0, pady=6)

        cb_ad_click = ctk.CTkCheckBox(main, text="Click Ads",
                                      font=make_font(11),
                                      text_color=C_TEXT, fg_color=C_BLUE,
                                      border_color=C_TEXT_SEC)
        cb_ad_click.select()
        cb_ad_click.pack(anchor="w", padx=0, pady=2)

        # ETA label
        eta_lbl = ctk.CTkLabel(main, text="", font=make_font(10),
                               text_color=C_TEXT_SEC)
        eta_lbl.pack(anchor="w", pady=6)

        # Use StringVar for ETA updates
        visits_var = ctk.StringVar(value=e_visits.get())
        threads_var = ctk.StringVar(value=e_threads.get())
        e_visits.configure(textvariable=visits_var)
        e_threads.configure(textvariable=threads_var)

        def update_eta(*args):
            try:
                v = int(visits_var.get()) if visits_var.get().isdigit() else 0
                tr = int(threads_var.get()) if threads_var.get().isdigit() else 10
                if v > 0 and tr > 0:
                    eta_mins = (v * 45) / (tr * 60)
                    if eta_mins < 1:
                        eta_lbl.configure(text="⏳ Estimated time: < 1 minute")
                    else:
                        hr, mn = int(eta_mins // 60), int(eta_mins % 60)
                        eta_lbl.configure(text=f"⏳ Estimated time: ~{hr}h {mn}m" if hr > 0 else f"⏳ Estimated time: ~{mn} minutes")
            except Exception:
                pass

        visits_var.trace_add("write", update_eta)
        threads_var.trace_add("write", update_eta)
        update_eta()

        def do_quick_setup():
            url = e_url.get().strip()
            name = e_name.get().strip() or urlparse(url).netloc.replace("www.", "")
            if not url.startswith("http"):
                messagebox.showerror("Error", "URL tidak valid", parent=dialog)
                return

            visits = int(e_visits.get()) if e_visits.get().isdigit() else 600
            threads = int(e_threads.get()) if e_threads.get().isdigit() else 10
            discover = bool(cb_discover.get())
            ad_click = bool(cb_ad_click.get())

            # Update config
            if self.config:
                self.config.data.setdefault("general", {})
                self.config.data["general"]["threads"] = threads
                self.config.data["general"]["visit_duration_min"] = 30
                self.config.data["general"]["visit_duration_max"] = 80
                if not ad_click:
                    self.config.data.setdefault("ad_clicking", {})
                    self.config.data["ad_clicking"]["enabled"] = False
                self.config.save()

            # Initialize bot
            self.bot = TrafficBot(self.config) if self.config else None
            if self.bot:
                self.bot.add_target(name, url, weight=1, click_prob=0.3,
                                    ad_click_prob=0.25 if ad_click else 0.0,
                                    target_visits=visits, discover_articles=discover,
                                    article_distribution="random")

                # Discover articles
                if discover:
                    self._add_log(f"Discovering articles for {name}...", "info")
                    try:
                        for t in self.bot.targets:
                            if t.discover_articles:
                                self.bot._discover_articles_for(t)
                                self._add_log(f"  {t.name}: {len(t.articles)} articles found", "info")
                    except Exception as e:
                        self._add_log(f"Discover error: {e}", "error")

            self._refresh_targets_list()
            dialog.destroy()
            self._add_log(f"Quick setup: {name} → {url} ({visits} visits)", "success")

            # Auto-start
            self._on_start()

        ctk.CTkButton(main, text="▶ Start Bot", command=do_quick_setup,
                      fg_color=C_GREEN, hover_color=self._darken(C_GREEN),
                      font=make_font(13, "bold"),
                      corner_radius=8, height=36,
                      ).pack(pady=(12, 0))

    # ── Bot Control ────────────────────────────────────────────────────

    # ── Loading indicator ────────────────────────────────────────────

    def _show_loading(self, text="Starting..."):
        self._loading_label.configure(text=text)
        self._loading_dots = 0
        self._animate_loading()

    def _hide_loading(self):
        self._loading_label.configure(text="")
        self._loading_dots = -1  # stop animation

    def _animate_loading(self):
        if self._loading_dots < 0:
            return
        dots = "." * ((self._loading_dots % 3) + 1)
        self._loading_label.configure(text=f"⏳ Starting{dots}")
        self._loading_dots += 1
        self.after(500, self._animate_loading)

    # ── Bot Control ────────────────────────────────────────────────────

    def _on_start(self):
        if not self.bot or self._running:
            return
        if not self.bot.targets:
            messagebox.showwarning("No Targets", "Add a target first before starting.")
            return

        self._running = True
        self._paused = False
        self._bot_start_time = time.time()  # ← FIX: track when start was called

        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._btn_pause.configure(state="normal")
        self._btn_resume.configure(state="disabled")
        self._status_indicator.configure(text=" ● RUNNING", text_color=C_GREEN)
        self._show_loading("Starting...")

        self._add_log("Starting bot...", "info")

        # Start bot in background thread
        self._bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self._bot_thread.start()

        # Reset elapsed timer
        self._elapsed_start = time.time()
        self._update_elapsed()

    # ── Cycle tab ─────────────────────────────────────────────────────

    def _cycle_tab(self):
        """Cycle through tabs (Ctrl+Tab)."""
        tab_names = ["📊 Dashboard", "🎯 Targets", "⚙️ Config", "📋 Logs", "📈 Reports"]
        current = self._tab_view.get()
        try:
            idx = tab_names.index(current)
        except ValueError:
            idx = -1
        next_idx = (idx + 1) % len(tab_names)
        self._tab_view.set(tab_names[next_idx])

    def _run_bot(self):
        try:
            self.bot.start()
        except Exception as e:
            self.after(0, lambda: self._add_log(f"Bot error: {e}", "error"))
            self.after(0, self._on_stop)

    def _on_stop(self):
        if self.bot:
            try:
                self.bot.stop()
            except Exception:
                pass
        self._running = False
        self._paused = False

        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._btn_pause.configure(state="disabled")
        self._btn_resume.configure(state="disabled")
        self._status_indicator.configure(text=" ● STOPPED", text_color=C_RED)
        self._hide_loading()

        self._action_indicator.configure(text="")
        self._add_log("Bot stopped", "warn")
        self._refresh_report()

    def _on_pause(self):
        if self.bot and self._running:
            self.bot.pause()
            self._paused = True
            self._btn_pause.configure(state="disabled")
            self._btn_resume.configure(state="normal")
            self._status_indicator.configure(text=" ● PAUSED", text_color=C_ORANGE)
            self._add_log("Bot paused", "warn")

    def _on_resume(self):
        if self.bot and self._running:
            self.bot.resume()
            self._paused = False
            self._btn_pause.configure(state="normal")
            self._btn_resume.configure(state="disabled")
            self._status_indicator.configure(text=" ● RUNNING", text_color=C_GREEN)
            self._add_log("Bot resumed", "info")

    def _update_elapsed(self):
        if self._running:
            elapsed = time.time() - self._elapsed_start
            h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
            self._elapsed_label.configure(text=f"⏱ {h:02d}:{m:02d}:{s:02d}")
            self.after(1000, self._update_elapsed)

    # ── Pollers ────────────────────────────────────────────────────────

    def _poll_stats(self):
        if not self._polling:
            return

        if self._running and self.bot:
            try:
                status = self.bot.get_status()
                s = status.get("stats", {})
                self._stats_cache = status
                self._last_stats_time = time.time()

                # Update dashboard
                self._update_dashboard(s)

                # Update action indicator
                targets_st = status.get("targets", 0)
                campaigns_st = status.get("campaigns", [])
                if campaigns_st:
                    current_camp = campaigns_st[0]
                    pct = current_camp.get("progress", 0)
                    name = current_camp.get("name", "")
                    self._action_indicator.configure(
                        text=f"🎯 {name}: {pct:.0f}%" if pct > 0 else f"🎯 {name}: starting...",
                    )
                elif targets_st > 0:
                    total_v = s.get('total_visits', 0)
                    self._action_indicator.configure(
                        text=f"🌐 {total_v} visits so far"
                    )
                else:
                    self._action_indicator.configure(text="")

                # Update status bar
                self._status_right.configure(
                    text=f"Visits: {s.get('total_visits', 0)} | "
                         f"Rate: {s.get('success_rate', 0):.1f}% | "
                         f"Ads: {s.get('total_ads_clicked', 0)}/{s.get('total_ads_found', 0)}"
                )

                # Update scheduler status in dashboard (read from config directly)
                if hasattr(self, '_scheduler_status') and self.config:
                    try:
                        sched_enabled = self.config.get("scheduler", "enabled", default=False)
                        if sched_enabled:
                            mode = self.config.get("scheduler", "mode", default="interval")
                            if mode == "interval":
                                interval = self.config.get("scheduler", "interval_minutes", default=60)
                                self._scheduler_status.configure(
                                    text=f"⏰ Scheduler: ON (every {interval} min)",
                                    text_color=C_GREEN
                                )
                            else:
                                daily_time = self.config.get("scheduler", "daily_time", default="09:00")
                                runs = self.config.get("scheduler", "daily_runs", default=10)
                                self._scheduler_status.configure(
                                    text=f"⏰ Scheduler: ON ({daily_time}, {runs}x)",
                                    text_color=C_GREEN
                                )
                            running = self.scheduler.is_running() if self.scheduler else False
                            self._scheduler_next.configure(
                                text="● active" if running else "○ scheduled",
                                text_color=C_CYAN if running else C_TEXT_SEC
                            )
                        else:
                            self._scheduler_status.configure(
                                text="⏰ Scheduler: OFF", text_color=C_TEXT_SEC
                            )
                            self._scheduler_next.configure(text="")
                    except Exception:
                        pass

                # Hide loading once we have stats
                if self._loading_label.cget("text"):
                    self._hide_loading()

                # Check if bot stopped by itself (campaign complete)
                # FIX: only check after 3s grace period to avoid race condition
                if not self.bot.is_running and self._running:
                    elapsed_since_start = time.time() - getattr(self, '_bot_start_time', 0)
                    if elapsed_since_start > 3.0:
                        self.after(0, self._on_stop)
                        self.after(0, lambda: self._add_log("Bot completed all campaigns", "success"))
            except Exception:
                pass

        self.after(1000, self._poll_stats)

    def _poll_logs(self):
        if not self._polling:
            return

        # Drain log queue
        try:
            while True:
                msg = self._log_queue.get_nowait()
                # Parse level from message
                if "[SUCCESS]" in msg:
                    self._add_log(msg.split("[SUCCESS] ", 1)[-1], "success")
                elif "[WARN]" in msg:
                    self._add_log(msg.split("[WARN] ", 1)[-1], "warn")
                elif "[ERROR]" in msg:
                    self._add_log(msg.split("[ERROR] ", 1)[-1], "error")
                elif "[FAIL]" in msg:
                    self._add_log(msg.split("[FAIL] ", 1)[-1], "error")
                else:
                    self._add_log(msg.split("[INFO] ", 1)[-1] if "[INFO]" in msg else msg, "info")
        except queue.Empty:
            pass

        self.after(500, self._poll_logs)

    # ── Logging Setup ──────────────────────────────────────────────────

    def _setup_log_handler(self):
        """Install the GUI log handler on the project's logger."""
        root_logger = logging.getLogger("CPABot")
        for handler in root_logger.handlers[:]:
            if isinstance(handler, GUILogHandler):
                root_logger.removeHandler(handler)
        gui_handler = GUILogHandler(self._log_queue)
        root_logger.addHandler(gui_handler)
        self._log_handler = gui_handler

    # ── Cleanup ────────────────────────────────────────────────────────

    def _on_close(self):
        self._polling = False
        if self._running:
            if messagebox.askyesno("Confirm Exit", "Bot is running. Stop and exit?"):
                self._on_stop()
            else:
                return
        # Remove GUI log handler
        if self._log_handler:
            root_logger = logging.getLogger("CPABot")
            root_logger.removeHandler(self._log_handler)
        self.destroy()


# ═════════════════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════════════════

def main():
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)

    app = CPABotGUI()
    app._setup_log_handler()
    app.mainloop()


if __name__ == "__main__":
    main()
