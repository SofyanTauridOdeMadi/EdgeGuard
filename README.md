# 🛡️ Edge Guard

> **Smart Parental Control Berbasis Hybrid Edge-AI pada Router OpenWrt**

Edge Guard adalah sistem kontrol orang tua (*parental control*) cerdas yang menanamkan
model AI **langsung di dalam router**. Klasifikasi konten dilakukan di sisi *edge*
(router) secara *real-time*, lalu hasilnya dipantau dan dikendalikan oleh orang tua
melalui **dashboard web** dan **bot Telegram dua arah**.

---

## 📌 Deskripsi Singkat

Berbeda dari solusi *parental control* berbasis cloud, Edge Guard memproses lalu lintas
jaringan **secara lokal di router**. Router menyadap nama domain (SNI) dari setiap koneksi,
mengklasifikasikannya dengan model **Naive Bayes** yang berjalan murni di Python (tanpa
ketergantungan library berat), lalu memberlakukan aturan firewall (`iptables`) sesuai
kebijakan. Setiap kejadian penting dikirim ke VPS untuk dicatat dan diteruskan sebagai
notifikasi Telegram kepada orang tua.

---

## ✨ Fitur Utama

- 🧠 **Klasifikasi konten di edge** — model Naive Bayes berjalan langsung di router (offline, low-latency).
- 🌐 **Penyadapan SNI** — mendeteksi domain tujuan tanpa membongkar enkripsi HTTPS.
- 🚫 **Penegakan otomatis** — pemblokiran via `iptables`/firewall berdasarkan kategori & jadwal.
- ⏰ **Jadwal akses & manajemen kuota** — batasi waktu dan kuota pemakaian per perangkat.
- 📊 **Dashboard web** — pantau aktivitas, kelola perangkat, kategori, dan aturan filter.
- 🤖 **Bot Telegram dua arah** — notifikasi *real-time* + menu kontrol interaktif (`/start`).
- 🔔 **Permintaan izin** — anak dapat meminta akses, orang tua menyetujui dari Telegram.
- 🎁 **Sistem reward** — pemberian waktu/kuota tambahan sebagai insentif.

---

## 🏗️ Arsitektur Sistem

```
┌──────────────────────────────────────┐        ┌──────────────────────────────┐
│       ROUTER (OpenWrt / Python)      │        │           VPS (Cloud)        │
│                                      │        │                              │
│ Sniff SNI ─► Naive Bayes ─► iptables │        │  Flask :8080  +  MySQL/Maria │
│      │            │            │     │        │       │                      │
│      └──────── POST log ───────┼─────┼───────►│  Dashboard Web (orang tua)   │
│                                │     │        │       │                      │
│        Heartbeat / Kuota ──────┘     │        │       └──► Bot & Notifikasi  │
└──────────────────────────────────────┘        │            Telegram          │
                                                └──────────────┬───────────────┘
                                                               │
                                                          ┌────▼─────┐
                                                          │ Telegram │
                                                          │ Orang Tua│
                                                          └──────────┘
```

**Alur kerja:**
1. Router menyadap **SNI** dari koneksi yang lewat.
2. Domain diklasifikasikan oleh **Naive Bayes** (model di-*embed* di router).
3. Router memberlakukan **aturan firewall** sesuai kategori, jadwal, dan kuota.
4. Setiap kejadian (blokir, permintaan izin, heartbeat) dikirim via **HTTP POST** ke VPS.
5. VPS menyimpan log di **MySQL/MariaDB** dan menampilkannya di **dashboard**.
6. **Bot Telegram** meneruskan notifikasi dan menerima perintah kontrol dari orang tua.

---

## 🧰 Teknologi

| Komponen        | Teknologi                                                        |
|-----------------|------------------------------------------------------------------|
| **Edge Device** | Router OpenWrt (Xiaomi AX3000T)                                  |
| **AI Engine**   | Naive Bayes — *pure-Python* (Multinomial), di-*embed* di router  |
| **Pelatihan**   | Python · scikit-learn · Jupyter Notebook (`model_ai/`)           |
| **Sistem Router** | Python · `iptables` · shell script                             |
| **Backend / API** | Python · Flask (port `8080`)                                   |
| **Database**    | MySQL / MariaDB (XAMPP)                                           |
| **Frontend**    | HTML · CSS · JavaScript (server-rendered)                        |
| **Notifikasi**  | Telegram Bot API (long-polling, dua arah)                        |
| **Keamanan**    | bcrypt · login lockout · kredensial via env/file (gitignored)    |

> Akurasi model pada pengujian: **±94.5%**.

---

## 📂 Struktur Proyek

```
EdgeGuard/
├── sistem_router/          # Program yang berjalan di router OpenWrt
│   ├── pemantau_trafik.py   #  Sniff SNI + pipeline klasifikasi
│   ├── klasifikasi_ai.py    #  Inferensi Naive Bayes (pure-Python)
│   ├── kuota_tracker.py     #  Pelacakan kuota per perangkat
│   ├── reward_sistem.py     #  Sistem reward
│   ├── heartbeat.py         #  Health check ke VPS
│   ├── notifikasi_telegram.py
│   ├── aturan_firewall.sh   #  Aturan iptables
│   ├── install.sh / edgeguard.init
│   └── model_export.json    #  Model terlatih (siap dipakai router)
│
├── dashboard/              # Backend Flask + dashboard web (di VPS)
│   ├── api_dashboard.py     #  Server Flask + API + bot Telegram
│   ├── schema.sql           #  Skema database
│   ├── *.html               #  Halaman dashboard
│   ├── aset/                #  Logo, background, CSS
│   └── token_bot.txt        #  Token bot (gitignored — tidak di-commit)
│
├── model_ai/              # Pelatihan model
│   ├── AI_LATIH.ipynb       #  Notebook pelatihan
│   └── datasetkumpulanweb.xlsx
│
└── README.md
```

---

## 🚀 Menjalankan Dashboard (Pengembangan)

```bash
# 1. Siapkan database (MySQL/MariaDB via XAMPP)
mysql -u root -p < dashboard/schema.sql

# 2. Konfigurasi token bot Telegram
cp dashboard/token_bot.contoh.txt dashboard/token_bot.txt
#   lalu isi token dari @BotFather, atau set environment variable:
export TG_BOT_TOKEN="token_anda"

# 3. Jalankan server Flask
cd dashboard
python3 api_dashboard.py
#   Dashboard tersedia di http://localhost:8080
```

> **Catatan keamanan:** Token bot **tidak pernah** disimpan di kode atau database.
> Token dibaca dari environment variable `TG_BOT_TOKEN`, atau dari berkas lokal
> `dashboard/token_bot.txt` yang sudah masuk `.gitignore`.

---

## 📈 Status Proyek

> **v9.01** —  Pengujian Proyek

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
