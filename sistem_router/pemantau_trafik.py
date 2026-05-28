"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — PEMANTAU TRAFIK (Router OpenWrt)                       ║
║                                                                       ║
║  Inti sistem realtime:                                                ║
║   1) Capture SNI dari TLS ClientHello (tshark, fallback tcpdump)     ║
║   2) Map IP source → MAC via /proc/net/arp                            ║
║   3) Klasifikasi domain (klasifikasi_ai.putuskan)                    ║
║   4) Eksekusi firewall jika perlu (aturan_firewall.sh)               ║
║   5) Push log ke VPS (/api/log)                                      ║
║                                                                       ║
║  Jalankan:                                                            ║
║    python3 pemantau_trafik.py                                         ║
║    python3 pemantau_trafik.py --interface br-lan --debug              ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, re, time, json, subprocess, threading, argparse
import urllib.request, urllib.error
from datetime import datetime
from collections import OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import CLOUD_URL, IFACE as IFACE_DEFAULT, HTTP_TIMEOUT, DEBUG as DEBUG_DEFAULT
from klasifikasi_ai import putuskan, load_model

# ─── Konfigurasi runtime ──────────────────────────────────────────────────
IFACE     = IFACE_DEFAULT
PORT      = 443
DEBUG     = DEBUG_DEFAULT
MAX_CACHE = 2000
CACHE_TTL = 300                                  # 5 menit
FIREWALL_SH = os.path.join(BASE, 'aturan_firewall.sh')

# ═══════════════════════════════════════════════════════════════════════════
# ARP CACHE (IP → MAC)
# ═══════════════════════════════════════════════════════════════════════════
_arp_cache    = {}
_arp_cache_ts = 0

def baca_arp_table() -> dict:
    """Cache 60 detik. Return {ip: mac_upper}."""
    global _arp_cache, _arp_cache_ts
    if time.time() - _arp_cache_ts < 60 and _arp_cache:
        return _arp_cache
    hasil = {}
    try:
        with open('/proc/net/arp') as f:
            lines = f.read().strip().split('\n')[1:]
        for line in lines:
            parts = line.split()
            if len(parts) >= 4 and parts[3] not in ('00:00:00:00:00:00', ''):
                hasil[parts[0]] = parts[3].upper()
    except FileNotFoundError:
        try:
            res = subprocess.check_output(['arp','-n'], timeout=2, text=True)
            for line in res.split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 3 and ':' in parts[2]:
                    hasil[parts[0]] = parts[2].upper()
        except Exception:
            pass
    except Exception:
        pass
    _arp_cache    = hasil
    _arp_cache_ts = time.time()
    return hasil

# ═══════════════════════════════════════════════════════════════════════════
# PERANGKAT (MAC → nama anak) — diambil dari VPS
# ═══════════════════════════════════════════════════════════════════════════
_perangkat_cache    = {}
_perangkat_cache_ts = 0

def refresh_perangkat():
    """GET /api/perangkat → cache {mac: {nama, id, label}}."""
    global _perangkat_cache, _perangkat_cache_ts
    try:
        req = urllib.request.Request(CLOUD_URL + '/api/perangkat',
                                     headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode())
        c = {}
        for d in data.get('perangkat', []):
            mac = (d.get('mac') or '').upper()
            if mac:
                c[mac] = {'nama':d.get('nama') or mac, 'id':d.get('id', ''),
                          'label':d.get('label') or d.get('nama') or mac}
        _perangkat_cache    = c
        _perangkat_cache_ts = time.time()
    except Exception:
        pass

def nama_perangkat(mac: str) -> str:
    mac_u = (mac or '').upper()
    if time.time() - _perangkat_cache_ts > 60 or not _perangkat_cache:
        refresh_perangkat()
    e = _perangkat_cache.get(mac_u)
    return e['nama'] if e else mac_u

# ═══════════════════════════════════════════════════════════════════════════
# CACHE DOMAIN (skip duplikat dalam 5 menit per (domain, mac))
# ═══════════════════════════════════════════════════════════════════════════
class DomainCache:
    def __init__(self, maxsize=MAX_CACHE, ttl=CACHE_TTL):
        self._store = OrderedDict()
        self.maxsize = maxsize; self.ttl = ttl
        self.hits = 0; self.misses = 0
    def get(self, key):
        if key in self._store:
            entry, ts = self._store[key]
            if time.time() - ts < self.ttl:
                self.hits += 1; return entry
            del self._store[key]
        self.misses += 1; return None
    def set(self, key, val):
        if key in self._store: del self._store[key]
        elif len(self._store) >= self.maxsize: self._store.popitem(last=False)
        self._store[key] = (val, time.time())

cache = DomainCache()

# ═══════════════════════════════════════════════════════════════════════════
# PUSH LOG ke VPS  (/api/log)
# ═══════════════════════════════════════════════════════════════════════════
def kirim_log(keputusan: dict, perangkat: str, mac: str):
    try:
        payload = json.dumps({
            'domain':     keputusan['domain'],
            'kategori':   keputusan.get('kategori','unknown'),
            'status':     'diblokir' if keputusan['aksi']=='blokir' else 'diizinkan',
            'alasan':     keputusan.get('alasan',''),
            'confidence': keputusan.get('confidence', 0),
            'perangkat':  perangkat,
            'mac':        mac,
        }).encode()
        req = urllib.request.Request(
            CLOUD_URL + '/api/log',
            data=payload,
            headers={'Content-Type':'application/json'},
            method='POST')
        urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
    except Exception as e:
        if DEBUG: print(f"[push] gagal: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# EKSEKUSI FIREWALL
# ═══════════════════════════════════════════════════════════════════════════
def fw_blokir(domain: str):
    if os.path.exists(FIREWALL_SH):
        subprocess.run(['sh', FIREWALL_SH, 'blokir', domain],
                       timeout=5, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ═══════════════════════════════════════════════════════════════════════════
# PROSES SATU DOMAIN  (entry-point dari capture)
# ═══════════════════════════════════════════════════════════════════════════
_SKIP = {'.local','localhost','.arpa','broadcasthost','.internal',
         'router.asus.com','dlp.openwrt.pool.ntp.org'}

def tangani(domain: str, ip_src: str = '', mac_src: str = ''):
    domain = (domain or '').lower().strip()
    if not domain or len(domain) < 4 or '.' not in domain: return
    if any(s in domain for s in _SKIP): return

    # Resolve MAC jika belum
    if not mac_src and ip_src:
        mac_src = baca_arp_table().get(ip_src, '')

    key = (domain, mac_src)
    cached = cache.get(key)
    if cached:
        if DEBUG: print(f"  [cache] {domain} → {cached}")
        return

    nama = nama_perangkat(mac_src) if mac_src else (ip_src or 'unknown')
    keputusan = putuskan(domain, mac_src)
    cache.set(key, keputusan['aksi'])

    # Eksekusi firewall + log
    if keputusan['aksi'] == 'blokir':
        fw_blokir(domain)
        ic = '🚫'
    else:
        ic = '✅'
    kirim_log(keputusan, nama, mac_src)

    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {ic} {nama:14s} {domain:40s} "
          f"({keputusan.get('alasan','')}, {keputusan.get('confidence',0)}%)")

# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE — TSHARK (utama)
# ═══════════════════════════════════════════════════════════════════════════
def capture_tshark(iface: str):
    cmd = [
        'tshark', '-i', iface, '-l',
        '-Y', f'tls.handshake.extensions_server_name and tcp.dstport=={PORT}',
        '-T', 'fields',
        '-e', 'ip.src', '-e', 'eth.src',
        '-e', 'tls.handshake.extensions_server_name',
    ]
    if DEBUG: print(f"[tshark] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    print(f"[EdgeGuard] Memantau SNI via tshark ({iface})...")
    try:
        for line in proc.stdout:
            parts = line.strip().split('\t')
            if len(parts) >= 3 and parts[2].strip():
                ip_src  = parts[0].strip()
                mac_src = parts[1].strip().upper().replace('-', ':')
                # SNI bisa banyak dipisah koma, ambil yang pertama
                domain  = parts[2].strip().split(',')[0]
                tangani(domain, ip_src, mac_src)
    except KeyboardInterrupt: pass
    finally: proc.terminate()

# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE — TCPDUMP (fallback, parse SNI dari raw TLS)
# ═══════════════════════════════════════════════════════════════════════════
_RE_SNI = re.compile(
    r'(?<!\d)(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)'
    r'+(?:com|net|org|id|co|io|info|biz|gov|edu|ac|uk|us|au|de|jp|'
    r'fr|br|in|sg|my|xyz|cc|tv|me)(?!\w)', re.I)
_RE_IP  = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\.\d+ > ')

def capture_tcpdump(iface: str):
    cmd = [
        'tcpdump', '-i', iface, '-A', '-l', '-nn',
        f'tcp port {PORT} and (tcp[((tcp[12:1] & 0xf0) >> 2):1] = 0x16)',
    ]
    if DEBUG: print(f"[tcpdump] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    print(f"[EdgeGuard] Memantau via tcpdump fallback ({iface})...")
    ip_curr = ''
    try:
        for line in proc.stdout:
            m_ip = _RE_IP.search(line)
            if m_ip: ip_curr = m_ip.group(1)
            for d in _RE_SNI.findall(line.lower()):
                if len(d) > 6: tangani(d, ip_curr)
    except KeyboardInterrupt: pass
    finally: proc.terminate()

# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE — DNS (tshark UDP/53 + UDP/853, optional 2nd thread)
#   Berguna saat anak akses domain via plain DNS (Android sebagian)
# ═══════════════════════════════════════════════════════════════════════════
def capture_dns(iface: str):
    cmd = [
        'tshark', '-i', iface, '-l',
        '-Y', 'dns.flags.response == 0',
        '-T', 'fields',
        '-e', 'ip.src', '-e', 'eth.src', '-e', 'dns.qry.name',
    ]
    if DEBUG: print(f"[tshark-dns] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    try:
        for line in proc.stdout:
            parts = line.strip().split('\t')
            if len(parts) >= 3 and parts[2].strip():
                ip_src  = parts[0].strip()
                mac_src = parts[1].strip().upper().replace('-', ':')
                domain  = parts[2].strip().rstrip('.')
                tangani(domain, ip_src, mac_src)
    except KeyboardInterrupt: pass
    finally: proc.terminate()

# ═══════════════════════════════════════════════════════════════════════════
# STATS LOOP
# ═══════════════════════════════════════════════════════════════════════════
def stats_loop():
    while True:
        time.sleep(300)
        print(f"\n[Stats] Cache: {len(cache._store)} domain | "
              f"Hits: {cache.hits} | Misses: {cache.misses} | "
              f"{datetime.now().strftime('%H:%M')}\n")

def tool_ada(nama):
    try:
        subprocess.run(['which', nama], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception: return False

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    global DEBUG, IFACE
    p = argparse.ArgumentParser(description='Edge Guard — Pemantau Trafik')
    p.add_argument('--interface','-i', default=IFACE, help=f'(default: {IFACE})')
    p.add_argument('--debug','-d', action='store_true')
    p.add_argument('--with-dns', action='store_true',
                   help='Aktifkan capture DNS sebagai pendukung SNI')
    args = p.parse_args()
    IFACE = args.interface
    DEBUG = args.debug or DEBUG

    print("=" * 60)
    print("  Edge Guard — Pemantau Trafik")
    print(f"  Interface : {IFACE}  | Port: {PORT}")
    print(f"  Cloud URL : {CLOUD_URL}")
    print(f"  Debug     : {'Ya' if DEBUG else 'Tidak'}")
    print("=" * 60)

    if hasattr(os, 'geteuid') and os.geteuid() != 0:
        print("⚠️  Butuh root untuk sniff & iptables — jalankan via sudo")
        sys.exit(1)

    # Load model AI (fail fast)
    try: load_model()
    except FileNotFoundError as e:
        print(f"\n❌ {e}"); sys.exit(1)

    # Thread statistik
    threading.Thread(target=stats_loop, daemon=True).start()

    # Thread heartbeat (push status MAC ke VPS)
    try:
        from heartbeat import loop as heartbeat_loop
        threading.Thread(target=heartbeat_loop, daemon=True, name='heartbeat').start()
        print("[EdgeGuard] Heartbeat thread aktif.")
    except Exception as e:
        print(f"[EdgeGuard] Heartbeat tidak aktif: {e}")

    # Thread DNS (opsional)
    if args.with_dns and tool_ada('tshark'):
        threading.Thread(target=capture_dns, args=(IFACE,),
                         daemon=True, name='dns').start()
        print("[EdgeGuard] DNS capture thread aktif.")

    # Refresh perangkat pertama kali
    refresh_perangkat()

    print()
    if tool_ada('tshark'):
        capture_tshark(IFACE)
    elif tool_ada('tcpdump'):
        print("⚠️  tshark tidak ada → pakai tcpdump (kurang akurat)")
        print("    Install: opkg update && opkg install tshark")
        capture_tcpdump(IFACE)
    else:
        print("❌ tshark/tcpdump tidak ditemukan."); sys.exit(1)

if __name__ == '__main__':
    main()
