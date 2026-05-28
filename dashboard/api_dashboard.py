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
import os, sys, json, time, math, hashlib, secrets, re
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
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING
# ══════════════════════════════════════════════════════════════════════════════
def hash_password(plain: str) -> str:
    if _BCRYPT:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()
    salt = secrets.token_hex(16)
    h    = hashlib.sha256((salt + plain).encode()).hexdigest()
    return f'sha256${salt}${h}'

def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    if hashed.startswith('$2'):
        if not _BCRYPT: return False
        try:    return bcrypt.checkpw(plain.encode(), hashed.encode())
        except: return False
    if hashed.startswith('sha256$'):
        try:
            _, salt, h = hashed.split('$', 2)
            return hashlib.sha256((salt + plain).encode()).hexdigest() == h
        except: return False
    return False

# ══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP ADMIN PASSWORD
# ══════════════════════════════════════════════════════════════════════════════
def ensure_admin_password(default_pw: str = 'admin123'):
    """Pastikan admin pertama punya hash valid."""
    try:
        u = query("SELECT admin_id, password_hash FROM admin_orang_tua "
                  "ORDER BY admin_id LIMIT 1", one=True)
        if not u:
            h = hash_password(default_pw)
            query("INSERT INTO admin_orang_tua (nama, email, password_hash) "
                  "VALUES ('Admin Orang Tua', 'admin@edgeguard.local', %s)", (h,))
            print(f"[Bootstrap] Admin dibuat. Password awal: {default_pw}")
            return
        h = u.get('password_hash') or ''
        if not (h.startswith('$2') or h.startswith('sha256$')):
            new_h = hash_password(default_pw)
            query("UPDATE admin_orang_tua SET password_hash=%s, gagal_login=0, "
                  "locked_until=NULL WHERE admin_id=%s", (new_h, u['admin_id']))
            print(f"[Bootstrap] Password admin di-reset ke '{default_pw}'.")
    except Exception as e:
        print(f"[Bootstrap] Gagal cek admin: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# RESET KUOTA HARIAN + STATUS ONLINE
# ══════════════════════════════════════════════════════════════════════════════
def reset_kuota_jika_hari_baru():
    today = date.today().isoformat()
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

    now_h    = datetime.now().hour
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
    today     = date.today()
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
                    and row['session_expired_at'] < datetime.now())):
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
        username = (request.form.get('username') or 'admin').strip().lower()
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
            if user.get('locked_until') and user['locked_until'] > datetime.now():
                lock_detik = int((user['locked_until'] - datetime.now()).total_seconds())
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
                lock_until = datetime.now() + timedelta(seconds=lock_dur)
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

    def _notif(nama, jeda):
        try:
            sys.path.insert(0, os.path.join(ROOT, 'sistem_router'))
            from notifikasi_telegram import notif_jeda
            notif_jeda(nama, 'jeda' if jeda else 'lanjutkan')
        except Exception: pass

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
        for d in devs_after: _notif(d['nama'], bool(d['jeda']))
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
    _notif(dev['nama'], new_jeda)
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
# JADWAL
# ══════════════════════════════════════════════════════════════════════════════
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
    bar_data = hitung_bar_data_hari_ini()
    ada_data = any(b['edu'] or b['hib'] for b in bar_data)
    return render_template('jadwal_akses.html',
        cfg=cfg, bar_data=bar_data, ada_data=ada_data)

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
@app.route('/blokir')
def blokir():
    return render_template('halaman_blokir.html',
        tipe='blokir',
        domain=request.args.get('domain', 'situs ini'),
        device_id=request.args.get('device_id', ''),
        perangkat=request.args.get('perangkat', ''))

@app.route('/habis')
def habis():
    sisa = int(get_cfg('durasi_belajar_menit', 30))
    return render_template('halaman_blokir.html',
        tipe='habis', sisa_belajar=sisa,
        device_id=request.args.get('device_id', ''),
        perangkat=request.args.get('perangkat', ''))

@app.route('/minta-izin', methods=['POST'])
def minta_izin():
    data      = request.get_json(silent=True) or request.form
    domain    = data.get('domain', '')
    perangkat = data.get('perangkat', '')
    device_id = data.get('device_id', '')
    ok = False
    try:
        sys.path.insert(0, os.path.join(ROOT, 'sistem_router'))
        from notifikasi_telegram import notif_minta_izin
        ok = notif_minta_izin(domain, perangkat or device_id)
    except Exception: pass
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
        try:
            sys.path.insert(0, os.path.join(ROOT, 'sistem_router'))
            from notifikasi_telegram import notif_blokir
            notif_blokir(domain=domain, alasan=data.get('alasan',''),
                         kategori=kat, perangkat=perangkat, confidence=confidence)
        except Exception: pass
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

    try: ensure_admin_password('admin123')
    except Exception as e:
        print(f"[Startup] DB belum siap? {e}")
        print("[Startup] Jalankan dulu: mysql -u <user> -p < dashboard/schema.sql")

    print("=" * 60)
    print("  🛡️  Edge Guard Dashboard")
    print(f"  DB     : {DB['host']}:{DB['port']}/{DB.get('database', DB.get('db','?'))}")
    print(f"  URL    : http://0.0.0.0:8080")
    print(f"  Login  : admin / admin123  (segera ganti!)")
    print(f"  bcrypt : {'ON' if _BCRYPT else 'OFF (fallback sha256, install bcrypt!)'}")
    print("=" * 60)
    app.run(debug=False, host='0.0.0.0', port=8080)
