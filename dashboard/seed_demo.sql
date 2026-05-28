-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║  EDGE GUARD — SEED DATA DEMO (schema baru ERD)                       ║
-- ║                                                                       ║
-- ║  Jalankan SETELAH schema.sql:                                         ║
-- ║    mysql -u edgeguard -p edgeguard < dashboard/seed_demo.sql          ║
-- ║                                                                       ║
-- ║  Isi:                                                                 ║
-- ║   • 3 pengguna_anak (Stom / Miku / Asraf)                        ║
-- ║   • Dompet kuota per anak                                            ║
-- ║   • Beberapa jadwal blokir                                           ║
-- ║   • 12 whitelist + 12 blacklist                                      ║
-- ║   • ~30 cache_domain (knowledge AI realtime)                         ║
-- ║   • ~50 log_akses tersebar sejak jam 7 pagi hari ini                 ║
-- ║                                                                       ║
-- ║  Aman dijalankan berkali-kali — script RESET data demo dulu.         ║
-- ╚══════════════════════════════════════════════════════════════════════╝

USE edgeguard;

-- ════════════════════════════════════════════════════════════════════════
-- BERSIHKAN data demo lama (jaga FK cascade)
-- ════════════════════════════════════════════════════════════════════════
DELETE FROM log_akses;
DELETE FROM dompet_kuota;
DELETE FROM jadwal_blokir;
DELETE FROM daftar_filter;
DELETE FROM cache_domain;
DELETE FROM pengguna_anak;
ALTER TABLE pengguna_anak AUTO_INCREMENT = 1;

-- ════════════════════════════════════════════════════════════════════════
-- 1. 3 PENGGUNA ANAK (admin_id = 1, hasil seed schema.sql)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO pengguna_anak
  (user_id, admin_id, mac_address, device_name, status_aktif,
   nama, ip_terakhir, jeda, kuota_harian, kuota_terpakai,
   last_reset, last_seen) VALUES
  (1, 1, '8A:48:1C:98:15:C6', 'MacBook Air M2',          TRUE,
   'Stom',  '192.168.31.145', 0, 180,  85, CURDATE(), NOW() - INTERVAL 1 MINUTE),
  (2, 1, 'AA:BB:CC:44:55:66', 'iPad Pro M2',             TRUE,
   'Miku', '192.168.31.62',  0, 120,  72, CURDATE(), NOW() - INTERVAL 3 MINUTE),
  (3, 1, 'AA:BB:CC:77:88:99', 'Samsung Galaxy A56 5G',   FALSE,
   'Asraf', '192.168.31.23',  0, 150, 110, CURDATE(), NOW() - INTERVAL 4 HOUR);

-- ════════════════════════════════════════════════════════════════════════
-- 2. DOMPET KUOTA per anak
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO dompet_kuota
  (user_id, sisa_hiburan, total_edukasi, batas_harian, terakhir_reset) VALUES
  (1, 25, 95, 60, CURDATE()),      -- Stom: belajar banyak → sisa bonus 25
  (2,  5, 25, 60, CURDATE()),      -- Miku: cukup
  (3,  0,  8, 60, CURDATE());      -- Asraf: belum belajar → bonus habis

-- ════════════════════════════════════════════════════════════════════════
-- 3. JADWAL BLOKIR contoh (jam malam tidak boleh internet)
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO jadwal_blokir (user_id, hari, jam_mulai, jam_selesai, mode) VALUES
  -- Stom: jam belajar (07:00–14:00 izinkan, 22:00–05:00 blokir)
  (1, 'senin',   '22:00:00', '05:00:00', 'blokir'),
  (1, 'selasa',  '22:00:00', '05:00:00', 'blokir'),
  (1, 'rabu',    '22:00:00', '05:00:00', 'blokir'),
  -- Miku: 21:30–06:00 blokir
  (2, 'senin',   '21:30:00', '06:00:00', 'blokir'),
  (2, 'selasa',  '21:30:00', '06:00:00', 'blokir'),
  -- Asraf: hari sekolah 08:00–15:00 blokir, malam 22:00–06:00 blokir
  (3, 'senin',   '08:00:00', '15:00:00', 'blokir'),
  (3, 'senin',   '22:00:00', '06:00:00', 'blokir');

-- ════════════════════════════════════════════════════════════════════════
-- 4. DAFTAR_FILTER (admin_id = 1, berlaku global)
--    WHITELIST: tipe = 'putih'  — selalu diizinkan
--    BLACKLIST: tipe = 'hitam'  — selalu diblokir
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO daftar_filter (admin_id, tipe, domain_url, alasan) VALUES
  -- ── Whitelist ─────────────────────────────────────────────────────
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

  -- ── Blacklist ─────────────────────────────────────────────────────
  (1, 'hitam', 'bet365.com',          'Situs perjudian'),
  (1, 'hitam', '1xbet.com',           'Situs perjudian'),
  (1, 'hitam', 'pkv-games.org',       'Judi online'),
  (1, 'hitam', 'dewa777slot.net',     'Judi slot'),
  (1, 'hitam', 'judi-online.net',     'Judi online'),
  (1, 'hitam', 'slot-gacor99.id',     'Judi slot'),
  (1, 'hitam', 'pornhub.com',         'Pornografi'),
  (1, 'hitam', 'xnxx.com',            'Pornografi'),
  (1, 'hitam', 'xvideos.com',         'Pornografi'),
  (1, 'hitam', 'scam-payment.id',     'Scam pembayaran'),
  (1, 'hitam', 'malware-redirect.net','Malware / redirect jahat'),
  (1, 'hitam', 'phishing-bank.cc',    'Phishing perbankan');

-- ════════════════════════════════════════════════════════════════════════
-- 6. CACHE_DOMAIN — knowledge base AI (hasil klasifikasi realtime)
--    Setiap domain unik yang pernah ditemui AI tercatat di sini.
--    Akan terus bertambah & diupdate seiring perangkat anak browsing.
-- ════════════════════════════════════════════════════════════════════════
INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, terakhir_diakses, jumlah_hit) VALUES
  -- ── EDUKASI ──
  ('khanacademy.org',        'edukasi',  98.5, NOW() - INTERVAL  10 MINUTE, 42),
  ('duolingo.com',           'edukasi',  97.8, NOW() - INTERVAL  45 MINUTE, 38),
  ('ruangguru.com',          'edukasi',  96.2, NOW() - INTERVAL   2 HOUR,   31),
  ('zenius.net',             'edukasi',  95.1, NOW() - INTERVAL   3 HOUR,   18),
  ('classroom.google.com',   'edukasi',  99.0, NOW() - INTERVAL  20 MINUTE, 56),
  ('wikipedia.org',          'edukasi',  94.7, NOW() - INTERVAL   1 HOUR,   24),
  ('scholar.google.com',     'edukasi',  98.9, NOW() - INTERVAL   5 HOUR,    9),
  ('quipper.com',            'edukasi',  93.5, NOW() - INTERVAL   4 HOUR,   12),
  ('brainly.co.id',          'edukasi',  91.2, NOW() - INTERVAL   6 HOUR,    7),
  ('kemdikbud.go.id',        'edukasi',  99.5, NOW() - INTERVAL   8 HOUR,    4),
  ('coursera.org',           'edukasi',  90.4, NOW() - INTERVAL   1 DAY,     3),
  ('edx.org',                'edukasi',  92.1, NOW() - INTERVAL   2 DAY,     2),

  -- ── HIBURAN ──
  ('youtube.com',            'hiburan',  89.3, NOW() - INTERVAL  15 MINUTE, 87),
  ('tiktok.com',             'hiburan',  85.7, NOW() - INTERVAL  30 MINUTE, 62),
  ('instagram.com',          'hiburan',  82.4, NOW() - INTERVAL   1 HOUR,   45),
  ('roblox.com',             'hiburan',  79.1, NOW() - INTERVAL   2 HOUR,   29),
  ('spotify.com',            'hiburan',  87.8, NOW() - INTERVAL   3 HOUR,   21),
  ('netflix.com',            'hiburan',  88.5, NOW() - INTERVAL   5 HOUR,   14),
  ('youtubekids.com',        'hiburan',  91.2, NOW() - INTERVAL  40 MINUTE, 33),
  ('twitch.tv',              'hiburan',  76.8, NOW() - INTERVAL   4 HOUR,    8),
  ('discord.com',            'hiburan',  71.3, NOW() - INTERVAL   6 HOUR,   11),
  ('genshin.hoyoverse.com',  'hiburan',  74.5, NOW() - INTERVAL   1 DAY,     5),

  -- ── NEGATIF ──
  ('dewa777slot.net',        'negatif',  99.8, NOW() - INTERVAL   3 HOUR,    3),
  ('bet365.com',              'negatif', 100.0, NOW() - INTERVAL   8 HOUR,    2),
  ('xnxx.com',                'negatif', 100.0, NOW() - INTERVAL   5 HOUR,    1),
  ('slot-gacor99.id',        'negatif',  98.2, NOW() - INTERVAL   2 HOUR,    2),
  ('phishing-bank.cc',       'negatif',  96.5, NOW() - INTERVAL   1 DAY,     1),
  ('judi-online.net',         'negatif',  99.1, NOW() - INTERVAL   2 DAY,     1),

  -- ── UNKNOWN (skor rendah) ──
  ('random-cdn-04.com',      'unknown',  45.2, NOW() - INTERVAL  20 MINUTE,  3),
  ('static-files.io',        'unknown',  38.7, NOW() - INTERVAL   1 HOUR,    2);

-- ════════════════════════════════════════════════════════════════════════
-- 7. LOG_AKSES — riwayat akses anak HARI INI (jam 7 pagi → sekarang)
--    Pola realistis:
--      Stom  → dominan edukasi (anak rajin)
--      Miku → mix seimbang
--      Asraf → dominan hiburan + beberapa percobaan negatif
-- ════════════════════════════════════════════════════════════════════════

-- ─── Stom (user_id=1, MAC 8a:48:1c:98:15:c6) ─────────────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 420, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 11 HOUR),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 180, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 10 HOUR - INTERVAL 50 MINUTE),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 95.2,210,'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 10 HOUR),
  (1, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 320, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 9 HOUR - INTERVAL 30 MINUTE),
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 450, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 9 HOUR),
  (1, 'scholar.google.com',   'edukasi','izinkan','whitelist',     100, 110, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 8 HOUR - INTERVAL 40 MINUTE),
  (1, 'brainly.co.id',        'edukasi','izinkan','whitelist',     100,  85, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 8 HOUR),
  (1, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.7, 1800,'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 7 HOUR - INTERVAL 20 MINUTE),
  (1, 'kemdikbud.go.id',      'edukasi','izinkan','whitelist',     100,  60, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 7 HOUR),
  (1, 'zenius.net',           'edukasi','izinkan','whitelist',     100, 280, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 6 HOUR),
  (1, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 72.3, 1200,'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 5 HOUR - INTERVAL 30 MINUTE),
  (1, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 81.0, 950, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 5 HOUR),
  (1, 'quipper.com',          'edukasi','izinkan','whitelist',     100,  90, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 4 HOUR),
  (1, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 96.4, 140,'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 3 HOUR - INTERVAL 30 MINUTE),
  (1, 'slot-gacor99.id',      'negatif','blokir', 'blacklist',     100,   0, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 2 HOUR - INTERVAL 50 MINUTE),
  (1, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 200, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 2 HOUR),
  (1, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 84.1, 320,'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 1 HOUR - INTERVAL 30 MINUTE),
  (1, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 380, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 45 MINUTE),
  (1, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 410, 'Stom','8a:48:1c:98:15:c6', NOW() - INTERVAL 10 MINUTE);

-- ─── Miku (user_id=2, MAC AA:BB:CC:44:55:66) ────────────────────────
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  (2, 'classroom.google.com', 'edukasi','izinkan','whitelist',     100, 390, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 10 HOUR),
  (2, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 175, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 9 HOUR - INTERVAL 20 MINUTE),
  (2, 'brainly.co.id',        'edukasi','izinkan','whitelist',     100,  78, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 9 HOUR),
  (2, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 94.8, 130,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 8 HOUR - INTERVAL 30 MINUTE),
  (2, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 87.5,1700,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 8 HOUR),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 79.2,2100,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 7 HOUR - INTERVAL 30 MINUTE),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 91.0,1400,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 7 HOUR),
  (2, 'khanacademy.org',      'edukasi','izinkan','whitelist',     100, 410, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 5 HOUR - INTERVAL 30 MINUTE),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 80.4,1900,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 5 HOUR),
  (2, 'malware-redirect.net', 'negatif','blokir', 'blacklist',     100,   0, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 4 HOUR - INTERVAL 40 MINUTE),
  (2, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.6,1100,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 4 HOUR),
  (2, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 280, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 3 HOUR - INTERVAL 15 MINUTE),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 92.3,1500,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 2 HOUR - INTERVAL 30 MINUTE),
  (2, 'roblox.com',           'hiburan','izinkan','klasifikasi_ai', 78.9,2000,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 1 HOUR - INTERVAL 50 MINUTE),
  (2, 'duolingo.com',         'edukasi','izinkan','whitelist',     100, 190, 'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 1 HOUR),
  (2, 'youtubekids.com',      'hiburan','izinkan','klasifikasi_ai', 90.6,1450,'Miku','AA:BB:CC:44:55:66', NOW() - INTERVAL 25 MINUTE);

-- ─── Asraf (user_id=3, MAC AA:BB:CC:77:88:99) — banyak hiburan + 3 blokir
INSERT INTO log_akses
  (user_id, domain_url, kategori, aksi, alasan, confidence,
   traffic_kbps, perangkat_nama, mac, waktu_akses) VALUES
  (3, 'kemdikbud.go.id',      'edukasi','izinkan','whitelist',     100,  55, 'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 10 HOUR - INTERVAL 30 MINUTE),
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 88.2,1900,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 10 HOUR),
  (3, 'instagram.com',        'hiburan','izinkan','klasifikasi_ai', 81.7, 850,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 9 HOUR - INTERVAL 30 MINUTE),
  (3, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 85.4,1200,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 9 HOUR),
  (3, 'dewa777slot.net',      'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 8 HOUR - INTERVAL 45 MINUTE),
  (3, 'bet365.com',           'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 8 HOUR - INTERVAL 30 MINUTE),
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 89.1,2000,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 8 HOUR),
  (3, 'twitch.tv',            'hiburan','izinkan','klasifikasi_ai', 76.8,2500,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 7 HOUR - INTERVAL 30 MINUTE),
  (3, 'wikipedia.org',        'edukasi','izinkan','klasifikasi_ai', 93.7, 145,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 7 HOUR),
  (3, 'discord.com',          'hiburan','izinkan','klasifikasi_ai', 71.3, 320,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 6 HOUR - INTERVAL 30 MINUTE),
  (3, 'tiktok.com',           'hiburan','izinkan','klasifikasi_ai', 84.0,1150,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 6 HOUR),
  (3, 'xnxx.com',             'negatif','blokir', 'blacklist',     100,   0, 'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 5 HOUR - INTERVAL 30 MINUTE),
  (3, 'spotify.com',          'hiburan','izinkan','klasifikasi_ai', 86.5, 380,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 5 HOUR),
  (3, 'ruangguru.com',        'edukasi','izinkan','whitelist',     100, 250, 'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 4 HOUR - INTERVAL 30 MINUTE),
  (3, 'youtube.com',          'hiburan','izinkan','klasifikasi_ai', 87.9,2100,'Asraf','AA:BB:CC:77:88:99', NOW() - INTERVAL 4 HOUR);

-- ════════════════════════════════════════════════════════════════════════
-- Ringkasan
-- ════════════════════════════════════════════════════════════════════════
SELECT 'PENGGUNA ANAK'    AS info, COUNT(*) AS n FROM pengguna_anak
UNION ALL SELECT 'WHITELIST',          COUNT(*) FROM daftar_filter WHERE tipe='putih'
UNION ALL SELECT 'BLACKLIST',          COUNT(*) FROM daftar_filter WHERE tipe='hitam'
UNION ALL SELECT 'CACHE_DOMAIN total', COUNT(*) FROM cache_domain
UNION ALL SELECT '  └─ edukasi',       COUNT(*) FROM cache_domain WHERE kategori='edukasi'
UNION ALL SELECT '  └─ hiburan',       COUNT(*) FROM cache_domain WHERE kategori='hiburan'
UNION ALL SELECT '  └─ negatif',       COUNT(*) FROM cache_domain WHERE kategori='negatif'
UNION ALL SELECT 'LOG HARI INI',       COUNT(*) FROM log_akses WHERE DATE(waktu_akses)=CURDATE()
UNION ALL SELECT 'JADWAL BLOKIR',      COUNT(*) FROM jadwal_blokir
UNION ALL SELECT 'DOMPET KUOTA',       COUNT(*) FROM dompet_kuota;
