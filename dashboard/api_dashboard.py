"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — Flask Dashboard (VPS / Cloud)                          ║
║  Database  : MySQL relational (schema ERD baru)                      ║
║  Port      : 8080                                                    ║
║                                                                       ║
║  Tabel utama (sesuai ERD):                                           ║
║   admin_orang_tua, pengguna_anak, whitelist, blacklist,              ║
║   cache_domain, log_akses, kebijakan_router, jadwal_blokir,          ║
║   dompet_kuota, konfigurasi                                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash)
import pymysql, pymysql.cursors
import os, sys, json, time, math, secrets, re, threading
from datetime import datetime, date, timedelta
from functools import wraps

try:
    import bcrypt
    _BCRYPT = True
except ImportError:
    _BCRYPT = False

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI APP
# ══════════════════════════════════════════════════════════════════════════════
app = Flask(__name__, template_folder='.', static_folder='aset',
            static_url_path='/aset')
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY = True,
    SESSION_COOKIE_SAMESITE = 'Lax',
    SESSION_COOKIE_SECURE   = bool(int(os.environ.get('COOKIE_SECURE', '0'))),
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8),
)

DB = {
    'host':        '127.0.0.1',
    'port':        3306,
    'user':        'edgeguard',
    'password':    'admin123',
    'database':    'edgeguard',
    'charset':     'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit':  True,
    # Paksa zona waktu sesi ke WITA (+08:00 = Makassar/Singapura) supaya NOW()
    # & TIMESTAMP konsisten walau server VPS-nya berjalan di UTC.
    'init_command': "SET time_zone = '+08:00'",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════════════════════════════════════════════════════════════
# ZONA WAKTU — WITA (Makassar/Singapura, UTC+8)
# Dipakai untuk semua timestamp yang dibuat di sisi Python (notif Telegram, bot).
# ══════════════════════════════════════════════════════════════════════════════
from datetime import timezone as _tz
TZ_WITA = _tz(timedelta(hours=8))

def now_lokal():
    """datetime sekarang dalam zona WITA (UTC+8), apapun TZ host-nya."""
    return datetime.now(TZ_WITA)

def now_lokal_naive():
    """WITA sekarang sebagai datetime NAIVE (tanpa tzinfo).
    Cocok untuk dibandingkan dengan datetime dari DB (pymysql → naive) yang
    kini juga WITA karena session 'SET time_zone=+08:00'."""
    return datetime.now(TZ_WITA).replace(tzinfo=None)

# ══════════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def get_db():
    return pymysql.connect(**DB)

def query(sql, args=None, one=False):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            up = sql.lstrip().upper()
            if up.startswith(('INSERT','UPDATE','DELETE','REPLACE')):
                conn.commit()
                return cur.lastrowid if up.startswith('INSERT') else cur.rowcount
            return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()

def get_cfg(key, default=None):
    row = query("SELECT v FROM konfigurasi WHERE k=%s", (key,), one=True)
    return row['v'] if row else default

def set_cfg(key, value):
    query("INSERT INTO konfigurasi (k,v) VALUES(%s,%s) "
          "ON DUPLICATE KEY UPDATE v=%s", (key, str(value), str(value)))
    # Kalau kredensial Telegram berubah → batalkan cache agar langsung efektif.
    if str(key) in ('telegram_chat_id', 'telegram_aktif'):
        try: _tg_cred_cache['ts'] = 0.0
        except NameError: pass

# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING
# ══════════════════════════════════════════════════════════════════════════════
def hash_password(plain: str) -> str:
    """Hash password dengan bcrypt (cost 12). Wajib paket 'bcrypt'."""
    if not _BCRYPT:
        raise RuntimeError("Paket 'bcrypt' belum terpasang → jalankan: pip install bcrypt")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    if not _BCRYPT or not hashed or not hashed.startswith('$2'):
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP ADMIN PASSWORD
# ══════════════════════════════════════════════════════════════════════════════
def ensure_admin_password(default_username: str = 'stom',
                          default_pw: str = ''):
    """Pastikan admin pertama ada dengan username & password valid.

    Login UI menerima username (yang dicocokkan dengan prefix email atau email
    full). Jadi 'username' di sini = prefix email.

    Password default dibaca dari env ADMIN_BOOTSTRAP_PW (fallback 'maba22ft'),
    jadi tidak hardcoded mencolok di repo.

    Perilaku:
      • Tidak ada admin → buat baru dengan default.
      • Hash kosong/placeholder/invalid → reset + paksa pakai username default.
      • Hash valid (admin sudah punya password) → biarkan apa adanya
        (jangan timpa password user yang sudah diganti).
    """
    default_pw = default_pw or os.environ.get('ADMIN_BOOTSTRAP_PW', 'maba22ft')
    try:
        u = query("SELECT admin_id, email, password_hash FROM admin_orang_tua "
                  "ORDER BY admin_id LIMIT 1", one=True)
        new_email = f'{default_username}@edgeguard.local'
        nama_disp = default_username.capitalize()

        if not u:
            h = hash_password(default_pw)
            query("INSERT INTO admin_orang_tua (nama, email, password_hash) "
                  "VALUES (%s, %s, %s)", (nama_disp, new_email, h))
            print(f"[Bootstrap] Admin '{default_username}' dibuat. "
                  f"Password awal: {default_pw}")
            return

        h = u.get('password_hash') or ''
        valid = h.startswith('$2')   # hanya bcrypt yang dianggap valid
        if not valid:
            # Hash placeholder/'BOOTSTRAP'/invalid → reset segalanya
            new_h = hash_password(default_pw)
            query("UPDATE admin_orang_tua SET "
                  "  password_hash=%s, gagal_login=0, locked_until=NULL, "
                  "  email=%s, nama=%s "
                  "WHERE admin_id=%s",
                  (new_h, new_email, nama_disp, u['admin_id']))
            print(f"[Bootstrap] Akun di-reset ke '{default_username}' / "
                  f"'{default_pw}'.")
    except Exception as e:
        print(f"[Bootstrap] Gagal cek admin: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# RESET KUOTA HARIAN + STATUS ONLINE
# ══════════════════════════════════════════════════════════════════════════════
def reset_kuota_jika_hari_baru():
    today = now_lokal().date().isoformat()
    query("UPDATE pengguna_anak SET kuota_terpakai=0, last_reset=%s "
          "WHERE last_reset IS NULL OR last_reset <> %s", (today, today))

def refresh_status_online():
    th = int(get_cfg('heartbeat_offline_detik', '120'))
    query("UPDATE pengguna_anak SET status_aktif=0 "
          "WHERE last_seen IS NULL "
          "   OR last_seen < (NOW() - INTERVAL %s SECOND)", (th,))

# ══════════════════════════════════════════════════════════════════════════════
# HELPER UMUM
# ══════════════════════════════════════════════════════════════════════════════
def fmt(m):
    m = int(m or 0)
    if m <= 0: return "0m"
    if m >= 60:
        j, s = m // 60, m % 60
        return f"{j}j {s}m" if s else f"{j}j"
    return f"{m}m"

def proporsi_dari_logs(rows):
    edu = sum(1 for r in rows if r.get('kategori') == 'edukasi')
    hib = sum(1 for r in rows if r.get('kategori') == 'hiburan')
    neg = sum(1 for r in rows if r.get('kategori') == 'negatif')
    tot = edu + hib + neg
    if tot == 0: return 0, 0, 0
    return round(edu/tot*100), round(hib/tot*100), round(neg/tot*100)

def hitung_bar_data_hari_ini():
    """Bar chart 2-jam-an dari log hari ini."""
    rows = query(
        "SELECT HOUR(waktu_akses) AS h, kategori, COUNT(*) AS c "
        "FROM log_akses "
        "WHERE DATE(waktu_akses) = CURDATE() "
        "GROUP BY HOUR(waktu_akses), kategori"
    ) or []
    by_hour = {}
    for r in rows:
        by_hour.setdefault(int(r['h']), {})[r['kategori']] = int(r['c'])

    now_h    = now_lokal().hour
    buckets  = [8, 10, 12, 14, 16, 18, 20]
    edu_max  = max((sum(by_hour.get(h2, {}).get('edukasi', 0)
                       for h2 in range(b, b+2)) for b in buckets), default=0) or 1
    hib_max  = max((sum(by_hour.get(h2, {}).get('hiburan', 0)
                       for h2 in range(b, b+2)) for b in buckets), default=0) or 1
    out = []
    for b in buckets:
        edu_raw = sum(by_hour.get(h2, {}).get('edukasi', 0) for h2 in range(b, b+2))
        hib_raw = sum(by_hour.get(h2, {}).get('hiburan', 0) for h2 in range(b, b+2))
        out.append({
            "label":  f"{b:02d}:00",
            "edu":    round(edu_raw / edu_max * 80) if edu_raw else 0,
            "hib":    round(hib_raw / hib_max * 80) if hib_raw else 0,
            "future": b > now_h,
        })
    return out

BULAN_ID = ['', 'Jan','Feb','Mar','Apr','Mei','Jun',
            'Jul','Agu','Sep','Okt','Nov','Des']

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM HELPER
# ══════════════════════════════════════════════════════════════════════════════
import urllib.request, urllib.error
from urllib.parse import urlencode

# Token bot Telegram — TIDAK boleh di-hardcode (repo ini di-push ke GitHub).
# Sumber token, berurutan:
#   1) env var  TG_BOT_TOKEN
#   2) file lokal  dashboard/token_bot.txt  (di-.gitignore, tidak ikut commit)
# Kalau keduanya kosong → bot mati (notif & menu nonaktif) sampai diisi.
# Bot tetap "fixed" dari sisi pengguna: tak ada field token di dashboard.
def _muat_token_bot() -> str:
    tok = os.environ.get('TG_BOT_TOKEN', '').strip()
    if tok:
        return tok
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token_bot.txt')
    try:
        with open(p, encoding='utf-8') as f:
            for baris in f:
                baris = baris.strip()
                if baris and not baris.startswith('#'):
                    return baris
    except Exception:
        pass
    return ''

TG_BOT_TOKEN_TETAP = _muat_token_bot()

# ── Cache kredensial di memori ──────────────────────────────────────────────
# Tiap query() membuka koneksi MySQL baru + menjalankan SET time_zone. Poll-loop
# bot memanggil tg_aktif()/tg_credentials() berkali-kali tiap 25-35 detik; tanpa
# cache itu jadi ±7 koneksi DB per siklus walau tidak ada pesan masuk → bot
# terasa berat/lag. Cache TTL pendek (30 dtk) memangkasnya jadi nyaris nol.
# Disegarkan paksa begitu pengaturan Telegram disimpan (lihat set_cfg).
_tg_cred_cache = {'ts': 0.0, 'bot': '', 'chat': '', 'aktif': False}
_TG_CRED_TTL = 30  # detik

def _tg_cred_load():
    # Token TETAP (hardcode) — tidak dibaca dari DB. Env hanya untuk override.
    bot  = (os.environ.get('TG_BOT_TOKEN', '') or TG_BOT_TOKEN_TETAP).strip()
    chat = (get_cfg('telegram_chat_id', '') or
            os.environ.get('TG_CHAT_ID',  '')).strip()
    try:    flag = int(get_cfg('telegram_aktif', '1'))
    except Exception: flag = 1
    _tg_cred_cache.update(ts=time.time(), bot=bot, chat=chat,
                          aktif=bool(bot and chat and flag))
    return _tg_cred_cache

def _tg_cred():
    if time.time() - _tg_cred_cache['ts'] > _TG_CRED_TTL:
        _tg_cred_load()
    return _tg_cred_cache

def tg_credentials():
    """Return (bot_token, chat_id). DB konfigurasi → env var (di-cache 30 dtk)."""
    c = _tg_cred()
    return c['bot'], c['chat']

def tg_aktif():
    """Telegram aktif jika token+chat_id ada dan flag ON (dibaca dari cache)."""
    return _tg_cred()['aktif']

def tg_send_message(text: str, parse_mode: str = 'Markdown',
                    reply_markup: dict = None, override_chat=None) -> tuple:
    """Kirim pesan Telegram. Return (ok: bool, msg: str).
       msg adalah deskripsi error atau 'sent' saat sukses."""
    bot, chat = tg_credentials()
    chat = override_chat or chat
    if not bot:    return (False, "BOT_TOKEN belum diatur")
    if not chat:   return (False, "CHAT_ID belum diatur")

    payload = {'chat_id': chat, 'text': text, 'parse_mode': parse_mode}
    if reply_markup is not None:
        payload['reply_markup'] = json.dumps(reply_markup)

    url  = f'https://api.telegram.org/bot{bot}/sendMessage'
    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(url, data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            resp = json.loads(r.read().decode())
            if resp.get('ok'):
                # Catat last_test_at — jangan sampai error DB menutupi
                # fakta bahwa pesan SUDAH terkirim.
                try: set_cfg('telegram_last_ok', str(int(time.time())))
                except Exception: pass
                return (True, 'sent')
            return (False, resp.get('description', 'API menolak'))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            return (False, body.get('description', f'HTTP {e.code}'))
        except Exception:
            return (False, f'HTTP {e.code}: {e.reason}')
    except urllib.error.URLError as e:
        return (False, f'Tidak dapat menghubungi Telegram API: {e.reason}')
    except Exception as e:
        return (False, f'Gagal: {e}')

def tg_get_updates() -> list:
    """Panggil getUpdates untuk bantu user temukan CHAT_ID."""
    bot, _ = tg_credentials()
    if not bot: return []
    url = f'https://api.telegram.org/bot{bot}/getUpdates'
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode())
        if not data.get('ok'): return []
        chats = {}
        for upd in data.get('result', []):
            msg = upd.get('message') or upd.get('edited_message', {})
            chat = (msg or {}).get('chat') or {}
            cid  = chat.get('id')
            if cid and cid not in chats:
                chats[cid] = {
                    'id':       cid,
                    'nama':     (chat.get('first_name','') + ' ' +
                                 chat.get('last_name','')).strip() or chat.get('title',''),
                    'username': chat.get('username',''),
                    'tipe':     chat.get('type','private'),
                }
        return list(chats.values())
    except Exception:
        return []

# Wrapper friendly notif (panggil dari event handler dashboard)
def notif_telegram(kind: str, **kwargs):
    """Kirim notif Telegram sesuai jenis event. Silent-fail.
    Hanya 3 kejadian yang dinotifikasi:
      • 'blokir'     — anak membuka situs blacklist ATAU web baru yang
                       diklasifikasi AI router sebagai negatif.
      • 'minta_izin' — durasi/kuota anak habis dan anak meminta izin akses.
    """
    if not tg_aktif(): return False
    if kind == 'blokir':
        text = (
            f"🚫 *SITUS DIBLOKIR*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Domain     : `{kwargs.get('domain','')}`\n"
            f"📱 Perangkat  : {kwargs.get('perangkat','Tidak diketahui')}\n"
            f"📂 Kategori   : {kwargs.get('kategori','negatif').capitalize()}\n"
            f"🎯 Confidence : {float(kwargs.get('confidence',0)):.0f}%\n"
            f"⚙️ Alasan     : {kwargs.get('alasan','').replace('_',' ').title()}"
        )
    elif kind == 'minta_izin':
        text = (
            f"🙋 *PERMINTAAN IZIN AKSES*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Domain     : `{kwargs.get('domain','?')}`\n"
            f"📱 Perangkat  : {kwargs.get('perangkat','?')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_Buka dashboard untuk memberikan izin._"
        )
    else:
        return False
    ok, _ = tg_send_message(text)
    return ok

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT DUA ARAH — menu interaktif (long-polling getUpdates)
#   Menu: Riwayat Aktivitas · Konfigurasi Reward · Jadwal Istirahat · Sisa Kuota
#   Hanya merespon chat_id yang terdaftar (telegram_chat_id).
# ══════════════════════════════════════════════════════════════════════════════
def tg_api(method: str, payload: dict, timeout: int = 30):
    """POST generik ke Bot API. Return dict respons / None."""
    bot, _ = tg_credentials()
    if not bot: return None
    url = f'https://api.telegram.org/bot{bot}/{method}'
    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(url, data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def tg_edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {'chat_id': chat_id, 'message_id': message_id,
               'text': text, 'parse_mode': 'Markdown'}
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    return tg_api('editMessageText', payload)

def tg_answer_callback(cb_id, text=''):
    return tg_api('answerCallbackQuery', {'callback_query_id': cb_id, 'text': text})

def tg_set_commands():
    return tg_api('setMyCommands', {'commands': [
        {'command': 'start', 'description': 'Buka menu kontrol Edge Guard'},
    ]})

def primary_admin_id():
    """admin_id orang tua utama (single-parent) — dipakai bot tanpa sesi web."""
    try:
        row = query("SELECT admin_id FROM admin_orang_tua "
                    "ORDER BY admin_id LIMIT 1", one=True)
        return row['admin_id'] if row else 1
    except Exception:
        return 1

# ── Formatter konten laporan ────────────────────────────────────────────────
def bot_reward():
    durasi = int(get_cfg('durasi_belajar_menit', 30))
    bonus  = int(get_cfg('waktu_bonus_menit', 10))
    batas  = int(get_cfg('batas_bonus_menit', 60))
    return ("🎁 *KONFIGURASI REWARD*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 Durasi belajar   : *{durasi} menit*\n"
            "      _Lama akses edukasi untuk dapat bonus._\n\n"
            f"➕ Bonus per sesi    : *{bonus} menit*\n"
            "      _Waktu hiburan ekstra tiap selesai belajar._\n\n"
            f"🔒 Batas bonus/hari : *{batas} menit*\n"
            "      _Maksimum total bonus harian per anak._")

def bot_jadwal():
    rows = query(
        "SELECT j.hari, TIME_FORMAT(j.jam_mulai,'%%H:%%i') AS jm, "
        "       TIME_FORMAT(j.jam_selesai,'%%H:%%i') AS js, j.mode, "
        "       p.nama, p.device_name "
        "FROM jadwal_blokir j JOIN pengguna_anak p ON p.user_id = j.user_id "
        "WHERE p.admin_id=%s "
        "ORDER BY p.nama, j.jam_mulai, "
        "         FIELD(j.hari,'senin','selasa','rabu','kamis','jumat','sabtu','minggu')",
        (primary_admin_id(),)) or []
    if not rows:
        return ("🌙 *JADWAL ISTIRAHAT INTERNET*\n━━━━━━━━━━━━━━━━━━━━\n"
                "_Belum ada jadwal._")
    HARI = {'senin':'Sen','selasa':'Sel','rabu':'Rab','kamis':'Kam',
            'jumat':'Jum','sabtu':'Sab','minggu':'Min'}
    groups = {}
    for r in rows:
        key = (r['nama'], r['device_name'], r['jm'], r['js'], r['mode'])
        groups.setdefault(key, []).append(HARI.get(r['hari'], r['hari']))
    lines = ["🌙 *JADWAL ISTIRAHAT INTERNET*", "━━━━━━━━━━━━━━━━━━━━"]
    for (nama, devname, jm, js, mode), hari in groups.items():
        ikon = device_icon(devname)
        tag  = '⛔ Blokir' if mode == 'blokir' else '✅ Izinkan'
        lines.append(f"{ikon} *{nama}* — {tag}\n"
                     f"        🕐 `{jm}–{js}` · {', '.join(hari)}")
    return "\n".join(lines)

def bot_kuota():
    try: reset_kuota_jika_hari_baru()
    except Exception: pass
    rows = query(
        "SELECT nama, device_name, kuota_harian, kuota_terpakai, jeda "
        "FROM pengguna_anak WHERE admin_id=%s ORDER BY nama",
        (primary_admin_id(),)) or []
    if not rows:
        return ("⏳ *SISA KUOTA ANAK*\n━━━━━━━━━━━━━━━━━━━━\n"
                "_Belum ada perangkat._")
    lines = ["⏳ *SISA KUOTA ANAK — HARI INI*", "━━━━━━━━━━━━━━━━━━━━"]
    for r in rows:
        harian = int(r['kuota_harian'] or 0)
        pakai  = int(r['kuota_terpakai'] or 0)
        sisa   = max(0, harian - pakai)
        pct    = round(pakai / harian * 100) if harian else 0
        filled = min(10, round(pct / 10))
        bar    = '▰' * filled + '▱' * (10 - filled)
        ikon   = device_icon(r['device_name'])
        status = ' ⏸_dijeda_' if r['jeda'] else ''
        lines.append(f"{ikon} *{r['nama']}*{status}\n"
                     f"        {bar} {pct}%\n"
                     f"        Sisa *{fmt(sisa)}* / {fmt(harian)}")
    return "\n".join(lines)

def bot_laporan():
    """Laporan lengkap dalam SATU pesan (tanpa menu/tombol):
    konfigurasi reward → jadwal internet anak → sisa kuota."""
    return (bot_reward() + "\n\n"
            + bot_jadwal() + "\n\n"
            + bot_kuota())

# ── Router update ────────────────────────────────────────────────────────────
def tg_handle_update(upd):
    _, chat_conf = tg_credentials()
    chat_conf = str(chat_conf) if chat_conf else ''

    # 1) Tombol inline lama (dari pesan menu versi sebelumnya) → tetap tanggapi
    #    dengan menampilkan laporan, lalu copot tombolnya.
    cb = upd.get('callback_query')
    if cb:
        msg = cb.get('message') or {}
        cid = str((msg.get('chat') or {}).get('id', ''))
        mid = msg.get('message_id')
        if chat_conf and cid != chat_conf:
            tg_answer_callback(cb.get('id', ''), 'Akses tidak diizinkan.')
            return
        threading.Thread(target=tg_answer_callback, args=(cb.get('id', ''),),
                         daemon=True).start()
        tg_edit_message(cid, mid, "⏳ _Memuat…_", {'inline_keyboard': []})
        tg_edit_message(cid, mid, bot_laporan(), {'inline_keyboard': []})
        return

    # 2) Pesan teks / command
    msg = upd.get('message') or upd.get('edited_message')
    if not msg: return
    cid  = str((msg.get('chat') or {}).get('id', ''))
    text = (msg.get('text') or '').strip().lower()
    if chat_conf and cid != chat_conf:
        return  # abaikan orang asing

    # /start → langsung tampilkan laporan (reward + jadwal + kuota), tanpa menu.
    if text == '/start':
        tg_send_message(bot_laporan(), override_chat=cid)
    else:
        tg_send_message("Ketik */start* untuk melihat status kontrol Edge Guard. 🛡️",
                        override_chat=cid)

# ── Long-poll loop (daemon thread) ────────────────────────────────────────────
# Lama long-poll di sisi Telegram (detik). Server menahan koneksi hingga ada
# update → balas seketika. Nilai besar = lebih sedikit "celah" antar-request,
# jadi /start nyaris tak pernah ketinggalan. urlopen diberi margin +10 dtk.
_TG_POLL_TIMEOUT = 50

def tg_long_poll(offset):
    """Ambil update via getUpdates. Pakai urlopen langsung (bukan tg_api) supaya
    bisa MELIHAT error — terutama 409 Conflict yang artinya ada poller/instance
    lain memakai token yang sama (penyebab paling umum bot terasa lag puluhan
    detik). Kembalikan list update; sleep singkat saat error agar tak hammer."""
    bot, _ = tg_credentials()
    if not bot: return []
    url     = f'https://api.telegram.org/bot{bot}/getUpdates'
    payload = {'offset': offset, 'timeout': _TG_POLL_TIMEOUT,
               'allowed_updates': ['message', 'callback_query']}
    data    = json.dumps(payload).encode('utf-8')
    req     = urllib.request.Request(url, data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=_TG_POLL_TIMEOUT + 10) as r:
            resp = json.loads(r.read().decode())
        return resp.get('result', []) if resp.get('ok') else []
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("[Bot Telegram] ⚠️  409 CONFLICT — ada poller/instance LAIN "
                  "memakai bot token yang sama (proses lama belum mati, atau "
                  "webhook aktif). Update terlambat sampai poller lain berhenti. "
                  "Pastikan HANYA SATU yang berjalan.")
            time.sleep(3)
        else:
            print(f"[Bot Telegram] getUpdates HTTP {e.code}: {e.reason}")
            time.sleep(2)
        return []
    except Exception as e:
        print(f"[Bot Telegram] getUpdates err: {e}")
        time.sleep(2)
        return []

_tg_poll_started = False
_tg_lock_fh      = None   # pegang file-lock single-instance seumur proses

def _tg_acquire_lock():
    """Advisory file-lock agar HANYA satu proses (di host ini) yang polling.
    Mencegah dua instance dashboard saling mencuri update (409). Proses yang
    crash otomatis melepas lock (flock terikat ke proses). Platform tanpa
    fcntl (mis. Windows) → lewati guard (anggap single-instance)."""
    global _tg_lock_fh
    try:
        import fcntl
    except Exception:
        return True
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '.tg_poller.lock')
        _tg_lock_fh = open(path, 'w')
        fcntl.flock(_tg_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (OSError, IOError):
        try: _tg_lock_fh.close()
        except Exception: pass
        _tg_lock_fh = None
        return False

def tg_poll_loop():
    try:    offset = int(get_cfg('telegram_update_offset', '0') or 0)
    except Exception: offset = 0
    # Hapus webhook kalau ada — webhook & getUpdates tak bisa bersamaan (409).
    try: tg_api('deleteWebhook', {'drop_pending_updates': False})
    except Exception: pass
    try: tg_set_commands()
    except Exception: pass
    print(f"[Bot Telegram] long-polling dimulai (timeout {_TG_POLL_TIMEOUT}s)…")
    while True:
        try:
            if not tg_aktif():
                time.sleep(5); continue
            updates = tg_long_poll(offset)
            for upd in updates:
                offset = max(offset, int(upd.get('update_id', 0)) + 1)
                try: tg_handle_update(upd)
                except Exception as e:
                    print(f"[Bot Telegram] handle error: {e}")
            if updates:
                try: set_cfg('telegram_update_offset', str(offset))
                except Exception: pass
        except Exception as e:
            print(f"[Bot Telegram] loop error: {e}")
            time.sleep(3)

def mulai_bot_telegram():
    """Start thread polling sekali saja — dijaga file-lock single-instance."""
    global _tg_poll_started
    if _tg_poll_started: return
    if not _tg_acquire_lock():
        print("[Bot Telegram] ⏭  Poller lain sudah aktif di host ini (lock) — "
              "tidak start poller kedua untuk hindari 409 Conflict.")
        _tg_poll_started = True   # jangan coba-coba lagi di proses ini
        return
    _tg_poll_started = True
    threading.Thread(target=tg_poll_loop, name='tg-poll', daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# DEVICE ICON — pilih emoji berdasarkan device_name
# ══════════════════════════════════════════════════════════════════════════════
def device_icon(device_name: str) -> str:
    """Map device_name → emoji ikon.
       💻 Laptop  · 📟 Tablet  · 📱 Ponsel  · 🎮 Konsol  · 📺 TV  · 🖥 Default."""
    n = (device_name or '').lower()
    if not n: return '📱'
    # Konsol / Game (cek dulu sebelum 'pro' agar PS Pro tidak nyangkut ke laptop)
    if any(k in n for k in ('playstation','ps5','ps4','ps3','xbox',
                            'nintendo','switch','konsol','steam deck')):
        return '🎮'
    # TV
    if any(k in n for k in ('smart tv','android tv','chromecast','tv ',
                            'tv-','tv:','televisi','roku','firestick','apple tv')):
        return '📺'
    # Laptop / PC
    if any(k in n for k in ('macbook','laptop','notebook','pc ','desktop',
                            'windows','imac','surface','chromebook','thinkpad',
                            'inspiron','vivobook','zenbook')):
        return '💻'
    # Tablet
    if any(k in n for k in ('ipad','tablet','tab ','tab-','galaxy tab',
                            'mi pad','redmi pad','huawei matepad')):
        return '📟'
    # Ponsel / HP (default mobile)
    if any(k in n for k in ('iphone','samsung galaxy','galaxy s','galaxy a',
                            'galaxy m','galaxy z','xiaomi','redmi','poco',
                            'oppo','vivo','realme','infinix','tecno',
                            'pixel','huawei','honor','asus rog','rog phone',
                            'ponsel','hp ','phone')):
        return '📱'
    return '📱'   # default ke ponsel

def format_waktu_ramah(dt):
    """Format datetime jadi: '14:20' (hari ini), 'Kemarin 19:30', '23 Mei 14:20'."""
    if not isinstance(dt, datetime):
        return ''
    today     = now_lokal().date()
    yesterday = today - timedelta(days=1)
    hm = dt.strftime('%H:%M')
    if dt.date() == today:      return f'Hari ini {hm}'
    if dt.date() == yesterday:  return f'Kemarin {hm}'
    return f'{dt.day} {BULAN_ID[dt.month]} {hm}'

def normalize_log(row):
    """Adaptor agar template lama tetap baca .kategori_nama/.perangkat/.status/.waktu/.domain."""
    r = dict(row)
    # kompatibilitas
    r['kategori_nama'] = r.get('kategori', 'unknown')
    r['perangkat']     = r.get('perangkat_nama', '')
    r['status']        = 'diblokir' if r.get('aksi') == 'blokir' else 'diizinkan'
    r['domain']        = r.get('domain_url', '')
    if 'waktu_akses' in r and isinstance(r['waktu_akses'], datetime):
        r['waktu_str']    = format_waktu_ramah(r['waktu_akses'])
        r['waktu']        = r['waktu_akses'].strftime('%H:%M')
    return r

def login_required(f):
    """Validasi sesi: user_id + token cookie cocok dengan DB."""
    @wraps(f)
    def d(*a, **k):
        uid = session.get('user_id')
        tok = session.get('token')
        if not uid or not tok:
            return redirect(url_for('login'))
        try:
            row = query("SELECT session_token, session_expired_at "
                        "FROM admin_orang_tua WHERE admin_id=%s",
                        (uid,), one=True)
        except Exception:
            row = None
        if (not row
                or row.get('session_token') != tok
                or (row.get('session_expired_at')
                    and row['session_expired_at'] < now_lokal_naive())):
            session.clear()
            return redirect(url_for('login'))
        return f(*a, **k)
    return d

def client_ip():
    return (request.headers.get('X-Forwarded-For', request.remote_addr) or '').split(',')[0].strip()

def current_admin_id():
    return session.get('user_id') or 1

# ══════════════════════════════════════════════════════════════════════════════
# AUTH — LOGIN dengan LOCKOUT
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('beranda'))

    err = None; sisa_percobaan = None; lock_detik = 0
    max_gagal = int(get_cfg('login_max_gagal', '3'))
    lock_dur  = int(get_cfg('login_lockout_detik', '300'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().lower()
        if not username:
            return render_template('halaman_login.html',
                err='Username dan password wajib diisi.',
                sisa_percobaan=None, lock_detik=0)
        pw       = request.form.get('password', '')
        ip       = client_ip()
        ua       = (request.headers.get('User-Agent','') or '')[:255]

        # Cari user: cocokkan dengan email, atau prefix email = username
        user = query(
            "SELECT * FROM admin_orang_tua "
            "WHERE LOWER(email) = %s "
            "   OR LOWER(SUBSTRING_INDEX(email,'@',1)) = %s "
            "LIMIT 1",
            (username, username), one=True)
        ok = False

        if user:
            if user.get('locked_until') and user['locked_until'] > now_lokal_naive():
                lock_detik = int((user['locked_until'] - now_lokal_naive()).total_seconds())
                err = f'Akun terkunci. Coba lagi dalam {lock_detik} detik.'
            else:
                if user.get('locked_until'):
                    query("UPDATE admin_orang_tua SET locked_until=NULL, gagal_login=0 "
                          "WHERE admin_id=%s", (user['admin_id'],))
                    user['gagal_login']  = 0
                    user['locked_until'] = None
                ok = verify_password(pw, user['password_hash'])

        if ok and user:
            token = secrets.token_hex(32)
            query("UPDATE admin_orang_tua SET "
                  "  gagal_login=0, locked_until=NULL, "
                  "  last_login_at=NOW(), last_login_ip=%s, "
                  "  session_token=%s, session_expired_at = NOW() + INTERVAL 8 HOUR, "
                  "  session_ip=%s, session_user_agent=%s "
                  "WHERE admin_id=%s",
                  (ip, token, ip, ua, user['admin_id']))
            session.permanent  = True
            session['user_id'] = user['admin_id']
            session['username']= user['email']
            session['token']   = token
            return redirect(url_for('beranda'))

        if user and err is None:
            gagal = (user.get('gagal_login') or 0) + 1
            if gagal >= max_gagal:
                lock_until = now_lokal_naive() + timedelta(seconds=lock_dur)
                query("UPDATE admin_orang_tua SET gagal_login=%s, locked_until=%s, "
                      "last_gagal_at=NOW(), last_gagal_ip=%s WHERE admin_id=%s",
                      (gagal, lock_until, ip, user['admin_id']))
                lock_detik = lock_dur
                err = f'Password salah {gagal}x. Akun dikunci {lock_dur} detik.'
            else:
                query("UPDATE admin_orang_tua SET gagal_login=%s, last_gagal_at=NOW(), "
                      "last_gagal_ip=%s WHERE admin_id=%s",
                      (gagal, ip, user['admin_id']))
                sisa_percobaan = max_gagal - gagal
                err = f'Password salah. Sisa percobaan: {sisa_percobaan}.'
        elif err is None:
            err = 'Username atau password salah.'

    return render_template('halaman_login.html', err=err,
                           sisa_percobaan=sisa_percobaan,
                           lock_detik=lock_detik)

@app.route('/logout')
def logout():
    uid = session.get('user_id')
    if uid:
        query("UPDATE admin_orang_tua SET session_token=NULL, session_expired_at=NULL "
              "WHERE admin_id=%s", (uid,))
    session.clear()
    return redirect(url_for('login'))

# ══════════════════════════════════════════════════════════════════════════════
# BERANDA
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
@login_required
def beranda():
    reset_kuota_jika_hari_baru()
    refresh_status_online()

    devs = query(
        "SELECT p.*, "
        "  COALESCE(s.total_akses, 0)  AS _log_count, "
        "  COALESCE(s.total_blokir, 0) AS _blokir_count "
        "FROM pengguna_anak p "
        "LEFT JOIN v_statistik s ON s.user_id = p.user_id "
        "WHERE p.admin_id = %s "
        "ORDER BY p.nama", (current_admin_id(),)) or []
    for d in devs:
        d['jeda']   = bool(d.get('jeda', 0))
        d['id']     = d['user_id']                              # alias template lama
        d['mac']    = d.get('mac_address', '')
        d['label']  = d['nama']                                 # nama anak (utama)
        d['model']  = d.get('device_name') or 'Tidak diketahui' # jenis perangkat (sub)
        d['ikon']   = device_icon(d.get('device_name'))          # emoji sesuai jenis
        d['status'] = 'online' if d.get('status_aktif') else 'offline'

    total_harian   = sum(int(d.get('kuota_harian',  120)) for d in devs)
    total_terpakai = sum(int(d.get('kuota_terpakai', 0))  for d in devs)
    total_sisa     = max(0, total_harian - total_terpakai)
    pct_global     = round(total_terpakai / total_harian * 100) if total_harian else 0

    circ = round(2 * math.pi * 54, 2)
    dash = round((1 - pct_global / 100) * circ, 2)

    # Riwayat 5 terbaru — JOIN ke pengguna_anak (nama live)
    # HANYA HARI INI agar konsisten dengan proporsi & kuota.
    # Log kemarin lihat di halaman /riwayat (yang punya pagination).
    rows = query(
        "SELECT l.domain_url, l.kategori, l.aksi, l.waktu_akses, l.mac, "
        "       COALESCE(p.nama, l.perangkat_nama) AS perangkat_nama "
        "FROM log_akses l "
        "LEFT JOIN pengguna_anak p ON p.user_id = l.user_id "
        "WHERE DATE(l.waktu_akses) = CURDATE() "
        "ORDER BY l.waktu_akses DESC LIMIT 5") or []
    riwayat = [normalize_log(r) for r in rows]

    # Proporsi: log HARI INI
    logs_today = query(
        "SELECT kategori FROM log_akses "
        "WHERE DATE(waktu_akses) = CURDATE()") or []
    pe, ph, pn    = proporsi_dari_logs(logs_today)
    prop_total    = pe + ph + pn
    prop_dash_edu = round(pe / 100 * 251.33, 1) if prop_total else 0
    pv            = devs[0] if devs else {}

    return render_template('dashboard.html',
        pv=pv,
        perangkat_list=[dict(d) for d in devs],
        nama_anak="Semua Perangkat",
        kS=fmt(total_sisa), kT=fmt(total_harian),
        kS_raw=total_sisa,  kT_raw=total_harian,
        pct=pct_global, circ=circ, dash=dash,
        jml_perangkat=len(devs),
        pct_edu=pe, pct_hib=ph, pct_neg=pn,
        prop_total=prop_total,
        prop_dash_edu=prop_dash_edu,
        riwayat=riwayat,
        jeda_aktif=bool(pv.get('jeda', 0)))

# ══════════════════════════════════════════════════════════════════════════════
# JEDA TOGGLE
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/jeda-toggle', methods=['POST'])
@login_required
def jeda_toggle():
    data   = request.get_json(silent=True) or {}
    dev_id = data.get('dev_id')

    if not dev_id:
        devs = query("SELECT user_id AS id, nama, jeda FROM pengguna_anak "
                     "WHERE admin_id=%s", (current_admin_id(),)) or []
        if not devs:
            return jsonify({"status":"error","code":"no_devices",
                            "msg":"Belum ada perangkat anak — "
                                  "tambahkan dulu di menu Kelola Perangkat."}), 404
        any_active = any(not d['jeda'] for d in devs)
        query("UPDATE pengguna_anak SET jeda=%s WHERE admin_id=%s",
              (int(any_active), current_admin_id()))
        devs_after = query("SELECT user_id AS id, nama, jeda FROM pengguna_anak "
                           "WHERE admin_id=%s", (current_admin_id(),)) or []
        return jsonify({
            "status":"ok", "code":"ok",
            "msg":("Semua perangkat dijeda." if any_active
                   else "Semua perangkat dilanjutkan."),
            "jeda":any_active, "mode":"all",
            "perangkat":[{"id":d['id'],"jeda":bool(d['jeda']),"nama":d['nama']}
                         for d in devs_after]
        })

    dev = query("SELECT user_id AS id, nama, jeda FROM pengguna_anak "
                "WHERE user_id=%s AND admin_id=%s",
                (dev_id, current_admin_id()), one=True)
    if not dev:
        return jsonify({"status":"error","code":"dev_not_found",
                        "msg":"Perangkat tidak ditemukan."}), 404
    new_jeda = not bool(dev['jeda'])
    query("UPDATE pengguna_anak SET jeda=%s WHERE user_id=%s",
          (int(new_jeda), dev_id))
    return jsonify({
        "status":"ok", "code":"ok",
        "msg":(f"{dev['nama']} dijeda." if new_jeda
               else f"{dev['nama']} dilanjutkan."),
        "jeda":new_jeda, "mode":"single",
        "nama":dev['nama'], "id":dev_id
    })

# ══════════════════════════════════════════════════════════════════════════════
# TAMBAH WAKTU
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/atur-waktu', methods=['POST'])
@app.route('/api/tambah-waktu', methods=['POST'])           # alias backward-compat
@login_required
def api_atur_waktu():
    """Atur kuota internet harian.
    Body: {dev_id: 'all'|<int>, menit: int, mode: 'tambah'|'kurang'}
      • tambah: kasih anak waktu ekstra → kuota_terpakai berkurang
      • kurang: cabut waktu anak       → kuota_terpakai bertambah
    """
    data   = request.get_json(silent=True) or {}
    dev_id = data.get('dev_id', 'all')
    mode   = (data.get('mode') or 'tambah').lower()

    # ── Validasi parameter ──────────────────────────────────────────────
    try:
        menit = int(data.get('menit', 30))
    except (TypeError, ValueError):
        return jsonify({"status":"error","code":"menit_invalid",
                        "msg":"Durasi harus berupa angka."}), 400

    if menit < 1:
        return jsonify({"status":"error","code":"menit_terlalu_kecil",
                        "msg":"Durasi minimum 1 menit."}), 400
    if menit > 240:
        return jsonify({"status":"error","code":"menit_terlalu_besar",
                        "msg":"Durasi maksimum 240 menit (4 jam) per sekali atur."}), 400
    if mode not in ('tambah', 'kurang'):
        return jsonify({"status":"error","code":"mode_invalid",
                        "msg":"Mode harus 'tambah' atau 'kurang'."}), 400

    # ── Ambil target perangkat ──────────────────────────────────────────
    if dev_id == 'all':
        target_devs = query(
            "SELECT user_id AS id, nama, kuota_terpakai, kuota_harian "
            "FROM pengguna_anak WHERE admin_id=%s", (current_admin_id(),)) or []
        if not target_devs:
            return jsonify({"status":"error","code":"no_devices",
                            "msg":"Belum ada perangkat anak terdaftar."}), 404
    else:
        try: dev_id = int(dev_id)
        except (TypeError, ValueError):
            return jsonify({"status":"error","code":"dev_id_invalid",
                            "msg":"ID perangkat tidak valid."}), 400
        target = query(
            "SELECT user_id AS id, nama, kuota_terpakai, kuota_harian "
            "FROM pengguna_anak WHERE user_id=%s AND admin_id=%s",
            (dev_id, current_admin_id()), one=True)
        if not target:
            return jsonify({"status":"error","code":"dev_not_found",
                            "msg":"Perangkat tidak ditemukan atau bukan milik Anda."}), 404
        target_devs = [target]

    # ── Pre-validasi mode kurang (cek sisa kuota minimum di antara target) ──
    if mode == 'kurang':
        sisa_min = min(max(0, int(d['kuota_harian']) - int(d['kuota_terpakai']))
                       for d in target_devs)
        if sisa_min <= 0:
            return jsonify({
                "status":"error","code":"sudah_habis",
                "msg":"Kuota sudah habis — tidak ada lagi yang bisa dikurangi."}), 400
        if menit > sisa_min:
            nm = (target_devs[0]['nama'] if len(target_devs) == 1
                  else 'salah satu perangkat')
            return jsonify({
                "status":"error","code":"melebihi_sisa",
                "msg":f"Tidak bisa kurangi {menit} menit — sisa kuota {nm} "
                      f"hanya {sisa_min} menit. Coba kurangi nilainya."}), 400

    if mode == 'tambah':
        # Jika SEMUA target sudah kuota_terpakai=0 → info, bukan error
        all_full = all(int(d['kuota_terpakai']) == 0 for d in target_devs)
        if all_full:
            return jsonify({
                "status":"info","code":"sudah_penuh",
                "msg":"Kuota semua perangkat target sudah penuh — "
                      "tidak ada yang ditambah."}), 200

    # ── Eksekusi UPDATE ────────────────────────────────────────────────
    if mode == 'tambah':
        # kuota_terpakai -= menit (clamp ke 0)
        sql_set = "kuota_terpakai = GREATEST(0, kuota_terpakai - %s)"
    else:  # kurang
        # kuota_terpakai += menit (clamp ke kuota_harian)
        sql_set = "kuota_terpakai = LEAST(kuota_harian, kuota_terpakai + %s)"

    if dev_id == 'all':
        query(f"UPDATE pengguna_anak SET {sql_set} WHERE admin_id=%s",
              (menit, current_admin_id()))
    else:
        query(f"UPDATE pengguna_anak SET {sql_set} "
              f"WHERE user_id=%s AND admin_id=%s",
              (menit, dev_id, current_admin_id()))

    # ── Ambil snapshot semua perangkat untuk respon UI ─────────────────
    devs = query("SELECT user_id AS id, nama, kuota_terpakai, kuota_harian "
                 "FROM pengguna_anak WHERE admin_id=%s",
                 (current_admin_id(),)) or []
    if dev_id == 'all':
        updated = [d['nama'] for d in devs]
    else:
        updated = [d['nama'] for d in devs if d['id'] == dev_id]

    total_harian   = sum(int(d['kuota_harian'])   for d in devs)
    total_terpakai = sum(int(d['kuota_terpakai']) for d in devs)
    total_sisa     = max(0, total_harian - total_terpakai)
    pct            = round(total_terpakai / total_harian * 100) if total_harian else 0
    circ           = round(2 * math.pi * 54, 2)
    dash           = round((1 - pct / 100) * circ, 2)

    aksi_lbl  = 'Menambahkan' if mode == 'tambah' else 'Mengurangi'
    who_lbl   = 'semua perangkat' if len(updated) > 1 else (updated[0] if updated else '?')

    return jsonify({
        "status":"ok", "code":"ok",
        "msg":f"{aksi_lbl} {menit} menit untuk {who_lbl}.",
        "mode":mode, "menit":menit, "updated":updated,
        "kuota_sisa":fmt(total_sisa), "kuota_sisa_raw":total_sisa,
        "kuota_total":fmt(total_harian),
        "pct":pct, "dash":dash, "circ":circ,
        "perangkat":[{
            "id":d['id'], "nama":d['nama'],
            "kuota_terpakai":int(d['kuota_terpakai']),
            "kuota_harian":  int(d['kuota_harian']),
            "pct":round(int(d['kuota_terpakai'])/int(d['kuota_harian'])*100)
                  if d['kuota_harian'] else 0
        } for d in devs]
    })

# ══════════════════════════════════════════════════════════════════════════════
# PROPORSI (AJAX)
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/proporsi')
@login_required
def api_proporsi():
    nama = request.args.get('nama', '')
    # Riwayat 10 terbaru — HANYA HARI INI agar konsisten dengan proporsi
    sql  = ("SELECT l.domain_url, l.kategori, l.aksi, l.waktu_akses, "
            "       COALESCE(p.nama, l.perangkat_nama) AS perangkat_nama "
            "FROM log_akses l "
            "LEFT JOIN pengguna_anak p ON p.user_id = l.user_id "
            "WHERE DATE(l.waktu_akses) = CURDATE()")
    args = ()
    if nama:
        sql  += " AND COALESCE(p.nama, l.perangkat_nama) = %s"
        args  = (nama,)
    sql += " ORDER BY l.waktu_akses DESC LIMIT 10"
    rows = [normalize_log(r) for r in (query(sql, args) or [])]

    sql2 = ("SELECT l.kategori FROM log_akses l "
            "LEFT JOIN pengguna_anak p ON p.user_id = l.user_id "
            "WHERE DATE(l.waktu_akses)=CURDATE()")
    args2 = ()
    if nama:
        sql2  += " AND COALESCE(p.nama, l.perangkat_nama) = %s"
        args2  = (nama,)
    logs_today = query(sql2, args2) or []
    pe, ph, pn = proporsi_dari_logs(logs_today)
    prop_total = pe + ph + pn
    return jsonify({
        "pct_edu":pe, "pct_hib":ph, "pct_neg":pn,
        "prop_total":prop_total,
        "prop_dash_edu":round(pe/100*251.33, 1) if prop_total else 0,
        "riwayat":rows
    })

# ══════════════════════════════════════════════════════════════════════════════
# RIWAYAT DETAIL
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/riwayat')
@login_required
def riwayat_detail():
    nama = request.args.get('nama', '')
    kat  = request.args.get('kat',  'all')
    page = max(1, int(request.args.get('page', 1)))
    per  = 20

    conds, args = [], []
    if nama:
        conds.append("COALESCE(p.nama, l.perangkat_nama) = %s"); args.append(nama)
    if   kat == 'edukasi': conds.append("l.kategori = 'edukasi'")
    elif kat == 'hiburan': conds.append("l.kategori = 'hiburan'")
    elif kat == 'negatif': conds.append("l.aksi = 'blokir'")

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    total = query(
        f"SELECT COUNT(*) AS n FROM log_akses l "
        f"LEFT JOIN pengguna_anak p ON p.user_id = l.user_id {where}",
        args, one=True)['n']
    rows  = query(
        f"SELECT l.domain_url, l.kategori, l.aksi, l.waktu_akses, l.mac, "
        f"       COALESCE(p.nama, l.perangkat_nama) AS perangkat_nama "
        f"FROM log_akses l "
        f"LEFT JOIN pengguna_anak p ON p.user_id = l.user_id "
        f"{where} ORDER BY l.waktu_akses DESC LIMIT %s OFFSET %s",
        args + [per, (page - 1) * per]) or []
    items = [normalize_log(r) for r in rows]
    devs  = query("SELECT nama FROM pengguna_anak WHERE admin_id=%s ORDER BY nama",
                  (current_admin_id(),)) or []

    return render_template('riwayat_detail.html',
        riwayat=items, total=total, page=page,
        per=per, kat=kat, nama=nama,
        total_pages=max(1, math.ceil(total / per)),
        perangkat_list=list(devs))

# ══════════════════════════════════════════════════════════════════════════════
# JADWAL — konfigurasi reward + JADWAL_BLOKIR (per anak, per hari, jam)
# ══════════════════════════════════════════════════════════════════════════════
HARI_LIST    = ['senin','selasa','rabu','kamis','jumat','sabtu','minggu']
HARI_LABEL   = {'senin':'Sen','selasa':'Sel','rabu':'Rab','kamis':'Kam',
                'jumat':'Jum','sabtu':'Sab','minggu':'Min'}
HARI_LABEL_FULL = {'senin':'Senin','selasa':'Selasa','rabu':'Rabu',
                   'kamis':'Kamis','jumat':"Jum'at",'sabtu':'Sabtu','minggu':'Minggu'}

@app.route('/jadwal', methods=['GET','POST'])
@login_required
def jadwal():
    if request.method == 'POST':
        set_cfg('durasi_belajar_menit', request.form.get('durasi_belajar', 30))
        set_cfg('waktu_bonus_menit',    request.form.get('waktu_bonus', 10))
        set_cfg('batas_bonus_menit',    request.form.get('batas_bonus', 60))
        flash('Konfigurasi penjadwalan disimpan!', 'success')
        return redirect(url_for('jadwal'))

    cfg = {
        'durasi_belajar_menit':     int(get_cfg('durasi_belajar_menit', 30)),
        'waktu_bonus_menit':        int(get_cfg('waktu_bonus_menit', 10)),
        'batas_bonus_harian_menit': int(get_cfg('batas_bonus_menit', 60)),
    }

    # ── Ambil daftar perangkat & jadwal_blokir ──────────────────────────
    perangkat = query(
        "SELECT user_id AS id, nama, device_name "
        "FROM pengguna_anak WHERE admin_id=%s ORDER BY nama",
        (current_admin_id(),)) or []

    jadwal_rows = query(
        "SELECT j.jadwal_id AS id, j.user_id, j.hari, "
        "       TIME_FORMAT(j.jam_mulai,   '%%H:%%i') AS jam_mulai, "
        "       TIME_FORMAT(j.jam_selesai, '%%H:%%i') AS jam_selesai, "
        "       j.mode, p.nama AS perangkat_nama, p.device_name "
        "FROM jadwal_blokir j "
        "JOIN pengguna_anak p ON p.user_id = j.user_id "
        "WHERE p.admin_id=%s "
        "ORDER BY p.nama, j.jam_mulai, "
        "         FIELD(j.hari,'senin','selasa','rabu','kamis',"
        "                      'jumat','sabtu','minggu')",
        (current_admin_id(),)) or []

    # Group by (user_id, jam_mulai, jam_selesai, mode) → 1 baris per group,
    # kumpulkan hari sebagai list & ids untuk delete bulk.
    groups = {}
    for r in jadwal_rows:
        key = (r['user_id'], r['jam_mulai'], r['jam_selesai'], r['mode'])
        g   = groups.setdefault(key, {
            'user_id':    r['user_id'],
            'nama':       r['perangkat_nama'],
            'device_name': r['device_name'],
            'ikon':       device_icon(r.get('device_name')),
            'jam_mulai':  r['jam_mulai'],
            'jam_selesai':r['jam_selesai'],
            'mode':       r['mode'],
            'hari':       [],
            'hari_label': [],
            'ids':        [],
        })
        g['hari'].append(r['hari'])
        g['hari_label'].append(HARI_LABEL.get(r['hari'], r['hari']))
        g['ids'].append(str(r['id']))

    jadwal_grup = list(groups.values())

    return render_template('jadwal_akses.html',
        cfg=cfg,
        perangkat_list=list(perangkat),
        jadwal_grup=jadwal_grup,
        total_jadwal=len(jadwal_rows),
        hari_list=HARI_LIST,
        hari_label=HARI_LABEL,
        hari_label_full=HARI_LABEL_FULL)

# ── Tambah jadwal_blokir (boleh multi-hari sekaligus) ──────────────────
@app.route('/jadwal/blokir/tambah', methods=['POST'])
@login_required
def jadwal_blokir_tambah():
    try:
        user_id = int(request.form.get('user_id', 0))
    except (TypeError, ValueError):
        flash('Pilih perangkat terlebih dulu.', 'error')
        return redirect(url_for('jadwal'))

    # Cek perangkat milik admin
    dev = query("SELECT user_id, nama FROM pengguna_anak "
                "WHERE user_id=%s AND admin_id=%s",
                (user_id, current_admin_id()), one=True)
    if not dev:
        flash('Perangkat tidak valid atau bukan milik Anda.', 'error')
        return redirect(url_for('jadwal'))

    hari_arr   = request.form.getlist('hari')          # list dari checkboxes
    jam_mulai  = (request.form.get('jam_mulai')   or '').strip()
    jam_selesai= (request.form.get('jam_selesai') or '').strip()
    mode       = request.form.get('mode', 'blokir')

    # Validasi
    if not hari_arr:
        flash('Pilih minimal 1 hari.', 'error')
        return redirect(url_for('jadwal'))
    if mode not in ('blokir', 'izinkan'):
        mode = 'blokir'
    if not re.match(r'^\d{2}:\d{2}$', jam_mulai) or \
       not re.match(r'^\d{2}:\d{2}$', jam_selesai):
        flash('Format jam tidak valid (HH:MM).', 'error')
        return redirect(url_for('jadwal'))
    if jam_mulai == jam_selesai:
        flash('Jam mulai dan selesai tidak boleh sama.', 'error')
        return redirect(url_for('jadwal'))

    inserted = 0
    skipped  = []
    for h in hari_arr:
        if h not in HARI_LIST:
            continue
        # Cek bentrok jam yang sama di hari yang sama (anti duplikat persis)
        dup = query("SELECT jadwal_id FROM jadwal_blokir "
                    "WHERE user_id=%s AND hari=%s "
                    "  AND jam_mulai=%s AND jam_selesai=%s AND mode=%s",
                    (user_id, h, jam_mulai, jam_selesai, mode), one=True)
        if dup:
            skipped.append(HARI_LABEL_FULL[h])
            continue
        query("INSERT INTO jadwal_blokir "
              "(user_id, hari, jam_mulai, jam_selesai, mode) "
              "VALUES (%s,%s,%s,%s,%s)",
              (user_id, h, jam_mulai, jam_selesai, mode))
        inserted += 1

    if inserted:
        flash(f'{inserted} jadwal {mode} ditambahkan untuk {dev["nama"]}.',
              'success')
    if skipped:
        flash(f'Jadwal sama sudah ada di hari: {", ".join(skipped)}.', 'info')
    if not inserted and not skipped:
        flash('Tidak ada jadwal yang ditambahkan.', 'error')
    return redirect(url_for('jadwal'))

@app.route('/jadwal/blokir/hapus/<int:jid>', methods=['POST'])
@login_required
def jadwal_blokir_hapus(jid):
    row = query(
        "SELECT j.jadwal_id, j.hari, p.nama "
        "FROM jadwal_blokir j "
        "JOIN pengguna_anak p ON p.user_id = j.user_id "
        "WHERE j.jadwal_id=%s AND p.admin_id=%s",
        (jid, current_admin_id()), one=True)
    if not row:
        flash('Jadwal tidak ditemukan.', 'error')
        return redirect(url_for('jadwal'))
    query("DELETE FROM jadwal_blokir WHERE jadwal_id=%s", (jid,))
    flash(f'Jadwal hari {HARI_LABEL_FULL.get(row["hari"], row["hari"])} '
          f'untuk {row["nama"]} dihapus.', 'success')
    return redirect(url_for('jadwal'))

@app.route('/jadwal/blokir/hapus-grup', methods=['POST'])
@login_required
def jadwal_blokir_hapus_grup():
    """Hapus sekelompok jadwal (semua hari pada (anak, jam, mode) yang sama)."""
    raw_ids = request.form.get('ids', '')
    try:
        ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
    except Exception:
        ids = []
    if not ids:
        flash('Tidak ada jadwal untuk dihapus.', 'error')
        return redirect(url_for('jadwal'))
    # Ambil info untuk pesan & cek kepemilikan
    placeholders = ','.join(['%s'] * len(ids))
    rows = query(
        f"SELECT j.jadwal_id, j.hari, p.nama, "
        f"       TIME_FORMAT(j.jam_mulai,'%%H:%%i')   AS jm, "
        f"       TIME_FORMAT(j.jam_selesai,'%%H:%%i') AS js "
        f"FROM jadwal_blokir j "
        f"JOIN pengguna_anak p ON p.user_id = j.user_id "
        f"WHERE j.jadwal_id IN ({placeholders}) AND p.admin_id=%s",
        ids + [current_admin_id()]) or []
    if not rows:
        flash('Jadwal tidak ditemukan.', 'error')
        return redirect(url_for('jadwal'))
    valid_ids = [r['jadwal_id'] for r in rows]
    placeholders2 = ','.join(['%s'] * len(valid_ids))
    n = query(f"DELETE FROM jadwal_blokir WHERE jadwal_id IN ({placeholders2})",
              valid_ids)
    nama = rows[0]['nama']
    jm   = rows[0]['jm']
    js   = rows[0]['js']
    flash(f'Jadwal {jm}–{js} untuk {nama} dihapus ({n} hari).', 'success')
    return redirect(url_for('jadwal'))

# ══════════════════════════════════════════════════════════════════════════════
# ATURAN FILTER  (whitelist + blacklist digabung di tabel daftar_filter)
# ══════════════════════════════════════════════════════════════════════════════

# Regex domain valid: contoh.com, sub.domain.co.id, api.example.io
# - tiap label 1..63 char, huruf/angka/dash (tidak boleh awal/akhir dash)
# - minimal 1 dot, TLD ≥ 2 huruf
_DOMAIN_RE = re.compile(
    r'^(?=.{1,253}$)'                                            # total ≤ 253
    r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+'              # ≥ 1 label
    r'[a-z]{2,63}$'                                              # TLD
)

def normalisasi_domain(raw: str) -> str:
    """Buang http(s)://, port, path, lowercase, trim — supaya user bisa paste URL."""
    d = (raw or '').strip().lower()
    if not d: return ''
    # Buang skema
    d = re.sub(r'^[a-z][a-z0-9+.\-]*://', '', d)
    # Buang path/query/fragment
    d = d.split('/')[0].split('?')[0].split('#')[0]
    # Buang port
    d = d.split(':')[0]
    # Buang www. (boleh, tapi simpan tanpa www.)
    if d.startswith('www.'): d = d[4:]
    return d.strip().strip('.')

def domain_valid(domain: str) -> bool:
    return bool(_DOMAIN_RE.match(domain))


@app.route('/aturan')
@login_required
def aturan():
    tab = request.args.get('tab', 'putih')
    putih = query(
        "SELECT filter_id AS id, domain_url AS domain, alasan "
        "FROM daftar_filter "
        "WHERE admin_id=%s AND tipe='putih' "
        "ORDER BY filter_id DESC",
        (current_admin_id(),)) or []
    hitam = query(
        "SELECT filter_id AS id, domain_url AS domain, alasan "
        "FROM daftar_filter "
        "WHERE admin_id=%s AND tipe='hitam' "
        "ORDER BY filter_id DESC",
        (current_admin_id(),)) or []
    ai = bool(int(get_cfg('ai_aktif', '1')))
    return render_template('aturan_filter.html',
        cfg={'ai_aktif':ai}, tab=tab,
        daftar_putih=list(putih), daftar_hitam=list(hitam), ai_aktif=ai)

@app.route('/aturan/tambah', methods=['POST'])
@login_required
def tambah_domain():
    raw    = request.form.get('domain') or ''
    tipe   = request.form.get('tipe', 'putih')
    alasan = (request.form.get('alasan') or '').strip()[:255]
    if tipe not in ('putih', 'hitam'): tipe = 'putih'

    domain = normalisasi_domain(raw)
    if not domain:
        flash('Domain tidak boleh kosong.', 'error')
        return redirect(url_for('aturan', tab=tipe))
    if not domain_valid(domain):
        flash(f'Format domain tidak valid: "{raw}". '
              f'Contoh: youtube.com, brainly.co.id, scholar.google.com', 'error')
        return redirect(url_for('aturan', tab=tipe))

    # Cek apakah sudah ada (untuk pesan yang ramah)
    exists = query("SELECT filter_id FROM daftar_filter "
                   "WHERE admin_id=%s AND tipe=%s AND domain_url=%s",
                   (current_admin_id(), tipe, domain), one=True)
    if exists:
        flash(f'"{domain}" sudah ada di daftar {tipe} — tidak perlu ditambahkan lagi.',
              'info')
        return redirect(url_for('aturan', tab=tipe))

    try:
        query("INSERT INTO daftar_filter (admin_id, tipe, domain_url, alasan) "
              "VALUES (%s,%s,%s,%s)",
              (current_admin_id(), tipe, domain, alasan or None))
        flash(f'"{domain}" ditambahkan ke daftar {tipe}.', 'success')
    except pymysql.err.IntegrityError:
        # Race condition fallback (kalau ada concurrent insert)
        flash(f'"{domain}" sudah ada di daftar {tipe}.', 'info')
    return redirect(url_for('aturan', tab=tipe))

# Hapus by ID — endpoint terpadu (whitelist/blacklist sama tabel)
@app.route('/aturan/hapus/<int:fid>', methods=['POST'])
@login_required
def aturan_hapus(fid):
    row = query("SELECT domain_url, tipe FROM daftar_filter "
                "WHERE filter_id=%s AND admin_id=%s",
                (fid, current_admin_id()), one=True)
    if not row:
        flash('Data tidak ditemukan.', 'error')
        return redirect(url_for('aturan'))
    query("DELETE FROM daftar_filter WHERE filter_id=%s AND admin_id=%s",
          (fid, current_admin_id()))
    flash(f'"{row["domain_url"]}" dihapus dari daftar {row["tipe"]}.', 'success')
    return redirect(url_for('aturan', tab=row['tipe']))

# ══════════════════════════════════════════════════════════════════════════════
# KATEGORI AI — sekarang menampilkan cache_domain (knowledge base AI)
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/kategori')
@login_required
def kategori_list():
    q     = (request.args.get('q')   or '').strip().lower()
    kat   = (request.args.get('kat') or 'all').strip().lower()
    urut  = (request.args.get('urut')or 'terbaru').strip().lower()
    if kat not in ('all','edukasi','hiburan','negatif','unknown'): kat = 'all'
    if urut not in ('terbaru','populer','confidence'):              urut = 'terbaru'

    # Statistik per kategori
    stats = {r['kategori']: r['n'] for r in (query(
        "SELECT kategori, COUNT(*) AS n FROM cache_domain GROUP BY kategori") or [])}
    total = sum(stats.values()) or 0

    # Filter + search
    sql  = "SELECT * FROM cache_domain"
    conds, args = [], []
    if kat != 'all':
        conds.append("kategori=%s"); args.append(kat)
    if q:
        conds.append("LOWER(domain_url) LIKE %s"); args.append(f"%{q}%")
    if conds: sql += " WHERE " + " AND ".join(conds)
    sql += {
        'populer':    " ORDER BY jumlah_hit DESC, terakhir_diakses DESC",
        'confidence': " ORDER BY confidence_score DESC, terakhir_diakses DESC",
    }.get(urut, " ORDER BY terakhir_diakses DESC")
    sql += " LIMIT 300"

    rows = query(sql, args) or []
    for r in rows:
        r['waktu_str'] = format_waktu_ramah(r.get('terakhir_diakses'))

    return render_template('kategori_ai.html',
        cache_list=list(rows),
        stats={
            'edukasi': stats.get('edukasi', 0),
            'hiburan': stats.get('hiburan', 0),
            'negatif': stats.get('negatif', 0),
            'unknown': stats.get('unknown', 0),
            'total':   total,
        },
        q=q, kat=kat, urut=urut,
        ai_aktif=bool(int(get_cfg('ai_aktif', '1'))))

@app.route('/kategori/toggle-ai', methods=['POST'])
@login_required
def toggle_ai():
    curr = int(get_cfg('ai_aktif', '1'))
    set_cfg('ai_aktif', '0' if curr else '1')
    flash(f"AI {'diaktifkan' if not curr else 'dinonaktifkan'}.", 'success')
    return redirect(url_for('kategori_list'))

# ══════════════════════════════════════════════════════════════════════════════
# KELOLA PERANGKAT
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/perangkat')
@login_required
def kelola_perangkat():
    reset_kuota_jika_hari_baru()
    refresh_status_online()
    devs = query(
        "SELECT p.*, "
        "  COALESCE(s.total_akses, 0)  AS _log_count, "
        "  COALESCE(s.total_blokir, 0) AS _blokir_count "
        "FROM pengguna_anak p "
        "LEFT JOIN v_statistik s ON s.user_id = p.user_id "
        "WHERE p.admin_id=%s ORDER BY p.nama",
        (current_admin_id(),)) or []
    for d in devs:
        d['jeda']   = bool(d.get('jeda', 0))
        d['id']     = d['user_id']
        d['mac']    = d.get('mac_address', '')
        d['label']  = d['nama']                                 # nama anak (utama)
        d['model']  = d.get('device_name') or 'Tidak diketahui' # jenis perangkat (sub)
        d['ikon']   = device_icon(d.get('device_name'))          # emoji sesuai jenis
        d['status'] = 'online' if d.get('status_aktif') else 'offline'
    return render_template('kelola_perangkat.html', perangkat_list=list(devs))

@app.route('/perangkat/tambah', methods=['GET','POST'])
@login_required
def tambah_perangkat():
    if request.method == 'POST':
        mac   = (request.form.get('mac', '')   or '').strip().upper()
        nama  = (request.form.get('nama', '')  or '').strip()
        model = (request.form.get('model', '') or '').strip() or 'Tidak diketahui'
        kuota = int(request.form.get('kuota', 120))
        if not mac or not nama:
            flash('MAC Address dan nama wajib diisi.', 'error')
            return redirect(url_for('tambah_perangkat'))
        try:
            new_uid = query(
                "INSERT INTO pengguna_anak "
                "(admin_id, mac_address, device_name, status_aktif, nama, "
                " jeda, kuota_terpakai, kuota_harian, last_reset) "
                "VALUES (%s,%s,%s,0,%s,0,0,%s,CURDATE())",
                (current_admin_id(), mac, model, nama, kuota))
            # Buat dompet kuota default
            query("INSERT INTO dompet_kuota (user_id, batas_harian, terakhir_reset) "
                  "VALUES (%s, %s, CURDATE())",
                  (new_uid, int(get_cfg('batas_bonus_menit', '60'))))
            flash(f'Perangkat {nama} ditambahkan!', 'success')
        except pymysql.err.IntegrityError:
            flash(f'MAC {mac} sudah terdaftar.', 'error')
        return redirect(url_for('kelola_perangkat'))
    return render_template('tambah_perangkat.html', mode='tambah', dev=None)

@app.route('/perangkat/edit/<int:dev_id>', methods=['GET','POST'])
@login_required
def edit_perangkat(dev_id):
    dev = query("SELECT * FROM pengguna_anak WHERE user_id=%s AND admin_id=%s",
                (dev_id, current_admin_id()), one=True)
    if not dev:
        flash('Perangkat tidak ditemukan.', 'error')
        return redirect(url_for('kelola_perangkat'))
    dev['jeda']  = bool(dev.get('jeda', 0))
    dev['mac']   = dev.get('mac_address','')
    dev['model'] = dev.get('device_name','')
    dev['id']    = dev['user_id']
    if request.method == 'POST':
        nama_lama = dev['nama']
        nama  = (request.form.get('nama',  dev['nama'])  or '').strip()
        model = (request.form.get('model', dev['device_name'] or '') or '').strip()
        kuota = int(request.form.get('kuota', dev['kuota_harian']))
        query("UPDATE pengguna_anak SET nama=%s, device_name=%s, kuota_harian=%s "
              "WHERE user_id=%s", (nama, model, kuota, dev_id))
        if nama != nama_lama:
            n = query("UPDATE log_akses SET perangkat_nama=%s WHERE user_id=%s",
                      (nama, dev_id))
            flash(f'Perangkat {nama_lama} → {nama} diperbarui. '
                  f'{n} entri log ikut tersinkronisasi.', 'success')
        else:
            flash(f'Perangkat {nama} diperbarui.', 'success')
        return redirect(url_for('kelola_perangkat'))
    return render_template('tambah_perangkat.html', mode='edit', dev=dict(dev))

@app.route('/perangkat/hapus/<int:dev_id>', methods=['POST'])
@login_required
def hapus_perangkat(dev_id):
    dev = query("SELECT nama FROM pengguna_anak WHERE user_id=%s AND admin_id=%s",
                (dev_id, current_admin_id()), one=True)
    if not dev:
        flash('Perangkat tidak ditemukan.', 'error')
        return redirect(url_for('kelola_perangkat'))
    n_log = query("SELECT COUNT(*) AS n FROM log_akses WHERE user_id=%s",
                  (dev_id,), one=True)['n']
    query("DELETE FROM pengguna_anak WHERE user_id=%s AND admin_id=%s",
          (dev_id, current_admin_id()))
    flash(f'Perangkat {dev["nama"]} dihapus beserta {n_log} entri log miliknya. '
          f'Data perangkat lain tetap aman.', 'success')
    return redirect(url_for('kelola_perangkat'))

# Halaman /perangkat/detail/<id> dihapus — semua akses lewat:
#   • Beranda (card perangkat → device sheet)
#   • /perangkat (kelola)
#   • /perangkat/edit/<id> (edit + hapus jadi satu halaman)
# Untuk backward-compat / link lama, redirect ke kelola:
@app.route('/perangkat/detail/<int:dev_id>')
@login_required
def detail_perangkat_legacy(dev_id):
    return redirect(url_for('edit_perangkat', dev_id=dev_id))

# ══════════════════════════════════════════════════════════════════════════════
# CAPTIVE PORTAL
# ══════════════════════════════════════════════════════════════════════════════
def domain_terakhir(perangkat: str = '', device_id: str = '') -> str:
    """Domain terakhir yang diakses perangkat SEBELUM dialihkan ke captive portal
    (mis. saat kuota habis). Dipakai untuk mengisi notif 'minta izin'."""
    try:
        if perangkat:
            row = query(
                "SELECT domain_url FROM log_akses "
                "WHERE perangkat_nama=%s AND domain_url IS NOT NULL "
                "  AND domain_url<>'' "
                "ORDER BY waktu_akses DESC LIMIT 1",
                (perangkat,), one=True)
            if row and row.get('domain_url'):
                return row['domain_url']
        if device_id:
            row = query(
                "SELECT l.domain_url FROM log_akses l "
                "JOIN pengguna_anak p ON p.user_id = l.user_id "
                "WHERE UPPER(p.mac_address)=%s AND l.domain_url IS NOT NULL "
                "  AND l.domain_url<>'' "
                "ORDER BY l.waktu_akses DESC LIMIT 1",
                (device_id.upper(),), one=True)
            if row and row.get('domain_url'):
                return row['domain_url']
    except Exception:
        pass
    return ''

@app.route('/blokir')
def blokir():
    return render_template('halaman_blokir.html',
        tipe='blokir',
        domain=request.args.get('domain', 'situs ini'),
        device_id=request.args.get('device_id', ''),
        perangkat=request.args.get('perangkat', ''))

@app.route('/habis')
def habis():
    sisa      = int(get_cfg('durasi_belajar_menit', 30))
    perangkat = request.args.get('perangkat', '')
    device_id = request.args.get('device_id', '')
    # Link terakhir yang dicoba diakses anak sebelum dialihkan ke sini.
    last_dom  = (request.args.get('domain', '')
                 or domain_terakhir(perangkat, device_id))
    return render_template('halaman_blokir.html',
        tipe='habis', sisa_belajar=sisa,
        domain=last_dom,
        device_id=device_id,
        perangkat=perangkat)

@app.route('/minta-izin', methods=['POST'])
def minta_izin():
    data      = request.get_json(silent=True) or request.form
    domain    = (data.get('domain', '') or '').strip()
    perangkat = data.get('perangkat', '')
    device_id = data.get('device_id', '')
    # Kalau captive portal tidak membawa domain (kasus kuota habis),
    # ambil domain terakhir yang diakses perangkat dari log.
    if not domain or domain in ('situs ini', '-', '—'):
        domain = domain_terakhir(perangkat, device_id) or domain
    ok = notif_telegram('minta_izin',
                        domain=domain or '(tidak diketahui)',
                        perangkat=perangkat or device_id)
    return jsonify({"status": "ok" if ok else "queued"})

# ══════════════════════════════════════════════════════════════════════════════
# API UNTUK ROUTER (push-based, tidak butuh login)
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/config')
def api_config():
    putih  = query("SELECT domain_url FROM daftar_filter WHERE tipe='putih'") or []
    hitam  = query("SELECT domain_url FROM daftar_filter WHERE tipe='hitam'") or []
    dijeda = query("SELECT mac_address FROM pengguna_anak WHERE jeda=1") or []
    return jsonify({
        "ai_aktif":             bool(int(get_cfg('ai_aktif', '1'))),
        "daftar_putih":         [r['domain_url']  for r in putih],
        "daftar_hitam":         [r['domain_url']  for r in hitam],
        "perangkat_jeda":       [r['mac_address'] for r in dijeda],
        "kategori_ai":          [
            {"nama":"edukasi","aksi":"izinkan"},
            {"nama":"hiburan","aksi":"netral"},
            {"nama":"negatif","aksi":"blokir"},
        ],
        "kuota_harian_menit":   int(get_cfg('kuota_harian_menit','120')),
        "durasi_belajar_menit": int(get_cfg('durasi_belajar_menit','30')),
        "waktu_bonus_menit":    int(get_cfg('waktu_bonus_menit','10')),
    })

@app.route('/api/perangkat')
def api_perangkat():
    reset_kuota_jika_hari_baru()
    devs = query(
        "SELECT user_id AS id, nama, device_name AS label, mac_address AS mac, "
        "       kuota_harian, kuota_terpakai, jeda, "
        "       (CASE WHEN status_aktif THEN 'online' ELSE 'offline' END) AS status, "
        "       last_seen "
        "FROM pengguna_anak") or []
    return jsonify({"perangkat":[dict(d, last_seen=str(d['last_seen']) if d.get('last_seen') else None)
                                 for d in devs]})

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    data = request.get_json(silent=True) or {}
    mac  = (data.get('mac') or '').upper()
    ip   = data.get('ip', '')
    if not mac:
        return jsonify({"status":"error","msg":"mac required"}), 400
    n = query("UPDATE pengguna_anak SET status_aktif=1, last_seen=NOW(), "
              "ip_terakhir=%s WHERE UPPER(mac_address)=%s", (ip, mac))
    return jsonify({"status":"ok","known":bool(n)})

@app.route('/api/log', methods=['POST'])
def api_log():
    """Router push log akses. Sekaligus update cache_domain (jumlah_hit, terakhir_diakses).
    Payload: {domain, kategori, status, alasan, confidence, perangkat, mac, traffic_kbps?}"""
    data = request.get_json(silent=True)
    if not data: return jsonify({"status":"error"}), 400

    mac        = (data.get('mac') or '').upper()
    kat        = data.get('kategori', 'unknown')
    if kat not in ('edukasi','hiburan','negatif','unknown'): kat = 'unknown'
    status     = data.get('status', 'diizinkan')
    aksi       = 'blokir' if status == 'diblokir' else 'izinkan'
    domain     = (data.get('domain') or '').strip().lower()
    perangkat  = data.get('perangkat', '')
    confidence = float(data.get('confidence', 0) or 0)
    traffic    = float(data.get('traffic_kbps', 0) or 0)

    dev = query("SELECT user_id, nama FROM pengguna_anak WHERE UPPER(mac_address)=%s",
                (mac,), one=True) if mac else None
    user_id = dev['user_id'] if dev else None
    if dev and not perangkat: perangkat = dev['nama']

    # Upsert cache_domain
    if domain:
        query(
            "INSERT INTO cache_domain (domain_url, kategori, confidence_score, jumlah_hit) "
            "VALUES (%s, %s, %s, 1) "
            "ON DUPLICATE KEY UPDATE "
            "  kategori = VALUES(kategori), "
            "  confidence_score = VALUES(confidence_score), "
            "  terakhir_diakses = CURRENT_TIMESTAMP, "
            "  jumlah_hit = jumlah_hit + 1",
            (domain, kat, confidence))

    # Insert log_akses
    query(
        "INSERT INTO log_akses "
        "(user_id, domain_url, kategori, aksi, alasan, confidence, traffic_kbps, "
        " perangkat_nama, mac, waktu_akses) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())",
        (user_id, domain or None, kat, aksi,
         data.get('alasan',''), confidence, traffic,
         perangkat, mac))

    # Heartbeat implisit
    if mac and dev:
        query("UPDATE pengguna_anak SET status_aktif=1, last_seen=NOW() "
              "WHERE user_id=%s", (user_id,))

    # Notif Telegram jika diblokir karena negatif
    if aksi == 'blokir' and kat == 'negatif':
        notif_telegram('blokir',
                       domain=domain, alasan=data.get('alasan',''),
                       kategori=kat, perangkat=perangkat,
                       confidence=confidence)
    return jsonify({"status":"ok"})

@app.route('/api/kuota-update', methods=['POST'])
def api_kuota_update():
    data = request.get_json(silent=True)
    if not data: return jsonify({"status":"error"}), 400
    try:
        dev_id = int(data.get('dev_id', 0))
    except: dev_id = 0
    kuota_terpakai = max(0, int(data.get('kuota_terpakai', 0)))

    dev = query("SELECT user_id AS id, nama, kuota_harian FROM pengguna_anak "
                "WHERE user_id=%s", (dev_id,), one=True)
    if not dev:
        return jsonify({"status":"error","msg":"not found"}), 404

    query("UPDATE pengguna_anak SET kuota_terpakai=%s, last_seen=NOW(), "
          "status_aktif=1 WHERE user_id=%s", (kuota_terpakai, dev_id))

    kh = int(dev['kuota_harian'])
    return jsonify({
        "status":"ok","nama":dev['nama'],
        "kuota_terpakai":kuota_terpakai,
        "kuota_harian":kh,
        "kuota_sisa":max(0, kh - kuota_terpakai),
        "pct":round(kuota_terpakai/kh*100) if kh else 0,
        "habis":kuota_terpakai >= kh,
    })

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM — halaman pengaturan + endpoint test
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/telegram', methods=['GET', 'POST'])
@login_required
def telegram_settings():
    if request.method == 'POST':
        # Token bot TETAP (hardcode) → tidak disimpan/diubah dari form.
        chat  = (request.form.get('chat_id') or '').strip()
        aktif = '1' if request.form.get('aktif') == 'on' else '0'
        set_cfg('telegram_chat_id', chat)
        set_cfg('telegram_aktif',   aktif)
        # Nyalakan bot dua-arah begitu kredensial valid (kalau belum jalan).
        if tg_aktif():
            mulai_bot_telegram()
        flash('✅ Pengaturan Telegram disimpan.', 'success')
        return redirect(url_for('telegram_settings'))

    bot, chat = tg_credentials()
    last_ok   = get_cfg('telegram_last_ok', '0')
    try:
        last_ok_dt = (datetime.fromtimestamp(int(last_ok), TZ_WITA)
                      if int(last_ok) else None)
    except: last_ok_dt = None
    return render_template('pengaturan_telegram.html',
        bot_token = bot,
        chat_id   = chat,
        aktif     = bool(int(get_cfg('telegram_aktif', '1'))),
        terhubung = bool(bot and chat),
        last_ok   = last_ok_dt,
        last_ok_str = (format_waktu_ramah(last_ok_dt) if last_ok_dt else '—'))

@app.route('/api/telegram/test', methods=['POST'])
@login_required
def api_telegram_test():
    """Kirim pesan test ke chat yang sudah dikonfigurasi."""
    bot, chat = tg_credentials()
    if not bot:
        return jsonify({"status":"error","code":"no_token",
                        "msg":"BOT_TOKEN belum diatur. Buat bot di @BotFather "
                              "lalu salin token-nya."}), 400
    if not chat:
        return jsonify({"status":"error","code":"no_chat",
                        "msg":"CHAT_ID belum diatur. Tap tombol 'Cari Chat ID' "
                              "setelah Anda chat /start ke bot."}), 400
    teks = (
        "🛡️ *Edge Guard — Test Koneksi*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Bot Telegram berhasil terhubung!\n"
        "📱 Notifikasi sistem akan dikirim ke chat ini."
    )
    ok, err = tg_send_message(teks)
    # Pastikan bot dua-arah tetap hidup (untuk /start).
    try:
        if tg_aktif(): mulai_bot_telegram()
    except Exception: pass
    if ok:
        return jsonify({"status":"ok","msg":"Pesan test terkirim. "
                        "Cek aplikasi Telegram Anda."})
    return jsonify({"status":"error","code":"send_fail",
                    "msg":f"Gagal mengirim: {err}"}), 400

@app.route('/api/telegram/getchatid', methods=['POST'])
@login_required
def api_telegram_getchatid():
    """Bantu user temukan CHAT_ID dari getUpdates."""
    bot, _ = tg_credentials()
    if not bot:
        return jsonify({"status":"error","code":"no_token",
                        "msg":"Simpan BOT_TOKEN dulu, lalu kirim /start ke bot, "
                              "kemudian klik tombol ini."}), 400
    chats = tg_get_updates()
    if not chats:
        return jsonify({"status":"info","code":"no_chat",
                        "msg":"Belum ada chat yang terdeteksi. Kirim /start ke "
                              "bot Anda dari Telegram, lalu klik tombol ini lagi."}), 200
    return jsonify({"status":"ok","chats":chats})

@app.route('/api/status')
def api_status():
    return jsonify({"status":"online","ts":datetime.now().isoformat()})

# ══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════════════
@app.errorhandler(404)
def err_404(e):
    if request.path.startswith('/api/') or \
       request.accept_mimetypes.best == 'application/json':
        return jsonify({"status":"error","code":404,
                        "msg":"Endpoint tidak ditemukan","path":request.path}), 404
    return render_template('halaman_404.html',
        kode=404, judul='Halaman Tidak Ditemukan',
        pesan='Halaman yang kamu cari tidak ada di server ini.',
        path=request.path, login_user=bool(session.get('user_id'))), 404

@app.errorhandler(500)
def err_500(e):
    if request.path.startswith('/api/'):
        return jsonify({"status":"error","code":500,"msg":"Kesalahan server"}), 500
    return render_template('halaman_404.html',
        kode=500, judul='Kesalahan Server',
        pesan='Terjadi kesalahan di sisi server. Silakan coba lagi.',
        path=request.path, login_user=bool(session.get('user_id'))), 500

@app.errorhandler(403)
def err_403(e):
    return render_template('halaman_404.html',
        kode=403, judul='Akses Ditolak',
        pesan='Kamu tidak punya izin untuk membuka halaman ini.',
        path=request.path, login_user=bool(session.get('user_id'))), 403

# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════
def _reset_admin_password(new_pw: str):
    h = hash_password(new_pw)
    n = query("UPDATE admin_orang_tua SET password_hash=%s, gagal_login=0, "
              "locked_until=NULL ORDER BY admin_id LIMIT 1", (h,))
    print(f"[OK] Password admin di-reset ({n} baris).")

if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'reset-password':
        _reset_admin_password(sys.argv[2])
        sys.exit(0)

    try: ensure_admin_password('stom')
    except Exception as e:
        print(f"[Startup] DB belum siap? {e}")
        print("[Startup] Jalankan dulu: mysql -u <user> -p < dashboard/schema.sql")

    # Mulai bot Telegram dua arah (long-polling) di thread terpisah.
    try:
        if tg_aktif():
            mulai_bot_telegram()
            bot_status = 'ON (long-polling)'
        else:
            bot_status = 'OFF (atur token+chat_id di /telegram)'
    except Exception as e:
        bot_status = f'gagal start: {e}'

    print("=" * 60)
    print("  🛡️  Edge Guard Dashboard")
    print(f"  DB     : {DB['host']}:{DB['port']}/{DB.get('database', DB.get('db','?'))}")
    print(f"  URL    : http://0.0.0.0:8080")
    print(f"  bcrypt : {'ON' if _BCRYPT else '❌ OFF — WAJIB: pip install bcrypt'}")
    print(f"  Bot TG : {bot_status}")
    print("=" * 60)
    app.run(debug=False, host='0.0.0.0', port=8080)
