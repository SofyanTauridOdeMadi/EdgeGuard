"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — KUOTA TRACKER (Router OpenWrt)                         ║
║                                                                       ║
║  Siklus tiap N detik (default 60):                                    ║
║    1) Ambil daftar perangkat dari VPS (/api/perangkat)               ║
║    2) Baca byte counter per MAC (iptables/nftables FORWARD)          ║
║    3) Kalau rata-rata Kbps > threshold → +interval/60 menit          ║
║    4) Push kuota_terpakai baru ke VPS (/api/kuota-update)            ║
║    5) Kalau kuota habis → trigger blokir (sh aturan_firewall.sh)     ║
║    6) Kalau orang tua tambah waktu (kuota_terpakai turun) → buka    ║
║                                                                       ║
║  Jalankan:                                                            ║
║    python3 kuota_tracker.py                                          ║
║    python3 kuota_tracker.py --interval 30 --kbps-aktif 8             ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time, argparse, subprocess, threading
import urllib.request, urllib.error
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import CLOUD_URL, HTTP_TIMEOUT, KUOTA_INTERVAL, KBPS_AKTIF, DEBUG

ROOT        = os.path.dirname(BASE)
FIREWALL_SH = os.path.join(BASE, 'aturan_firewall.sh')

# ═══════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════
_state = {
    'devs':       [],
    'devs_ts':    0,
    'bytes_prev': defaultdict(lambda: 0),
    'habis_set':  set(),       # MAC yg sudah di-blokir karena habis
    'sesi':       defaultdict(float),
    'lock':       threading.Lock(),
}
DEVS_TTL = 30   # detik

# ═══════════════════════════════════════════════════════════════════════════
# AMBIL DAFTAR PERANGKAT dari VPS
# ═══════════════════════════════════════════════════════════════════════════
def ambil_perangkat():
    now = time.time()
    with _state['lock']:
        if now - _state['devs_ts'] < DEVS_TTL and _state['devs']:
            return _state['devs']
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/perangkat',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode())
        with _state['lock']:
            _state['devs']    = data.get('perangkat', [])
            _state['devs_ts'] = now
        return _state['devs']
    except Exception:
        return _state['devs'] or []

# ═══════════════════════════════════════════════════════════════════════════
# SETUP & READ iptables counter per MAC
# ═══════════════════════════════════════════════════════════════════════════
def setup_counter(macs: list):
    """Pasang rule kosong (-j RETURN) per MAC di chain FORWARD agar
    kita bisa baca byte-counter-nya. Idempoten."""
    for mac in macs:
        try:
            subprocess.run(
                ['iptables','-C','FORWARD','-m','mac','--mac-source',mac,'-j','RETURN'],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            subprocess.run(
                ['iptables','-I','FORWARD','-m','mac','--mac-source',mac,'-j','RETURN'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def baca_bytes(macs: list) -> dict:
    """Return {mac_upper: total_bytes_seenInForwardSince_setup}."""
    out = {m.upper(): 0 for m in macs}
    try:
        res = subprocess.check_output(
            ['iptables','-L','FORWARD','-v','-n','-x'],
            timeout=5, text=True, stderr=subprocess.DEVNULL)
        for line in res.split('\n'):
            if 'MAC' not in line.upper(): continue
            for tok in line.split():
                if len(tok) == 17 and tok.count(':') == 5:
                    mac_u = tok.upper()
                    if mac_u in out:
                        # bytes adalah kolom ke-2 (setelah pkts)
                        parts = line.split()
                        try: out[mac_u] += int(parts[1])
                        except (ValueError, IndexError): pass
                    break
    except Exception as e:
        if DEBUG: print(f"[kuota] baca_bytes err: {e}")
    return out

# ═══════════════════════════════════════════════════════════════════════════
# PUSH UPDATE ke VPS
# ═══════════════════════════════════════════════════════════════════════════
def push_kuota(dev_id, kuota_terpakai: int) -> bool:
    try:
        payload = json.dumps({'dev_id': dev_id,
                              'kuota_terpakai': kuota_terpakai}).encode()
        req = urllib.request.Request(
            CLOUD_URL + '/api/kuota-update',
            data=payload,
            headers={'Content-Type':'application/json'},
            method='POST')
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode()).get('status') == 'ok'
    except Exception: return False

# ═══════════════════════════════════════════════════════════════════════════
# FIREWALL TRIGGER  (kuota habis → jeda, ditambah → lanjutkan)
# ═══════════════════════════════════════════════════════════════════════════
def fw_jeda(mac: str):     _sh('jeda', mac)
def fw_lanjut(mac: str):   _sh('lanjutkan', mac)
def _sh(*args):
    if not os.path.exists(FIREWALL_SH): return
    subprocess.run(['sh', FIREWALL_SH, *args],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=5, check=False)

# ═══════════════════════════════════════════════════════════════════════════
# SIKLUS UTAMA
# ═══════════════════════════════════════════════════════════════════════════
def siklus(interval: int, kbps_th: float):
    devs = ambil_perangkat()
    if not devs: return
    macs = [d['mac'].upper() for d in devs if d.get('mac')]
    if not macs: return

    setup_counter(macs)
    bytes_now = baca_bytes(macs)

    for dev in devs:
        mac = (dev.get('mac') or '').upper()
        if not mac: continue
        dev_id  = dev.get('id')
        nama    = dev.get('nama', mac)
        jeda    = bool(dev.get('jeda', 0))
        kH      = int(dev.get('kuota_harian', 120))
        kU      = int(dev.get('kuota_terpakai', 0))

        if jeda:
            _state['habis_set'].discard(mac)
            continue

        prev   = _state['bytes_prev'][mac]
        curr   = bytes_now.get(mac, 0)
        delta  = max(0, curr - prev)
        if curr < prev: delta = 0     # counter reset (router reboot)
        _state['bytes_prev'][mac] = curr

        kbps = (delta * 8) / (interval * 1000)
        if kbps >= kbps_th:
            tambah_menit = interval / 60.0
            kU = min(kH, int(kU + tambah_menit + 0.5))
            _state['sesi'][mac] += tambah_menit
            push_kuota(dev_id, kU)
            ts = datetime.now().strftime('%H:%M:%S')
            print(f"[{ts}] {nama:14s} +{tambah_menit:.2f}m | "
                  f"{kU}/{kH}m | {kbps:.1f} Kbps")

        # Kuota habis → blokir (TANPA notif otomatis).
        # Notif Telegram untuk kasus ini hanya dikirim VPS saat anak benar-benar
        # menekan "Minta Izin" di captive portal (/minta-izin), bukan otomatis
        # ketika kuota menyentuh nol — sesuai 3 kejadian notifikasi yang diminta.
        if kU >= kH and mac not in _state['habis_set']:
            _state['habis_set'].add(mac)
            fw_jeda(mac)
            log(f"⏹  KUOTA HABIS — {nama} dijeda")
        elif kU < kH and mac in _state['habis_set']:
            # Orang tua sudah tambahkan waktu → buka
            _state['habis_set'].discard(mac)
            fw_lanjut(mac)
            log(f"▶  KUOTA DIISI — {nama} dibuka")

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[KuotaTracker {ts}] {msg}")

def main():
    p = argparse.ArgumentParser(description='Edge Guard — Kuota Tracker')
    p.add_argument('--interval','-i', type=int, default=KUOTA_INTERVAL)
    p.add_argument('--kbps-aktif','-k', type=float, default=KBPS_AKTIF)
    args = p.parse_args()

    print("=" * 55)
    print("  Edge Guard — Kuota Tracker")
    print(f"  Interval  : {args.interval} detik")
    print(f"  Threshold : {args.kbps_aktif} Kbps")
    print(f"  Cloud URL : {CLOUD_URL}")
    print("=" * 55)

    if hasattr(os, 'geteuid') and os.geteuid() != 0:
        print("⚠️  Butuh root untuk iptables")
        sys.exit(1)

    log("Sinkronisasi perangkat awal...")
    ambil_perangkat()

    cycle = 0
    try:
        while True:
            time.sleep(args.interval)
            cycle += 1
            siklus(args.interval, args.kbps_aktif)
    except KeyboardInterrupt:
        log("Dihentikan.")

if __name__ == '__main__':
    main()
