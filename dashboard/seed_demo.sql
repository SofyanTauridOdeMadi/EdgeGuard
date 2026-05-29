-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║  EDGE GUARD — SEED DATA DEMO (schema baru ERD, dataset lebih kaya)   ║
-- ║                                                                       ║
-- ║  Jalankan SETELAH schema.sql:                                         ║
-- ║    mysql -u edgeguard -p edgeguard < dashboard/seed_demo.sql          ║
-- ║                                                                       ║
-- ║  Isi:                                                                 ║
-- ║   • 6 pengguna_anak (Stom/Miku/Asraf/Bila/Naufal/Aira)               ║
-- ║   • Dompet kuota per anak                                            ║
-- ║   • Jadwal istirahat internet per anak                               ║
-- ║   • 18 whitelist + 16 blacklist                                      ║
-- ║   • ~45 cache_domain (knowledge AI realtime)                         ║
-- ║   • ~140 log_akses tersebar 3 hari terakhir (hari ini/kemarin/H-2)   ║
-- ║                                                                       ║
-- ║  Aman dijalankan berkali-kali — script RESET data demo dulu.         ║
-- ╚══════════════════════════════════════════════════════════════════════╝

USE edgeguard;

-- ════════════════════════════════════════════════════════════════════════
-- 1. 6 PENGGUNA ANAK (admin_id = 1, hasil seed schema.sql)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO pengguna_anak
  (user_id, admin_id, mac_address, device_name, status_aktif,
   nama, ip_terakhir, jeda, kuota_harian, kuota_terpakai,
   last_reset, last_seen) VALUES
  (1, 1, '8A:48:1C:98:15:C6', 'MacBook Air M2',         TRUE,
   'Stom',  '192.168.31.145', 0, 180,  85, CURDATE(), NOW() - INTERVAL  1 MINUTE),
  (2, 1, 'AA:BB:CC:44:55:66', 'iPad Pro M2',            TRUE,
   'Miku',  '192.168.31.62',  0, 120,  72, CURDATE(), NOW() - INTERVAL  3 MINUTE),
  (3, 1, 'AA:BB:CC:77:88:99', 'Samsung Galaxy A56 5G',  FALSE,
   'Asraf', '192.168.31.23',  0, 150, 110, CURDATE(), NOW() - INTERVAL  4 HOUR),
  (4, 1, 'D4:90:9C:11:22:33', 'Samsung Smart TV',       TRUE,
   'Bila',  '192.168.31.40',  0, 240, 165, CURDATE(), NOW() - INTERVAL  2 MINUTE),
  (5, 1, 'B8:27:EB:55:66:77', 'PlayStation 5',          FALSE,
   'Naufal','192.168.31.55',  0, 180, 142, CURDATE(), NOW() - INTERVAL 30 MINUTE),
  (6, 1, '90:81:58:AA:BB:CC', 'iPhone 11 Pro Max',      TRUE,
   'Aira',  '192.168.31.77',  0, 120,  64, CURDATE(), NOW() - INTERVAL  8 MINUTE);

-- ════════════════════════════════════════════════════════════════════════
-- 2. DOMPET KUOTA per anak
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO dompet_kuota
  (user_id, sisa_hiburan, total_edukasi, batas_harian, terakhir_reset) VALUES
  (1, 25, 95, 60, CURDATE()),   -- Stom: rajin → bonus tersisa
  (2,  5, 25, 60, CURDATE()),   -- Miku: seimbang
  (3,  0,  8, 60, CURDATE()),   -- Asraf: bonus habis
  (4,  0,  0, 30, CURDATE()),   -- Bila (TV): tidak ada edu, bonus 0
  (5, 10, 20, 60, CURDATE()),   -- Naufal: gaming, sedikit edu
  (6, 15, 45, 60, CURDATE());   -- Aira: cukup belajar

-- ════════════════════════════════════════════════════════════════════════
-- 3. JADWAL ISTIRAHAT INTERNET (jadwal_blokir)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO jadwal_blokir (user_id, hari, jam_mulai, jam_selesai, mode) VALUES
  -- Stom: malam belajar (22:00–05:00 hari sekolah)
  (1, 'senin',   '22:00:00', '05:00:00', 'blokir'),
  (1, 'selasa',  '22:00:00', '05:00:00', 'blokir'),
  (1, 'rabu',    '22:00:00', '05:00:00', 'blokir'),
  (1, 'kamis',   '22:00:00', '05:00:00', 'blokir'),
  (1, 'jumat',   '22:00:00', '05:00:00', 'blokir'),
  -- Miku: 21:30–06:00
  (2, 'senin',   '21:30:00', '06:00:00', 'blokir'),
  (2, 'selasa',  '21:30:00', '06:00:00', 'blokir'),
  -- Asraf: hari sekolah pagi (08:00–15:00) + malam (22:00–06:00)
  (3, 'senin',   '08:00:00', '15:00:00', 'blokir'),
  (3, 'senin',   '22:00:00', '06:00:00', 'blokir'),
  (3, 'selasa',  '22:00:00', '06:00:00', 'blokir'),
  -- Bila (TV): nonton terbatas sampai jam 21:00
  (4, 'senin',   '21:00:00', '06:00:00', 'blokir'),
  (4, 'selasa',  '21:00:00', '06:00:00', 'blokir'),
  (4, 'rabu',    '21:00:00', '06:00:00', 'blokir'),
  -- Naufal (PS5): no gaming saat jam sekolah & malam
  (5, 'senin',   '07:00:00', '14:00:00', 'blokir'),
  (5, 'senin',   '23:00:00', '06:00:00', 'blokir'),
  (5, 'selasa',  '07:00:00', '14:00:00', 'blokir'),
  -- Aira: malam saja
  (6, 'senin',   '22:30:00', '05:30:00', 'blokir'),
  (6, 'selasa',  '22:30:00', '05:30:00', 'blokir'),
  (6, 'rabu',    '22:30:00', '05:30:00', 'blokir');

-- ════════════════════════════════════════════════════════════════════════
-- 4. DAFTAR_FILTER — 18 putih + 16 hitam
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
-- 5. CACHE_DOMAIN — knowledge base AI (45 domain unik)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, terakhir_diakses, jumlah_hit) VALUES
  -- ── EDUKASI ──
  ('khanacademy.org',         'edukasi',  98.5, NOW() - INTERVAL  10 MINUTE,  62),
  ('duolingo.com',            'edukasi',  97.8, NOW() - INTERVAL  45 MINUTE,  58),
  ('ruangguru.com',           'edukasi',  96.2, NOW() - INTERVAL   2 HOUR,   41),
  ('zenius.net',              'edukasi',  95.1, NOW() - INTERVAL   3 HOUR,   23),
  ('classroom.google.com',    'edukasi',  99.0, NOW() - INTERVAL  20 MINUTE,  78),
  ('wikipedia.org',           'edukasi',  94.7, NOW() - INTERVAL   1 HOUR,   34),
  ('scholar.google.com',      'edukasi',  98.9, NOW() - INTERVAL   5 HOUR,   12),
  ('quipper.com',             'edukasi',  93.5, NOW() - INTERVAL   4 HOUR,   17),
  ('brainly.co.id',           'edukasi',  91.2, NOW() - INTERVAL   6 HOUR,   11),
  ('kemdikbud.go.id',         'edukasi',  99.5, NOW() - INTERVAL   8 HOUR,    8),
  ('coursera.org',            'edukasi',  90.4, NOW() - INTERVAL   1 DAY,     5),
  ('edx.org',                 'edukasi',  92.1, NOW() - INTERVAL   2 DAY,     3),
  ('meet.google.com',         'edukasi',  88.6, NOW() - INTERVAL  30 MINUTE,  19),
  ('unm.ac.id',               'edukasi',  96.0, NOW() - INTERVAL   1 DAY,     4),
  ('detik.com',               'edukasi',  72.4, NOW() - INTERVAL   2 HOUR,   22),
  ('kompas.com',              'edukasi',  73.8, NOW() - INTERVAL   3 HOUR,   15),

  -- ── HIBURAN ──
  ('youtube.com',             'hiburan',  89.3, NOW() - INTERVAL  15 MINUTE, 142),
  ('tiktok.com',              'hiburan',  85.7, NOW() - INTERVAL  30 MINUTE,  98),
  ('instagram.com',           'hiburan',  82.4, NOW() - INTERVAL   1 HOUR,   72),
  ('roblox.com',              'hiburan',  79.1, NOW() - INTERVAL   2 HOUR,   45),
  ('spotify.com',             'hiburan',  87.8, NOW() - INTERVAL   3 HOUR,   33),
  ('netflix.com',             'hiburan',  88.5, NOW() - INTERVAL   5 HOUR,   28),
  ('youtubekids.com',         'hiburan',  91.2, NOW() - INTERVAL  40 MINUTE,  51),
  ('twitch.tv',               'hiburan',  76.8, NOW() - INTERVAL   4 HOUR,   24),
  ('discord.com',             'hiburan',  71.3, NOW() - INTERVAL   6 HOUR,   17),
  ('genshin.hoyoverse.com',   'hiburan',  74.5, NOW() - INTERVAL   1 DAY,    13),
  ('disneyplus.com',          'hiburan',  89.0, NOW() - INTERVAL   2 HOUR,   29),
  ('vidio.com',               'hiburan',  84.5, NOW() - INTERVAL   1 HOUR,   18),
  ('viu.com',                 'hiburan',  85.2, NOW() - INTERVAL   3 HOUR,   12),
  ('mobilelegends.com',       'hiburan',  78.4, NOW() - INTERVAL  20 MINUTE,  36),
  ('store.steampowered.com',  'hiburan',  82.1, NOW() - INTERVAL   2 DAY,    14),
  ('epicgames.com',           'hiburan',  80.7, NOW() - INTERVAL   1 DAY,    10),
  ('snapchat.com',            'hiburan',  77.9, NOW() - INTERVAL   4 HOUR,    9),
  ('telegram.org',            'hiburan',  68.3, NOW() - INTERVAL   2 HOUR,   16),

  -- ── NEGATIF ──
  ('dewa777slot.net',         'negatif',  99.8, NOW() - INTERVAL   3 HOUR,    5),
  ('bet365.com',              'negatif', 100.0, NOW() - INTERVAL   8 HOUR,    3),
  ('xnxx.com',                'negatif', 100.0, NOW() - INTERVAL   5 HOUR,    2),
  ('slot-gacor99.id',         'negatif',  98.2, NOW() - INTERVAL   2 HOUR,    4),
  ('phishing-bank.cc',        'negatif',  96.5, NOW() - INTERVAL   1 DAY,     1),
  ('judi-online.net',         'negatif',  99.1, NOW() - INTERVAL   2 DAY,     2),
  ('pragmaticplay.net',       'negatif',  98.8, NOW() - INTERVAL   6 HOUR,    3),
  ('redtube.com',             'negatif',  99.5, NOW() - INTERVAL   1 DAY,     1),
  ('crack-software.io',       'negatif',  93.7, NOW() - INTERVAL  18 HOUR,    2),
  ('malware-redirect.net',    'negatif',  98.0, NOW() - INTERVAL  10 HOUR,    2),
  ('pkv-games.org',           'negatif',  99.4, NOW() - INTERVAL   1 DAY,     1),
  ('kerumput-iklan.xyz',      'negatif',  91.2, NOW() - INTERVAL   2 DAY,     1),

  -- ── UNKNOWN (skor rendah) ──
  ('random-cdn-04.com',       'unknown',  45.2, NOW() - INTERVAL  20 MINUTE,  6),
  ('static-files.io',         'unknown',  38.7, NOW() - INTERVAL   1 HOUR,    4);

-- ════════════════════════════════════════════════════════════════════════
-- 6. LOG_AKSES — riwayat HARI INI + KEMARIN + H-2 (~140 entri)
--    Pola per-anak:
--      Stom   rajin    → dominan edukasi
--      Miku   seimbang → mix edukasi + hiburan
--      Asraf  santai   → lebih hiburan + 2-3 percobaan negatif
--      Bila   TV       → 95% hiburan (streaming)
--      Naufal gamer    → 80% hiburan/game + percobaan negatif
--      Aira   sosmed   → 30% edu, 55% hiburan, beberapa percobaan negatif
-- ════════════════════════════════════════════════════════════════════════

-- ─────────────────── HARI INI (jam 6 pagi → sekarang) ───────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  -- Stom (MacBook) — rajin belajar
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 410, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '06:30' HOUR_MINUTE)),
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '07:10' HOUR_MINUTE)),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 95.2,210, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '07:45' HOUR_MINUTE)),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 180, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '08:20' HOUR_MINUTE)),
  (1, 'meet.google.com',      'edukasi','izinkan','whitelist',     100,1100, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '09:00' HOUR_MINUTE)),
  (1, 'brainly.co.id',        'edukasi','izinkan','whitelist',     100,  85, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '10:15' HOUR_MINUTE)),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.7,1800,'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '11:30' HOUR_MINUTE)),
  (1, 'kemdikbud.go.id',      'edukasi','izinkan','whitelist',     100,  60, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '12:45' HOUR_MINUTE)),
  (1, 'slot-gacor99.id',      'negatif','blokir', 'blacklist',     100,   0, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '13:20' HOUR_MINUTE)),
  (1, 'zenius.net',           'edukasi','izinkan','whitelist',     100, 280, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '14:00' HOUR_MINUTE)),
  (1, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 84.1, 320,'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '15:30' HOUR_MINUTE)),
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 410, 'Stom','8A:48:1C:98:15:C6', LEAST(NOW(), CURDATE() + INTERVAL '16:50' HOUR_MINUTE)),

  -- Miku (iPad) — seimbang
  (2, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 390, 'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '07:00' HOUR_MINUTE)),
  (2, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 175, 'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '08:30' HOUR_MINUTE)),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 91.0,1400,'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '09:15' HOUR_MINUTE)),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 79.2,2100,'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '10:00' HOUR_MINUTE)),
  (2, 'malware-redirect.net', 'negatif','blokir', 'blacklist',     100,   0, 'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '10:45' HOUR_MINUTE)),
  (2, 'brainly.co.id',        'edukasi','izinkan','whitelist',     100,  78, 'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '11:20' HOUR_MINUTE)),
  (2, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.6,1100,'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '12:30' HOUR_MINUTE)),
  (2, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.0,1700,'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '13:45' HOUR_MINUTE)),
  (2, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 280, 'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '14:30' HOUR_MINUTE)),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 80.4,1900,'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '15:50' HOUR_MINUTE)),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 90.6,1450,'Miku','AA:BB:CC:44:55:66', LEAST(NOW(), CURDATE() + INTERVAL '16:40' HOUR_MINUTE)),

  -- Asraf (Samsung) — dominan hiburan + negatif
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.2,1900,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '06:45' HOUR_MINUTE)),
  (3, 'kemdikbud.go.id',      'edukasi','izinkan','whitelist',     100,  55, 'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '07:30' HOUR_MINUTE)),
  (3, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 81.7, 850,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '08:20' HOUR_MINUTE)),
  (3, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.4,1200,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '09:00' HOUR_MINUTE)),
  (3, 'dewa777slot.net',      'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '09:45' HOUR_MINUTE)),
  (3, 'bet365.com',           'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '10:30' HOUR_MINUTE)),
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 89.1,2000,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '11:15' HOUR_MINUTE)),
  (3, 'mobilelegends.com',    'hiburan','izinkan','klasifikasi_ai', 78.4, 950,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '12:00' HOUR_MINUTE)),
  (3, 'twitch.tv',            'hiburan','izinkan','klasifikasi_ai', 76.8,2500,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '12:50' HOUR_MINUTE)),
  (3, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 93.7, 145,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '13:40' HOUR_MINUTE)),
  (3, 'discord.com',          'hiburan','izinkan','klasifikasi_ai', 71.3, 320,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '14:30' HOUR_MINUTE)),
  (3, 'xnxx.com',             'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '15:20' HOUR_MINUTE)),
  (3, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 86.5, 380,'Asraf','AA:BB:CC:77:88:99', LEAST(NOW(), CURDATE() + INTERVAL '16:10' HOUR_MINUTE)),

  -- Bila (Smart TV) — streaming dominan
  (4, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 90.5,4200,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '07:30' HOUR_MINUTE)),
  (4, 'netflix.com',          'hiburan','izinkan','klasifikasi_ai', 89.0,5800,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '09:00' HOUR_MINUTE)),
  (4, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 92.0,3100,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '10:30' HOUR_MINUTE)),
  (4, 'disneyplus.com',       'hiburan','izinkan','klasifikasi_ai', 89.5,4500,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '12:00' HOUR_MINUTE)),
  (4, 'vidio.com',            'hiburan','izinkan','klasifikasi_ai', 84.5,3200,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '13:45' HOUR_MINUTE)),
  (4, 'viu.com',              'hiburan','izinkan','klasifikasi_ai', 85.2,3000,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '14:50' HOUR_MINUTE)),
  (4, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 91.0,4000,'Bila','D4:90:9C:11:22:33', LEAST(NOW(), CURDATE() + INTERVAL '16:00' HOUR_MINUTE)),

  -- Naufal (PlayStation 5) — gaming
  (5, 'store.steampowered.com','hiburan','izinkan','klasifikasi_ai',82.1, 850,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '08:00' HOUR_MINUTE)),
  (5, 'epicgames.com',        'hiburan','izinkan','klasifikasi_ai', 80.7, 920,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '09:30' HOUR_MINUTE)),
  (5, 'genshin.hoyoverse.com','hiburan','izinkan','klasifikasi_ai', 74.5,3400,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '10:45' HOUR_MINUTE)),
  (5, 'discord.com',          'hiburan','izinkan','klasifikasi_ai', 71.3, 280,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '12:00' HOUR_MINUTE)),
  (5, 'twitch.tv',            'hiburan','izinkan','klasifikasi_ai', 76.8,3800,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '13:30' HOUR_MINUTE)),
  (5, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.4,2500,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '14:45' HOUR_MINUTE)),
  (5, 'crack-software.io',    'negatif','blokir', 'blacklist',     100,   0, 'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '15:15' HOUR_MINUTE)),
  (5, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 92.1, 120,'Naufal','B8:27:EB:55:66:77', LEAST(NOW(), CURDATE() + INTERVAL '16:20' HOUR_MINUTE)),

  -- Aira (iPhone 11 Pro Max) — sosmed + edu
  (6, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 180, 'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '07:00' HOUR_MINUTE)),
  (6, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 83.2, 920,'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '08:30' HOUR_MINUTE)),
  (6, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 86.0,1200,'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '09:45' HOUR_MINUTE)),
  (6, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 380, 'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '10:30' HOUR_MINUTE)),
  (6, 'pragmaticplay.net',    'negatif','blokir', 'blacklist',     100,   0, 'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '11:00' HOUR_MINUTE)),
  (6, 'snapchat.com',         'hiburan','izinkan','klasifikasi_ai', 77.9, 680,'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '11:50' HOUR_MINUTE)),
  (6, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 94.5, 130,'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '13:00' HOUR_MINUTE)),
  (6, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.7,1600,'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '14:15' HOUR_MINUTE)),
  (6, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 87.0, 290,'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '15:30' HOUR_MINUTE)),
  (6, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 290, 'Aira','90:81:58:AA:BB:CC', LEAST(NOW(), CURDATE() + INTERVAL '16:45' HOUR_MINUTE));

-- ─────────────────── KEMARIN (H-1) ───────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  -- Stom
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 410, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '07:00' HOUR_MINUTE),
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '08:30' HOUR_MINUTE),
  (1, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 290, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '09:45' HOUR_MINUTE),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.7,1800,'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '11:30' HOUR_MINUTE),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 96.4, 140,'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '13:00' HOUR_MINUTE),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 200, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:15' HOUR_MINUTE),
  (1, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 84.1, 320,'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '17:30' HOUR_MINUTE),
  (1, 'zenius.net',           'edukasi','izinkan','whitelist',     100, 280, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '19:00' HOUR_MINUTE),

  -- Miku
  (2, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 390, 'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '07:30' HOUR_MINUTE),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 90.6,1450,'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '09:00' HOUR_MINUTE),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 78.9,2000,'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '10:30' HOUR_MINUTE),
  (2, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 290, 'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '13:00' HOUR_MINUTE),
  (2, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.6,1100,'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (2, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 190, 'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '18:00' HOUR_MINUTE),

  -- Asraf
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.2,1900,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '08:00' HOUR_MINUTE),
  (3, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.4,1200,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '10:00' HOUR_MINUTE),
  (3, 'judi-online.net',      'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '11:15' HOUR_MINUTE),
  (3, 'mobilelegends.com',    'hiburan','izinkan','klasifikasi_ai', 78.4, 950,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '13:30' HOUR_MINUTE),
  (3, 'discord.com',          'hiburan','izinkan','klasifikasi_ai', 71.3, 320,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:45' HOUR_MINUTE),
  (3, 'redtube.com',          'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '17:00' HOUR_MINUTE),
  (3, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 86.5, 380,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '19:30' HOUR_MINUTE),

  -- Bila (Smart TV)
  (4, 'netflix.com',          'hiburan','izinkan','klasifikasi_ai', 89.0,5800,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '08:00' HOUR_MINUTE),
  (4, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 91.0,4000,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '10:30' HOUR_MINUTE),
  (4, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 92.0,3100,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '13:00' HOUR_MINUTE),
  (4, 'disneyplus.com',       'hiburan','izinkan','klasifikasi_ai', 89.5,4500,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (4, 'vidio.com',            'hiburan','izinkan','klasifikasi_ai', 84.5,3200,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '19:00' HOUR_MINUTE),
  (4, 'viu.com',              'hiburan','izinkan','klasifikasi_ai', 85.2,3000,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '20:30' HOUR_MINUTE),

  -- Naufal (PS5)
  (5, 'epicgames.com',        'hiburan','izinkan','klasifikasi_ai', 80.7, 920,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '14:00' HOUR_MINUTE),
  (5, 'store.steampowered.com','hiburan','izinkan','klasifikasi_ai',82.1, 850,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:30' HOUR_MINUTE),
  (5, 'genshin.hoyoverse.com','hiburan','izinkan','klasifikasi_ai', 74.5,3400,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '17:00' HOUR_MINUTE),
  (5, 'pkv-games.org',        'negatif','blokir', 'blacklist',     100,   0, 'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '18:15' HOUR_MINUTE),
  (5, 'discord.com',          'hiburan','izinkan','klasifikasi_ai', 71.3, 280,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '19:30' HOUR_MINUTE),
  (5, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.4,2500,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '20:45' HOUR_MINUTE),

  -- Aira (iPhone)
  (6, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 380, 'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '07:30' HOUR_MINUTE),
  (6, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 83.2, 920,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '09:00' HOUR_MINUTE),
  (6, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 86.0,1200,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '10:45' HOUR_MINUTE),
  (6, 'xnxx.com',             'negatif','blokir', 'blacklist',     100,   0, 'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '12:00' HOUR_MINUTE),
  (6, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 180, 'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '13:30' HOUR_MINUTE),
  (6, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.7,1600,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (6, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 87.0, 290,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '17:30' HOUR_MINUTE),
  (6, 'snapchat.com',         'hiburan','izinkan','klasifikasi_ai', 77.9, 680,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 1 DAY) + INTERVAL '20:00' HOUR_MINUTE);

-- ─────────────────── 2 HARI LALU (H-2) ───────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  -- Stom
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '08:00' HOUR_MINUTE),
  (1, 'scholar.google.com',   'edukasi','izinkan','whitelist',     100, 110, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '10:00' HOUR_MINUTE),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.0,1800,'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '13:00' HOUR_MINUTE),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 95.2,210, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '15:30' HOUR_MINUTE),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 180, 'Stom','8A:48:1C:98:15:C6', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '19:00' HOUR_MINUTE),

  -- Miku
  (2, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 390, 'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '07:30' HOUR_MINUTE),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 79.2,2100,'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '10:15' HOUR_MINUTE),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 91.0,1400,'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '14:00' HOUR_MINUTE),
  (2, 'brainly.co.id',        'edukasi','izinkan','whitelist',     100,  78, 'Miku','AA:BB:CC:44:55:66', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '17:30' HOUR_MINUTE),

  -- Asraf
  (3, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.4,1200,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '09:00' HOUR_MINUTE),
  (3, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 81.7, 850,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '11:30' HOUR_MINUTE),
  (3, 'phishing-bank.cc',     'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '13:15' HOUR_MINUTE),
  (3, 'mobilelegends.com',    'hiburan','izinkan','klasifikasi_ai', 78.4, 950,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 89.1,2000,'Asraf','AA:BB:CC:77:88:99', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '17:45' HOUR_MINUTE),

  -- Bila (Smart TV)
  (4, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 91.0,4000,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '09:00' HOUR_MINUTE),
  (4, 'netflix.com',          'hiburan','izinkan','klasifikasi_ai', 89.0,5800,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '12:30' HOUR_MINUTE),
  (4, 'disneyplus.com',       'hiburan','izinkan','klasifikasi_ai', 89.5,4500,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (4, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 92.0,3100,'Bila','D4:90:9C:11:22:33', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '18:30' HOUR_MINUTE),

  -- Naufal (PS5)
  (5, 'store.steampowered.com','hiburan','izinkan','klasifikasi_ai',82.1, 850,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '15:00' HOUR_MINUTE),
  (5, 'twitch.tv',            'hiburan','izinkan','klasifikasi_ai', 76.8,3800,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '17:00' HOUR_MINUTE),
  (5, 'genshin.hoyoverse.com','hiburan','izinkan','klasifikasi_ai', 74.5,3400,'Naufal','B8:27:EB:55:66:77', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '19:30' HOUR_MINUTE),

  -- Aira (iPhone)
  (6, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 83.2, 920,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '09:30' HOUR_MINUTE),
  (6, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 94.5, 130,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '12:00' HOUR_MINUTE),
  (6, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 86.0,1200,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '14:30' HOUR_MINUTE),
  (6, 'kerumput-iklan.xyz',   'negatif','blokir', 'blacklist',     100,   0, 'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '16:00' HOUR_MINUTE),
  (6, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.7,1600,'Aira','90:81:58:AA:BB:CC', (CURDATE() - INTERVAL 2 DAY) + INTERVAL '18:30' HOUR_MINUTE);

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
