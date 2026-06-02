-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║  Jalankan SETELAH schema.sql:                                        ║
-- ║    mysql -u edgeguard -p edgeguard < dashboard/seed_demo.sql         ║
-- ║                                                                      ║
-- ║  Isi:                                                                ║
-- ║   • pengguna_anak (F2:9C:78:8F:1F:FB) milik "Stom"                   ║
-- ║   • Dompet kuota + jadwal istirahat untuk perangkat tsb              ║
-- ║   • 18 whitelist + 16 blacklist (aturan filter manual)               ║
-- ║   • cache_domain — knowledge base AI (dataset v2.11, 809 entri)      ║
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
-- Reset + isi ulang dari datasetkumpulanweb.xlsx (809 SNI, dataset v2.11)
-- Kategori diambil dari label dataset (ground truth), bukan prediksi AI.
-- Aman dijalankan ulang — ON DUPLICATE KEY UPDATE menjaga idempoten.
-- ════════════════════════════════════════════════════════════════════════
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE cache_domain;
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('ac.id/e-learning', 'edukasi', 100.0, 1),
  ('ac.id/jurnal', 'edukasi', 100.0, 1),
  ('ac.id/library', 'edukasi', 100.0, 1),
  ('ac.id/repository', 'edukasi', 99.9, 1),
  ('ac.in', 'edukasi', 46.3, 1),
  ('academia.edu', 'edukasi', 99.5, 1),
  ('belajar.id', 'edukasi', 100.0, 1),
  ('bettermarks.com', 'edukasi', 0.0, 1),
  ('bps.go.id', 'edukasi', 73.1, 1),
  ('brainly.co.id', 'edukasi', 87.8, 1),
  ('brainpop.com', 'edukasi', 84.8, 1),
  ('brilliant.org', 'edukasi', 100.0, 1),
  ('brilliant.org/page1', 'edukasi', 100.0, 1),
  ('brilliant.org/page2', 'edukasi', 100.0, 1),
  ('bsn.go.id', 'edukasi', 82.7, 1),
  ('byjus.com', 'edukasi', 54.3, 1),
  ('cambridge.org/learn', 'edukasi', 98.6, 1),
  ('canva.com', 'edukasi', 96.0, 1),
  ('canva.com/education', 'edukasi', 100.0, 1),
  ('cerdas.id', 'edukasi', 30.3, 1),
  ('ck12.org', 'edukasi', 22.9, 1),
  ('classcraft.com', 'edukasi', 70.8, 1),
  ('classroom.com', 'edukasi', 99.3, 1),
  ('co.uk/learning', 'edukasi', 100.0, 1),
  ('code.org', 'edukasi', 71.0, 1),
  ('codecademy.com', 'edukasi', 99.5, 1),
  ('coursehero.com', 'edukasi', 100.0, 1),
  ('coursera.org', 'edukasi', 100.0, 1),
  ('detik.com/edu', 'edukasi', 99.4, 1),
  ('duolingo.com', 'edukasi', 100.0, 1),
  ('edmodo.com', 'edukasi', 100.0, 1),
  ('edpuzzle.com', 'edukasi', 75.2, 1),
  ('edulastic.com', 'edukasi', 100.0, 1),
  ('edx.org', 'edukasi', 63.0, 1),
  ('flipgrid.com', 'edukasi', 0.0, 1),
  ('futurelearn.com', 'edukasi', 100.0, 1),
  ('google.co.id', 'edukasi', 0.2, 1),
  ('google.com/classroom', 'edukasi', 90.3, 1),
  ('harvard.edu/online', 'edukasi', 100.0, 1),
  ('iain-tulungagung.ac.id', 'edukasi', 83.9, 1),
  ('indonesiax.co.id', 'edukasi', 11.9, 1),
  ('ipb.ac.id', 'edukasi', 83.0, 1),
  ('iqbelajar.com', 'edukasi', 100.0, 1),
  ('itb.ac.id', 'edukasi', 76.3, 1),
  ('its.ac.id', 'edukasi', 51.0, 1),
  ('kahoot.com', 'edukasi', 52.6, 1),
  ('kemdikbud.go.id', 'edukasi', 100.0, 1),
  ('khanacademy.org', 'edukasi', 100.0, 1),
  ('learnosity.com', 'edukasi', 99.8, 1),
  ('ltmpt.ac.id', 'edukasi', 30.2, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('mastah.id', 'edukasi', 83.9, 1),
  ('mathway.com', 'edukasi', 100.0, 1),
  ('memrise.com', 'edukasi', 83.9, 1),
  ('mercubuana.ac.id', 'edukasi', 96.0, 1),
  ('mit.edu', 'edukasi', 87.9, 1),
  ('mit.edu/opencourseware', 'edukasi', 100.0, 1),
  ('moodle.org', 'edukasi', 70.9, 1),
  ('nearpod.com', 'edukasi', 66.7, 1),
  ('openculture.com', 'edukasi', 23.8, 1),
  ('openstax.org', 'edukasi', 44.6, 1),
  ('oxfordlearnersdictionaries.com', 'edukasi', 93.6, 1),
  ('padlet.com', 'edukasi', 84.3, 1),
  ('quipper.com', 'edukasi', 100.0, 1),
  ('quipper.com/id', 'edukasi', 100.0, 1),
  ('quizlet.com', 'edukasi', 99.6, 1),
  ('readworks.org', 'edukasi', 31.4, 1),
  ('ruangguru.com', 'edukasi', 100.0, 1),
  ('scribd.com', 'edukasi', 18.9, 1),
  ('sekolah.id', 'edukasi', 100.0, 1),
  ('sekolah.mu', 'edukasi', 100.0, 1),
  ('siswapintar.com', 'edukasi', 100.0, 1),
  ('skillshare.com', 'edukasi', 98.3, 1),
  ('slideshare.net', 'edukasi', 67.1, 1),
  ('smartschool.id', 'edukasi', 15.9, 1),
  ('socrative.com', 'edukasi', 65.2, 1),
  ('stanford.edu/online', 'edukasi', 100.0, 1),
  ('studylib.net', 'edukasi', 100.0, 1),
  ('ted.com', 'edukasi', 33.2, 1),
  ('telkomuniversity.ac.id', 'edukasi', 99.9, 1),
  ('typito.com', 'edukasi', 59.3, 1),
  ('uad.ac.id', 'edukasi', 48.2, 1),
  ('ub.ac.id', 'edukasi', 29.5, 1),
  ('udemy.com', 'edukasi', 100.0, 1),
  ('ugm.ac.id', 'edukasi', 80.2, 1),
  ('uhamka.ac.id', 'edukasi', 77.6, 1),
  ('uho.ac.id', 'edukasi', 45.3, 1),
  ('ui.ac.id', 'edukasi', 80.0, 1),
  ('uin-malang.ac.id', 'edukasi', 98.2, 1),
  ('uin-suka.ac.id', 'edukasi', 98.1, 1),
  ('uinjkt.ac.id', 'edukasi', 86.9, 1),
  ('uinsby.ac.id', 'edukasi', 90.7, 1),
  ('uksw.edu', 'edukasi', 45.3, 1),
  ('umm.ac.id', 'edukasi', 55.1, 1),
  ('umsu.ac.id', 'edukasi', 34.3, 1),
  ('umy.ac.id', 'edukasi', 71.8, 1),
  ('unair.ac.id', 'edukasi', 85.8, 1),
  ('undiksha.ac.id', 'edukasi', 90.0, 1),
  ('undip.ac.id', 'edukasi', 57.9, 1),
  ('unej.ac.id', 'edukasi', 51.1, 1),
  ('unesa.ac.id', 'edukasi', 54.7, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('unhas.ac.id', 'edukasi', 87.3, 1),
  ('unila.ac.id', 'edukasi', 82.0, 1),
  ('unimed.ac.id', 'edukasi', 88.6, 1),
  ('unm.ac.id', 'edukasi', 57.6, 1),
  ('unpad.ac.id', 'edukasi', 95.9, 1),
  ('unram.ac.id', 'edukasi', 39.5, 1),
  ('uns.ac.id', 'edukasi', 74.9, 1),
  ('unsrat.ac.id', 'edukasi', 76.7, 1),
  ('unsyiah.ac.id', 'edukasi', 93.0, 1),
  ('untan.ac.id', 'edukasi', 57.0, 1),
  ('unud.ac.id', 'edukasi', 72.3, 1),
  ('uny.ac.id', 'edukasi', 52.9, 1),
  ('upi.edu', 'edukasi', 67.8, 1),
  ('upi.edu/repository', 'edukasi', 100.0, 1),
  ('ut.ac.id', 'edukasi', 66.9, 1),
  ('w3schools.com', 'edukasi', 56.1, 1),
  ('wikipedia.org/wiki', 'edukasi', 100.0, 1),
  ('wolframalpha.com', 'edukasi', 67.9, 1),
  ('zenius.net', 'edukasi', 100.0, 1),
  ('17live.com', 'hiburan', 96.8, 1),
  ('akadns.net', 'hiburan', 6.5, 1),
  ('animeindo.cc', 'hiburan', 96.3, 1),
  ('anoboy.com', 'hiburan', 27.3, 1),
  ('apple.com/tvplus', 'hiburan', 0.0, 1),
  ('bigo.tv', 'hiburan', 42.2, 1),
  ('bilibili.com', 'hiburan', 96.9, 1),
  ('bola.com', 'hiburan', 71.4, 1),
  ('boombastis.com', 'hiburan', 37.3, 1),
  ('branch.io', 'netral', 99.0, 1),
  ('brightcove.com', 'hiburan', 79.0, 1),
  ('brilio.net', 'hiburan', 58.1, 1),
  ('catchplay.com', 'hiburan', 100.0, 1),
  ('cbsinteractive.com', 'hiburan', 43.8, 1),
  ('cdninstagram.com', 'hiburan', 99.4, 1),
  ('cloudinary.com', 'hiburan', 16.0, 1),
  ('cnnindonesia.com/hiburan', 'hiburan', 100.0, 1),
  ('co.id/olahraga', 'hiburan', 95.0, 1),
  ('co.id/showbiz', 'hiburan', 11.0, 1),
  ('codashop.com', 'hiburan', 49.7, 1),
  ('dailymotion.com', 'hiburan', 15.7, 1),
  ('detik.com', 'hiburan', 99.8, 1),
  ('detikforum.com', 'hiburan', 99.8, 1),
  ('discord.gg', 'hiburan', 98.5, 1),
  ('discordapp.com', 'hiburan', 97.9, 1),
  ('disneyplus.com', 'hiburan', 99.7, 1),
  ('duniagames.co.id', 'hiburan', 100.0, 1),
  ('epicgames.com', 'hiburan', 100.0, 1),
  ('espncdn.com', 'hiburan', 81.8, 1),
  ('esportsnesia.com', 'hiburan', 99.4, 1),
  ('facebook.com', 'hiburan', 96.7, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('fimela.com', 'hiburan', 27.3, 1),
  ('freefiremobile.com', 'hiburan', 98.9, 1),
  ('gamebrott.com', 'hiburan', 100.0, 1),
  ('gamespot.com', 'hiburan', 100.0, 1),
  ('gamevil.com', 'hiburan', 100.0, 1),
  ('garena.co.id', 'hiburan', 98.5, 1),
  ('garena.com', 'hiburan', 98.5, 1),
  ('gengame.net', 'hiburan', 100.0, 1),
  ('goal.com/id', 'hiburan', 58.5, 1),
  ('gojek.com', 'hiburan', 28.5, 1),
  ('googleusercontent.com', 'hiburan', 0.0, 1),
  ('googlevideo.com', 'hiburan', 100.0, 1),
  ('grid.id', 'hiburan', 99.5, 1),
  ('hbomax.com', 'hiburan', 7.0, 1),
  ('helo.me', 'hiburan', 12.4, 1),
  ('hipwee.com', 'hiburan', 50.4, 1),
  ('hooq.tv', 'hiburan', 88.1, 1),
  ('hoyoverse.com', 'hiburan', 96.8, 1),
  ('hybrid.co.id', 'hiburan', 36.7, 1),
  ('idbytes.com', 'hiburan', 69.6, 1),
  ('idntimes.com', 'hiburan', 71.3, 1),
  ('iflix.com', 'hiburan', 96.4, 1),
  ('igaworks.com', 'hiburan', 44.9, 1),
  ('ign.com', 'hiburan', 39.0, 1),
  ('imdb-api.com', 'hiburan', 28.4, 1),
  ('indiexx.com', 'hiburan', 33.4, 1),
  ('insertlive.com', 'hiburan', 98.1, 1),
  ('instagram.com', 'hiburan', 99.9, 1),
  ('iqiyi.com', 'hiburan', 15.3, 1),
  ('itemku.com', 'hiburan', 17.6, 1),
  ('jagatplay.com', 'hiburan', 100.0, 1),
  ('joox.com', 'hiburan', 39.1, 1),
  ('kakao.com', 'hiburan', 10.3, 1),
  ('kapanlagi.com', 'hiburan', 99.8, 1),
  ('kaskus.co.id', 'hiburan', 69.9, 1),
  ('kwai.com', 'hiburan', 15.9, 1),
  ('lge.com', 'hiburan', 20.3, 1),
  ('licdn.com', 'hiburan', 47.1, 1),
  ('likee.video', 'hiburan', 99.9, 1),
  ('line.me', 'hiburan', 91.5, 1),
  ('line.me/tv', 'hiburan', 94.0, 1),
  ('liputan6.com', 'hiburan', 18.9, 1),
  ('listenbrainz.org', 'hiburan', 27.2, 1),
  ('lolesports.com', 'hiburan', 0.4, 1),
  ('mangastream.net', 'hiburan', 99.9, 1),
  ('matamata.com', 'hiburan', 16.6, 1),
  ('metacafe.com', 'hiburan', 37.4, 1),
  ('mineski.net', 'hiburan', 23.0, 1),
  ('mlbb.com', 'hiburan', 99.6, 1),
  ('mobilelegends.com', 'hiburan', 99.8, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('mojok.co', 'hiburan', 33.2, 1),
  ('mola.tv', 'hiburan', 46.8, 1),
  ('mxplayer.in', 'hiburan', 100.0, 1),
  ('netflix.com', 'hiburan', 100.0, 1),
  ('nflxvideo.net', 'hiburan', 99.8, 1),
  ('nhncorp.com', 'hiburan', 35.2, 1),
  ('niconico.jp', 'hiburan', 43.3, 1),
  ('nimo.tv', 'hiburan', 90.6, 1),
  ('nintendo.net', 'hiburan', 98.6, 1),
  ('ntvplus.id', 'hiburan', 92.4, 1),
  ('okezone.com', 'hiburan', 32.1, 1),
  ('pgyer.com', 'hiburan', 56.6, 1),
  ('pinimg.com', 'hiburan', 88.8, 1),
  ('pinterest.com', 'hiburan', 98.6, 1),
  ('playfabapi.com', 'hiburan', 100.0, 1),
  ('playstation.net', 'hiburan', 100.0, 1),
  ('primevideo.com', 'hiburan', 99.9, 1),
  ('reddit.com/r/indonesia', 'hiburan', 88.0, 1),
  ('resso.com', 'hiburan', 19.8, 1),
  ('roblox.com', 'hiburan', 100.0, 1),
  ('sc-cdn.net', 'hiburan', 51.0, 1),
  ('selular.id', 'hiburan', 48.3, 1),
  ('shopee.co.id', 'netral', 99.0, 1),
  ('snackvideo.com', 'hiburan', 99.9, 1),
  ('snapchat.com', 'hiburan', 100.0, 1),
  ('soundcloud.com', 'hiburan', 1.2, 1),
  ('spotify.com', 'hiburan', 99.9, 1),
  ('steam-api.com', 'hiburan', 100.0, 1),
  ('steam.cdn', 'hiburan', 100.0, 1),
  ('steam.com', 'hiburan', 100.0, 1),
  ('steampowered.com', 'hiburan', 99.9, 1),
  ('tabloidpulsa.co.id', 'hiburan', 44.3, 1),
  ('tenor.com', 'hiburan', 37.3, 1),
  ('tiktok.com', 'hiburan', 100.0, 1),
  ('tiktokv.com', 'hiburan', 100.0, 1),
  ('tokopedia.com', 'hiburan', 63.2, 1),
  ('tribunnews.com/sport', 'hiburan', 99.6, 1),
  ('tumblr.com', 'hiburan', 36.6, 1),
  ('twimg.com', 'hiburan', 95.0, 1),
  ('twitch.tv', 'hiburan', 99.5, 1),
  ('twitchapps.com', 'hiburan', 97.6, 1),
  ('twitchsvc.net', 'hiburan', 99.0, 1),
  ('unipin.com', 'hiburan', 22.4, 1),
  ('vidio.com', 'hiburan', 97.2, 1),
  ('viki.io', 'hiburan', 40.1, 1),
  ('vimeo.com', 'hiburan', 48.6, 1),
  ('viu.com', 'hiburan', 26.6, 1),
  ('wargaming.net', 'hiburan', 100.0, 1),
  ('wattpad.com', 'hiburan', 10.1, 1),
  ('webtoon.com', 'hiburan', 91.4, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('webtoons.com', 'hiburan', 92.4, 1),
  ('wehear.id', 'hiburan', 26.6, 1),
  ('wetv.vip', 'hiburan', 50.4, 1),
  ('xboxlive.com', 'hiburan', 98.8, 1),
  ('youtube.com', 'hiburan', 100.0, 1),
  ('ytimg.com', 'hiburan', 87.3, 1),
  ('zili.com', 'hiburan', 64.9, 1),
  ('zingmp3.vn', 'hiburan', 56.0, 1),
  ('adyen.com', 'netral', 20.6, 1),
  ('aka.ms', 'netral', 24.1, 1),
  ('amazonaws.com', 'netral', 100.0, 1),
  ('amplitude.com', 'netral', 59.5, 1),
  ('apple-cloudkit.com', 'netral', 100.0, 1),
  ('apple.com', 'netral', 100.0, 1),
  ('atlassian.net', 'netral', 99.6, 1),
  ('azure.com', 'netral', 100.0, 1),
  ('bing.com', 'netral', 99.7, 1),
  ('bitbucket.org', 'netral', 77.2, 1),
  ('bootstrapcdn.com', 'netral', 10.1, 1),
  ('cloudflare.com', 'netral', 100.0, 1),
  ('cloudfront.net', 'netral', 100.0, 1),
  ('crashlytics.com', 'netral', 100.0, 1),
  ('digicert.com', 'netral', 99.9, 1),
  ('dns.google', 'netral', 99.9, 1),
  ('doku.com', 'netral', 84.1, 1),
  ('facebook.net', 'netral', 3.0, 1),
  ('firebaseio.com', 'netral', 100.0, 1),
  ('fly.io', 'netral', 43.2, 1),
  ('fontawesome.com', 'netral', 100.0, 1),
  ('freshworks.com', 'netral', 51.9, 1),
  ('github.com', 'netral', 99.9, 1),
  ('githubusercontent.com', 'netral', 99.9, 1),
  ('globalsign.net', 'netral', 100.0, 1),
  ('gmail.com', 'netral', 85.0, 1),
  ('google-analytics.com', 'netral', 100.0, 1),
  ('google.com', 'netral', 99.7, 1),
  ('googleapis.com', 'netral', 100.0, 1),
  ('googletagmanager.com', 'netral', 99.4, 1),
  ('gstatic.com', 'netral', 100.0, 1),
  ('heroku.com', 'netral', 87.7, 1),
  ('hotjar.com', 'netral', 19.8, 1),
  ('icloud.com', 'netral', 100.0, 1),
  ('intercom.io', 'netral', 18.1, 1),
  ('jquery.com', 'netral', 31.5, 1),
  ('jsdelivr.net', 'netral', 99.8, 1),
  ('lencr.org', 'netral', 68.3, 1),
  ('letsencrypt.org', 'netral', 99.9, 1),
  ('live.com', 'netral', 0.1, 1),
  ('mi.com', 'netral', 59.9, 1),
  ('microsoft.com', 'netral', 100.0, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('microsoftonline.com', 'netral', 100.0, 1),
  ('midtrans.com', 'netral', 99.7, 1),
  ('miui.com', 'netral', 99.4, 1),
  ('msftncsi.com', 'netral', 100.0, 1),
  ('netlify.com', 'netral', 44.3, 1),
  ('notion.com', 'netral', 98.4, 1),
  ('notion.so', 'netral', 98.2, 1),
  ('npmjs.org', 'netral', 48.4, 1),
  ('ntp.org', 'netral', 94.7, 1),
  ('office.net', 'netral', 100.0, 1),
  ('office365.com', 'netral', 100.0, 1),
  ('one.one', 'netral', 23.0, 1),
  ('optimizely.com', 'netral', 74.8, 1),
  ('paypal.com', 'netral', 92.5, 1),
  ('paypalobjects.com', 'netral', 99.5, 1),
  ('pki.goog', 'netral', 91.5, 1),
  ('pypi.org', 'netral', 18.3, 1),
  ('quad9.net', 'netral', 34.3, 1),
  ('render.com', 'netral', 85.9, 1),
  ('samsung.com', 'netral', 100.0, 1),
  ('samsungapps.com', 'netral', 100.0, 1),
  ('samsungcloud.com', 'netral', 100.0, 1),
  ('samsungfind.com', 'netral', 100.0, 1),
  ('samsungknox.com', 'netral', 100.0, 1),
  ('samsungmobile.com', 'netral', 100.0, 1),
  ('samsungosp.com', 'netral', 100.0, 1),
  ('samsungsmartcam.com', 'netral', 100.0, 1),
  ('samsungtv.com', 'netral', 100.0, 1),
  ('segment.com', 'netral', 99.6, 1),
  ('segment.io', 'netral', 99.6, 1),
  ('sentry.io', 'netral', 100.0, 1),
  ('sharepoint.com', 'netral', 87.4, 1),
  ('skype.com', 'netral', 32.5, 1),
  ('slack.com', 'netral', 5.1, 1),
  ('stripe.com', 'netral', 96.6, 1),
  ('tailwindcss.com', 'netral', 80.3, 1),
  ('trello.com', 'netral', 33.5, 1),
  ('twilio.com', 'netral', 9.9, 1),
  ('twitter.com', 'netral', 0.0, 1),
  ('ubuntu.com', 'netral', 99.1, 1),
  ('unpkg.com', 'netral', 99.8, 1),
  ('vercel.com', 'netral', 14.9, 1),
  ('wa.me', 'netral', 20.7, 1),
  ('whatsapp.com', 'netral', 0.2, 1),
  ('windows.com', 'netral', 99.8, 1),
  ('windows.net', 'netral', 99.8, 1),
  ('windowsphone.com', 'netral', 99.2, 1),
  ('windowsupdate.com', 'netral', 100.0, 1),
  ('xendit.co', 'netral', 4.3, 1),
  ('xiaomi.com', 'netral', 99.9, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('xiaomi.net', 'netral', 99.9, 1),
  ('zdassets.com', 'netral', 23.4, 1),
  ('zendesk.com', 'netral', 92.5, 1),
  ('zoom.us', 'netral', 3.6, 1),
  ('1337x.to', 'negatif', 48.6, 1),
  ('18plus-streaming.net', 'negatif', 0.0, 1),
  ('88gasia.com', 'negatif', 25.1, 1),
  ('88tangkas.com', 'negatif', 27.3, 1),
  ('account-hacker.net', 'negatif', 100.0, 1),
  ('adultcontent-id.cc', 'negatif', 100.0, 1),
  ('agen-sbobet.xyz', 'negatif', 100.0, 1),
  ('agenbolaterpercaya.net', 'negatif', 100.0, 1),
  ('agensabung.id', 'negatif', 100.0, 1),
  ('agenslot-terpercaya.net', 'negatif', 100.0, 1),
  ('animeindo.cam', 'negatif', 3.6, 1),
  ('apple-id-suspend.net', 'negatif', 0.0, 1),
  ('arisan-online-bodong.cc', 'negatif', 95.7, 1),
  ('ashemaletube.com', 'negatif', 9.0, 1),
  ('baccarat-online.cc', 'negatif', 100.0, 1),
  ('bajakanfilm.cc', 'negatif', 100.0, 1),
  ('bandar-bola-online.xyz', 'negatif', 100.0, 1),
  ('bandar-togel.net', 'negatif', 100.0, 1),
  ('bandarjudi.net', 'negatif', 100.0, 1),
  ('bandarq-online.net', 'negatif', 100.0, 1),
  ('bca-login-verify.cc', 'negatif', 98.0, 1),
  ('bet365-indo.cc', 'negatif', 100.0, 1),
  ('betting-premier.cc', 'negatif', 100.0, 1),
  ('bigo-diamond-hack.cc', 'negatif', 100.0, 1),
  ('binary-option-scam.net', 'negatif', 100.0, 1),
  ('bioskopkeren.cam', 'negatif', 53.0, 1),
  ('bitcoin-cepat-kaya.net', 'negatif', 60.7, 1),
  ('bni-mobile-banking.cc', 'negatif', 86.2, 1),
  ('bokep-viral.net', 'negatif', 100.0, 1),
  ('bokepindo.cc', 'negatif', 100.0, 1),
  ('bola-tangkas.net', 'negatif', 55.9, 1),
  ('bonus-deposit-judi.cc', 'negatif', 100.0, 1),
  ('botnet-panel.cc', 'negatif', 99.5, 1),
  ('botnet-service.cc', 'negatif', 77.8, 1),
  ('bri-m-banking.xyz', 'negatif', 93.4, 1),
  ('bri-verifikasi.cc', 'negatif', 75.4, 1),
  ('bully-forum.cc', 'negatif', 85.7, 1),
  ('capsa-susun-online.id', 'negatif', 30.4, 1),
  ('capsa-susun.cc', 'negatif', 30.4, 1),
  ('card-dump.xyz', 'negatif', 46.4, 1),
  ('carding-forum.net', 'negatif', 98.5, 1),
  ('carding-tools.net', 'negatif', 98.6, 1),
  ('casino-338a.com', 'negatif', 100.0, 1),
  ('casino-live-indonesia.cc', 'negatif', 100.0, 1),
  ('casino-online.id', 'negatif', 100.0, 1),
  ('ceme-online.xyz', 'negatif', 28.2, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('cheat-engine-game.xyz', 'negatif', 0.0, 1),
  ('cheat-pubgm.xyz', 'negatif', 3.0, 1),
  ('clickbait-hoax.cc', 'negatif', 94.3, 1),
  ('cracked-software.net', 'negatif', 100.0, 1),
  ('credential-harvest.cc', 'negatif', 89.5, 1),
  ('crypto-ponzi.cc', 'negatif', 98.6, 1),
  ('cryptominer-silent.net', 'negatif', 93.8, 1),
  ('daftar-situs-slot.net', 'negatif', 100.0, 1),
  ('darkweb-access.net', 'negatif', 96.0, 1),
  ('darkweb-id.xyz', 'negatif', 98.0, 1),
  ('darkweb-market-id.cc', 'negatif', 99.0, 1),
  ('ddos-stresser.xyz', 'negatif', 85.7, 1),
  ('ddos-tools.net', 'negatif', 98.5, 1),
  ('dewacasino.com', 'negatif', 100.0, 1),
  ('dewasa-live.cc', 'negatif', 100.0, 1),
  ('dewasa18plus.cc', 'negatif', 100.0, 1),
  ('dewatogel.net', 'negatif', 100.0, 1),
  ('dominoqq99.com', 'negatif', 100.0, 1),
  ('dominoqq99.net', 'negatif', 100.0, 1),
  ('downloadgratis-id.xyz', 'negatif', 32.7, 1),
  ('drakorindo.cam', 'negatif', 30.2, 1),
  ('exploit-cdn.net', 'negatif', 97.1, 1),
  ('exploit-kit.xyz', 'negatif', 98.5, 1),
  ('eztv.re', 'negatif', 28.5, 1),
  ('fake-follower-jual.net', 'negatif', 96.3, 1),
  ('fake-id-online.net', 'negatif', 84.7, 1),
  ('fake-news-indo.cc', 'negatif', 85.1, 1),
  ('forex-robot-profit.xyz', 'negatif', 36.4, 1),
  ('free-chip-slot.net', 'negatif', 100.0, 1),
  ('ganool.cam', 'negatif', 55.5, 1),
  ('gofood-cashback.net', 'negatif', 89.6, 1),
  ('gopay-topup-bonus.net', 'negatif', 59.1, 1),
  ('hacking-tools.cc', 'negatif', 100.0, 1),
  ('hate-speech.net', 'negatif', 44.3, 1),
  ('hentai-streaming.xyz', 'negatif', 0.0, 1),
  ('hoax-berita.cc', 'negatif', 48.2, 1),
  ('identity-theft.xyz', 'negatif', 27.8, 1),
  ('ilegal-cepat-cair.cc', 'negatif', 100.0, 1),
  ('indopoker.org', 'negatif', 100.0, 1),
  ('indotogel.net', 'negatif', 100.0, 1),
  ('indoxxi.cam', 'negatif', 30.3, 1),
  ('infostealer-panel.xyz', 'negatif', 98.8, 1),
  ('jayatogel.com', 'negatif', 100.0, 1),
  ('jual-akun-banned.xyz', 'negatif', 97.2, 1),
  ('judi-bola-parlay.xyz', 'negatif', 100.0, 1),
  ('judi-kartu-online.id', 'negatif', 100.0, 1),
  ('judionline-terpercaya.xyz', 'negatif', 100.0, 1),
  ('judionline99.cc', 'negatif', 100.0, 1),
  ('kasino88.net', 'negatif', 98.6, 1),
  ('kaskus-hack.net', 'negatif', 100.0, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('keezmovies.com', 'negatif', 0.9, 1),
  ('keygen-serial.xyz', 'negatif', 85.0, 1),
  ('keylogger-free.xyz', 'negatif', 98.0, 1),
  ('keylogger-pro.xyz', 'negatif', 98.7, 1),
  ('klikbca-secure.xyz', 'negatif', 94.2, 1),
  ('konten-asusila.xyz', 'negatif', 100.0, 1),
  ('konten-kekerasan.cc', 'negatif', 100.0, 1),
  ('layarkaca21.cam', 'negatif', 41.6, 1),
  ('live-casino-indo.net', 'negatif', 100.0, 1),
  ('livescore-bola.net', 'negatif', 3.3, 1),
  ('lk21.cam', 'negatif', 39.6, 1),
  ('lotere-online-id.net', 'negatif', 65.0, 1),
  ('malware-cdn.xyz', 'negatif', 99.9, 1),
  ('malware-doc.xyz', 'negatif', 99.9, 1),
  ('malware-drop.xyz', 'negatif', 99.9, 1),
  ('mandiri-secure-login.xyz', 'negatif', 99.7, 1),
  ('maxbet-mobile.com', 'negatif', 100.0, 1),
  ('maxwin-slot.cc', 'negatif', 100.0, 1),
  ('money-game-ilegal.net', 'negatif', 100.0, 1),
  ('nontonfilm-gratis.net', 'negatif', 27.8, 1),
  ('nyaa.si', 'negatif', 33.0, 1),
  ('onion.ws', 'negatif', 15.7, 1),
  ('openload.cam', 'negatif', 45.8, 1),
  ('pasarantogel2.com', 'negatif', 100.0, 1),
  ('paypal-id-verify.com', 'negatif', 50.5, 1),
  ('phishtank-bni-verify.xyz', 'negatif', 100.0, 1),
  ('phishtank-shopee-bonus.cc', 'negatif', 99.9, 1),
  ('phishtank-tokopedia-login.net', 'negatif', 99.7, 1),
  ('pinjaman-bodong.net', 'negatif', 97.0, 1),
  ('pirateproxy.cam', 'negatif', 94.0, 1),
  ('poker-indo.net', 'negatif', 100.0, 1),
  ('poker-online.id', 'negatif', 100.0, 1),
  ('poker88-vip.net', 'negatif', 100.0, 1),
  ('poker88asia.com', 'negatif', 100.0, 1),
  ('pokerrepublik.com', 'negatif', 100.0, 1),
  ('ponzi-robot-trading.net', 'negatif', 98.0, 1),
  ('pornhub-alt.cc', 'negatif', 100.0, 1),
  ('pornhub.com', 'negatif', 100.0, 1),
  ('radikalisme-konten.cc', 'negatif', 100.0, 1),
  ('ransomware-as-service.net', 'negatif', 3.9, 1),
  ('rarbg.to', 'negatif', 51.9, 1),
  ('rat-builder.cc', 'negatif', 21.0, 1),
  ('redtube.com', 'negatif', 6.0, 1),
  ('rekomendasi-judi.cc', 'negatif', 100.0, 1),
  ('roulette-indo.xyz', 'negatif', 100.0, 1),
  ('rubibet.com', 'negatif', 100.0, 1),
  ('sabung-ayam-s128.cc', 'negatif', 94.9, 1),
  ('sara-bokep.cc', 'negatif', 100.0, 1),
  ('sbobet88-indo.cc', 'negatif', 100.0, 1),
  ('sexvideo-indo.net', 'negatif', 98.3, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

INSERT INTO cache_domain
  (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  ('shopee-winner.cc', 'negatif', 58.9, 1),
  ('situs-judi303.net', 'negatif', 100.0, 1),
  ('skimmer-cc-shop.net', 'negatif', 95.0, 1),
  ('skimming-atm.cc', 'negatif', 94.6, 1),
  ('slot-gacor99.xyz', 'negatif', 100.0, 1),
  ('slot-maxwin.xyz', 'negatif', 100.0, 1),
  ('slot888.xyz', 'negatif', 100.0, 1),
  ('slotgacor88.net', 'negatif', 100.0, 1),
  ('slotpulsa777.net', 'negatif', 100.0, 1),
  ('sms-spoofing.net', 'negatif', 90.9, 1),
  ('softwarebajakan.net', 'negatif', 100.0, 1),
  ('spam-sms-blast.xyz', 'negatif', 86.2, 1),
  ('spankbang.com', 'negatif', 77.9, 1),
  ('sportbook-indo.cc', 'negatif', 24.5, 1),
  ('spyware-indo.cc', 'negatif', 87.7, 1),
  ('stealer-logs.cc', 'negatif', 69.8, 1),
  ('subscene-sub.com', 'negatif', 20.1, 1),
  ('taruhan-bola88.net', 'negatif', 100.0, 1),
  ('thepiratebay.org', 'negatif', 76.9, 1),
  ('togel-sgp-hari-ini.com', 'negatif', 100.0, 1),
  ('togel-singapore.id', 'negatif', 100.0, 1),
  ('togel4d.net', 'negatif', 100.0, 1),
  ('tube8.com', 'negatif', 2.1, 1),
  ('update-akun-palsu.net', 'negatif', 8.7, 1),
  ('update-mandiri.net', 'negatif', 7.3, 1),
  ('vegas77.net', 'negatif', 64.4, 1),
  ('verifikasi-akun.cc', 'negatif', 80.8, 1),
  ('verify-now.net', 'negatif', 90.8, 1),
  ('videoporno-indo.net', 'negatif', 100.0, 1),
  ('virus-installer.net', 'negatif', 100.0, 1),
  ('warez-id.com', 'negatif', 100.0, 1),
  ('webshell-pack.cc', 'negatif', 32.2, 1),
  ('xhamster.com', 'negatif', 18.2, 1),
  ('xnxx-cdn.com', 'negatif', 76.7, 1),
  ('xnxx.com', 'negatif', 87.2, 1),
  ('xvideos-cdn.com', 'negatif', 1.2, 1),
  ('xvideos-proxy.net', 'negatif', 10.3, 1),
  ('xvideos.com', 'negatif', 1.8, 1),
  ('youporn.com', 'negatif', 100.0, 1),
  ('yts.mx', 'negatif', 11.2, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

-- Extra: domain log_akses demo + domain dari dataset v2.11 (baru ditambahkan)
INSERT INTO cache_domain (domain_url, kategori, confidence_score, jumlah_hit) VALUES
  -- domain untuk log_akses demo
  ('classroom.google.com', 'edukasi',  99.0, 1),
  ('scholar.google.com',   'edukasi',  98.9, 1),
  ('wikipedia.org',        'edukasi',  95.2, 1),
  ('dewa777slot.net',      'negatif',  99.8, 1),
  ('kerumput-iklan.xyz',   'negatif',  91.2, 1),
  -- e-commerce Indonesia (netral — tidak diblokir)
  ('tokopediax.com',       'netral',   99.0, 1),
  ('shopee.com',           'netral',   99.0, 1),
  ('shopee.sg',            'netral',   99.0, 1),
  ('shopeepay.co.id',      'netral',   99.0, 1),
  -- banking Indonesia (netral — WAJIB tidak diblokir)
  ('bca.co.id',            'netral',   99.0, 1),
  ('klikbca.com',          'netral',   99.0, 1),
  -- analytics / monitoring / ad-tech (netral — infrastruktur)
  ('mix.panel.com',        'netral',   99.0, 1),
  ('adnxs.com',            'netral',   99.0, 1),
  ('newrelic.com',         'netral',   99.0, 1),
  ('doubleverify.com',     'netral',   99.0, 1),
  ('imrworldwide.com',     'netral',   99.0, 1),
  ('revenuecat.com',       'netral',   99.0, 1),
  -- CDN / device system (netral)
  ('avcdn.net',            'netral',   99.0, 1),
  ('heytapmobile.com',     'netral',   99.0, 1),
  ('heytapdl.com',         'netral',   99.0, 1),
  -- streaming sah (hiburan)
  ('wetvinfo.com',         'hiburan',  99.0, 1),
  ('vu.tv',                'hiburan',  57.0, 1),
  -- domain pendek teknis (netral)
  ('vr.in',                'netral',   99.0, 1),
  ('8d.au',                'netral',   99.0, 1),
  ('9.sg',                 'netral',   99.0, 1),
  ('i8.cc',                'netral',   99.0, 1),
  ('u.uk',                 'netral',   99.0, 1),
  ('5sh0.jp',              'netral',   99.0, 1),
  ('popin-minus.com',      'netral',   99.0, 1)
ON DUPLICATE KEY UPDATE
  kategori=VALUES(kategori),
  confidence_score=VALUES(confidence_score),
  jumlah_hit=jumlah_hit+1;

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
UNION ALL SELECT '  └─ netral',               COUNT(*) FROM cache_domain WHERE kategori='netral'
UNION ALL SELECT 'LOG total',                 COUNT(*) FROM log_akses
UNION ALL SELECT '  └─ Hari ini',             COUNT(*) FROM log_akses WHERE DATE(waktu_akses) = CURDATE()
UNION ALL SELECT '  └─ Kemarin',              COUNT(*) FROM log_akses WHERE DATE(waktu_akses) = CURDATE() - INTERVAL 1 DAY
UNION ALL SELECT '  └─ H-2',                  COUNT(*) FROM log_akses WHERE DATE(waktu_akses) = CURDATE() - INTERVAL 2 DAY
UNION ALL SELECT '  └─ diblokir total',       COUNT(*) FROM log_akses WHERE aksi='blokir'
UNION ALL SELECT 'JADWAL BLOKIR',             COUNT(*) FROM jadwal_blokir
UNION ALL SELECT 'DOMPET KUOTA',              COUNT(*) FROM dompet_kuota;
