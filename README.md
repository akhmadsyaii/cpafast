# 🚀 CPA Traffic Bot

Bot traffic otomatis dengan fitur **campaign**, **article discovery**, **ad clicking**, **proxy support**, dan **human-like behavior**. Simulasi pengunjung realistis dengan durasi baca 30-80 detik, scroll, klik iklan, dan rotasi IP.

---

## ✨ Fitur Lengkap

### 🎯 Campaign Mode
Tentukan jumlah kunjungan per target (50, 100, 1000, dll). Bot berhenti otomatis setelah target tercapai. Ada **ETA** di dashboard — tinggal liat berapa lama lagi selesai.

### 📰 Article Discovery
Bot bisa menemukan artikel sendiri dari:
- **sitemap.xml** / sitemap_index.xml
- **robots.txt**
- **Homepage** HTML parsing
- **Structured data** (JSON-LD)

Support 3 mode distribusi artikel:
| Mode | Cara Kerja |
|------|------------|
| `random` | Acak tiap visit |
| `sequential` | Berurutan dari pertama |
| `round-robin` | Giliran merata |

### 🖱️ Ad Clicking Cerdas
Deteksi & klik 10+ jenis iklan:
- 🖥️ **Display** (AdSense, banner)
- 📰 **Native** (Outbrain, Taboola, Revcontent)
- 💼 **Sponsored link**
- 🪟 **Popup / Popunder**
- 🖼️ **Image ads**
- 📦 **Iframe ads**
- 🎪 **AMP ads**
- 🔗 **Contextual links**

Bisa filter berdasarkan tipe iklan & network. Probabilitas klik bisa diatur.

### 🌐 Multi-Proxy Support
- HTTP, HTTPS, SOCKS4, SOCKS5
- Rotasi otomatis (acak tiap request)
- Sticky session (1 proxy per sesi)
- Test proxy sebelum dipakai
- Auto-ganti kalau proxy mati
- **`proxy.txt`** — isi file kosong = bot jalan normal, isi ada proxy = visitor beda asal

### 🧠 Human-like Behavior
| Fitur | Detail |
|-------|--------|
| ⏱️ **Visit duration** | 30-80 detik (seperti baca artikel) |
| ⏳ **Random delay** | 2-8 detik antar aksi |
| 📜 **Scroll simulasi** | Scroll bertahap kayak manusia |
| 🍪 **Cookie consent** | Auto-accept biar gak dicurigai |
| 📄 **Multi-page** | Browsing ke halaman lain |
| 🔗 **External link** | Klik link keluar website |
| 🔄 **User-Agent** | Rotasi Desktop & Mobile |
| 🔗 **Referrer spoofing** | Google, FB, Twitter, Bing, dll |

### ⚡ Multi-threading
Kirim traffic dari banyak thread simultan. Saran: 10-20 thread untuk 200 proxy.

### 📊 Live Dashboard Interaktif
```
┌─ CPA Traffic Bot ─▶️  RUNNING ─🎯 CAMPAIGN ─⏱️ 00:45:32 ─🕐 14:30:00─┐
│ ┌─ 📊 Live Statistics ─┐ ┌─ 🎯 Campaign Progress ─┐                    │
│ │ 🎯 Targets       1   │ │ BlogKu  ━━━━━━━━━━━━━ 75% │                    │
│ │ 🧵 Threads      10   │ │ 450/600  50 articles    │                    │
│ │ 📥 Total Visits 450  │ └──────────────────────────┘                    │
│ │ ✅ Success      432  │ ┌─ 📢 Ad Activity ────────┐                    │
│ │ ❌ Failed        18  │ │ Ads Found:   120        │                    │
│ │ 📈 Rate         96%  │ │ Ads Clicked:  45        │                    │
│ │ 🚀 Visits/min  12.5  │ │ Click Rate: 37.5%      │                    │
│ │ ⏳ ETA        ~12m   │ │ 🖥️ display    30        │                    │
│ └──────────────────────┘ └──────────────────────────┘                    │
│ ┌─ 📈 Performance ──────────┐ ┌─ 🌐 Per Target ───────────┐             │
│ │ Success Rate [████░░] 96% │ │ BlogKu   432 18  96% 45/120│             │
│ │ Ad Click   [███░░░] 38%  │ └────────────────────────────┘             │
│ └───────────────────────────┘                                           │
│ 🌐 Proxy aktif = visitor dari banyak IP berbeda     🕐 tips bergulir    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 📈 Laporan & Statistik
- Export **CSV** atau **JSON**
- Detail per target
- Statistik klik iklan per tipe & network
- Riwayat kunjungan & klik iklan
- Summary otomatis setelah campaign selesai

---

## 🛠️ Instalasi

```bash
# 1. Clone & masuk direktori
cd cpafast

# 2. Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser
python -m playwright install chromium

# 5. (Opsional) Buat file proxy
touch proxy.txt
```

---

## ⚙️ Konfigurasi

### `config.json`

```jsonc
{
  "general": {
    "engine": "playwright",      // "playwright" (default) atau "requests"
    "threads": 10,               // Jumlah thread
    "visit_duration_min": 30,    // Durasi baca minimal (detik)
    "visit_duration_max": 80,    // Durasi baca maksimal (detik)
    "timeout": 15,               // Timeout request (detik)
    "max_retries": 3             // Retry kalau gagal
  },
  "proxies": {
    "enabled": true,
    "file": "proxy.txt",         // File daftar proxy
    "test_before_use": true,     // Test proxy sebelum dipakai
    "rotate_every_request": true // Ganti proxy tiap request
  },
  "ad_clicking": {
    "enabled": true,
    "probability": 0.25,         // Probabilitas klik iklan (25%)
    "max_ads_per_visit": 3,      // Maks klik iklan per kunjungan
    "ad_types": {                // Filter tipe iklan
      "display": true,
      "native": true,
      "banner": true,
      "popup": false
    }
  }
}
```

### `proxy.txt`

Buat file `proxy.txt` di folder project. Satu proxy per baris. Support semua jenis:

| Type | Format | Contoh |
|------|--------|--------|
| HTTP | `http://user:pass@host:port` | `http://user:pass@192.168.1.1:8080` |
| HTTPS | `https://host:port` | `https://192.168.1.2:3128` |
| SOCKS4 | `socks4://host:port` | `socks4://192.168.1.3:1080` |
| SOCKS5 | `socks5://user:pass@host:port` | `socks5://user:pass@192.168.1.4:1080` |
| SOCKS5h | `socks5h://host:port` | `socks5h://192.168.1.5:1080` |

> `socks5h` = SOCKS5 dengan remote DNS (resolve domain di server proxy, bukan di lokal)

Contoh isi `proxy.txt`:
```
# HTTP with auth
http://alice:secret@192.168.1.1:8080

# HTTP tanpa auth
http://192.168.1.2:3128

# SOCKS5 with auth
socks5://bob:pass123@192.168.1.3:1080

# SOCKS5 tanpa auth
socks5://192.168.1.4:1080

# SOCKS4
socks4://192.168.1.5:1080

# SOCKS5h (remote DNS)
socks5h://192.168.1.6:1080
```

> 💡 **Kosongin aja** file `proxy.txt` kalo gak pake proxy. Bot tetap jalan normal tanpa proxy.
>
> ⚠️ **Catatan Playwright**: SOCKS4 tidak didukung Playwright. Bot bakal skip otomatis dan pake proxy lain.
> SOCKS5, SOCKS5h, HTTP, HTTPS全部 works with Playwright.

---

## 🚀 Cara Pakai

### 🏃 Quick Start (Interaktif)

Jalanin aja, tinggal jawab pertanyaan:

```bash
python main.py quick
```

Nanti muncul panduan interaktif:
```
╭──────────────────────────────────────────╮
│         🚀  CPA Traffic Bot Quick Setup  │
│         Isi data di bawah untuk mulai    │
╰──────────────────────────────────────────╯

🌐 Link target: https://blog-ku.com
📛 Nama target (blog-ku.com): BlogKu
🎯 Jumlah visitor (600): 600
🧵 Threads (10): 10
📰 Auto-discover artikel? (Y/n): y
🖱️ Klik iklan? (Y/n): y
⏱️ Durasi baca minimal (30):
⏱️ Durasi baca maksimal (80):
```

Bot akan:
1. ✅ Save config
2. 📡 Discover artikel dari sitemap/homepage
3. 🚀 Langsung start dengan dashboard

### 📝 Setup Manual

```bash
# Tambah target + discover artikel
python main.py add-target BlogKu https://blog-ku.com --visits 600 --discover

# Discover artikel manual
python main.py discover BlogKu

# Jalankan bot
python main.py start
```

### ▶️ Perintah Lengkap

| Perintah | Fungsi |
|----------|--------|
| `quick` | Setup interaktif + langsung jalan 🆕 |
| `start` | Jalankan bot dengan live dashboard |
| `start --threads 20` | Jalankan dengan 20 thread |
| `start --daemon` | Jalankan tanpa dashboard |
| `stop` | Hentikan bot |
| `pause` | Jeda bot |
| `resume` | Lanjutkan bot |
| `status` | Tampilkan semua statistik |
| `campaigns` | Progress campaign saja |
| `discover [nama]` | Temukan artikel (semua atau spesifik) |
| `targets` | Daftar semua target |
| `add-target NAMA URL` | Tambah target baru |
| `add-target --visits 100 --discover` | Tambah target + campaign + discover |
| `remove-target NAMA` | Hapus target |
| `ad-stats` | Detail klik iklan per tipe & network |
| `report` | Export laporan CSV/JSON |
| `test-proxies` | Tes semua proxy |
| `reload` | Reload konfigurasi |
| `reset-stats` | Reset statistik |

---

## 📁 Struktur Proyek

```
cpafast/
├── main.py               # CLI entry point + dashboard interaktif
├── config.py             # Manajemen konfigurasi JSON
├── config.json           # File konfigurasi utama
├── traffic_bot.py        # Core engine bot + campaign
├── visitor.py            # Request & Playwright visitor
├── browser_engine.py     # Async browser engine + pool
├── proxy_manager.py      # Manajemen & rotasi proxy
├── proxy.txt             # Daftar proxy (buat sendiri)
├── user_agent.py         # Rotasi User-Agent
├── ad_detector.py        # Deteksi & klik iklan
├── article_discovery.py  # Discovery artikel
├── statistics.py         # Statistik & reporting
├── scheduler.py          # Penjadwal otomatis
├── logger.py             # Logging dengan rotasi
├── requirements.txt      # Dependencies
└── README.md             # Dokumentasi
```

---

## 💡 Tips Penggunaan

### ⏱️ Durasi Kunjungan
`visit_duration_min: 30` dan `visit_duration_max: 80` — jangan kurang dari 30 detik biar keliatan natural.

### 🌐 Proxy
200 proxy untuk 600 visitor itu aman. Tiap proxy rata-rata cuma kepake 3 kali. Settings recommened:
```json
"rotate_every_request": true,
"test_before_use": true
```

### 🧵 Threads
| Proxy | Saran Threads | Estimasi 600 visit |
|-------|--------------|-------------------|
| 50 proxy | 5-10 | ~1-2 jam |
| 200 proxy | 10-20 | ~30-55 menit |
| 500+ proxy | 20-30 | ~20-30 menit |

### 🖱️ Ad Clicking
Probabilitas 25% cukup realistis. Jangan lebih dari 50% biar gak kelihatan bot.

### 🛡️ Safety
- ✅ Bot **untuk edukasi**
- ✅ Patuhi **ToS** website target
- ✅ Jangan overload server (max 20-30 thread)
- ✅ Gunakan proxy biar IP gak ganti-ganti sendiri
- ✅ Jangan klik iklan yg sama berulang kali

---

## 📦 Dependencies

| Package | Fungsi |
|---------|--------|
| `requests` | HTTP requests + SOCKS support |
| `playwright` | Browser automation (Chromium) |
| `rich` | Dashboard interaktif & CLI styling |
| `beautifulsoup4` | HTML parsing |
| `lxml` | XML/HTML parser cepat |
| `schedule` | Task scheduling |
| `fake-useragent` | User-Agent rotation |

---

## 📊 Contoh Output Campaign

```
[SUCCESS] BlogKu | 200 | 1.23s | Ads: 3/8 | [BROWSER]
[SUCCESS] BlogKu | Campaign: 451/600 (75%)
[SUCCESS] BlogKu | 200 | 0.89s | no proxy
[SUCCESS] BlogKu | Campaign: 452/600 (75%)
...
[SUCCESS] ALL CAMPAIGNS COMPLETE!
[SUMMARY] Total visits: 600
[SUMMARY] Success: 578 | Fail: 22
[SUMMARY] Rate: 96.33%
[SUMMARY] Time: 3210s
[SUMMARY] Avg response: 1.45s
[SUMMARY] Ads clicked: 45/120
```
