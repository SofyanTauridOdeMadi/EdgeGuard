-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║  EDGE GUARD — SKEMA MySQL (Relasional, sesuai ERD baru)              ║
-- ║                                                                       ║
-- ║  Diagram entitas (FK arrow = "many → one"):                          ║
-- ║                                                                       ║
-- ║   admin_orang_tua ─┬─< pengguna_anak ─┬─< log_akses >── cache_domain  ║
-- ║                    │                  ├─< jadwal_blokir              ║
-- ║                    │                  └─< dompet_kuota               ║
-- ║                    ├─< whitelist                                     ║
-- ║                    ├─< blacklist                                     ║
-- ║                    └─< kebijakan_router                              ║
-- ║                                                                       ║
-- ║  Jalankan satu kali:                                                  ║
-- ║    mysql -u edgeguard -p < dashboard/schema.sql                       ║
-- ╚══════════════════════════════════════════════════════════════════════╝

CREATE DATABASE IF NOT EXISTS edgeguard
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE edgeguard;

-- ════════════════════════════════════════════════════════════════════════
-- 1. ADMIN_ORANG_TUA — pemilik dashboard (login)
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE admin_orang_tua (
  admin_id        INT          AUTO_INCREMENT PRIMARY KEY,
  nama            VARCHAR(100) NOT NULL,
  email           VARCHAR(100) NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NOT NULL,
  dibuat_pada     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- ── lockout + audit login (kept dari iterasi sebelumnya) ────────────
  gagal_login        TINYINT UNSIGNED NOT NULL DEFAULT 0,
  locked_until       DATETIME    DEFAULT NULL,
  last_gagal_ip      VARCHAR(45) DEFAULT NULL,
  last_gagal_at      DATETIME    DEFAULT NULL,
  -- ── sesi aktif (single-session) ────────────────────────────────────
  session_token      CHAR(64)    DEFAULT NULL,
  session_expired_at DATETIME    DEFAULT NULL,
  session_ip         VARCHAR(45) DEFAULT NULL,
  session_user_agent VARCHAR(255) DEFAULT NULL,
  last_login_at      DATETIME    DEFAULT NULL,
  last_login_ip      VARCHAR(45) DEFAULT NULL,
  telegram_chatid    VARCHAR(64) DEFAULT NULL,

  INDEX idx_admin_token (session_token)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 2. PENGGUNA_ANAK — perangkat anak (milik admin)
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE pengguna_anak (
  user_id         INT          AUTO_INCREMENT PRIMARY KEY,
  admin_id        INT          NOT NULL,
  mac_address     VARCHAR(17)  NOT NULL UNIQUE,
  device_name     VARCHAR(100) DEFAULT NULL,    -- "MacBook Air", "iPad Pro"
  status_aktif    BOOLEAN      NOT NULL DEFAULT FALSE,
  dibuat_pada     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- ── kolom domain-spesifik EdgeGuard ────────────────────────────────
  nama            VARCHAR(120) NOT NULL,        -- nama anak: "Stom"
  ip_terakhir     VARCHAR(45)  DEFAULT NULL,
  jeda            TINYINT(1)   NOT NULL DEFAULT 0,
  kuota_harian    INT UNSIGNED NOT NULL DEFAULT 120,
  kuota_terpakai  INT UNSIGNED NOT NULL DEFAULT 0,
  last_reset      DATE         DEFAULT NULL,
  last_seen       DATETIME     DEFAULT NULL,

  CONSTRAINT fk_anak_admin
    FOREIGN KEY (admin_id) REFERENCES admin_orang_tua(admin_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_anak_mac    (mac_address),
  INDEX idx_anak_status (status_aktif)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 3. DAFTAR_FILTER — gabungan whitelist (putih) & blacklist (hitam)
--    UNIQUE (admin_id, tipe, domain_url) mencegah duplikasi otomatis.
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE daftar_filter (
  filter_id    INT          AUTO_INCREMENT PRIMARY KEY,
  admin_id     INT          NOT NULL,
  tipe         ENUM('putih','hitam') NOT NULL,
  domain_url   VARCHAR(255) NOT NULL,
  alasan       VARCHAR(255) DEFAULT NULL,
  CONSTRAINT fk_filter_admin
    FOREIGN KEY (admin_id) REFERENCES admin_orang_tua(admin_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  UNIQUE KEY uq_filter (admin_id, tipe, domain_url),
  INDEX idx_filter_tipe (tipe)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 5. CACHE_DOMAIN — knowledge base AI (hasil klasifikasi realtime)
--    Setiap domain unik yang pernah diklasifikasi disimpan di sini.
--    Akses berulang → jumlah_hit naik, terakhir_diakses di-update.
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE cache_domain (
  domain_url        VARCHAR(255) PRIMARY KEY,
  kategori          ENUM('edukasi','hiburan','negatif','unknown')
                       NOT NULL DEFAULT 'unknown',
  confidence_score  FLOAT        NOT NULL DEFAULT 0,
  terakhir_diakses  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP,
  jumlah_hit        INT UNSIGNED NOT NULL DEFAULT 1,
  INDEX idx_cache_kategori (kategori),
  INDEX idx_cache_diakses  (terakhir_diakses DESC)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 6. LOG_AKSES — riwayat tiap akses anak (ke domain)
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE log_akses (
  log_id        BIGINT       AUTO_INCREMENT PRIMARY KEY,
  user_id       INT          DEFAULT NULL,
  domain_url    VARCHAR(255) DEFAULT NULL,
  kategori      ENUM('edukasi','hiburan','negatif','unknown')
                  NOT NULL DEFAULT 'unknown',
  aksi          ENUM('izinkan','blokir') NOT NULL DEFAULT 'izinkan',
  alasan        VARCHAR(64)  DEFAULT '',          -- 'whitelist','blacklist','klasifikasi_ai',...
  confidence    DECIMAL(5,2) DEFAULT 0.00,
  traffic_kbps  FLOAT        DEFAULT 0,
  -- snapshot untuk performa (sinkron via update saat pengguna_anak.nama diubah)
  perangkat_nama VARCHAR(120) DEFAULT '',
  mac           VARCHAR(17)  DEFAULT '',
  waktu_akses   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_log_user
    FOREIGN KEY (user_id) REFERENCES pengguna_anak(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_log_domain
    FOREIGN KEY (domain_url) REFERENCES cache_domain(domain_url)
    ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_log_waktu (waktu_akses DESC),
  INDEX idx_log_user  (user_id),
  INDEX idx_log_kat   (kategori),
  INDEX idx_log_aksi  (aksi)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 7. KEBIJAKAN_ROUTER — versi kebijakan yang di-sync ke router
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE kebijakan_router (
  kebijakan_id     INT          AUTO_INCREMENT PRIMARY KEY,
  admin_id         INT          NOT NULL,
  versi_kebijakan  VARCHAR(50)  NOT NULL DEFAULT '1.0',
  terakhir_sinkron TIMESTAMP    NULL DEFAULT NULL,
  status_sinkron   ENUM('menunggu','sukses','gagal') NOT NULL DEFAULT 'menunggu',
  catatan          VARCHAR(255) DEFAULT NULL,
  CONSTRAINT fk_keb_admin
    FOREIGN KEY (admin_id) REFERENCES admin_orang_tua(admin_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 8. JADWAL_BLOKIR — jadwal blokir/izinkan per anak per hari
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE jadwal_blokir (
  jadwal_id    INT     AUTO_INCREMENT PRIMARY KEY,
  user_id      INT     NOT NULL,
  hari         ENUM('senin','selasa','rabu','kamis','jumat','sabtu','minggu')
                 NOT NULL,
  jam_mulai    TIME    NOT NULL,
  jam_selesai  TIME    NOT NULL,
  mode         ENUM('blokir','izinkan') NOT NULL DEFAULT 'blokir',
  CONSTRAINT fk_jadwal_user
    FOREIGN KEY (user_id) REFERENCES pengguna_anak(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_jadwal_user (user_id, hari)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 9. DOMPET_KUOTA — saldo kuota & bonus reward per anak
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE dompet_kuota (
  wallet_id        INT          AUTO_INCREMENT PRIMARY KEY,
  user_id          INT          NOT NULL UNIQUE,
  sisa_hiburan     INT UNSIGNED NOT NULL DEFAULT 0,    -- menit bonus tersisa
  total_edukasi    INT UNSIGNED NOT NULL DEFAULT 0,    -- akumulasi menit edu hari ini
  batas_harian     INT UNSIGNED NOT NULL DEFAULT 120,  -- maks bonus per hari
  terakhir_reset   DATE         DEFAULT NULL,
  CONSTRAINT fk_dompet_user
    FOREIGN KEY (user_id) REFERENCES pengguna_anak(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- 10. KONFIGURASI — key/value untuk pengaturan global
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE konfigurasi (
  k VARCHAR(64) PRIMARY KEY,
  v TEXT
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════════════
-- VIEW: statistik per pengguna_anak
-- ════════════════════════════════════════════════════════════════════════
CREATE VIEW v_statistik AS
SELECT
  p.user_id,
  p.nama,
  COUNT(l.log_id) AS total_akses,
  SUM(CASE WHEN l.aksi = 'blokir'             THEN 1 ELSE 0 END) AS total_blokir,
  SUM(CASE WHEN l.kategori = 'edukasi'        THEN 1 ELSE 0 END) AS total_edukasi,
  SUM(CASE WHEN l.kategori = 'hiburan'        THEN 1 ELSE 0 END) AS total_hiburan,
  SUM(CASE WHEN l.kategori = 'negatif'        THEN 1 ELSE 0 END) AS total_negatif
FROM pengguna_anak p
LEFT JOIN log_akses l ON l.user_id = p.user_id
GROUP BY p.user_id, p.nama;

INSERT INTO admin_orang_tua (nama, email, password_hash) VALUES
  ('Stom', 'stom@edgeguard.id', 'BOOTSTRAP');

INSERT INTO kebijakan_router (admin_id, versi_kebijakan, status_sinkron, catatan) VALUES
  (1, '1.0', 'menunggu', 'Kebijakan awal — belum disinkron');

INSERT INTO konfigurasi (k, v) VALUES
  ('ai_aktif',               '1'),
  ('kuota_harian_menit',     '120'),
  ('durasi_belajar_menit',   '30'),
  ('waktu_bonus_menit',      '10'),
  ('batas_bonus_menit',      '60'),
  ('login_max_gagal',        '3'),
  ('login_lockout_detik',    '300'),
  ('heartbeat_offline_detik','120'),
  ('telegram_bot_token',     '8609267262:AAGY66donQMGAhGUO_kSdjjFF5gmGyi1HIs'),
  ('telegram_chat_id',       '7108892785'),
  ('telegram_aktif',         '1'),
  ('telegram_last_ok',       '0'),
  ('telegram_update_offset', '0');
