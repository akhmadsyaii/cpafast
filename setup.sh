#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  CPA Traffic Bot — Auto Setup Script
#  ═══════════════════════════════════════════════════════════════════════════
#  Usage:
#    chmod +x setup.sh && ./setup.sh
#    ./setup.sh --quick    # skip confirmation prompts
#    ./setup.sh --no-browser  # skip Playwright browser install
# ═══════════════════════════════════════════════════════════════════════════

set -e

# ── Colors ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Config ────────────────────────────────────────────────────────────
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PYTHON="${PYTHON_CMD:-python3}"
VENV_DIR="venv"
REQUIREMENTS="requirements.txt"
QUICK_MODE=false
INSTALL_BROWSER=true
SKIP_GUI=false

# Parse args
for arg in "$@"; do
    case "$arg" in
        --quick) QUICK_MODE=true ;;
        --no-browser) INSTALL_BROWSER=false ;;
        --no-gui) SKIP_GUI=true ;;
    esac
done

# ── Functions ──────────────────────────────────────────────────────────

log()     { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; }
header()  { echo -e "\n${CYAN}╔══════════════════════════════════════════════════════╗${NC}"; }
section() { echo -e "${CYAN}║${NC}  ${BOLD}$1${NC}"; }
footer()  { echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"; }
prompt()  {
    if [ "$QUICK_MODE" = true ]; then
        return 0
    fi
    while true; do
        read -p "$(echo -e "${YELLOW}[?]${NC} $1 [Y/n]: ")" yn
        yn="${yn:-Y}"
        case "$yn" in
            [YyJj]* ) return 0 ;;
            [Nn]* ) return 1 ;;
            * ) echo "  Jawab Y atau N" ;;
        esac
    done
}

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        error "'$1' tidak ditemukan. Install dulu: $2"
        exit 1
    fi
}

# Auto-detect: skip GUI packages if no display server
if [ "$SKIP_GUI" = false ]; then
    if [ -z "$DISPLAY" ] && ! command -v xdpyinfo &>/dev/null; then
        SKIP_GUI=true
        warn "Tidak terdeteksi display server — GUI packages akan dilewati"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
#  WELCOME
# ═══════════════════════════════════════════════════════════════════════

clear
header
section "   🚀  CPA Traffic Bot — Auto Setup"
section "   Project: $(basename "$DIR")"
section "   Python:  $($PYTHON --version 2>&1 || echo 'not found')"
footer
echo ""

# ── 0. Check prerequisites ──────────────────────────────────────────
echo -e "${BOLD}🔍 Memeriksa prerequisites...${NC}"

PREREQ_OK=true

check_cmd "$PYTHON" "python3"
check_cmd "pip3" "python3-pip"
$PYTHON -c "import venv" 2>/dev/null || {
    error "Modul 'venv' tidak tersedia. Install: $PYTHON -m pip install venv"
    PREREQ_OK=false
}

if [ "$PREREQ_OK" = false ]; then
    exit 1
fi

log "$PYTHON ditemukan: $($PYTHON --version)"
log "pip3 ditemukan"

# ── 1. Create virtual environment ────────────────────────────────────
echo ""
echo -e "${BOLD}📦 Membuat virtual environment...${NC}"

if [ -d "$VENV_DIR" ]; then
    warn "Directory '$VENV_DIR' sudah ada."
    if prompt "Hapus dan buat ulang?"; then
        echo -n "  Menghapus $VENV_DIR ... "
        rm -rf "$VENV_DIR"
        echo -e "${GREEN}done${NC}"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -n "  Membuat $VENV_DIR ... "
    $PYTHON -m venv "$VENV_DIR"
    echo -e "${GREEN}done${NC}"
fi

# Detect activation path
if [ -f "$VENV_DIR/bin/activate" ]; then
    ACTIVATE="$VENV_DIR/bin/activate"
    PIP="$VENV_DIR/bin/pip"
    PYTHON_VENV="$VENV_DIR/bin/python"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    ACTIVATE="$VENV_DIR/Scripts/activate"
    PIP="$VENV_DIR/Scripts/pip"
    PYTHON_VENV="$VENV_DIR/Scripts/python"
else
    error "Virtual environment tidak valid — tidak ditemukan activate script"
    exit 1
fi

log "Virtual environment: $VENV_DIR"
log "Pip: $($PIP --version 2>&1 | head -1)"

# ── 2. Upgrade pip ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}⬆️  Mengupdate pip...${NC}"
$PIP install --upgrade pip -q
log "pip siap"

# ── 3. Install dependencies ─────────────────────────────────────────
echo ""
echo -e "${BOLD}📚 Menginstall dependencies dari requirements.txt...${NC}"

if [ ! -f "$REQUIREMENTS" ]; then
    error "File '$REQUIREMENTS' tidak ditemukan!"
    exit 1
fi

# Parse requirements (handle inline comments)
REQUIRED_PACKAGES=$(grep -v '^#' "$REQUIREMENTS" | grep -v '^$' | wc -l)
echo -n "  $REQUIRED_PACKAGES packages akan diinstall ... "

if $PIP install -r "$REQUIREMENTS" -q 2>&1; then
    echo -e "${GREEN}done${NC}"
    # Verify key packages (optional GUI packages handled separately)
    KEY_PACKAGES="requests rich beautifulsoup4 lxml playwright"
    GUI_PACKAGES="customtkinter pillow"
    MISSING=""
    GUI_MISSING=""
    for pkg in $KEY_PACKAGES; do
        if ! $PYTHON_VENV -c "import $pkg" 2>/dev/null; then
            MISSING="$MISSING $pkg"
        fi
    done
    for pkg in $GUI_PACKAGES; do
        if ! $PYTHON_VENV -c "import $pkg" 2>/dev/null; then
            GUI_MISSING="$GUI_MISSING $pkg"
        fi
    done
    if [ -n "$MISSING" ]; then
        warn "Beberapa package gagal diverifikasi:$MISSING"
        echo "  Mencoba install ulang..."
        $PIP install --force-reinstall $MISSING -q
    fi
    if [ -n "$GUI_MISSING" ]; then
        if [ "$SKIP_GUI" = true ]; then
            warn "GUI packages tidak terinstall:$GUI_MISSING"
            warn "  → Bot tetap bisa jalan via: $PYTHON_VENV main.py tui"
            warn "  → Untuk GUI, install display server: apt install xvfb"
        else
            warn "GUI packages gagal diverifikasi:$GUI_MISSING"
            echo "  Mencoba install ulang..."
            $PIP install --force-reinstall $GUI_MISSING -q
        fi
    fi
    log "Semua dependencies terinstall"
else
    error "Gagal install dependencies!"
    warn "Coba jalankan manual: $PIP install -r $REQUIREMENTS"
    exit 1
fi

# ── 4. Install Playwright Browser ──────────────────────────────────
if [ "$INSTALL_BROWSER" = true ]; then
    echo ""
    echo -e "${BOLD}🌐 Menginstall Playwright browser (Chromium)...${NC}"

    # Check if already installed
    if $PYTHON_VENV -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.launch(headless=True).close(); p.stop()" 2>/dev/null; then
        log "Playwright Chromium sudah terinstall dan berfungsi"
    else
        if prompt "Install Playwright Chromium (~200MB)?"; then
            echo -n "  Menginstall Chromium ... "
            $PYTHON_VENV -m playwright install chromium 2>&1 | tail -3
            echo -e "${GREEN}done${NC}"
            log "Playwright Chromium siap"
        else
            warn "Playwright browser tidak diinstall. Bot akan fallback ke mode requests."
        fi
    fi
else
    warn "Playwright browser dilewati (--no-browser)"
    warn "Bot akan fallback ke mode requests."
fi

# ── 5. Check dependencies ──────────────────────────────────────────
echo ""
echo -e "${BOLD}🔍 Verifikasi instalasi...${NC}"

$PYTHON_VENV -c "
import os
import sys
sys.path.insert(0, '.')

core_ok = True

# ── Core dependencies (wajib) ───────────────────────────────────
core_tests = [
    ('requests', 'requests'),
    ('bs4', 'BeautifulSoup'),
    ('lxml', 'lxml'),
    ('rich', 'rich'),
]
for mod, name in core_tests:
    try:
        __import__(mod)
        print(f'  [✓] {name} — OK')
    except ImportError:
        print(f'  [✗] {name} — TIDAK TERINSTALL')
        core_ok = False

# ── Playwright (opsional) ───────────────────────────────────────
try:
    import playwright
    print(f'  [✓] playwright')
except ImportError:
    print(f'  [ ] playwright — opsional')

# ── GUI dependencies (opsional, butuh display server) ──────────
gui_ok = True
has_display = bool(os.environ.get('DISPLAY'))
try:
    import customtkinter
    print(f'  [✓] customtkinter — GUI siap')
except ImportError:
    print(f'  [ ] customtkinter — TIDAK TERINSTALL (opsional, untuk GUI mode)')
    gui_ok = False
except Exception as e:
    if 'display' in str(e).lower() or 'tk' in str(e).lower():
        print(f'  [!] customtkinter — terinstall tapi butuh display server (GUI mode)')
        print(f'      Jalankan: apt install xvfb && xvfb-run bash run_gui.sh')
    else:
        print(f'  [!] customtkinter — error: {e}')
    gui_ok = False

try:
    from PIL import Image
    print(f'  [✓] pillow')
except ImportError:
    print(f'  [ ] pillow — TIDAK TERINSTALL (opsional)')

if not core_ok:
    print()
    print('  ❌ Core dependencies bermasalah! Bot TIDAK bisa jalan.')
    sys.exit(1)
else:
    print()
    if gui_ok:
        print('  ✅ Semua dependencies OK (termasuk GUI)')
    else:
        print('  ✅ Core dependencies OK')
        if has_display:
            print('  ⚠️  GUI dependencies tidak lengkap — GUI mode mungkin tidak berfungsi')
        else:
            print('  ⚠️  GUI mode tidak tersedia (tidak ada display server)')
        print('     Bot tetap bisa dijalankan via: source venv/bin/activate && python main.py tui')
"

if [ $? -ne 0 ]; then
    warn "Core dependencies bermasalah. Coba: source venv/bin/activate && pip install requests rich beautifulsoup4 lxml"
fi

# ── 6. Create default files ─────────────────────────────────────────
echo ""
echo -e "${BOLD}📝 Membuat file default...${NC}"

# proxy.txt — create if not exists
if [ ! -f "proxy.txt" ]; then
    touch proxy.txt
    log "proxy.txt dibuat (kosong — bot jalan tanpa proxy)"
else
    COUNT=$(grep -v '^#' proxy.txt | grep -v '^$' | wc -l)
    log "proxy.txt sudah ada ($COUNT proxy)"
fi

# config.json — check if it exists
if [ ! -f "config.json" ]; then
    warn "config.json tidak ditemukan! Buat dari template."
    cat > config.json << 'CONFIG'
{
  "general": {
    "engine": "playwright",
    "threads": 10,
    "min_delay": 2.0,
    "max_delay": 8.0,
    "visit_duration_min": 30,
    "visit_duration_max": 80,
    "timeout": 15,
    "max_retries": 3,
    "max_pages_per_session": 3
  },
  "proxies": {
    "enabled": false,
    "type": "http",
    "file": "proxy.txt",
    "test_before_use": true,
    "test_url": "http://httpbin.org/ip",
    "rotate_every_request": true,
    "sticky_session": false,
    "list": []
  },
  "ad_clicking": {
    "enabled": true,
    "probability": 0.25,
    "max_ads_per_visit": 3,
    "click_delay_min": 2.0,
    "click_delay_max": 5.0,
    "log_all_ads_found": false,
    "ad_types": {
      "display": true,
      "native": true,
      "banner": true,
      "sponsored_link": true,
      "popup": false,
      "image_ad": true,
      "iframe": true,
      "link": true
    }
  },
  "user_agent": {
    "rotate": true,
    "device_type": "desktop"
  },
  "behavior": {
    "simulate_scroll": true,
    "simulate_reading": true,
    "cookie_consent": true,
    "multi_page_browsing": true,
    "form_interaction": false,
    "link_click_min": 1,
    "link_click_max": 3
  },
  "scheduler": {
    "enabled": false,
    "mode": "interval",
    "interval_minutes": 60,
    "daily_time": "09:00",
    "daily_runs": 10,
    "run_duration_minutes": 30
  },
  "logging": {
    "level": "INFO",
    "file": "logs/bot.log",
    "max_size_mb": 10,
    "backup_count": 5,
    "console_output": true
  },
  "statistics": {
    "save_to_file": true,
    "file_format": "csv",
    "export_path": "reports"
  },
  "captcha": {
    "enabled": false,
    "solver": [
      {
        "service": "2captcha",
        "api_key": ""
      }
    ]
  },
  "stealth": {
    "enabled": true,
    "use_fingerprint_db": true,
    "use_enhanced_stealth": true,
    "randomize_viewport": true,
    "randomize_timezone": true,
    "random_locale": true,
    "randomize_geolocation": true,
    "device_type": "desktop",
    "browser_type": "chrome"
  }
}
CONFIG
    log "config.json dibuat dari template default"
else
    log "config.json sudah ada"
fi

# sessions directory
mkdir -p sessions
mkdir -p logs
mkdir -p reports

# ── 7. Make scripts executable ─────────────────────────────────────
echo ""
echo -e "${BOLD}🔧 Membuat file executable...${NC}"
chmod +x main.py gui.py run_gui.sh setup.sh 2>/dev/null || true
log "Script permissions diatur"

# ═══════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════════

echo ""
header
section "  ✅  Setup Selesai!"
footer
echo ""
echo -e "  ${BOLD}Virtual environment:${NC}  $VENV_DIR"
echo -e "  ${BOLD}Cara aktivasi:${NC}       source $ACTIVATE"
echo -e "  ${BOLD}Jalankan bot:${NC}         $PYTHON_VENV main.py tui"
echo -e "  ${BOLD}Jalankan GUI:${NC}         bash run_gui.sh"
echo -e "  ${BOLD}Quick setup:${NC}          $PYTHON_VENV main.py quick"
echo ""

# ── Next steps prompt ──────────────────────────────────────────────
if [ "$QUICK_MODE" = false ]; then
    echo -e "${BOLD}📋 Langkah selanjutnya:${NC}"
    echo ""
    echo -e "  1. ${CYAN}Jalankan bot sekarang?${NC}"
    if prompt "  Mulai interactive TUI mode?"; then
        echo ""
        echo -e "  ${BOLD}Memulai CPA Traffic Bot...${NC}"
        echo ""
        exec "$PYTHON_VENV" main.py tui
    fi
    echo ""
    echo -e "  2. ${CYAN}Edit config.json${NC} untuk mengatur target, proxy, dll."
    echo -e "  3. ${CYAN}Isi proxy.txt${NC} kalau mau pakai proxy (1 baris per proxy)"
    echo ""
    echo -e "  ${BOLD}Selamat menggunakan CPA Traffic Bot! 🚀${NC}"
fi
