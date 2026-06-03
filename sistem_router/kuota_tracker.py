"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — KUOTA & ENFORCEMENT (Router OpenWrt)                   ║
║                                                                       ║
║  Otak enforcement KATEGORI-AWARE. Tiap N detik:                      ║
║    1) Ambil perangkat dari VPS (/api/perangkat): jeda, blokir_jadwal,║
║       kuota_harian, kuota_terpakai, sisa_hiburan.                    ║
║    2) Pasang counter byte HIBURAN per MAC (via captive_portal.sh).   ║
║    3) Byte hiburan naik signifikan → +menit ke kuota_terpakai        ║
║       (hanya pemakaian HIBURAN yang menghabiskan kuota; edukasi tidak)║
║    4) Hitung blok_hiburan = jeda OR blokir_jadwal OR                 ║
║         (kuota_terpakai >= kuota_harian + sisa_hiburan).             ║
║       → blok-hiburan / buka-hiburan <MAC>.                           ║
║                                                                       ║
║  EDUKASI & INFRA tidak pernah diblokir (lihat captive_portal.sh).    ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time, argparse, subprocess, threading
import urllib.request, urllib.error
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import CLOUD_URL, HTTP_TIMEOUT, KUOTA_INTERVAL, KBPS_AKTIF, DEBUG, mk_ssl_ctx

PORTAL_SH = os.path.join(BASE, 'captive_portal.sh')

# ═══════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════
_state = {
    'devs':       [],
    'devs_ts':    0,
    'hib_prev':   defaultdict(lambda: 0),   # byte hiburan terakhir per MAC
    'blok_set':   set(),                    # MAC yg sedang diblok hiburannya
    'jadwal_set': set(),                    # MAC yg sedang diblok jadwal (full)
    'primed':     set(),                    # MAC yg counter awalnya sudah dicatat
    'lock':       threading.Lock(),
}
DEVS_TTL = 25

# ═══════════════════════════════════════════════════════════════════════════
# AMBIL PERANGKAT
# ═══════════════════════════════════════════════════════════════════════════
def ambil_perangkat():
    now = time.time()
    with _state['lock']:
        if now - _state['devs_ts'] < DEVS_TTL and _state['devs']:
            return _state['devs']
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/perangkat',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            data = json.loads(r.read().decode())
        with _state['lock']:
            _state['devs']    = data.get('perangkat', [])
            _state['devs_ts'] = now
        return _state['devs']
    except Exception:
        return _state['devs'] or []

# ═══════════════════════════════════════════════════════════════════════════
# PORTAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _portal(*args):
    if not os.path.exists(PORTAL_SH): return ''
    try:
        return subprocess.run(['sh', PORTAL_SH, *args], timeout=15,
                              check=False, text=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout
    except Exception:
        return ''

def baca_byte_hiburan() -> dict:
    """Return {mac_upper: total_byte_hiburan} dari chain measure (nft -j).
    Rule diberi comment 'hib_<MAC>' agar mudah dipetakan."""
    out = {}
    raw = _portal('read-measure')
    if not raw: return out
    try:
        data = json.loads(raw)
    except Exception:
        return out
    for item in data.get('nftables', []):
        rule = item.get('rule')
        if not rule: continue
        cmt = rule.get('comment', '')
        if not cmt.startswith('hib_'): continue
        mac = cmt[4:].upper()
        # cari counter bytes di expr
        for e in rule.get('expr', []):
            if 'counter' in e:
                out[mac] = int(e['counter'].get('bytes', 0))
    return out

# ═══════════════════════════════════════════════════════════════════════════
# PUSH pemakaian hiburan ke VPS
# ═══════════════════════════════════════════════════════════════════════════
def push_kuota(dev_id, kuota_terpakai: int) -> bool:
    try:
        payload = json.dumps({'dev_id': dev_id,
                              'kuota_terpakai': kuota_terpakai}).encode()
        req = urllib.request.Request(CLOUD_URL + '/api/kuota-update',
                                     data=payload, method='POST',
                                     headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            return json.loads(r.read().decode()).get('status') == 'ok'
    except Exception:
        return False

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[Kuota {ts}] {msg}")

# ═══════════════════════════════════════════════════════════════════════════
# SIKLUS UTAMA
# ═══════════════════════════════════════════════════════════════════════════
def siklus(interval: int, kbps_th: float):
    devs = ambil_perangkat()
    if not devs: return

    # Pastikan counter hiburan terpasang utk tiap MAC.
    for d in devs:
        mac = (d.get('mac') or '').upper()
        if mac: _portal('measure-mac', mac)

    hib_now = baca_byte_hiburan()

    for dev in devs:
        mac = (dev.get('mac') or '').upper()
        if not mac: continue
        dev_id   = dev.get('id')
        nama     = dev.get('nama', mac)
        jeda     = bool(dev.get('jeda', 0))
        jadwal   = bool(dev.get('blokir_jadwal', 0))
        kH       = int(dev.get('kuota_harian', 120))      # jatah hiburan harian
        kU       = int(dev.get('kuota_terpakai', 0))      # hiburan terpakai
        bonus    = int(dev.get('sisa_hiburan', 0))        # bonus belajar
        budget   = kH + bonus                             # total jatah hiburan

        # ── Akumulasi pemakaian HIBURAN (hanya kalau tidak diblok) ─────────
        prev  = _state['hib_prev'][mac]
        curr  = hib_now.get(mac, 0)
        delta = max(0, curr - prev)
        if curr < prev: delta = 0          # counter reset
        _state['hib_prev'][mac] = curr

        # Prime: pada pengamatan PERTAMA sebuah MAC, jangan hitung delta.
        # Mencegah kuota terpotong salah saat tracker restart sementara counter
        # nft sudah berisi byte lama (delta = curr - 0 = besar → false spike).
        if mac not in _state['primed']:
            _state['primed'].add(mac)
            delta = 0

        sudah_blok = mac in _state['blok_set']
        if not sudah_blok:
            kbps = (delta * 8) / (interval * 1000)
            if kbps >= kbps_th:
                kU = min(budget if budget > 0 else kH, kU + max(1, round(interval/60)))
                push_kuota(dev_id, kU)
                if DEBUG:
                    log(f"{nama}: +{round(interval/60)}m hiburan → {kU}/{budget}m ({kbps:.0f}Kbps)")

        # ── Keputusan blok jadwal (full block internet) ────────────────────
        # jeda atau jadwal → blokir SEMUA trafik via jadwal_mac set
        in_jadwal_set = mac in _state['jadwal_set']
        perlu_jadwal  = jeda or jadwal

        if perlu_jadwal and not in_jadwal_set:
            _state['jadwal_set'].add(mac)
            _portal('blok-jadwal', mac)
            sebab = 'dijeda orang tua' if jeda else 'jadwal istirahat'
            log(f"🌙 {nama}: internet diblokir penuh ({sebab})")
        elif not perlu_jadwal and in_jadwal_set:
            _state['jadwal_set'].discard(mac)
            _portal('buka-jadwal', mac)
            log(f"☀️ {nama}: internet dibuka kembali (jadwal/jeda selesai)")

        # ── Keputusan blok hiburan ─────────────────────────────────────────
        hiburan_habis = (kU >= budget)
        # Kuota hiburan habis → blok hiburan saja (edukasi tetap jalan).
        # Jika sudah di-jadwal (full block), tidak perlu tambah blok_mac.
        perlu_blok    = hiburan_habis and not perlu_jadwal

        if perlu_blok and not sudah_blok:
            _state['blok_set'].add(mac)
            _portal('blok-hiburan', mac)
            log(f"⛔ {nama}: hiburan dibatasi (kuota habis) — edukasi tetap jalan")
        elif not perlu_blok and sudah_blok:
            _state['blok_set'].discard(mac)
            _portal('buka-hiburan', mac)
            log(f"✅ {nama}: hiburan dibuka kembali")

def main():
    p = argparse.ArgumentParser(description='Edge Guard — Kuota & Enforcement')
    p.add_argument('--interval','-i', type=int, default=KUOTA_INTERVAL)
    p.add_argument('--kbps-aktif','-k', type=float, default=KBPS_AKTIF)
    args = p.parse_args()

    print("=" * 55)
    print("  Edge Guard — Kuota & Enforcement (kategori-aware)")
    print(f"  Interval  : {args.interval} detik")
    print(f"  Threshold : {args.kbps_aktif} Kbps")
    print(f"  Cloud URL : {CLOUD_URL}")
    print("=" * 55)

    if hasattr(os, 'geteuid') and os.geteuid() != 0:
        print("⚠️  Butuh root untuk nft"); sys.exit(1)

    ambil_perangkat()
    # Siklus pertama langsung (prime counter + enforce jadwal/jeda segera,
    # tanpa menunggu satu interval penuh).
    try: siklus(args.interval, args.kbps_aktif)
    except Exception as e:
        if DEBUG: log(f"siklus awal error: {e}")
    try:
        while True:
            time.sleep(args.interval)
            try: siklus(args.interval, args.kbps_aktif)
            except Exception as e:
                if DEBUG: log(f"siklus error: {e}")
    except KeyboardInterrupt:
        log("Dihentikan.")

if __name__ == '__main__':
    main()
