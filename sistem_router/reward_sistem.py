"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — REWARD SISTEM (belajar → bonus kuota hiburan)          ║
║                                                                       ║
║  Konsep: anak yang mengakses konten EDUKASI mengumpulkan menit       ║
║  belajar. Tiap 'durasi_belajar_menit' menit belajar → +bonus         ║
║  'waktu_bonus_menit' menit ke kuota hiburan (sisa_hiburan di VPS),    ║
║  dibatasi batas_harian.                                              ║
║                                                                       ║
║  Pengukuran belajar = byte trafik ke set edukasi_ip per MAC          ║
║  (counter chain 'measure' di captive_portal.sh, comment 'edu_<MAC>').║
║                                                                       ║
║  Reset harian ditangani VPS (dompet_kuota).                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time, threading, subprocess, argparse
import urllib.request
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import CLOUD_URL, HTTP_TIMEOUT, CONFIG_TTL, DEBUG, mk_ssl_ctx

PORTAL_SH = os.path.join(BASE, 'captive_portal.sh')

# Ambang byte edukasi yang dianggap "aktif belajar" per siklus (anti idle-ping).
EDU_BYTES_AKTIF = 40_000          # ~40 KB / siklus

DEFAULT_CFG = {
    'durasi_belajar_menit': 30,
    'waktu_bonus_menit':    10,
}
_cfg_cache = {}; _cfg_ts = 0

def ambil_cfg() -> dict:
    global _cfg_cache, _cfg_ts
    now = time.time()
    if now - _cfg_ts < CONFIG_TTL and _cfg_cache:
        return _cfg_cache
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/config',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            _cfg_cache = json.loads(r.read().decode())
        _cfg_ts = now
        return _cfg_cache
    except Exception:
        return _cfg_cache or DEFAULT_CFG

# ─── State per MAC ──────────────────────────────────────────────────────────
_edu_prev   = defaultdict(lambda: 0)    # byte edukasi terakhir per MAC
_edu_menit  = defaultdict(float)        # akumulasi menit belajar (belum dibonus)
_mac_dev    = {}                        # mac → dev_id
_primed     = set()                     # mac yg counter awalnya sudah dicatat
_tanggal    = datetime.now().strftime('%Y-%m-%d')

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[Reward {ts}] {msg}")

def _portal(*args):
    if not os.path.exists(PORTAL_SH): return ''
    try:
        return subprocess.run(['sh', PORTAL_SH, *args], timeout=15, check=False,
                              text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout
    except Exception:
        return ''

def sync_perangkat():
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/perangkat',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            data = json.loads(r.read().decode())
        for d in data.get('perangkat', []):
            mac = (d.get('mac') or '').upper()
            if mac:
                _mac_dev[mac] = d.get('id')
                _portal('measure-mac', mac)
    except Exception:
        pass

def baca_byte_edukasi() -> dict:
    """{mac_upper: total_byte_edukasi} dari chain measure (comment 'edu_<MAC>')."""
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
        if not cmt.startswith('edu_'): continue
        mac = cmt[4:].upper()
        for e in rule.get('expr', []):
            if 'counter' in e:
                out[mac] = int(e['counter'].get('bytes', 0))
    return out

def beri_bonus(dev_id, edu_menit: int, bonus_menit: int):
    try:
        payload = json.dumps({'dev_id': dev_id,
                              'edu_menit': edu_menit,
                              'bonus_menit': bonus_menit}).encode()
        req = urllib.request.Request(CLOUD_URL + '/api/edu-bonus',
                                     data=payload, method='POST',
                                     headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def reset_harian_jika_perlu():
    global _tanggal
    td = datetime.now().strftime('%Y-%m-%d')
    if td != _tanggal:
        _tanggal = td
        # Hanya reset progres menit belajar (menuju bonus berikutnya).
        # _edu_prev TIDAK di-clear: counter nft kumulatif (tak reset tengah
        # malam), jadi baseline byte harus tetap kontinu agar delta tetap akurat
        # dan tidak memicu bonus palsu di siklus pertama hari baru.
        _edu_menit.clear()
        log("Hari baru — progres menit belajar di-reset.")

def siklus(interval: int):
    reset_harian_jika_perlu()
    cfg     = ambil_cfg()
    durasi  = int(cfg.get('durasi_belajar_menit', 30))
    bonus_m = int(cfg.get('waktu_bonus_menit', 10))
    edu_now = baca_byte_edukasi()

    for mac, dev_id in list(_mac_dev.items()):
        prev  = _edu_prev[mac]
        curr  = edu_now.get(mac, 0)
        delta = max(0, curr - prev)
        if curr < prev: delta = 0
        _edu_prev[mac] = curr

        # Prime pengamatan pertama → jangan hitung delta (cegah bonus salah
        # saat reward_sistem restart sementara counter nft masih berisi byte lama).
        if mac not in _primed:
            _primed.add(mac)
            continue

        if delta >= EDU_BYTES_AKTIF:
            _edu_menit[mac] += interval / 60.0
            if _edu_menit[mac] >= durasi:
                _edu_menit[mac] -= durasi
                res = beri_bonus(dev_id, durasi, bonus_m)
                sisa = res.get('sisa_hiburan') if res else '?'
                log(f"🎁 {mac}: belajar {durasi}m → +{bonus_m}m hiburan (sisa bonus: {sisa}m)")

def main():
    p = argparse.ArgumentParser(description='Edge Guard — Reward Sistem')
    p.add_argument('--interval','-i', type=int, default=30)
    args = p.parse_args()

    print("=" * 55)
    print("  Edge Guard — Reward Sistem (belajar → bonus hiburan)")
    cfg = ambil_cfg()
    print(f"  Aturan: belajar {cfg.get('durasi_belajar_menit',30)}m "
          f"→ +{cfg.get('waktu_bonus_menit',10)}m hiburan")
    print(f"  Cloud : {CLOUD_URL}")
    print("=" * 55)

    sync_perangkat()
    def sync_loop():
        while True:
            time.sleep(60); sync_perangkat()
    threading.Thread(target=sync_loop, daemon=True).start()

    try:
        while True:
            time.sleep(args.interval)
            try: siklus(args.interval)
            except Exception as e:
                if DEBUG: log(f"siklus error: {e}")
    except KeyboardInterrupt:
        log("Dihentikan.")

if __name__ == '__main__':
    main()
