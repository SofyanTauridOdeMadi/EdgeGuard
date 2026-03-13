# 🧠 Edge Guard

**Sistem Pengendalian Akses Internet Anak Berbasis Edge-AI di Router**\
Dengan fitur **pemblokiran situs otomatis**, **penjadwalan cerdas**, dan
**pengawasan real-time** untuk mendukung aktivitas digital anak yang
sehat dan aman.

------------------------------------------------------------------------

## 🚀 Deskripsi Singkat

**Edge Guard** adalah sistem pengawasan dan pengendalian akses internet
yang berjalan langsung di perangkat **router (Edge Device)**.\
Sistem ini dirancang untuk membantu **orang tua memantau aktivitas
online anak** dengan kecerdasan buatan yang mampu mendeteksi dan
memblokir situs berisiko, serta mengatur waktu akses sesuai kebutuhan
belajar dan istirahat.

------------------------------------------------------------------------

## ✨ Fitur Utama

-   🔍 **AI Site Classification** -- Model *Edge-AI* mendeteksi dan
    memblokir situs tidak layak secara otomatis.\
-   ⏰ **Penjadwalan Cerdas** -- Internet anak aktif hanya pada jam
    tertentu (belajar, tidur, bermain).\
-   📊 **Dashboard Pengawasan** -- Tampilan web interaktif untuk orang
    tua memantau status perangkat, aktivitas, dan log akses.\
-   🔒 **Kontrol Router Langsung** -- Integrasi dengan **OpenWRT** atau
    **Xiaomi Router** untuk mengatur firewall, DNS, dan routing.\
-   📡 **Dual Mode** -- Pengaturan otomatis oleh sistem atau manual oleh
    pengguna.\
-   💾 **Penyimpanan Konfigurasi Aman** -- Menggunakan **SQLite**.

------------------------------------------------------------------------

## 🧩 Arsitektur Sistem

    [Parent Dashboard] ⇄ [Backend + AI Engine] ⇄ [Router API (OpenWRT)]
                                         │
                                         └── Database (SQLite)

------------------------------------------------------------------------

## 🛠️ Teknologi yang Digunakan

  Komponen         Teknologi
  ---------------- -------------------------------------
  Backend          Flask
  AI Engine        Edge AI Model
  Frontend         HTML, CSS, JavaScript
  Router Control   OpenWRT API, Shell Integration
  Database         SQLite
  Deployment       Edge Device (Router) / Local Server

------------------------------------------------------------------------

## 🧪 Status Proyek

🚧 **Dalam Pengembangan Awal (v3.4-Alpha)**\
Target: Penyusunan Proposal, Tahap perancangan

------------------------------------------------------------------------

## 🧑‍💻 Kontributor

**Sofyan Taurid Ode Madi** -- Peneliti sistem Edge-AI\
Mahasiswa Teknik Komputer, Universitas Negeri Makassar

**Dr. Eng. Ir. Abdul Wahid, M.Kom., IPM.** -- Pembimbing 1\
**Dr. Eng. Ir. Jumadi M. Parenreng, S.ST, M.Kom., IPM.** -- Pembimbing 2

**Abd. Rahman Patta, S.Kom., M.T., Ph.D** -- Penguji 1\
**Muh. Syahid Nur Wahid, S.Pd., M.Pd.** -- Penguji 2

------------------------------------------------------------------------

## 📄 Lisensi

Proyek ini menggunakan **MIT License**.\
Bebas digunakan dan dimodifikasi dengan tetap mencantumkan atribusi
kepada penulis.
