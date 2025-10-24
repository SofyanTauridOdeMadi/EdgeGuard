# 🧠 Edge Guard
**Sistem Pengendalian Akses Internet Anak Berbasis Edge-AI di Router**  
Dengan fitur **pemblokiran situs otomatis**, **penjadwalan cerdas**, dan **pengawasan real-time** untuk mendukung aktivitas digital anak yang sehat dan aman.

---

## 🚀 Deskripsi Singkat
**Edge Guard** adalah sistem pengawasan dan pengendalian akses internet yang berjalan langsung di perangkat **router (Edge Device)**.  
Sistem ini dirancang untuk membantu **orang tua memantau aktivitas online anak** dengan kecerdasan buatan yang mampu mendeteksi dan memblokir situs berisiko, serta mengatur waktu akses sesuai kebutuhan belajar dan istirahat.

---

## ✨ Fitur Utama
- 🔍 **AI Site Classification** – Model *Edge-AI* mendeteksi dan memblokir situs tidak layak secara otomatis.  
- ⏰ **Penjadwalan Cerdas** – Internet anak aktif hanya pada jam tertentu (belajar, tidur, bermain).  
- 📊 **Dashboard Pengawasan** – Tampilan web interaktif untuk orang tua memantau status perangkat, aktivitas, dan log akses.  
- 🔒 **Kontrol Router Langsung** – Integrasi dengan **OpenWRT** atau **Xiaomi Router** untuk mengatur firewall, DNS, dan routing.  
- 📡 **Dual Mode** – Pengaturan otomatis oleh sistem atau manual oleh pengguna.  
- 💾 **Penyimpanan Konfigurasi Aman** – Menggunakan **SQLite / MongoDB**.  

---

## 🧩 Arsitektur Sistem
```
[Parent Dashboard] ⇄ [Flask Backend + AI Engine] ⇄ [Router API (OpenWRT)]
                                      │
                                      └── Database (SQLite / MongoDB)
```

---

## 🛠️ Teknologi yang Digunakan
| Komponen | Teknologi |
|-----------|------------|
| Backend | Python (Flask) |
| AI Engine | TensorFlow Lite / Edge AI Model |
| Frontend | HTML, CSS, JavaScript |
| Router Control | OpenWRT API, Shell Integration |
| Database | SQLite / MongoDB |
| Deployment | Edge Device (Router) / Local Server |

---

## 📆 Roadmap (Target Pengembangan)
| Bulan | Tahapan | Output |
|--------|----------|---------|
| 1 | Penyusunan Bab 1–2 Skripsi + Desain Sistem | Proposal + Mockup |
| 2 | Implementasi Backend + AI Detection | Model & API aktif |
| 3 | Dashboard & Integrasi Router | Sistem siap uji coba |
| 4 | Pengujian + Dokumentasi Skripsi | Laporan akhir & demo |

---

## 🧪 Status Proyek
🚧 **Dalam Pengembangan Awal (v0.1-alpha)**  
Target: Integrasi router dan sistem penjadwalan otomatis.

---

## 🧑‍💻 Kontributor
- **Sofyan TauriD Ode Madi** – Peneliti sistem Edge-AI  
*(Mahasiswa Teknik Komputer, Universitas Negeri Makassar)*

---

## 📄 Lisensi
Proyek ini dilindungi oleh **[MIT License](LICENSE)**.  
Bebas digunakan dan dimodifikasi dengan tetap mencantumkan atribusi.