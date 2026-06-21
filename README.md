# 🛡️ Edge Guard

> **Smart Parental Control Berbasis Hybrid Edge-AI pada Router OpenWrt**

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-edgeguard.my.id-2563EB?style=for-the-badge)](https://edgeguard.my.id)

Edge Guard adalah sistem kontrol orang tua (*parental control*) cerdas yang menanamkan
model AI **langsung di dalam router**. Klasifikasi konten dilakukan di sisi *edge*
(router) secara *real-time*, lalu dipantau dan dikendalikan oleh orang tua melalui
**dashboard web** dan **bot Telegram dua arah**.

---

## 📌 Deskripsi Singkat

Berbeda dari solusi *parental control* berbasis cloud, Edge Guard memproses lalu lintas
jaringan **secara lokal di router**. Router menyadap nama domain (**SNI**) dari setiap
koneksi TLS, mengklasifikasikannya dengan model **Multinomial Naive Bayes + TF-IDF char
n-gram** yang berjalan murni di Python (tanpa library berat), lalu memberlakukan kebijakan
melalui firewall **nftables**. Situs yang diblokir tidak sekadar gagal dimuat — anak
diarahkan ke **halaman peringatan** lewat *captive portal* (termasuk untuk HTTPS, via
MITM dengan CA EdgeGuard). Setiap kejadian penting dikirim ke VPS untuk dicatat, ditampilkan
di dashboard, dan diteruskan sebagai notifikasi Telegram.

---

## ✨ Fitur Utama

- 🧠 **Klasifikasi konten di edge** — Multinomial Naive Bayes (4 kelas) berjalan langsung di router (offline, low-latency, *pure-Python*).
- 🌐 **Penyadapan SNI** — mendeteksi domain tujuan dari handshake TLS tanpa membongkar enkripsi.
- 🚫 **Penegakan otomatis** — pemblokiran via **nftables** berdasarkan kategori, jadwal, dan kuota.
- 🪧 **Captive portal + MITM HTTPS** — situs terblokir menampilkan **halaman peringatan** (bukan error), termasuk situs HTTPS via CA EdgeGuard yang dipasang di perangkat anak.
- 🔒 **Anti-bypass DNS** — paksa DNS lewat router (Do53), blokir **DoT/DoH/DoQ**, dan *sinkhole* resolver terenkripsi via dnsmasq.
- ⏰ **Jadwal akses & manajemen kuota** — batasi waktu (mode istirahat / jeda) dan kuota hiburan per perangkat; pemakaian dihitung dari bandwidth aktif → menit.
- 🎁 **Sistem reward** — akses konten **edukasi** mengumpulkan menit belajar → otomatis menambah **kuota hiburan**; pengukuran trafik **dua arah** (upload + download).
- 🤖 **Bot Telegram dua arah** — notifikasi *real-time* + menu kontrol interaktif (`/start`).
- 🔔 **Permintaan izin** — anak dapat meminta akses, orang tua menyetujui dari dashboard/Telegram.
- 📊 **Dashboard web** — pantau aktivitas, kelola perangkat, kategori AI, filter, jadwal, dan kuota.
- 🖨️ **Laporan PDF (A4)** — rekap per perangkat: kuota harian, grafik durasi aktivitas, proporsi kategori, situs sering diakses, dan domain negatif yang sempat terbuka.
- 📱 **Demo perangkat anak** — simulator HP anak (`/demo`) yang tersambung langsung ke server untuk presentasi.

---

## 🏗️ Arsitektur Sistem

```
┌─────────────────────────────────────────────┐        ┌─────────────────────────────────┐
│        ROUTER (OpenWrt AX3000T · Python)     │        │            VPS (Cloud)          │
│                                              │        │       edgeguard.my.id           │
│  Sniff SNI ─► Naive Bayes ─► nftables        │        │                                 │
│      │            │             │            │        │   nginx :443 (Let's Encrypt)    │
│      │            │             ├─ Captive    │       │          │                      │
│      │            │             │  Portal +   │  HTTPS │          ▼                      │
│      │            │             │  MITM(443→  │  POST  │   Flask :8000 (systemd)         │
│      │            │             │  8843, CA)  │───────►│          │                      │
│      │            │             └─ Anti-bypass│        │      MySQL/MariaDB               │
│      │            │                DNS (DoT/  │        │          │                      │
│      │            └─ Kuota & Reward (thread)  │        │   ┌──────┴───────┐              │
│      └─ DNS sinkhole (dnsmasq)                │        │   │ Dashboard Web │              │
│         heartbeat (thread)                    │        │   │  + Bot Telegram│             │
└─────────────────────────────────────────────┘        └───┴──────┬────────┴──────────────┘
                                                                   │
                                                              ┌────▼─────┐
                                                              │ Telegram │
                                                              │ Orang Tua│
                                                              └──────────┘
```

**Alur kerja:**
1. Router menyadap **SNI** dari koneksi TLS yang lewat (`br-lan`).
2. Domain diklasifikasikan oleh **Naive Bayes** (model di-*embed* di router) → *negatif / edukasi / hiburan / netral*.
3. Router memberlakukan kebijakan **nftables**: blokir hiburan saat kuota habis, blokir penuh saat jadwal/jeda, dan arahkan situs negatif ke **halaman peringatan** (captive portal / MITM HTTPS).
4. **Anti-bypass**: DNS dipaksa lewat router, DoT/DoH diblokir & resolver terenkripsi di-*sinkhole*.
5. **Kuota & reward** dihitung dari counter trafik per-MAC (dua arah) → menit aktif & bonus belajar.
6. Setiap kejadian (blokir, izin, heartbeat, pemakaian) dikirim via **HTTPS POST** ke VPS.
7. VPS menyimpan log di **MySQL**, menampilkannya di **dashboard** (di balik nginx + systemd), dan **bot Telegram** meneruskan notifikasi serta menerima perintah orang tua.

---

## 🧰 Teknologi

| Komponen          | Teknologi                                                              |
|-------------------|-----------------------------------------------------------------------|
| **Edge Device**   | Router OpenWrt (Xiaomi AX3000T)                                        |
| **AI Engine**     | Multinomial Naive Bayes + TF-IDF *char n-gram* (3–5), *pure-Python*   |
| **Pelatihan**     | Python · scikit-learn · Jupyter Notebook (`model_ai/`)                |
| **Sistem Router** | Python · **nftables** (`nft`) · dnsmasq · shell script                |
| **Captive/MITM**  | `portal_server.py` (HTTPS SNI MITM) · CA EdgeGuard (OpenSSL)          |
| **Backend / API** | Python · Flask (di balik **nginx**, port `8000`) · systemd            |
| **Database**      | MySQL / MariaDB                                                        |
| **Frontend**      | HTML · CSS · JavaScript (server-rendered, Jinja2)                     |
| **Notifikasi**    | Telegram Bot API (long-polling, dua arah)                             |
| **Keamanan**      | TLS Let's Encrypt · bcrypt · login lockout per-akun · ProxyFix · kredensial via env/file (gitignored) |

> **Model v2.10** — 4 kelas (*negatif/edukasi/hiburan/netral*), 7.255 fitur, akurasi pengujian **≈ 92.5%**.

---

## 📂 Struktur Proyek

```
EdgeGuard/
├── sistem_router/             # Program yang berjalan di router OpenWrt
│   ├── pemantau_trafik.py      #  Sniff SNI + pipeline AI + sinkhole; host thread kuota/reward/heartbeat
│   ├── klasifikasi_ai.py       #  Inferensi Naive Bayes (pure-Python)
│   ├── kuota_tracker.py        #  Bandwidth aktif → menit kuota hiburan
│   ├── reward_sistem.py        #  Edukasi → bonus kuota hiburan (ukur 2 arah)
│   ├── eg_nft.py               #  Helper counter nft 'measure' (cache + guard per-MAC)
│   ├── captive_portal.sh       #  nftables eg_portal: portal, anti-bypass DNS, MITM, counter
│   ├── portal_server.py        #  Server halaman peringatan + MITM HTTPS (cert per-domain)
│   ├── aturan_firewall.sh      #  Wrapper firewall/ipset (pelengkap)
│   ├── heartbeat.py            #  Health-check ke VPS (kini thread di pemantau)
│   ├── config.py               #  Konfigurasi & util SSL (env EG_*)
│   ├── install.sh / edgeguard.init   #  Instalasi & init.d (procd)
│   └── model_export.json / model_router.pkl   #  Model terlatih untuk router
│
├── dashboard/                 # Backend Flask + dashboard web (di VPS)
│   ├── api_dashboard.py        #  Server Flask + API + bot Telegram
│   ├── schema.sql / seed_demo.sql    #  Skema & data contoh
│   ├── dashboard.html · laporan.html · demo.html · kelola_perangkat.html …  # Halaman
│   ├── aset/                   #  Logo, background, CSS
│   ├── ssl/                    #  Sertifikat (lokal/dev)
│   └── token_bot.txt           #  Token bot (gitignored — tidak di-commit)
│
├── model_ai/                 # Pelatihan & evaluasi model
│   ├── AI_LATIH.ipynb          #  Notebook pelatihan
│   ├── retrain.py              #  Latih ulang + ekspor model router
│   ├── datasetkumpulanweb.xlsx #  Dataset domain berlabel
│   └── hasil_pengujian/        #  Confusion matrix, ROC/PR, learning curve, dll.
│
├── demo/simulasi-hp-anak.html # Simulator HP anak (versi standalone)
├── EdgeGuard-CA.crt           # Sertifikat CA untuk dipasang di perangkat anak
└── README.md
```

---

## 🚀 Menjalankan Dashboard (Pengembangan)

```bash
# 1. Siapkan database (MySQL/MariaDB)
mysql -u root -p < dashboard/schema.sql
#   (opsional) data contoh untuk demo:
mysql -u root -p edgeguard < dashboard/seed_demo.sql

# 2. Konfigurasi token bot Telegram
export TG_BOT_TOKEN="token_dari_@BotFather"
#   atau simpan di dashboard/token_bot.txt (sudah masuk .gitignore)

# 3. Jalankan server Flask
cd dashboard
python3 api_dashboard.py
#   Dashboard dev tersedia di http://localhost:8080
```

> **Produksi** berjalan di balik **nginx** (TLS Let's Encrypt) yang mem-*proxy* ke
> Flask `127.0.0.1:8000`, dikelola **systemd** (`edgeguard-web.service`) di
> [edgeguard.my.id](https://edgeguard.my.id). Set `EG_BEHIND_PROXY=1 EG_PORT=8000`.

### Pemasangan di Router

```bash
# Salin folder sistem_router/ ke router (OpenWrt) lalu:
sh install.sh                 # instal dependensi + service init.d
/etc/init.d/edgeguard start   # jalankan (procd, auto-start saat boot)
```

> **Catatan:** untuk situs HTTPS yang diblokir agar tampil halaman peringatan (bukan error),
> pasang **`EdgeGuard-CA.crt`** sebagai *trusted CA* di tiap perangkat anak. Token & kredensial
> **tidak pernah** disimpan di kode/database (dibaca dari env atau file ber-`.gitignore`).

---

## 📈 Status Proyek

> **v2.10 (model) · sistem live** — Final Proyek. Dipakai pada router OpenWrt AX3000T
> dengan dashboard daring di edgeguard.my.id.

---

## 👥 Kontributor

**Peneliti**
- **Sofyan Taurid Ode Madi** — Mahasiswa Teknik Komputer, Universitas Negeri Makassar

**Dosen Pembimbing**
- Dr. Eng. Ir. Abdul Wahid, M.Kom., IPM. *(Pembimbing 1)*
- Dr. Eng. Ir. Jumadi M. Parenreng, S.ST., M.Kom., IPM. *(Pembimbing 2)*

**Dosen Penguji**
- Abd. Rahman Patta, S.Kom., M.T., Ph.D. *(Penguji 1)*
- Muh. Syahid Nur Wahid, S.Pd., M.Pd. *(Penguji 2)*

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah **MIT License**.
