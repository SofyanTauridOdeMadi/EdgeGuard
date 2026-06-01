-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║  Jalankan SETELAH schema.sql:                                        ║
-- ║    mysql -u edgeguard -p edgeguard < dashboard/seed_demo.sql         ║
-- ║                                                                      ║
-- ║  Isi:                                                                ║
-- ║   • pengguna_anak (F2:9C:78:8F:1F:FB) milik "Stom"                   ║
-- ║   • Dompet kuota + jadwal istirahat untuk perangkat tsb              ║
-- ║   • 18 whitelist + 16 blacklist (aturan filter manual)               ║
-- ║   • cache_domain — knowledge base AI realtime                        ║
-- ║   • log_akses 3 hari terakhir (semua milik perangkat nyata)          ║
-- ║                                                                      ║
-- ║  Aman dijalankan berkali-kali — RESET data lama dulu di awal.        ║
-- ║                                                                      ║
-- ║  CATATAN: F2:9C:78:8F:1F:FB adalah MAC "Private Wi-Fi Address"       ║
-- ║  iPhone (acak). Agar stabil, matikan Private Address utk SSID        ║
-- ║  EdgeGuard di: Settings → Wi-Fi → (i) → Private Wi-Fi Address: Off.  ║
-- ╚══════════════════════════════════════════════════════════════════════╝

USE edgeguard;

-- ════════════════════════════════════════════════════════════════════════
-- 1. PENGGUNA ANAK — 1 perangkat NYATA (iPhone milik "Stom")
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO pengguna_anak
  (user_id, admin_id, mac_address, device_name, status_aktif,
   nama, ip_terakhir, jeda, kuota_harian, kuota_terpakai,
   last_reset, last_seen) VALUES
  (1, 1, 'F2:9C:78:8F:1F:FB', 'iPhone', TRUE,
   'Stom', '192.168.1.237', 0, 180, 65, CURDATE(), NOW() - INTERVAL 1 MINUTE);

-- ════════════════════════════════════════════════════════════════════════
-- 2. DOMPET KUOTA
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO dompet_kuota
  (user_id, sisa_hiburan, total_edukasi, batas_harian, terakhir_reset) VALUES
  (1, 20, 80, 60, CURDATE());

-- ════════════════════════════════════════════════════════════════════════
-- 3. JADWAL ISTIRAHAT INTERNET (jadwal_blokir) — malam hari sekolah
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO jadwal_blokir (user_id, hari, jam_mulai, jam_selesai, mode) VALUES
  (1, 'senin',  '22:00:00', '05:00:00', 'blokir'),
  (1, 'selasa', '22:00:00', '05:00:00', 'blokir'),
  (1, 'rabu',   '22:00:00', '05:00:00', 'blokir'),
  (1, 'kamis',  '22:00:00', '05:00:00', 'blokir'),
  (1, 'jumat',  '22:00:00', '05:00:00', 'blokir');

-- ════════════════════════════════════════════════════════════════════════
-- 4. DAFTAR_FILTER — 18 putih + 16 hitam (aturan manual orang tua)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO daftar_filter (admin_id, tipe, domain_url, alasan) VALUES
  -- ── Whitelist (selalu diizinkan) ─────────────────────────────────
  (1, 'putih', 'khanacademy.org',                'Platform belajar matematika & sains'),
  (1, 'putih', 'duolingo.com',                   'Belajar bahasa'),
  (1, 'putih', 'ruangguru.com',                  'Bimbel online'),
  (1, 'putih', 'zenius.net',                     'Video pelajaran sekolah'),
  (1, 'putih', 'quipper.com',                    'Latihan soal'),
  (1, 'putih', 'wikipedia.org',                  'Ensiklopedia umum'),
  (1, 'putih', 'brainly.co.id',                  'Tanya jawab PR'),
  (1, 'putih', 'scholar.google.com',             'Jurnal & riset ilmiah'),
  (1, 'putih', 'kemdikbud.go.id',                'Situs resmi Kemdikbud'),
  (1, 'putih', 'sahabatkeluarga.kemdikbud.go.id','Edukasi keluarga'),
  (1, 'putih', 'whatsapp.com',                   'Komunikasi keluarga'),
  (1, 'putih', 'classroom.google.com',           'Kelas online sekolah'),
  (1, 'putih', 'coursera.org',                   'Kursus online internasional'),
  (1, 'putih', 'edx.org',                        'Kursus universitas dunia'),
  (1, 'putih', 'unm.ac.id',                      'Kampus UNM'),
  (1, 'putih', 'meet.google.com',                'Video call kelas'),
  (1, 'putih', 'detik.com',                      'Berita umum'),
  (1, 'putih', 'kompas.com',                     'Berita umum'),

  -- ── Blacklist (selalu diblokir) ──────────────────────────────────
  (1, 'hitam', 'bet365.com',          'Situs perjudian'),
  (1, 'hitam', '1xbet.com',           'Situs perjudian'),
  (1, 'hitam', 'pkv-games.org',       'Judi online'),
  (1, 'hitam', 'dewa777slot.net',     'Judi slot'),
  (1, 'hitam', 'judi-online.net',     'Judi online'),
  (1, 'hitam', 'slot-gacor99.id',     'Judi slot'),
  (1, 'hitam', 'pragmaticplay.net',   'Provider judi slot'),
  (1, 'hitam', 'pornhub.com',         'Pornografi'),
  (1, 'hitam', 'xnxx.com',            'Pornografi'),
  (1, 'hitam', 'xvideos.com',         'Pornografi'),
  (1, 'hitam', 'redtube.com',         'Pornografi'),
  (1, 'hitam', 'scam-payment.id',     'Scam pembayaran'),
  (1, 'hitam', 'malware-redirect.net','Malware / redirect jahat'),
  (1, 'hitam', 'phishing-bank.cc',    'Phishing perbankan'),
  (1, 'hitam', 'crack-software.io',   'Software bajakan / malware'),
  (1, 'hitam', 'kerumput-iklan.xyz',  'Iklan pop-up berbahaya');

-- ════════════════════════════════════════════════════════════════════════
-- 5. CACHE_DOMAIN — knowledge base AI (hasil klasifikasi realtime)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, terakhir_diakses, jumlah_hit) VALUES
  -- ── EDUKASI ──
  ('khanacademy.org',         'edukasi',  98.5, NOW() - INTERVAL  10 MINUTE,  18),
  ('duolingo.com',            'edukasi',  97.8, NOW() - INTERVAL  45 MINUTE,  15),
  ('ruangguru.com',           'edukasi',  96.2, NOW() - INTERVAL   2 HOUR,   12),
  ('zenius.net',              'edukasi',  95.1, NOW() - INTERVAL   3 HOUR,    6),
  ('classroom.google.com',    'edukasi',  99.0, NOW() - INTERVAL  20 MINUTE,  22),
  ('wikipedia.org',           'edukasi',  94.7, NOW() - INTERVAL   1 HOUR,   14),
  ('scholar.google.com',      'edukasi',  98.9, NOW() - INTERVAL   5 HOUR,    4),
  ('quipper.com',             'edukasi',  93.5, NOW() - INTERVAL   4 HOUR,    5),
  ('brainly.co.id',           'edukasi',  91.2, NOW() - INTERVAL   6 HOUR,    7),
  ('kemdikbud.go.id',         'edukasi',  99.5, NOW() - INTERVAL   8 HOUR,    3),
  ('coursera.org',            'edukasi',  90.4, NOW() - INTERVAL   1 DAY,     2),
  ('meet.google.com',         'edukasi',  88.6, NOW() - INTERVAL  30 MINUTE,  9),
  ('unm.ac.id',               'edukasi',  96.0, NOW() - INTERVAL   1 DAY,     3),
  ('detik.com',               'edukasi',  72.4, NOW() - INTERVAL   2 HOUR,    8),
  ('kompas.com',              'edukasi',  73.8, NOW() - INTERVAL   3 HOUR,    5),

  -- ── HIBURAN ──
  ('youtube.com',             'hiburan',  89.3, NOW() - INTERVAL  15 MINUTE,  41),
  ('tiktok.com',              'hiburan',  85.7, NOW() - INTERVAL  30 MINUTE,  28),
  ('instagram.com',           'hiburan',  82.4, NOW() - INTERVAL   1 HOUR,   24),
  ('spotify.com',             'hiburan',  87.8, NOW() - INTERVAL   3 HOUR,   11),
  ('netflix.com',             'hiburan',  88.5, NOW() - INTERVAL   5 HOUR,    7),
  ('twitch.tv',               'hiburan',  76.8, NOW() - INTERVAL   4 HOUR,    6),
  ('discord.com',             'hiburan',  71.3, NOW() - INTERVAL   6 HOUR,    9),
  ('vidio.com',               'hiburan',  84.5, NOW() - INTERVAL   1 HOUR,    5),
  ('snapchat.com',            'hiburan',  77.9, NOW() - INTERVAL   4 HOUR,    4),
  ('telegram.org',            'hiburan',  68.3, NOW() - INTERVAL   2 HOUR,    8),

  -- ── NEGATIF ──
  ('pornhub.com',             'negatif', 100.0, NOW() - INTERVAL   1 HOUR,    2),
  ('xnxx.com',                'negatif', 100.0, NOW() - INTERVAL   5 HOUR,    2),
  ('bet365.com',              'negatif', 100.0, NOW() - INTERVAL   8 HOUR,    1),
  ('dewa777slot.net',         'negatif',  99.8, NOW() - INTERVAL   3 HOUR,    1),
  ('slot-gacor99.id',         'negatif',  98.2, NOW() - INTERVAL   2 HOUR,    1),
  ('kerumput-iklan.xyz',      'negatif',  91.2, NOW() - INTERVAL   2 DAY,     1);

-- ════════════════════════════════════════════════════════════════════════
-- 6. LOG_AKSES — riwayat 3 hari (semua milik iPhone "Stom")
--    Pola realistis: dominan edukasi + hiburan, beberapa percobaan negatif.
-- ════════════════════════════════════════════════════════════════════════

-- ─────────────────── HARI INI (06:00 → sekarang) ───────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 410, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '06:40' HOUR_MINUTE)),
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '07:20' HOUR_MINUTE)),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 95.2,210, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '08:05' HOUR_MINUTE)),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 180, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '08:50' HOUR_MINUTE)),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 89.3,1800,'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '09:40' HOUR_MINUTE)),
  (1, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 280, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '10:30' HOUR_MINUTE)),
  (1, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.7,1100,'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '11:25' HOUR_MINUTE)),
  (1, 'pornhub.com',          'negatif','blokir', 'blacklist',     100,   0, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '12:10' HOUR_MINUTE)),
  (1, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 82.4, 850,'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '13:15' HOUR_MINUTE)),
  (1, 'brainly.co.id',        'edukasi','izinkan','whitelist',     100,  85, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '14:00' HOUR_MINUTE)),
  (1, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 87.8, 320,'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '15:20' HOUR_MINUTE)),
  (1, 'xnxx.com',             'negatif','blokir', 'blacklist',     100,   0, 'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '16:05' HOUR_MINUTE)),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 94.7, 160,'Stom','F2:9C:78:8F:1F:FB', LEAST(NOW(), CURDATE() + INTERVAL '17:00' HOUR_MINUTE));

-- ─────────────────── KEMARIN (H-1) ───────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 410, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '07:00' HOUR_MINUTE),
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '08:30' HOUR_MINUTE),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 89.0,1700,'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '10:15' HOUR_MINUTE),
  (1, 'dewa777slot.net',      'negatif','blokir', 'blacklist',     100,   0, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '11:00' HOUR_MINUTE),
  (1, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 290, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '13:00' HOUR_MINUTE),
  (1, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.6,1100,'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (1, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 87.0, 300,'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '17:30' HOUR_MINUTE),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 190, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '19:00' HOUR_MINUTE);

-- ─────────────────── 2 HARI LALU (H-2) ───────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '08:00' HOUR_MINUTE),
  (1, 'scholar.google.com',   'edukasi','izinkan','whitelist',     100, 110, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '10:00' HOUR_MINUTE),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.0,1800,'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '13:00' HOUR_MINUTE),
  (1, 'kerumput-iklan.xyz',   'negatif','blokir', 'blacklist',     100,   0, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '14:30' HOUR_MINUTE),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 95.2,210, 'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '16:00' HOUR_MINUTE),
  (1, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 82.0, 900,'Stom','F2:9C:78:8F:1F:FB', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '18:30' HOUR_MINUTE);

-- ════════════════════════════════════════════════════════════════════════
-- Ringkasan
-- ════════════════════════════════════════════════════════════════════════
SELECT 'PENGGUNA ANAK'        AS info, COUNT(*) AS n FROM pengguna_anak
UNION ALL SELECT 'WHITELIST',                 COUNT(*) FROM daftar_filter WHERE tipe='putih'
UNION ALL SELECT 'BLACKLIST',                 COUNT(*) FROM daftar_filter WHERE tipe='hitam'
UNION ALL SELECT 'CACHE_DOMAIN total',        COUNT(*) FROM cache_domain
UNION ALL SELECT '  └─ edukasi',              COUNT(*) FROM cache_domain WHERE kategori='edukasi'
UNION ALL SELECT '  └─ hiburan',              COUNT(*) FROM cache_domain WHERE kategori='hiburan'
UNION ALL SELECT '  └─ negatif',              COUNT(*) FROM cache_domain WHERE kategori='negatif'
UNION ALL SELECT 'LOG total',                 COUNT(*) FROM log_akses
UNION ALL SELECT '  └─ Hari ini',             COUNT(*) FROM log_akses WHERE DATE(waktu_akses) = CURDATE()
UNION ALL SELECT '  └─ Kemarin',              COUNT(*) FROM log_akses WHERE DATE(waktu_akses) = CURDATE() - INTERVAL 1 DAY
UNION ALL SELECT '  └─ H-2',                  COUNT(*) FROM log_akses WHERE DATE(waktu_akses) = CURDATE() - INTERVAL 2 DAY
UNION ALL SELECT '  └─ diblokir total',       COUNT(*) FROM log_akses WHERE aksi='blokir'
UNION ALL SELECT 'JADWAL BLOKIR',             COUNT(*) FROM jadwal_blokir
UNION ALL SELECT 'DOMPET KUOTA',              COUNT(*) FROM dompet_kuota;
