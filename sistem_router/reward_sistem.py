"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — REWARD SISTEM (Penjadwalan Cerdas)                    ║
║                                                                       ║
║  Konsep: anak yang belajar (akses kategori 'edukasi') dapat hadiah    ║
║          waktu hiburan otomatis.                                      ║
║                                                                       ║
║  Algoritma sederhana:                                                 ║
║   • Pantau log dari klasifikasi_ai (via shared cache, in-memory)     ║
║   • Edu N menit (cfg.durasi_belajar_menit, default 30) → buka        ║
║     akses 'eg_hiburan' selama M menit (cfg.waktu_bonus_menit, 10)    ║
║   • Maksimum bonus per hari = cfg.batas_bonus_menit (60)             ║
║                                                                       ║
║  Karena kita TIDAK simpan log lokal (langsung push ke VPS), reward    ║
║  ini bekerja in-memory selama proses jalan. Reset tiap ganti hari.   ║
║                                                                       ║
║  Jalankan:                                                            ║
║    python3 reward_sistem.py                                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time, threading, subprocess, argparse
import urllib.request
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import CLOUD_URL, HTTP_TIMEOUT, CONFIG_TTL, DEBUG

FIREWALL_SH = os.path.join(BASE, 'aturan_firewall.sh')

# ─── default cfg fallback ────────────────────────────────────────────────
DEFAULT_CFG = {
    'durasi_belajar_menit': 30,
    'waktu_bonus_menit':    10,
    'batas_bonus_menit':    60,
}

_cfg_cache = {}
_cfg_ts    = 0

def ambil_cfg() -> dict:
    global _cfg_cache, _cfg_ts
    now = time.time()
    if now - _cfg_ts < CONFIG_TTL and _cfg_cache:
        return _cfg_cache
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/config',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            _cfg_cache = json.loads(r.read().decode())
        _cfg_ts = now
        return _cfg_cache
    except Exception:
        return _cfg_cache or DEFAULT_CFG

# ═══════════════════════════════════════════════════════════════════════════
# STATE per-MAC (in-memory)
# ═══════════════════════════════════════════════════════════════════════════
class State:
    __slots__ = ['mac','nama','detik_belajar','bonus_tersisa','bonus_harian',
                 'mode','tanggal']
    def __init__(self, mac, nama=''):
        self.mac, self.nama = mac, nama
        self.detik_belajar  = 0.0
        self.bonus_tersisa  = 0.0
        self.bonus_harian   = 0.0
        self.mode           = 'normal'    # 'normal' | 'bonus'
        self.tanggal        = datetime.now().strftime('%Y-%m-%d')
    def reset_jika_hari_baru(self):
        td = datetime.now().strftime('%Y-%m-%d')
        if self.tanggal != td:
            self.detik_belajar = 0.0
            self.bonus_harian  = 0.0
            self.bonus_tersisa = 0.0
            self.mode          = 'normal'
            self.tanggal       = td

_perangkat: dict = {}     # {mac: State}
_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════════
# Firewall helpers
# ═══════════════════════════════════════════════════════════════════════════
def buka_hiburan(mac, nama, menit):
    if os.path.exists(FIREWALL_SH):
        subprocess.run(['sh', FIREWALL_SH, 'buka-hiburan-untuk', mac],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5, check=False)
    log(f"🎉 BONUS DIBUKA: {nama} ({mac}) — {menit:.1f}m hiburan")
    push_event(mac, nama, 'bonus_mulai', menit)

def tutup_hiburan(mac, nama):
    if os.path.exists(FIREWALL_SH):
        subprocess.run(['sh', FIREWALL_SH, 'blokir-hiburan-untuk', mac],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5, check=False)
    log(f"⏹  BONUS SELESAI: {nama}")
    push_event(mac, nama, 'bonus_selesai', 0)

# ═══════════════════════════════════════════════════════════════════════════
# Push event ke VPS (sebagai log_akses dengan alasan='reward_*')
# ═══════════════════════════════════════════════════════════════════════════
def push_event(mac, nama, event, menit):
    try:
        payload = json.dumps({
            'domain':     f'[Reward] {event}',
            'kategori':   'edukasi',
            'status':     'diizinkan',
            'alasan':     f'reward_{event}',
            'perangkat':  nama,
            'mac':        mac,
            'confidence': menit,
        }).encode()
        req = urllib.request.Request(CLOUD_URL + '/api/log',
                                     data=payload, method='POST',
                                     headers={'Content-Type':'application/json'})
        urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
    except Exception: pass

# ═══════════════════════════════════════════════════════════════════════════
# Sync daftar perangkat awal
# ═══════════════════════════════════════════════════════════════════════════
def sync_perangkat():
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/perangkat',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode())
        with _lock:
            for d in data.get('perangkat', []):
                mac = (d.get('mac') or '').upper()
                if mac and mac not in _perangkat:
                    _perangkat[mac] = State(mac, d.get('nama', mac))
                    log(f"Perangkat baru: {d.get('nama')} ({mac})")
    except Exception: pass

# ═══════════════════════════════════════════════════════════════════════════
# Catat akses edu — dipanggil oleh modul lain (atau via API hook future)
# ═══════════════════════════════════════════════════════════════════════════
def tambah_belajar(mac: str, nama: str, detik: float):
    """Public function: catat 'detik' menit aktivitas edukasi untuk MAC ini."""
    mac_u = mac.upper()
    cfg = ambil_cfg()
    durasi = int(cfg.get('durasi_belajar_menit', 30)) * 60
    bonus  = int(cfg.get('waktu_bonus_menit', 10))   * 60
    batas  = int(cfg.get('batas_bonus_menit', 60))   * 60

    with _lock:
        st = _perangkat.setdefault(mac_u, State(mac_u, nama))
        st.reset_jika_hari_baru()
        if st.mode == 'normal':
            st.detik_belajar += detik
            if (st.detik_belajar >= durasi
                    and st.bonus_harian < batas):
                aktual = min(bonus, batas - st.bonus_harian)
                st.mode = 'bonus'
                st.bonus_tersisa  = aktual
                st.bonus_harian  += aktual
                st.detik_belajar  = 0
                buka_hiburan(mac_u, st.nama, aktual / 60)

def tick(interval_detik: int):
    """Kurangi timer bonus untuk semua perangkat dalam mode 'bonus'."""
    with _lock:
        for mac, st in _perangkat.items():
            st.reset_jika_hari_baru()
            if st.mode == 'bonus':
                st.bonus_tersisa -= interval_detik
                if st.bonus_tersisa <= 0:
                    st.bonus_tersisa = 0
                    st.mode = 'normal'
                    tutup_hiburan(mac, st.nama)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[Reward {ts}] {msg}")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN — jalan sebagai daemon yang men-tick tiap N detik
# ═══════════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(description='Edge Guard — Reward Sistem')
    p.add_argument('--interval','-i', type=int, default=10)
    args = p.parse_args()

    print("=" * 55)
    print("  Edge Guard — Reward Sistem (Penjadwalan Cerdas)")
    print(f"  Interval  : {args.interval} detik")
    print(f"  Cloud URL : {CLOUD_URL}")
    cfg = ambil_cfg()
    print(f"  Config    : belajar {cfg.get('durasi_belajar_menit',30)}m "
          f"→ bonus {cfg.get('waktu_bonus_menit',10)}m "
          f"(max {cfg.get('batas_bonus_menit',60)}m/hari)")
    print("=" * 55)
    sync_perangkat()

    # Thread re-sync perangkat 60s
    def sync_loop():
        while True:
            time.sleep(60); sync_perangkat()
    threading.Thread(target=sync_loop, daemon=True).start()

    try:
        while True:
            time.sleep(args.interval)
            tick(args.interval)
    except KeyboardInterrupt:
        log("Dihentikan.")

if __name__ == '__main__':
    main()
