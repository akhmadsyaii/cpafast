#!/usr/bin/env python3
import argparse
import json
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from urllib.parse import urlparse

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.columns import Columns
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.progress import BarColumn, Progress, TextColumn, SpinnerColumn
from rich.rule import Rule

from config import Config
from logger import logger
from traffic_bot import TrafficBot
from scheduler import Scheduler

console = Console()
bot = None
scheduler = None
config = None

# ── TUI State & Log Capture ──────────────────────────────────────────
cmd_queue = queue.Queue()
log_filter = "all"  # all, success, error, ad, info
visit_history = deque(maxlen=60)  # visits per minute for sparklines


class TuiLogHandler(logging.Handler):
    """Captures log messages for display in the TUI dashboard."""
    def __init__(self, maxlen=200):
        super().__init__()
        self.logs = deque(maxlen=maxlen)
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logs.append((record.levelname, msg))
        except Exception:
            pass


def _input_listener():
    """Read commands from stdin in a background thread for TUI mode."""
    while True:
        try:
            cmd = input().strip().lower()
            cmd_queue.put(cmd)
        except (EOFError, KeyboardInterrupt):
            break
        except Exception:
            break


# ── Session Save/Load ─────────────────────────────────────────────────
SESSION_DIR = "sessions"

def _ensure_session_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)

def _save_session(name: str, config_obj, targets_data: list, setup_info: dict = None):
    """Save current session to a JSON file."""
    _ensure_session_dir()
    session = {
        "name": name,
        "saved_at": datetime.now().isoformat(),
        "_path": config_obj.path,
        "config": config_obj.data,
        "targets": targets_data,
        "setup": setup_info or {},
    }
    path = os.path.join(SESSION_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(session, f, indent=2)
    return path

def _load_session(name: str) -> dict:
    """Load a session file and return its data."""
    path = os.path.join(SESSION_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def _list_sessions() -> list:
    """List available session names."""
    _ensure_session_dir()
    sessions = []
    if not os.path.isdir(SESSION_DIR):
        return sessions
    for fname in sorted(os.listdir(SESSION_DIR)):
        if fname.endswith(".json"):
            sessions.append(fname[:-5])
    return sessions


def _apply_session(session_data: dict) -> Config:
    """Apply a loaded session to a new Config object."""
    cfg = Config(session_data.get("_path", "config.json"))
    # Override config data with session data
    if "config" in session_data:
        cfg.data.update(session_data["config"])
    # If session has targets, update config
    if session_data.get("targets"):
        cfg.data["targets"] = session_data["targets"]
    cfg.save()
    return cfg


# ── Desktop Notification ──────────────────────────────────────────────
def _notify(title: str, message: str, urgency: str = "normal"):
    """Send desktop notification (notify-send) with terminal bell fallback."""
    # Terminal bell
    sys.stdout.write("\a")
    sys.stdout.flush()
    # notify-send
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, title, message],
            timeout=3, capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


# ── Config Editor ─────────────────────────────────────────────────────
def _config_editor(config_obj) -> bool:
    """Interactive config editor. Returns True if config was changed."""
    from rich.prompt import IntPrompt, FloatPrompt, Prompt as RichPrompt
    from rich.panel import Panel as RichPanel

    changed = False
    categories = [
        ("general", [
            ("threads", "🧵 Threads", "int"),
            ("min_delay", "⏱️  Min Delay (s)", "float"),
            ("max_delay", "⏱️  Max Delay (s)", "float"),
            ("visit_duration_min", "📖 Min Visit Dur (s)", "int"),
            ("visit_duration_max", "📖 Max Visit Dur (s)", "int"),
            ("timeout", "⏰ Timeout (s)", "int"),
            ("max_retries", "🔄 Max Retries", "int"),
            ("max_pages_per_session", "📄 Max Pages/Session", "int"),
        ]),
        ("proxies", [
            ("enabled", "🌐 Proxy Enabled", "bool"),
            ("test_before_use", "🧪 Test Before Use", "bool"),
            ("rotate_every_request", "🔄 Rotate Each Request", "bool"),
            ("sticky_session", "📎 Sticky Session", "bool"),
        ]),
        ("ad_clicking", [
            ("enabled", "📢 Ad Clicking", "bool"),
            ("probability", "🎯 Ad Click Probability", "float"),
            ("max_ads_per_visit", "🖱️  Max Ads/Visit", "int"),
            ("click_delay_min", "⏱️  Click Delay Min (s)", "float"),
            ("click_delay_max", "⏱️  Click Delay Max (s)", "float"),
            ("log_all_ads_found", "📋 Log All Ads", "bool"),
        ]),
        ("scheduler", [
            ("enabled", "⏰ Scheduler Enabled", "bool"),
            ("mode", "📋 Mode (interval/daily)", "str"),
            ("interval_minutes", "⏱️  Interval (min)", "int"),
            ("daily_time", "🕐 Daily Time (HH:MM)", "str"),
            ("daily_runs", "📊 Daily Runs", "int"),
        ]),
        ("behavior", [
            ("simulate_scroll", "📜 Simulate Scroll", "bool"),
            ("cookie_consent", "🍪 Cookie Consent", "bool"),
            ("multi_page_browsing", "📄 Multi-Page Browsing", "bool"),
            ("form_interaction", "📝 Form Interaction", "bool"),
        ]),
    ]

    while True:
        console.clear()
        console.print()
        console.print(RichPanel.fit(
            "[bold cyan]⚙️  Config Editor — Edit Settings Langsung dari TUI[/bold cyan]",
            border_style="bright_blue",
        ))
        console.print()

        cat_options = [f"{i+1}. {cat[0].replace('_',' ').title()}" for i, (cat, _) in enumerate(categories)]
        cat_options.append(f"{len(categories)+1}. 💾 Save & Exit")
        cat_options.append(f"{len(categories)+2}. ❌ Discard & Exit")

        console.print("[bold]Pilih kategori:[/bold]")
        for opt in cat_options:
            console.print(f"  {opt}")
        console.print()

        choice = RichPrompt.ask("[bold cyan]>[/bold cyan]", default="1")
        try:
            ci = int(choice) - 1
        except ValueError:
            continue

        if ci < 0 or ci >= len(categories):
            if ci == len(categories):  # Save & Exit
                config_obj.save()
                console.print("[green]✅ Config saved![/green]")
                time.sleep(1)
                return True
            elif ci == len(categories) + 1:  # Discard
                config_obj.load()  # Reload from file
                console.print("[yellow]Changes discarded[/yellow]")
                time.sleep(1)
                return False
            continue

        cat_name, fields = categories[ci]
        section = config_obj.data.get(cat_name, {})

        while True:
            console.clear()
            console.print()
            console.print(RichPanel.fit(
                f"[bold cyan]⚙️  {cat_name.replace('_',' ').title()}[/bold cyan]",
                border_style="blue",
            ))
            console.print()

            for i, (key, label, typ) in enumerate(fields):
                val = section.get(key, "-")
                if typ == "bool":
                    val_str = "[green]ON[/green]" if val else "[red]OFF[/red]"
                else:
                    val_str = f"[white]{val}[/white]"
                console.print(f"  [cyan]{i+1}.[/cyan] {label}: {val_str}")

            console.print()
            console.print(f"  [dim]0. Kembali[/dim]")
            console.print()

            f_choice = RichPrompt.ask("[bold cyan]>[/bold cyan]", default="0")
            try:
                fi = int(f_choice) - 1
            except ValueError:
                continue

            if fi < 0 or fi >= len(fields):
                break

            key, label, typ = fields[fi]
            current = section.get(key, "")

            console.print(f"[white]Current [cyan]{key}[/cyan]: [bold]{current}[/bold][/white]")

            if typ == "bool":
                new_val = Confirm.ask(f"[bold yellow]Enable {label}?[/bold yellow]", default=bool(current))
            elif typ == "int":
                new_val = IntPrompt.ask(f"[bold yellow]{label}[/bold yellow]", default=int(current) if current else 0)
            elif typ == "float":
                new_val = FloatPrompt.ask(f"[bold yellow]{label}[/bold yellow]", default=float(current) if current else 0.0)
            else:
                new_val = RichPrompt.ask(f"[bold yellow]{label}[/bold yellow]", default=str(current) if current else "")

            section[key] = new_val
            config_obj.data[cat_name] = section
            changed = True
            console.print(f"[green]✅ {label} → {new_val}[/green]")
            time.sleep(0.5)


def signal_handler(sig, frame):
    console.print("\n[yellow]Shutting down...[/yellow]")
    if bot:
        bot.stop()
    if scheduler:
        scheduler.stop()
    os._exit(0)


def cmd_start(args):
    global bot, scheduler
    bot.start(threads=args.threads)

    if config.scheduler_enabled:
        scheduler.set_callback(lambda: bot.start(threads=args.threads))
        scheduler.start()

    if args.daemon:
        try:
            while bot.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        display_dashboard(bot)


def cmd_stop(args):
    if bot and bot.is_running:
        bot.stop()
    if scheduler:
        scheduler.stop()
    console.print("[green]Bot stopped[/green]")


def cmd_pause(args):
    if bot:
        bot.pause()


def cmd_resume(args):
    if bot:
        bot.resume()


def cmd_status(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    status = bot.get_status()
    s = status["stats"]

    main_table = Table(title="Bot Status", box=box.ROUNDED)
    main_table.add_column("Metric", style="cyan")
    main_table.add_column("Value", style="green")
    main_table.add_row("Running", str(status["running"]))
    main_table.add_row("Paused", str(status["paused"]))
    main_table.add_row("Threads", str(status["threads"]))
    main_table.add_row("Targets", str(status["targets"]))
    pw_usable = status['proxies'].get('playwright_compatible', status['proxies']['alive'])
    proxy_label = f"{status['proxies']['alive']}/{status['proxies']['total']}"
    if pw_usable < status['proxies']['alive']:
        proxy_label += f" ({pw_usable} PW-compatible)"
    main_table.add_row("Proxies", proxy_label)
    main_table.add_row("Ad Clicking", "ON" if status["ad_clicking"] else "OFF")
    console.print(Panel.fit(Text("Bot Status", style="bold white on blue"), box=box.HEAVY))
    console.print(main_table)

    if status.get("campaigns"):
        camp_table = Table(title="Campaign Progress", box=box.ROUNDED)
        camp_table.add_column("Target", style="cyan")
        camp_table.add_column("Progress", style="green")
        camp_table.add_column("Articles", style="white")
        for c in status["campaigns"]:
            bar = Progress(
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                BarColumn(),
                transient=True,
            )
            task_id = bar.add_task("", total=c["target"], completed=c["completed"])
            camp_table.add_row(
                c["name"],
                f"{c['completed']}/{c['target']}",
                str(c["articles"]),
            )
        console.print(camp_table)

    v = Table(title="Visits", box=box.ROUNDED)
    v.add_column("Metric", style="cyan")
    v.add_column("Value", style="green")
    v.add_row("Total", str(s["total_visits"]))
    v.add_row("OK", str(s["successful"]))
    v.add_row("Fail", str(s["failed"]))
    v.add_row("Rate", f"{s['success_rate']}%")
    v.add_row("Resp", f"{s['avg_response_time']}s")
    v.add_row("/min", str(s["visits_per_minute"]))
    v.add_row("Pages", str(s.get("total_pages_visited", 0)))
    console.print(v)

    if s.get("total_ads_found", 0) > 0:
        a = Table(title="Ads", box=box.ROUNDED)
        a.add_column("Metric", style="cyan")
        a.add_column("Value", style="yellow")
        a.add_row("Found", str(s["total_ads_found"]))
        a.add_row("Clicked", str(s["total_ads_clicked"]))
        a.add_row("OK", str(s.get("ad_clicks_success", 0)))
        a.add_row("Fail", str(s.get("ad_clicks_failed", 0)))
        a.add_row("Click Rate", f"{s.get('ad_click_rate', 0)}%")
        console.print(a)

    if s.get("ad_type_stats"):
        t = Table(title="Ad Types", box=box.SIMPLE)
        t.add_column("Type", style="cyan")
        t.add_column("Clicks", style="yellow")
        for k, v in sorted(s["ad_type_stats"].items(), key=lambda x: -x[1]):
            t.add_row(k, str(v))
        console.print(t)

    if s.get("targets"):
        t = Table(title="Per Target", box=box.ROUNDED)
        t.add_column("Target", style="cyan")
        t.add_column("Visits", style="white")
        t.add_column("OK", style="green")
        t.add_column("Fail", style="red")
        t.add_column("Ads", style="yellow")
        for name, td in s["targets"].items():
            t.add_row(name, str(td["total"]), str(td["success"]),
                      str(td["fail"]),
                      f"{td.get('ads_clicked', 0)}/{td.get('ads_found', 0)}")
        console.print(t)


def cmd_targets(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    targets = bot.list_targets()
    if not targets:
        console.print("[yellow]No targets[/yellow]")
        return

    table = Table(title="Targets", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="green")
    table.add_column("Visits", style="yellow")
    table.add_column("Articles", style="white")
    table.add_column("Distrib.", style="white")
    table.add_column("Discover", style="white")

    for t in targets:
        url_str = t["url"][:40] + ".." if len(t["url"]) > 40 else t["url"]
        visits = str(t.get("target_visits", 0)) if t.get("target_visits") else "-"
        arts = str(len(t.get("articles", []))) if t.get("discover_articles") else "-"
        table.add_row(
            t["name"], url_str, visits, arts,
            t.get("article_distribution", "random"),
            "Y" if t.get("discover_articles") else "N",
        )
    console.print(table)


def cmd_add_target(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    bot.add_target(
        args.name, args.url, args.weight,
        args.click_prob, args.ad_click_prob,
        target_visits=args.visits,
        discover_articles=args.discover,
        article_distribution=args.distrib,
    )
    console.print(f"[green]Target '{args.name}' added[/green]" +
                  (f" | {args.visits} visits" if args.visits else "") +
                  (" | Article discovery ON" if args.discover else ""))


def cmd_remove_target(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    if bot.remove_target(args.name):
        console.print(f"[green]Removed '{args.name}'[/green]")
    else:
        console.print(f"[red]'{args.name}' not found[/red]")


def cmd_report(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    bot.stats.export()
    console.print(f"[green]Report -> {config.stats_path}/[/green]")


def cmd_reset_stats(args):
    if bot:
        bot.stats.reset()
        console.print("[green]Stats reset[/green]")


def cmd_test_proxies(args):
    from proxy_manager import ProxyManager
    pm = ProxyManager(config)
    alive, total = pm.test_all()
    console.print(f"Proxies: {alive}/{total} alive")


def cmd_add_proxy(args):
    """Add a single proxy manually."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    proxy_url = args.proxy_url
    if "://" not in proxy_url:
        proxy_url = f"http://{proxy_url}"
    if bot.proxy_manager.add_manual(proxy_url):
        console.print(f"[green]✅ Proxy ditambahkan: {proxy_url}[/green]")
        # Quick test
        alive, latency = bot.proxy_manager.test_single(proxy_url)
        if alive:
            console.print(f"   [green]✔ Proxy hidup ({latency:.3f}s)[/green]")
        else:
            console.print(f"   [yellow]⚠ Proxy tidak merespon (mungkin mati)[/yellow]")
    else:
        console.print(f"[yellow]⚠ Proxy sudah ada atau gagal ditambahkan: {proxy_url}[/yellow]")


def cmd_add_proxy_bulk(args):
    """Add multiple proxies from a file."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    filepath = args.file
    try:
        with open(filepath, "r") as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        if not urls:
            console.print("[yellow]File kosong[/yellow]")
            return
        added, dupes = bot.proxy_manager.add_manual_bulk(urls)
        console.print(f"[green]✅ {added} proxy ditambahkan[/green]" + (f" ({dupes} duplikat)" if dupes else ""))
    except FileNotFoundError:
        console.print(f"[red]File tidak ditemukan: {filepath}[/red]")


def cmd_remove_proxy(args):
    """Remove a proxy by URL."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    if bot.proxy_manager.remove_manual(args.proxy_url):
        console.print(f"[green]✅ Proxy dihapus: {args.proxy_url}[/green]")
    else:
        console.print(f"[yellow]Proxy tidak ditemukan: {args.proxy_url}[/yellow]")


def cmd_list_proxies(args):
    """List all proxies with status."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return

    proxies = bot.proxy_manager.list_manual()
    if not proxies:
        console.print("[yellow]Tidak ada proxy[/yellow]")
        return

    from rich.table import Table
    table = Table(title=f"📋 Proxies ({len(proxies)})", box=box.ROUNDED)
    table.add_column("URL", style="cyan")
    table.add_column("Alive", style="bold")
    table.add_column("Latency", style="white")
    table.add_column("OK/Fail", style="white")
    table.add_column("Score", style="yellow")
    for p in proxies:
        alive_str = "[green]✔[/green]" if p["alive"] else "[red]✘[/red]"
        lat = f"{p['latency']:.3f}s" if p['latency'] > 0 else "-"
        table.add_row(p['url'][:50], alive_str, lat,
                      f"{p['successes']}/{p['fails']}",
                      f"{p['score']:.2f}")
    console.print(table)

    # Also show rotating providers if any
    rot_status = bot.proxy_manager.get_rotating_status()
    if rot_status.get("active_count", 0) > 0:
        console.print()
        rot_table = Table(title="🌐 Rotating Providers", box=box.SIMPLE)
        rot_table.add_column("Provider", style="bold cyan")
        rot_table.add_column("Country", style="white")
        rot_table.add_column("Sticky", style="green")
        for p in rot_status.get("providers", []):
            rot_table.add_row(
                p["name"],
                p.get("country", "any") or "any",
                "[green]✔[/green]" if p.get("sticky") else "[dim]─[/dim]",
            )
        console.print(rot_table)


def cmd_rotating_add(args):
    """Add a rotating proxy provider."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return

    try:
        from rotating_providers import get_provider, list_providers
    except ImportError:
        console.print("[red]Module rotating_providers.py tidak ditemukan[/red]")
        return

    slug = args.provider.lower()
    provider = get_provider(slug)
    if not provider:
        console.print(f"[red]Provider '{slug}' tidak dikenal. Gunakan: [green]{', '.join(p['slug'] for p in list_providers())}[/green][/red]")
        return

    console.print()
    console.print(f"[bold cyan]🌐 Setting up {provider.name}[/bold cyan]")
    console.print(f"   [dim]{provider.description}[/dim]")
    console.print()

    # Build credentials based on auth format
    creds = {}
    if provider.auth_format == "customer_zone":
        creds["customer_id"] = Prompt.ask("[bold]Customer ID[/bold]")
        creds["zone"] = Prompt.ask("[bold]Zone name[/bold]")
        creds["password"] = Prompt.ask("[bold]Zone password[/bold]", password=True)
    elif provider.auth_format == "token":
        creds["token"] = Prompt.ask("[bold]API Token[/bold]", password=True)
    else:
        creds["username"] = Prompt.ask("[bold]Username[/bold]")
        creds["password"] = Prompt.ask("[bold]Password[/bold]", password=True)

    country = Prompt.ask("[bold]Country code (e.g. 'us', 'gb')[/bold]", default="")
    sticky = Confirm.ask("[bold]Sticky session?[/bold]", default=False)

    config_dict = {
        "provider": slug,
        "enabled": True,
        "credentials": creds,
        "country": country.strip(),
        "sticky_session": sticky,
        "session_ttl_minutes": 10,
    }

    # Test connection first
    console.print("[yellow]Testing connection...[/yellow]")
    success, elapsed, ip = bot.proxy_manager.test_rotating_provider(slug) if hasattr(bot.proxy_manager, 'test_rotating_provider') else (False, 0, "N/A")

    # If not configured yet, do a direct test
    if not config.get("proxies", {}).get("rotating_providers", []):
        from rotating_providers import RotatingProxyManager
        rpm = RotatingProxyManager()
        success, elapsed, ip = rpm.test_connection(slug, creds, country)

    if success:
        console.print(f"[green]✅ Connected via {ip} in {elapsed:.2f}s[/green]")
        if bot.proxy_manager.add_rotating_provider(config_dict):
            console.print(f"[green]✅ {provider.name} berhasil ditambahkan![/green]")
            console.print(f"   [dim]Proxy URL: {provider.default_host}:{provider.default_port}[/dim]")
        else:
            console.print("[red]Gagal menyimpan konfigurasi[/red]")
    else:
        console.print(f"[red]❌ Connection failed: {ip}[/red]")
        if Confirm.ask("[yellow]Tetap simpan?[/yellow]", default=False):
            if bot.proxy_manager.add_rotating_provider(config_dict):
                console.print(f"[green]✅ {provider.name} disimpan (tapi tidak terhubung)[/green]")


def cmd_rotating_remove(args):
    """Remove a rotating proxy provider."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    if bot.proxy_manager.remove_rotating_provider(args.provider):
        console.print(f"[green]✅ Provider '{args.provider}' dihapus[/green]")
    else:
        console.print(f"[yellow]Provider '{args.provider}' tidak ditemukan[/yellow]")


def cmd_rotating_test(args):
    """Test a rotating proxy provider connection."""
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return

    slug = args.provider
    success, elapsed, info = bot.proxy_manager.test_rotating_provider(slug)
    if success:
        console.print(f"[green]✅ {slug}: Connected via {info} ({elapsed:.2f}s)[/green]")
    else:
        console.print(f"[red]❌ {slug}: {info}[/red]")


def cmd_rotating_list(args):
    """List all available rotating proxy providers."""
    try:
        from rotating_providers import get_available_providers_text
        console.print(get_available_providers_text())
    except ImportError:
        console.print("[red]Module rotating_providers.py tidak ditemukan[/red]")


def cmd_reload_config(args):
    global config, bot
    config = Config(args.config)
    bot = TrafficBot(config)
    logger.setup(config)
    console.print("[green]Config reloaded[/green]")


def cmd_ad_stats(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    status = bot.get_status()
    s = status["stats"]

    a = Table(title="Ad Stats", box=box.ROUNDED)
    a.add_column("Metric", style="cyan")
    a.add_column("Value", style="yellow")
    a.add_row("Found", str(s.get("total_ads_found", 0)))
    a.add_row("Clicked", str(s.get("total_ads_clicked", 0)))
    a.add_row("OK", str(s.get("ad_clicks_success", 0)))
    a.add_row("Fail", str(s.get("ad_clicks_failed", 0)))
    a.add_row("Rate", f"{s.get('ad_click_rate', 0)}%")
    a.add_row("Ads/Visit", str(s.get("ads_per_visit", 0)))
    console.print(a)

    if s.get("ad_type_stats"):
        t = Table(title="By Type", box=box.SIMPLE)
        t.add_column("Type", style="cyan")
        t.add_column("Clicks", style="yellow")
        for k, v in sorted(s["ad_type_stats"].items(), key=lambda x: -x[1]):
            t.add_row(k, str(v))
        console.print(t)
    if s.get("ad_network_stats"):
        t = Table(title="By Network", box=box.SIMPLE)
        t.add_column("Network", style="cyan")
        t.add_column("Clicks", style="yellow")
        for k, v in sorted(s["ad_network_stats"].items(), key=lambda x: -x[1]):
            t.add_row(k, str(v))
        console.print(t)


def cmd_discover(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    name = args.name
    bot.discover_articles(name)
    if name:
        for t in bot.targets:
            if t.name == name:
                console.print(f"[green]Articles for '{name}': {len(t.articles)} found[/green]")
                for a in t.articles[:10]:
                    console.print(f"  {a}")
                if len(t.articles) > 10:
                    console.print(f"  ... and {len(t.articles) - 10} more")
                break
    else:
        for t in bot.targets:
            if t.articles:
                console.print(f"[green]{t.name}: {len(t.articles)} articles[/green]")


def cmd_campaigns(args):
    if not bot:
        console.print("[red]Bot not initialized[/red]")
        return
    status = bot.get_status()
    if not status.get("campaigns"):
        console.print("[yellow]No active campaigns[/yellow]")
        return
    table = Table(title="Campaigns", box=box.ROUNDED)
    table.add_column("Target", style="cyan")
    table.add_column("Progress", style="green")
    table.add_column("Articles", style="white")
    for c in status["campaigns"]:
        pct = c["progress"]
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        table.add_row(c["name"], f"{bar} {c['completed']}/{c['target']} ({pct}%)", str(c["articles"]))
    console.print(table)


def _status_icon(running, paused):
    if paused:
        return "⏸️  PAUSED"
    if running:
        return "▶️  RUNNING"
    return "⏹️  STOPPED"


def _progress_bar(pct: float, width: int = 18) -> str:
    filled = int(pct / 100 * width)
    bar = "━" * filled + "─" * (width - filled)
    return f"[bold green]{bar}[/bold green]"


def _build_header(status: dict, s: dict) -> Panel:
    now = datetime.now().strftime("%H:%M:%S")
    icon = _status_icon(status["running"], status["paused"])
    mode = "🎯 CAMPAIGN" if status.get("campaigns") else "🌐 TRAFFIC"
    elapsed = s["elapsed_seconds"]
    elapsed_str = f"{int(elapsed // 3600):02d}:{int((elapsed % 3600) // 60):02d}:{int(elapsed % 60):02d}"

    header_text = Text()
    header_text.append("  CPA Traffic Bot  ", style="bold white on #0055ff")
    header_text.append(f"  {icon}  ", style="bold white on #ff6600" if status["paused"] else "bold white on #00cc44")
    header_text.append(f"  {mode}  ", style="bold white on #6600cc")
    header_text.append(f"  ⏱️ {elapsed_str}  ", style="bold white on #333333")
    header_text.append(f"  🕐 {now}  ", style="bold white on #222222")

    return Panel(header_text, box=box.HEAVY, border_style="bright_blue",
                 padding=(0, 1))


def _build_stats_table(status: dict, s: dict) -> Panel:
    vpm = s["visits_per_minute"]
    rate = s["success_rate"]
    rate_style = "green" if rate >= 80 else "yellow" if rate >= 50 else "red"

    # Calculate ETA
    total_visits = s["total_visits"] if "total_visits" in s else 0
    campaigns = status.get("campaigns", [])
    target_total = max(c["target"] for c in campaigns) if campaigns else 0
    completed = max(c["completed"] for c in campaigns) if campaigns else total_visits
    remaining = max(0, target_total - completed) if target_total > 0 else 0

    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2),
                  border_style="cyan")
    table.add_column("", style="bold cyan", no_wrap=True)
    table.add_column("", style="bold white")

    table.add_row("🎯 Targets", f"{status['targets']}")
    table.add_row("🧵 Threads", f"{status['threads']}")
    table.add_row("")
    table.add_row("📥 Total Visits", f"[bold bright_white]{s['total_visits']}[/bold bright_white]")
    table.add_row("   ✅ Success", f"[green]{s['successful']}[/green]")
    table.add_row("   ❌ Failed", f"[red]{s['failed']}[/red]")
    table.add_row("   📈 Success Rate", f"[{rate_style}]{rate}%[/{rate_style}]")
    table.add_row("")
    table.add_row("⚡ Response Time", f"{s['avg_response_time']}s")
    table.add_row("🚀 Visits/min", f"[bold yellow]{vpm}[/bold yellow]")
    table.add_row("📄 Pages Viewed", str(s.get("total_pages_visited", 0)))
    table.add_row("⏱️ Elapsed", f"{s['elapsed_seconds']:.0f}s")
    if remaining > 0:
        eta_sec = (remaining / vpm) * 60 if vpm > 0 else 999999
        eta_str = f"{int(eta_sec // 60)}m" if eta_sec < 3600 else f"{int(eta_sec // 3600)}j {int((eta_sec % 3600) // 60)}m"
        table.add_row("", "")
        table.add_row("🎯 Sisa", f"[bold yellow]{remaining}[/bold yellow]")
        table.add_row("⏳ ETA", f"[bold green]{eta_str}[/bold green]")

    return Panel(
        table,
        title="[bold white on blue] 📊 Live Statistics [/bold white on blue]",
        border_style="bright_blue", box=box.ROUNDED, padding=(1, 1),
    )


def _build_status_bars(s: dict) -> Panel:
    total = s["total_visits"]
    ok = s["successful"]
    fail = s["failed"]
    success_rate = s["success_rate"]
    ads_found = s.get("total_ads_found", 0)
    ads_clicked = s.get("total_ads_clicked", 0)

    progress = Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None, complete_style="green", finished_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        expand=True,
    )

    task_ok = progress.add_task("[green]Success Rate", total=100, completed=success_rate)
    task_ad = progress.add_task("[yellow]Ad Click Rate", total=100,
                                completed=s.get("ad_click_rate", 0))

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    table.add_column("", style="bold")
    table.add_column("", style="")

    if total > 0:
        ok_bar = "━" * max(1, int(ok / total * 20)) + "─" * max(0, 20 - int(ok / total * 20))
        table.add_row("✅ OK", f"[green]{ok_bar}[/green] {ok}")
        if fail > 0:
            fail_pct = fail / total * 20
            fail_bar = "━" * max(1, int(fail_pct)) + "─" * max(0, 20 - int(fail_pct))
            table.add_row("❌ Fail", f"[red]{fail_bar}[/red] {fail}")

    if ads_found > 0:
        click_pct = ads_clicked / ads_found * 20
        ad_bar = "━" * max(1, int(click_pct)) + "─" * max(0, 20 - int(click_pct))
        table.add_row("🖱️ Ads", f"[yellow]{ad_bar}[/yellow] {ads_clicked}/{ads_found}")

    content = Columns([progress, table])
    return Panel(
        content,
        title="[bold white on green] 📈 Performance [/bold white on green]",
        border_style="green", box=box.ROUNDED, padding=(1, 1),
    )


def _build_campaign_panel(status: dict) -> Panel:
    if not status.get("campaigns"):
        proxies = status["proxies"]
        proxy_text = f"{proxies['alive']}/{proxies['total']}"

        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("", style="bold cyan")
        table.add_column("", style="white")
        table.add_row("🎯 Targets Active", str(status["targets"]))
        pw_usable = proxies.get("playwright_compatible", proxies["alive"])
        pw_suffix = f" ({pw_usable} PW)" if pw_usable < proxies["alive"] else ""
        table.add_row("🌐 Proxies Alive", f"[green]{proxy_text}{pw_suffix}[/green]" if proxies["alive"] > 0 else "[red]0[/red]")
        table.add_row("🖱️ Ad Clicking", "[green]ON[/green]" if status["ad_clicking"] else "[red]OFF[/red]")

        return Panel(
            table,
            title="[bold white on yellow] ℹ️  System Info [/bold white on yellow]",
            border_style="yellow", box=box.ROUNDED, padding=(1, 1),
        )

    table = Table(box=box.ROUNDED, border_style="cyan", padding=(0, 1))
    table.add_column("🎯 Campaign", style="bold cyan", no_wrap=True)
    table.add_column("Progress", style="white", no_wrap=True)
    table.add_column("Done", style="bold green", justify="right")
    table.add_column("Articles", style="blue", justify="right")

    for c in status["campaigns"]:
        pct = c["progress"]
        bar = _progress_bar(pct)
        table.add_row(
            c["name"][:18],
            f"{bar} [bold]{pct:.0f}%[/bold]",
            f"{c['completed']}/{c['target']}",
            str(c["articles"]),
        )

    return Panel(
        table,
        title="[bold white on cyan] 🎯 Campaign Progress [/bold white on cyan]",
        border_style="cyan", box=box.ROUNDED, padding=(1, 1),
    )


def _build_ad_panel(s: dict) -> Panel:
    ads_found = s.get("total_ads_found", 0)
    ads_clicked = s.get("total_ads_clicked", 0)

    if ads_found == 0 and not s.get("ad_type_stats"):
        return Panel(
            Text("🛑 No ad activity yet", style="dim"),
            title="[bold white on yellow] 📢 Ad Activity [/bold white on yellow]",
            border_style="yellow", box=box.ROUNDED, padding=(1, 1),
        )

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("", style="bold cyan")
    table.add_column("", style="white")

    table.add_row("📢 Ads Found", str(ads_found))
    table.add_row("🖱️ Ads Clicked", str(ads_clicked))
    table.add_row("✅ Clicks OK", str(s.get("ad_clicks_success", 0)))
    table.add_row("❌ Clicks Fail", str(s.get("ad_clicks_failed", 0)))
    table.add_row("📊 Click Rate", f"[yellow]{s.get('ad_click_rate', 0)}%[/yellow]")

    if s.get("ad_type_stats"):
        table.add_row("", "")
        for k, v in sorted(s["ad_type_stats"].items(), key=lambda x: -x[1])[:5]:
            icon = {"display": "🖥️", "native": "📰", "banner": "🎪", "sponsored_link": "💼",
                    "popup": "🪟", "image_ad": "🖼️", "iframe": "📦", "link": "🔗"}.get(k, "📌")
            table.add_row(f"  {icon} {k[:12]}", str(v))

    return Panel(
        table,
        title="[bold white on yellow] 📢 Ad Activity [/bold white on yellow]",
        border_style="yellow", box=box.ROUNDED, padding=(1, 1),
    )


def _build_target_table(s: dict) -> Panel:
    targets = s.get("targets")
    if not targets:
        return Panel(
            Text("No target data", style="dim"),
            title="[bold white on blue] 🌐 Per Target [/bold white on blue]",
            border_style="blue", box=box.ROUNDED,
        )

    table = Table(box=box.SIMPLE, border_style="blue", padding=(0, 1))
    table.add_column("Target", style="bold cyan", no_wrap=True)
    table.add_column("OK", style="green", justify="right")
    table.add_column("Fail", style="red", justify="right")
    table.add_column("Rate", style="white", justify="right")
    table.add_column("Ads", style="yellow", justify="right")

    for name, td in targets.items():
        total = td["total"]
        r = (td["success"] / total * 100) if total > 0 else 0
        rate_style = "green" if r >= 80 else "yellow" if r >= 50 else "red"
        ads_str = f"{td.get('ads_clicked', 0)}/{td.get('ads_found', 0)}" if td.get('ads_found', 0) > 0 else "-"
        table.add_row(
            name[:16],
            str(td["success"]),
            str(td["fail"]),
            f"[{rate_style}]{r:.0f}%[/{rate_style}]",
            ads_str,
        )

    return Panel(
        table,
        title="[bold white on blue] 🌐 Per Target [/bold white on blue]",
        border_style="blue", box=box.ROUNDED, padding=(1, 1),
    )


def _tip_line() -> str:
    tips = [
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
    return tips[int(time.time() / 5) % len(tips)]


def _build_log_panel(tui_handler: TuiLogHandler, log_filter_state: str = "all") -> Panel:
    """Build a panel showing recent log messages with optional filter."""
    logs = list(tui_handler.logs)
    if not logs:
        return Panel(
            Text("No logs yet", style="dim"),
            title="[bold white on #333] 📋 Activity [/bold white on #333]",
            border_style="#555", box=box.ROUNDED, padding=(1, 1),
        )

    # Apply filter
    if log_filter_state == "success":
        filtered = [l for l in logs if "SUCCESS" in l[1]]
    elif log_filter_state == "error":
        filtered = [l for l in logs if "FAIL" in l[1] or "ERROR" in l[1] or "WARN" in l[1]]
    elif log_filter_state == "ad":
        filtered = [l for l in logs if "AD" in l[1] or "CLICK" in l[1] or "CPA" in l[1] or "Ads" in l[1]]
    else:
        filtered = logs

    if not filtered:
        return Panel(
            Text(f"  No {log_filter_state} logs", style="dim"),
            title="[bold white on #333] 📋 Activity [/bold white on #333]",
            border_style="#555", box=box.ROUNDED, padding=(1, 1),
        )

    # Show last 8 logs with filter
    recent = filtered[-8:]
    lines = []
    for level, msg in recent:
        content = msg[25:] if len(msg) > 25 else msg  # Skip timestamp + [LEVEL] + space
        if "SUCCESS" in msg:
            lines.append(f"  [green]{content[:80]}[/green]")
        elif "FAIL" in msg or "ERROR" in msg:
            lines.append(f"  [red]{content[:80]}[/red]")
        elif "WARN" in msg:
            lines.append(f"  [yellow]{content[:80]}[/yellow]")
        elif "AD" in msg or "CLICK" in msg or "CPA" in msg:
            lines.append(f"  [bright_yellow]{content[:80]}[/bright_yellow]")
        else:
            lines.append(f"  [white]{content[:80]}[/white]")

    # Filter indicator
    filter_labels = {"all": "[1]All", "success": "[2]OK", "error": "[3]Err", "ad": "[4]Ad"}
    current_label = filter_labels.get(log_filter_state, "[1]All")
    title_str = f"[bold white on #333] 📋 {current_label} [/bold white on #333]"

    return Panel(
        Text("\n".join(lines)),
        title=title_str,
        border_style="#555", box=box.ROUNDED, padding=(1, 1),
    )


def _build_scheduler_panel(sched: Scheduler, config_obj, visit_history: deque = None) -> Panel:
    """Build a panel showing scheduler, proxy status & sparklines."""
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("", style="bold cyan")
    table.add_column("", style="white")

    # Scheduler
    sched_enabled = config_obj.get("scheduler", "enabled", default=False) if config_obj else False
    if sched_enabled:
        mode = config_obj.get("scheduler", "mode", default="interval")
        if mode == "interval":
            interval = config_obj.get("scheduler", "interval_minutes", default=60)
            table.add_row("⏰ Scheduler", f"[green]ON[/green] (every {interval}min)")
        else:
            daily = config_obj.get("scheduler", "daily_time", default="09:00")
            runs = config_obj.get("scheduler", "daily_runs", default=10)
            table.add_row("⏰ Scheduler", f"[green]ON[/green] ({daily}, {runs}x)")
        sched_running = sched.is_running() if sched else False
        table.add_row("   Status", "[green]● active[/green]" if sched_running else "[yellow]○ waiting[/yellow]")
    else:
        table.add_row("⏰ Scheduler", "[dim]OFF[/dim]")

    table.add_row("", "")

    # Proxy info from status if bot available
    if bot:
        try:
            st = bot.get_status()
            p = st.get("proxies", {})
            if p.get("enabled"):
                alive, total = p.get("alive", 0), p.get("total", 0)
                pw = p.get("playwright_compatible", alive)
                color = "green" if alive > 0 else "red"
                label = f"[{color}]{alive}/{total}[/{color}] alive"
                if pw < alive:
                    label += f" [dim]({pw} for PW)[/dim]"
                table.add_row("🌐 Proxies", label)
                if alive > 0:
                    # Show estimated proxy rotation
                    if bot and hasattr(bot, 'proxy_manager'):
                        total_proxies = bot.proxy_manager.count
                        pw_usable = bot.proxy_manager.playwright_usable_count
                        if pw_usable < alive:
                            table.add_row("   ✅ PW", f"[green]{pw_usable}[/green] compatible")
                        table.add_row("   Total", str(total_proxies))
            else:
                table.add_row("🌐 Proxies", "[dim]Disabled[/dim]")
        except Exception:
            pass

    # ── Sparklines ─────────────────────────────────────────────────────
    if visit_history and len(visit_history) > 1:
        table.add_row("", "")
        max_v = max(visit_history)
        if max_v > 0:
            spark = ""
            for v in visit_history:
                h = max(1, int(v / max_v * 5))
                blocks = ["⣀", "⣄", "⣤", "⣦", "⣶", "⣾"][min(h - 1, 5)]
                spark += f"[green]{blocks}[/green]"
            table.add_row("📈 Trend", spark + f" [dim]{max_v}/m[/dim]")

    return Panel(
        table,
        title="[bold white on #555] ⚙️  System & Trend [/bold white on #555]",
        border_style="#555", box=box.ROUNDED, padding=(1, 1),
    )


def _process_tui_cmd(cmd: str, bot_instance, running_flag) -> bool:
    """Process a TUI command. Returns False if should quit."""
    global log_filter
    
    if cmd in ('q', 'quit', 'exit'):
        bot_instance.stop()
        return False
    elif cmd in ('p', 'pause', ' '):
        if bot_instance.is_paused:
            bot_instance.resume()
        else:
            bot_instance.pause()
    elif cmd in ('s', 'stop'):
        bot_instance.stop()
    elif cmd in ('h', 'help', '?'):
        console.print(Panel.fit(
            "[bold cyan]TUI Keyboard Commands:[/bold cyan]\n"
            "  [green]p[/green] / [green]Space[/green]  Pause/Resume bot\n"
            "  [green]s[/green] / [green]stop[/green]    Stop bot\n"
            "  [green]q[/green] / [green]quit[/green]    Quit TUI\n"
            "  [green]h[/green] / [green]?[/green]       Show this help\n"
            "  [green]1[/green]          Filter logs: All\n"
            "  [green]2[/green]          Filter logs: Success only\n"
            "  [green]3[/green]          Filter logs: Errors only\n"
            "  [green]4[/green]          Filter logs: Ad activity only\n"
            "  [green]c[/green]          Open Config Editor\n"
            "  [green]<Enter>[/green]    Refresh display",
            border_style="bright_blue",
        ))
        time.sleep(2)
        return True
    elif cmd == '1':
        log_filter = "all"
    elif cmd == '2':
        log_filter = "success"
    elif cmd == '3':
        log_filter = "error"
    elif cmd == '4':
        log_filter = "ad"
    elif cmd == 'c':
        bot_instance.pause()
        _config_editor(bot_instance.config if hasattr(bot_instance, 'config') else config)
        bot_instance.resume()
    return True


def display_dashboard(bot_instance, tui_handler: TuiLogHandler = None,
                      scheduler_instance=None, config_obj=None):
    """
    Live Rich dashboard with optional interactive controls.
    If tui_handler is provided, keyboard controls & log panel are enabled.
    """
    global log_filter, visit_history
    
    use_interactive = tui_handler is not None
    
    # Start input listener for interactive mode
    if use_interactive:
        listener = threading.Thread(target=_input_listener, daemon=True)
        listener.start()

    # Track last visit count for sparklines
    last_visits = 0
    last_tick_time = time.time()
    tick_visits = 0

    try:
        with Live(refresh_per_second=2, screen=True) as live:
            while bot_instance.is_running:
                # Process keyboard commands (interactive mode)
                if use_interactive:
                    try:
                        while True:
                            cmd = cmd_queue.get_nowait()
                            if not _process_tui_cmd(cmd, bot_instance, None):
                                return
                    except queue.Empty:
                        pass

                status = bot_instance.get_status()
                s = status["stats"]

                # ── Sparkline tracking ────────────────────────────────
                current_visits = s["total_visits"]
                new_visits = current_visits - last_visits
                now = time.time()
                tick_visits += new_visits
                if now - last_tick_time >= 3.0:
                    vpm_estimate = tick_visits / ((now - last_tick_time) / 60.0)
                    visit_history.append(int(vpm_estimate))
                    last_tick_time = now
                    tick_visits = 0
                last_visits = current_visits

                layout = Layout()
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="body"),
                    Layout(name="footer", size=3),
                )

                layout["header"].update(_build_header(status, s))

                body = Layout()
                body.split(
                    Layout(name="top"),
                    Layout(name="bottom"),
                )

                if use_interactive:
                    # 3-column top: stats | campaign | system
                    top = Layout()
                    top.split_row(
                        Layout(name="stats"),
                        Layout(name="campaign"),
                        Layout(name="system"),
                    )
                    top["stats"].update(_build_stats_table(status, s))
                    top["campaign"].update(_build_campaign_panel(status))
                    top["system"].update(_build_scheduler_panel(
                        scheduler_instance, config_obj, visit_history
                    ))

                    # 4-column bottom: perf | ads | targets | logs
                    bottom = Layout()
                    bottom.split_row(
                        Layout(name="perf"),
                        Layout(name="ads"),
                        Layout(name="targets"),
                        Layout(name="logs"),
                    )
                    bottom["perf"].update(_build_status_bars(s))
                    bottom["ads"].update(_build_ad_panel(s))
                    bottom["targets"].update(_build_target_table(s))
                    bottom["logs"].update(_build_log_panel(tui_handler, log_filter))
                else:
                    top = Layout()
                    top.split_row(
                        Layout(name="stats"),
                        Layout(name="campaign"),
                    )
                    top["stats"].update(_build_stats_table(status, s))
                    top["campaign"].update(_build_campaign_panel(status))

                    bottom = Layout()
                    bottom.split_row(
                        Layout(name="perf"),
                        Layout(name="ads"),
                        Layout(name="targets"),
                    )
                    bottom["perf"].update(_build_status_bars(s))
                    bottom["ads"].update(_build_ad_panel(s))
                    bottom["targets"].update(_build_target_table(s))

                body["top"].update(top)
                body["bottom"].update(bottom)
                layout["body"].update(body)

                # Footer with controls or tips
                tip = _tip_line()
                paused_text = "⏸️  PAUSED — Type [bold]p[/bold] to resume" if status["paused"] else ""
                if use_interactive:
                    filter_hint = {"all": "", "success": " [dim]| [2]Filter: OK[/dim]",
                                   "error": " [dim]| [3]Filter: Err[/dim]",
                                   "ad": " [dim]| [4]Filter: Ad[/dim]"}
                    fh = filter_hint.get(log_filter, "")
                    controls = f"[bold cyan]⌨️[/bold cyan] [green]p[/green]ause  [green]s[/green]top  [green]q[/green]uit  [green]h[/green]elp  [green]1-4[/green]log{fh}"
                    if paused_text:
                        footer_content = f"{paused_text}  |  {controls}"
                    else:
                        footer_content = f"{tip}  |  {controls}"
                else:
                    footer_content = f"{tip}  |  {paused_text}" if paused_text else tip

                layout["footer"].update(Panel(
                    Text(footer_content, style="bold white on #333333"),
                    box=box.HEAVY, border_style="bright_blue",
                ))

                live.update(layout)
                time.sleep(0.5)
    except KeyboardInterrupt:
        bot_instance.stop()


def _estimate_eta(total_visits: int, threads: int, visit_dur_min: int, visit_dur_max: int,
                   completed: int = 0) -> str:
    remaining = total_visits - completed
    if remaining <= 0:
        return "0 menit"
    avg_dur = (visit_dur_min + visit_dur_max) / 2
    effective_threads = max(threads, 1)
    est_seconds = (remaining * avg_dur) / effective_threads
    est_minutes = est_seconds / 60
    if est_minutes < 1:
        return "< 1 menit"
    hr = int(est_minutes // 60)
    mn = int(est_minutes % 60)
    if hr > 0:
        return f"~{hr}j {mn}m"
    return f"~{mn} menit"


def cmd_quick(args):
    """Quick setup with simple dashboard (no interactive controls)."""
    global bot, config, scheduler

    config = Config(args.config)

    console.print()
    console.print(Panel.fit(
        "[bold cyan]╭──────────────────────────────────────────╮\n"
        "│         🚀  CPA Traffic Bot Quick Setup      │\n"
        "│         Isi data di bawah untuk mulai        │\n"
        "╰──────────────────────────────────────────╯[/bold cyan]",
        border_style="bright_blue",
    ))
    console.print()

    url = Prompt.ask("[bold cyan]🌐[/bold cyan] [white]Link target[/white]", default="")
    while not url.startswith("http"):
        url = Prompt.ask("[bold red]❌[/bold red] [white]Link harus valid (https://...)[/white]")
    name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama target[/white]",
                       default=urlparse(url).netloc.replace("www.", ""))

    visits = IntPrompt.ask("[bold cyan]🎯[/bold cyan] [white]Jumlah visitor[/white]", default=600)
    threads = IntPrompt.ask("[bold cyan]🧵[/bold cyan] [white]Threads[/white]", default=10)
    discover = Confirm.ask("[bold cyan]📰[/bold cyan] [white]Auto-discover artikel?[/white]", default=True)
    ad_click = Confirm.ask("[bold cyan]🖱️[/bold cyan] [white]Klik iklan?[/white]", default=True)
    dur_min = IntPrompt.ask("[bold cyan]⏱️[/bold cyan] [white]Durasi baca minimal (detik)[/white]", default=30)
    dur_max = IntPrompt.ask("[bold cyan]⏱️[/bold cyan] [white]Durasi baca maksimal (detik)[/white]", default=80)

    if dur_max < dur_min:
        dur_min, dur_max = dur_max, dur_min

    # Count proxies
    proxy_count = 0
    proxy_file = config.get("proxies", "file")
    if proxy_file:
        try:
            with open(proxy_file) as f:
                proxy_count = sum(1 for line in f if line.strip() and not line.startswith("#"))
        except FileNotFoundError:
            pass

    eta = _estimate_eta(visits, threads, dur_min, dur_max)

    console.print()
    console.print(Rule(style="bright_blue"))
    console.print()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", justify="right")
    summary.add_column(style="white")
    summary.add_row("Target", f"[green]{name}[/green]")
    summary.add_row("URL", f"[blue]{url}[/blue]")
    summary.add_row("Visitor", f"[bold yellow]{visits}[/bold yellow]")
    summary.add_row("Threads", str(threads))
    summary.add_row("Durasi", f"{dur_min}-{dur_max} detik")
    summary.add_row("Discover", "[green]ON[/green]" if discover else "[red]OFF[/red]")
    summary.add_row("Klik Iklan", "[green]ON[/green]" if ad_click else "[red]OFF[/red]")
    summary.add_row("Proxy tersedia", str(proxy_count))
    summary.add_row("Estimasi selesai", f"[bold green]{eta}[/bold green]")

    console.print(Panel(
        summary,
        title="[bold white on blue] 📋 Ringkasan Setup [/bold white on blue]",
        border_style="blue", box=box.ROUNDED,
    ))

    console.print()
    if not Confirm.ask("[bold yellow]✅[/bold yellow] [white]Lanjutkan?[/white]", default=True):
        console.print("[red]Dibatalkan[/red]")
        return

    # ── MULTI-TARGET SUPPORT: loop untuk tambah target ────────────────
    config.data["targets"] = []
    config.save()

    # Apply settings to config
    config.data["general"]["threads"] = threads
    config.data["general"]["visit_duration_min"] = dur_min
    config.data["general"]["visit_duration_max"] = dur_max
    if not ad_click:
        config.data["ad_clicking"]["enabled"] = False
    config.save()

    # Add first target
    targets_added = []
    targets_added.append((name, url, visits, discover, ad_click))

    # Loop untuk tambah target tambahan
    while True:
        console.print()
        more_url = Prompt.ask("[bold cyan]➕[/bold cyan] [white]Link target lainnya? (Enter untuk skip)[/white]", default="")
        if not more_url:
            break
        while not more_url.startswith("http"):
            more_url = Prompt.ask("[bold red]❌[/bold red] [white]Link harus valid (https://...)[/white]")
        more_name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama target[/white]",
                               default=urlparse(more_url).netloc.replace("www.", ""))
        more_visits = IntPrompt.ask("[bold cyan]🎯[/bold cyan] [white]Jumlah visitor[/white]", default=visits)
        more_discover = Confirm.ask("[bold cyan]📰[/bold cyan] [white]Auto-discover artikel?[/white]", default=True)
        more_ad_click = Confirm.ask("[bold cyan]🖱️[/bold cyan] [white]Klik iklan?[/white]", default=True)
        targets_added.append((more_name, more_url, more_visits, more_discover, more_ad_click))
        console.print(f"[green]✅ Target '{more_name}' ditambahkan ke antrian[/green]")

    # Inisialisasi bot dan tambah semua target
    bot = TrafficBot(config)
    for t_name, t_url, t_visits, t_discover, t_ad_click in targets_added:
        bot.add_target(
            t_name, t_url, weight=1,
            click_prob=0.3,
            ad_click_prob=0.25 if t_ad_click else 0.0,
            target_visits=t_visits,
            discover_articles=t_discover,
            article_distribution="random",
        )

    scheduler = Scheduler(config)
    logger.setup(config)

    # Discover articles for all targets
    if any(td[3] for td in targets_added):
        console.print("[cyan]📡 Mendiscover artikel...[/cyan]")
        for t in bot.targets:
            if t.discover_articles:
                bot.discover_articles(t.name)
                console.print(f"   [green]→ {t.name}: {len(t.articles)} artikel ditemukan[/green]")

    console.print(f"[green]🚀 Memulai bot dengan {len(targets_added)} target...[/green]")
    bot.start(threads=threads)
    display_dashboard(bot)


def _show_summary(bot_instance, elapsed_seconds: float):
    """Show a summary report after bot stops."""
    try:
        status = bot_instance.get_status()
    except Exception:
        status = {"stats": {}}
    s = status.get("stats", {})

    console.print()
    console.print(Rule(style="bright_blue"))
    console.print()

    elapsed_str = f"{int(elapsed_seconds // 3600):02d}:{int((elapsed_seconds % 3600) // 60):02d}:{int(elapsed_seconds % 60):02d}"
    total = s.get("total_visits", 0)
    ok = s.get("successful", 0)
    fail = s.get("failed", 0)
    rate = s.get("success_rate", 0)
    ads_found = s.get("total_ads_found", 0)
    ads_clicked = s.get("total_ads_clicked", 0)
    pages = s.get("total_pages_visited", 0)
    vpm = s.get("visits_per_minute", 0)
    resp = s.get("avg_response_time", 0)

    summary_table = Table(box=box.ROUNDED, border_style="bright_blue")
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value", style="bold white", justify="right")

    summary_table.add_row("⏱️  Duration", elapsed_str)
    summary_table.add_row("📥 Total Visits", str(total))
    summary_table.add_row("   ✅ Success", f"[green]{ok}[/green]")
    summary_table.add_row("   ❌ Failed", f"[red]{fail}[/red]")
    summary_table.add_row("   📈 Rate", f"[green]{rate:.1f}%[/green]" if rate >= 80 else f"[yellow]{rate:.1f}%[/yellow]")
    summary_table.add_row("")
    summary_table.add_row("📄 Pages Viewed", str(pages))
    summary_table.add_row("🚀 Visits/min", f"[bold yellow]{vpm:.1f}[/bold yellow]")
    summary_table.add_row("⚡ Avg Response", f"{resp:.3f}s")
    if ads_found > 0:
        summary_table.add_row("")
        summary_table.add_row("📢 Ads Found", str(ads_found))
        summary_table.add_row("🖱️ Ads Clicked", str(ads_clicked))
        click_rate = (ads_clicked / ads_found * 100) if ads_found > 0 else 0
        summary_table.add_row("📊 Click Rate", f"[yellow]{click_rate:.1f}%[/yellow]")

    console.print(Panel(
        summary_table,
        title="[bold white on blue] 📊 Session Summary [/bold white on blue]",
        border_style="blue", box=box.HEAVY, padding=(1, 2),
    ))

    console.print()

    # Target details
    targets_data = s.get("targets", {})
    if targets_data:
        t_table = Table(box=box.SIMPLE, border_style="cyan")
        t_table.add_column("Target", style="bold cyan")
        t_table.add_column("OK", style="green", justify="right")
        t_table.add_column("Fail", style="red", justify="right")
        t_table.add_column("Rate", style="white", justify="right")
        t_table.add_column("Ads", style="yellow", justify="right")
        for name, td in targets_data.items():
            total_t = td["total"]
            r = (td["success"] / total_t * 100) if total_t > 0 else 0
            ads = f"{td.get('ads_clicked', 0)}/{td.get('ads_found', 0)}" if td.get('ads_found', 0) > 0 else "-"
            t_table.add_row(name[:20], str(td["success"]), str(td["fail"]), f"{r:.0f}%", ads)
        console.print(Panel(t_table, title="🌐 Per Target", border_style="cyan"))
        console.print()

    return {"total": total, "ok": ok, "fail": fail, "ads_clicked": ads_clicked}


def cmd_tui(args):
    """
    ✨ Full interactive TUI mode — Quick Setup → Live Dashboard → Summary
    
    Features:
    - Interactive setup wizard
    - Live dashboard with keyboard controls
    - Real-time log viewer
    - Post-session summary
    - Export options
    """
    global bot, config, scheduler

    # ── Welcome ────────────────────────────────────────────────────
    console.clear()
    console.print()
    console.print(Panel.fit(
        "[bold cyan]╭──────────────────────────────────────────────╮\n"
        "│           🚀  CPA Traffic Bot — TUI Mode        │\n"
        "│     Enhanced Terminal Dashboard with Controls    │\n"
        "╰──────────────────────────────────────────────╯[/bold cyan]",
        border_style="bright_blue",
    ))
    console.print()

    # ── Initialize Config FIRST ──────────────────────────────────
    config = Config(args.config)
    logger.setup(config)

    # ── Helper: attach TUI handler to logger (with old-handler cleanup) ──
    def _attach_tui_handler():
        """Create a fresh TuiLogHandler, remove any old ones, attach it."""
        th = TuiLogHandler()
        bl = logging.getLogger("CPABot")
        for h in bl.handlers[:]:
            if isinstance(h, TuiLogHandler):
                bl.removeHandler(h)
        bl.addHandler(th)
        return th

    tui_handler = _attach_tui_handler()

    # ── Check for Session Loading ──────────────────────────────
    if hasattr(args, 'session') and args.session:
        session_data = _load_session(args.session)
        if session_data:
            console.print(f"[green]✅ Loading session '{args.session}'...[/green]")
            config = _apply_session(session_data)
            bot = TrafficBot(config)
            scheduler = Scheduler(config)
            logger.setup(config)
            # logger.setup() clears ALL handlers including TUI — re-attach!
            tui_handler = _attach_tui_handler()
            console.print(f"[green]✅ Session loaded: {len(bot.targets)} targets[/green]")
            console.print()
            # ── Summary & Confirm ──────────────────────────────────
            console.print()
            console.print(Rule(style="bright_blue"))
            console.print()

            sum_rows = []
            for t in bot.targets:
                visits_str = str(t.target_visits) if t.target_visits else "∞"
                disc = "📰" if t.discover_articles else ""
                ads = "🖱️" if t.ad_click_prob > 0 else ""
                sum_rows.append(f"  [green]{t.name}[/green] → {t.url[:50]}  ({visits_str} visits) {disc} {ads}")

            proxy_count = 0
            if config.proxy_enabled:
                try:
                    with open(config.proxy_file) as f:
                        proxy_count = sum(1 for l in f if l.strip() and not l.startswith("#"))
                except Exception:
                    pass

            info_table = Table.grid(padding=(0, 2))
            info_table.add_column(style="bold cyan", justify="right")
            info_table.add_column(style="white")
            info_table.add_row("Threads", str(config.threads))
            info_table.add_row("Proxies", f"{proxy_count} tersedia" if proxy_count else "[dim]None[/dim]")
            info_table.add_row("Durasi", f"{config.visit_duration_min}-{config.visit_duration_max}s")
            if bot.targets:
                eta = _estimate_eta(
                    max(t.target_visits for t in bot.targets) if any(t.target_visits for t in bot.targets) else 1000,
                    config.threads, config.visit_duration_min,
                    config.visit_duration_max,
                )
                info_table.add_row("Estimasi", eta)

            console.print(Panel(
                f"[bold]Targets ({len(bot.targets)}):[/bold]\n" + "\n".join(sum_rows),
                title="[bold white on blue] 📋 Session Summary [/bold white on blue]",
                border_style="blue", box=box.ROUNDED, padding=(1, 2),
            ))
            console.print()
            console.print(info_table)
            console.print()

            console.print("[dim]⌨️  Controls: [green]p[/green]ause [green]s[/green]top [green]q[/green]uit [green]h[/green]elp [green]1-4[/green]log [green]c[/green]onfig[/dim]")

            # ── Discover articles ──────────────────────────────────
            for t in bot.targets:
                if t.discover_articles and not t.articles:
                    console.print(f"[cyan]📡 Discovering articles for {t.name}...[/cyan]")
                    bot.discover_articles(t.name)
                    console.print(f"   [green]→ {len(t.articles)} ditemukan[/green]")

            # ── Start & Dashboard ──────────────────────────────────
            console.print("[green]🚀 Memulai bot...[/green]")
            start_time = time.time()
            bot.start()
            display_dashboard(bot, tui_handler=tui_handler, scheduler_instance=scheduler, config_obj=config)

            # ── Post-Session Summary & Options ─────────────────────
            elapsed = time.time() - start_time
            console.print()
            console.print("[bold green]⏹️  Bot stopped[/bold green]")
            _notify("CPA Bot", f"Session '{args.session}' selesai!")
            _show_summary(bot, elapsed)
            _post_session_menu(bot, args)
            return
        else:
            console.print(f"[red]❌ Session '{args.session}' tidak ditemukan[/red]")
            avail = _list_sessions()
            if avail:
                console.print(f"   [dim]Available: [yellow]{', '.join(avail)}[/yellow][/dim]")
            console.print("[dim]Lanjut setup baru...[/dim]")
            time.sleep(2)

    # ── Config Editor Option ─────────────────────────────────────────
    console.print()
    if Confirm.ask("[bold cyan]⚙️[/bold cyan] [white]Edit config sebelum setup?[/white]", default=False):
        _config_editor(config)
        console.print()

    # ── Check proxy status ───────────────────────────────────────────
    proxy_count = 0
    if config.proxy_enabled and config.proxy_file:
        try:
            with open(config.proxy_file) as f:
                proxy_count = sum(1 for line in f if line.strip() and not line.startswith("#"))
        except Exception:
            pass

    console.print(f"📊 Proxy tersedia: {proxy_count} (enabled: {config.proxy_enabled})")

    # ── Setup ────────────────────────────────────────────────────────
    console.print("[bold cyan]📋[/bold cyan] [white]Konfigurasi target[/white]")
    console.print()

    # Try importing proxy_scraper
    try:
        from proxy_scraper import get_source_names, quick_scrape, scrape_and_save
        HAS_SCRAPER = True
    except ImportError:
        HAS_SCRAPER = False

    setup_choices = ["quick", "manual", "config"]
    if HAS_SCRAPER:
        setup_choices.insert(0, "auto_scrape")

    setup_type = Prompt.ask(
        "[bold cyan]Pilih setup[/bold cyan]",
        choices=setup_choices,
        default="quick",
    )

    _auto_scrape_completed = False

    if setup_type == "auto_scrape":
        """Auto-scrape option: asks target config FIRST, then scrapes proxies, then auto-starts."""
        if not HAS_SCRAPER:
            console.print("[red]❌ proxy_scraper.py tidak ditemukan[/red]")
            return

        # ── 1. TARGET CONFIG FIRST ────────────────────────────────────────
        console.print()
        console.print("[bold cyan]📋[/bold cyan] [white]Konfigurasi target terlebih dahulu:[/white]")
        console.print()

        config.data["targets"] = []
        config.save()

        url = Prompt.ask("[bold cyan]🌐[/bold cyan] [white]Link target[/white]", default="")
        while not url.startswith("http"):
            url = Prompt.ask("[bold red]❌[/bold red] [white]Link harus valid (https://...)[/white]")
        name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama target[/white]",
                           default=urlparse(url).netloc.replace("www.", ""))
        visits = IntPrompt.ask("[bold cyan]🎯[/bold cyan] [white]Jumlah visitor[/white]", default=600)
        threads = IntPrompt.ask("[bold cyan]🧵[/bold cyan] [white]Threads[/white]", default=10)
        discover = Confirm.ask("[bold cyan]📰[/bold cyan] [white]Auto-discover artikel?[/white]", default=True)
        ad_click = Confirm.ask("[bold cyan]🖱️[/bold cyan] [white]Klik iklan?[/white]", default=True)
        dur_min = IntPrompt.ask("[bold cyan]⏱️[/bold cyan] [white]Durasi baca minimal (detik)[/white]", default=30)
        dur_max = IntPrompt.ask("[bold cyan]⏱️[/bold cyan] [white]Durasi baca maksimal (detik)[/white]", default=80)

        if dur_max < dur_min:
            dur_min, dur_max = dur_max, dur_min

        # Simpan target config
        config.data["general"]["threads"] = threads
        config.data["general"]["visit_duration_min"] = dur_min
        config.data["general"]["visit_duration_max"] = dur_max
        if not ad_click:
            config.data["ad_clicking"]["enabled"] = False
        config.save()

        # ── 2. TAMBAH TARGET LAINNYA ─────────────────────────────────────
        targets_added = []
        targets_added.append((name, url, visits, discover, ad_click))

        while True:
            console.print()
            more_url = Prompt.ask("[bold cyan]➕[/bold cyan] [white]Link target lainnya? (Enter untuk skip)[/white]", default="")
            if not more_url:
                break
            while not more_url.startswith("http"):
                more_url = Prompt.ask("[bold red]❌[/bold red] [white]Link harus valid (https://...)[/white]")
            more_name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama target[/white]",
                                   default=urlparse(more_url).netloc.replace("www.", ""))
            more_visits = IntPrompt.ask("[bold cyan]🎯[/bold cyan] [white]Jumlah visitor[/white]", default=visits)
            more_discover = Confirm.ask("[bold cyan]📰[/bold cyan] [white]Auto-discover artikel?[/white]", default=True)
            more_ad_click = Confirm.ask("[bold cyan]🖱️[/bold cyan] [white]Klik iklan?[/white]", default=True)
            targets_added.append((more_name, more_url, more_visits, more_discover, more_ad_click))
            console.print(f"[green]✅ Target '{more_name}' ditambahkan ke antrian[/green]")

        # ── 3. PROXY SCRAPE CONFIG ────────────────────────────────────────
        console.print()
        console.print("[bold cyan]🌐 Auto-Scrape Proxy dari Internet[/bold cyan]")
        console.print()

        console.print("[bold]Pilih protocol:[/bold]")
        proto_http = Confirm.ask("  HTTP", default=True)
        proto_https = Confirm.ask("  HTTPS", default=True)
        proto_socks5 = Confirm.ask("  SOCKS5", default=False)

        protocols = set()
        if proto_http:
            protocols.add("http")
        if proto_https:
            protocols.add("https")
        if proto_socks5:
            protocols.add("socks5")
        if not protocols:
            protocols = {"http", "https"}

        min_alive = IntPrompt.ask("[bold cyan]Minimum proxy alive[/bold cyan]", default=50)
        proxy_file = Prompt.ask(
            "[bold cyan]File output[/bold cyan]",
            default=config.proxy_file or "proxy.txt",
        )

        # ── 4. RUN SCRAPE ─────────────────────────────────────────────────
        console.print()
        console.print(f"[bold]Scraping {len(get_source_names())} sumber...[/bold]")
        console.print()

        def tui_callback(msg, level="info"):
            icons = {"success": "✅", "info": "ℹ️", "warn": "⚠️", "error": "❌"}
            icon = icons.get(level, "•")
            color = {"success": "green", "info": "cyan", "warn": "yellow", "error": "red"}.get(level, "white")
            console.print(f"  [{color}]{icon} {msg}[/{color}]")

        count = scrape_and_save(
            protocols=protocols,
            output_file=proxy_file,
            min_proxies=min_alive,
            progress_callback=tui_callback,
        )

        # ── 5. APPLY CONFIG ─────────────────────────────────────────────
        if count > 0:
            console.print()
            console.print(f"[bold green]✅ {count} proxy siap digunakan![/bold green]")
            config.data.setdefault("proxies", {})
            config.data["proxies"]["file"] = proxy_file
            config.data["proxies"]["enabled"] = True
            config.data["proxies"]["type"] = "http"
            config.save()
            console.print(f"[green]✅ Proxy enabled & siap dimuat[/green]")
        else:
            console.print()
            console.print("[red]❌ Tidak ada proxy yang alive![/red]")
            console.print("[yellow]Melanjutkan tanpa proxy...[/yellow]")

        # Inisialisasi bot
        bot = TrafficBot(config)
        for t_name, t_url, t_visits, t_discover, t_ad_click in targets_added:
            bot.add_target(
                t_name, t_url, weight=1, click_prob=0.3,
                ad_click_prob=0.25 if t_ad_click else 0.0,
                target_visits=t_visits, discover_articles=t_discover,
                article_distribution="random",
            )

        _auto_scrape_completed = True
        
    if not _auto_scrape_completed and setup_type == "quick":
        # Hapus target lama agar tidak terakumulasi
        config.data["targets"] = []
        config.save()
        url = Prompt.ask("[bold cyan]🌐[/bold cyan] [white]Link target[/white]", default="")
        while not url.startswith("http"):
            url = Prompt.ask("[bold red]❌[/bold red] [white]Link harus valid (https://...)[/white]")
        name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama target[/white]",
                           default=urlparse(url).netloc.replace("www.", ""))
        visits = IntPrompt.ask("[bold cyan]🎯[/bold cyan] [white]Jumlah visitor[/white]", default=600)
        threads = IntPrompt.ask("[bold cyan]🧵[/bold cyan] [white]Threads[/white]", default=10)
        discover = Confirm.ask("[bold cyan]📰[/bold cyan] [white]Auto-discover artikel?[/white]", default=True)
        ad_click = Confirm.ask("[bold cyan]🖱️[/bold cyan] [white]Klik iklan?[/white]", default=True)
        dur_min = IntPrompt.ask("[bold cyan]⏱️[/bold cyan] [white]Durasi baca minimal (detik)[/white]", default=30)
        dur_max = IntPrompt.ask("[bold cyan]⏱️[/bold cyan] [white]Durasi baca maksimal (detik)[/white]", default=80)

        if dur_max < dur_min:
            dur_min, dur_max = dur_max, dur_min

        config.data["general"]["threads"] = threads
        config.data["general"]["visit_duration_min"] = dur_min
        config.data["general"]["visit_duration_max"] = dur_max
        if not ad_click:
            config.data["ad_clicking"]["enabled"] = False
        config.save()

        bot = TrafficBot(config)
        bot.add_target(
            name, url, weight=1, click_prob=0.3,
            ad_click_prob=0.25 if ad_click else 0.0,
            target_visits=visits, discover_articles=discover,
            article_distribution="random",
        )

    elif not _auto_scrape_completed and setup_type == "manual":
        console.print("[yellow]Masukkan target satu per satu. Kosongkan nama untuk selesai.[/yellow]")
        threads = IntPrompt.ask("[bold cyan]🧵[/bold cyan] [white]Threads[/white]", default=10)
        config.data["general"]["threads"] = threads
        config.data["targets"] = []  # Hapus target lama
        config.save()
        bot = TrafficBot(config)

        while True:
            console.print()
            console.print(Rule(style="dim"))
            name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama target (kosongkan untuk selesai)[/white]", default="")
            if not name:
                break
            url = Prompt.ask(f"[bold cyan]🌐[/bold cyan] [white]URL untuk '{name}'[/white]", default="https://")
            while not url.startswith("http"):
                url = Prompt.ask("[bold red]❌[/bold red] URL harus valid")
            visits = IntPrompt.ask("[bold cyan]🎯[/bold cyan] Visitor", default=0)
            discover = Confirm.ask("[bold cyan]📰[/bold cyan] Discover articles?", default=False)
            ad_click = Confirm.ask("[bold cyan]🖱️[/bold cyan] Click ads?", default=True)

            bot.add_target(
                name, url, weight=1, click_prob=0.3,
                ad_click_prob=0.25 if ad_click else 0.0,
                target_visits=visits, discover_articles=discover,
                article_distribution="random",
            )
            console.print(f"[green]✅ Target '{name}' ditambahkan[/green]")

        if not bot.targets:
            console.print("[red]❌ Tidak ada target. Keluar.[/red]")
            return

    elif not _auto_scrape_completed:
        bot = TrafficBot(config)
        console.print(f"[green]✅ Memuat {len(bot.targets)} target dari config[/green]")

    scheduler = Scheduler(config)

    # Attach TUI handler (replaces any old one)
    tui_handler = _attach_tui_handler()

    # ── Summary & Confirm ──────────────────────────────────────────
    console.print()
    console.print(Rule(style="bright_blue"))
    console.print()

    sum_rows = []
    for t in bot.targets:
        visits_str = str(t.target_visits) if t.target_visits else "∞"
        disc = "📰" if t.discover_articles else ""
        ads = "🖱️" if t.ad_click_prob > 0 else ""
        sum_rows.append(f"  [green]{t.name}[/green] → {t.url[:50]}  ({visits_str} visits) {disc} {ads}")

    proxy_count = 0
    if config.proxy_enabled:
        try:
            with open(config.proxy_file) as f:
                proxy_count = sum(1 for l in f if l.strip() and not l.startswith("#"))
        except Exception:
            pass

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan", justify="right")
    info_table.add_column(style="white")
    info_table.add_row("Threads", str(config.threads))
    info_table.add_row("Proxies", f"{proxy_count} tersedia" if proxy_count else "[dim]None[/dim]")
    info_table.add_row("Durasi", f"{config.visit_duration_min}-{config.visit_duration_max}s")
    if bot.targets:
        eta = _estimate_eta(
            max(t.target_visits for t in bot.targets) if any(t.target_visits for t in bot.targets) else 1000,
            config.threads, config.visit_duration_min,
            config.visit_duration_max,
        )
        info_table.add_row("Estimasi", eta)

    console.print(Panel(
        f"[bold]Targets ({len(bot.targets)}):[/bold]\n" + "\n".join(sum_rows),
        title="[bold white on blue] 📋 Setup Summary [/bold white on blue]",
        border_style="blue", box=box.ROUNDED, padding=(1, 2),
    ))
    console.print()
    console.print(info_table)
    console.print()

    console.print("[dim]⌨️  Controls: [green]p[/green]ause [green]s[/green]top [green]q[/green]uit [green]h[/green]elp [green]1-4[/green]log [green]c[/green]onfig[/dim]")

    # ── Discover articles ──────────────────────────────────────────
    for t in bot.targets:
        if t.discover_articles:
            console.print(f"[cyan]📡 Discovering articles for {t.name}...[/cyan]")
            bot.discover_articles(t.name)
            console.print(f"   [green]→ {len(t.articles)} ditemukan[/green]")

    # ── Start & Dashboard ──────────────────────────────────────────
    console.print("[green]🚀 Memulai bot...[/green]")
    start_time = time.time()
    bot.start()
    display_dashboard(bot, tui_handler=tui_handler, scheduler_instance=scheduler, config_obj=config)

    # ── Post-Session Summary ───────────────────────────────────────
    elapsed = time.time() - start_time
    console.print()
    console.print("[bold green]⏹️  Bot stopped[/bold green]")

    _show_summary(bot, elapsed)
    _notify("CPA Bot", f"Session selesai dalam {int(elapsed//60)}m {int(elapsed%60)}s")

    # ── Save Session Option ──────────────────────────────────────────
    if Confirm.ask("[bold cyan]💾[/bold cyan] [white]Simpan sesi ini untuk dipakai lagi?[/white]", default=True):
        session_name = Prompt.ask("[bold cyan]📛[/bold cyan] [white]Nama sesi[/white]",
                                   default=f"session_{datetime.now().strftime('%Y%m%d_%H%M')}")
        path = _save_session(session_name, config, bot.list_targets())
        console.print(f"[green]✅ Session saved → {path}[/green]")
        time.sleep(1)

    _post_session_menu(bot, args)


def _post_session_menu(bot_instance, args):
    """Post-session menu: export, restart, quit."""
    console.print()
    console.print(Rule(style="bright_blue"))
    console.print()

    while True:
        action = Prompt.ask(
            "[bold cyan]Apa yang ingin dilakukan?[/bold cyan]",
            choices=["export", "restart", "quit"],
            default="quit",
        )

        if action == "export":
            try:
                from statistics import VisitRecord, AdClickRecord
                export_dir = f"reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.makedirs(export_dir, exist_ok=True)
                csv_path = f"{export_dir}/report.csv"
                json_path = f"{export_dir}/report.json"
                bot_instance.stats.export_csv(csv_path)
                bot_instance.stats.export_json(json_path)
                console.print(f"[green]✅ CSV → {csv_path}[/green]")
                console.print(f"[green]✅ JSON → {json_path}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Export error: {e}[/red]")

        elif action == "restart":
            console.print("[cyan]🔄 Restarting...[/cyan]")
            # Proper restart: spawn new process instead of recursive call
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return

        elif action == "quit":
            console.print()
            console.print(Panel.fit(
                "[bold green]╭──────────────────────────────────────────╮\n"
                "│            Terima kasih! Sampai jumpa..      │\n"
                "╰──────────────────────────────────────────╯[/bold green]",
                border_style="green",
            ))
            console.print()
            return


def main():
    global bot, scheduler, config

    parser = argparse.ArgumentParser(
        description="CPA Traffic Bot - Traffic + Ad Clicking + Campaign",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py start                        # Start bot
  python main.py start --threads 20           # 20 threads
  python main.py status                       # All stats
  python main.py campaigns                    # Campaign progress
  python main.py discover                     # Auto-discover articles
  python main.py discover BlogKu              # Discover for specific target
  python main.py targets                      # List targets

  python main.py add-target BlogKu https://example.com \\
      --visits 50 --discover                  # Add with 50 visits + article discovery

  python main.py add-target BlogKu https://example.com \\
      --visits 100 --discover \\
      --distrib round-robin                   # Round-robin article distribution

  python main.py remove-target BlogKu         # Remove target
  python main.py report                       # Export report
  python main.py ad-stats                     # Ad click details
        """,
    )

    parser.add_argument("--config", "-c", default="config.json", help="Config file")
    parser.add_argument("--session", "-s", default=None,
                        help="Load saved session (use 'list' to see available)")

    sub = parser.add_subparsers(dest="command", help="Commands")

    p = sub.add_parser("start", help="Start bot")
    p.add_argument("--threads", "-t", type=int, default=None)
    p.add_argument("--daemon", "-d", action="store_true")
    p.set_defaults(func=cmd_start)

    sub.add_parser("stop").set_defaults(func=cmd_stop)
    sub.add_parser("pause").set_defaults(func=cmd_pause)
    sub.add_parser("resume").set_defaults(func=cmd_resume)

    p = sub.add_parser("status", help="Bot & campaign stats")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("targets", help="List targets")
    p.set_defaults(func=cmd_targets)

    p = sub.add_parser("add-target", help="Add target")
    p.add_argument("name", help="Name")
    p.add_argument("url", help="URL")
    p.add_argument("--weight", "-w", type=int, default=1)
    p.add_argument("--click-prob", type=float, default=0.3)
    p.add_argument("--ad-click-prob", type=float, default=None)
    p.add_argument("--visits", type=int, default=0, help="Target visit count")
    p.add_argument("--discover", action="store_true", help="Auto-discover articles")
    p.add_argument("--distrib", choices=["random", "sequential", "round-robin"],
                   default="random", help="Article distribution")
    p.set_defaults(func=cmd_add_target)

    p = sub.add_parser("remove-target", help="Remove target")
    p.add_argument("name")
    p.set_defaults(func=cmd_remove_target)

    sub.add_parser("report").set_defaults(func=cmd_report)
    sub.add_parser("reset-stats").set_defaults(func=cmd_reset_stats)
    sub.add_parser("test-proxies").set_defaults(func=cmd_test_proxies)

    # ── Proxy management commands ───────────────────────────────────
    p = sub.add_parser("add-proxy", help="Add a proxy manually")
    p.add_argument("proxy_url", help="Proxy URL (e.g. http://user:pass@host:port)")
    p.set_defaults(func=cmd_add_proxy)

    p = sub.add_parser("add-proxy-bulk", help="Add proxies from file")
    p.add_argument("file", help="File with one proxy per line")
    p.set_defaults(func=cmd_add_proxy_bulk)

    p = sub.add_parser("remove-proxy", help="Remove a proxy")
    p.add_argument("proxy_url", help="Proxy URL to remove")
    p.set_defaults(func=cmd_remove_proxy)

    sub.add_parser("list-proxies", help="List all proxies with status").set_defaults(func=cmd_list_proxies)
    sub.add_parser("proxy-list", help="Alias for list-proxies").set_defaults(func=cmd_list_proxies)

    # ── Rotating provider commands ──────────────────────────────────
    p = sub.add_parser("rotating-add", help="Add a rotating proxy provider")
    p.add_argument("provider", help="Provider slug (brightdata, oxylabs, smartproxy, etc.)")
    p.set_defaults(func=cmd_rotating_add)

    p = sub.add_parser("rotating-remove", help="Remove a rotating proxy provider")
    p.add_argument("provider", help="Provider slug to remove")
    p.set_defaults(func=cmd_rotating_remove)

    p = sub.add_parser("rotating-test", help="Test connection to a rotating provider")
    p.add_argument("provider", help="Provider slug to test")
    p.set_defaults(func=cmd_rotating_test)

    sub.add_parser("rotating-list", help="List all available rotating proxy providers").set_defaults(func=cmd_rotating_list)
    sub.add_parser("rotating-providers", help="Alias for rotating-list").set_defaults(func=cmd_rotating_list)

    sub.add_parser("reload").set_defaults(func=cmd_reload_config)
    sub.add_parser("ad-stats").set_defaults(func=cmd_ad_stats)

    p = sub.add_parser("campaigns", help="Campaign progress")
    p.set_defaults(func=cmd_campaigns)

    p = sub.add_parser("discover", help="Discover articles")
    p.add_argument("name", nargs="?", default=None, help="Target name (optional)")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("tui", help="✨ Interactive TUI mode (recommended)")
    p.set_defaults(func=cmd_tui)

    p = sub.add_parser("quick", help="Quick interactive setup (basic)")
    p.set_defaults(func=cmd_quick)

    args = parser.parse_args()

    # ── Handle --session list ──────────────────────────────────
    if args.session and args.session == "list":
        sessions = _list_sessions()
        if sessions:
            console.print("[bold cyan]📋 Available Sessions:[/bold cyan]")
            for s in sessions:
                console.print(f"  • [green]{s}[/green]")
            console.print()
            console.print("[dim]Load: python main.py --session <name>[/dim]")
        else:
            console.print("[yellow]No saved sessions yet[/yellow]")
        return

    # ── If no command, default to TUI mode ────────────────────
    if args.command is None:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        cmd_tui(args)
        return

    # quick mode handles its own setup
    if args.command == "quick":
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        args.func(args)
        return

    config = Config(args.config)
    bot = TrafficBot(config)
    scheduler = Scheduler(config)
    logger.setup(config)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    args.func(args)


if __name__ == "__main__":
    main()
