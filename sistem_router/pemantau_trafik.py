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
import os, sys, re, time, json, subprocess, threading, argparse, shutil
import urllib.request, urllib.error
from datetime import datetime
from collections import OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import CLOUD_URL, IFACE as IFACE_DEFAULT, HTTP_TIMEOUT, DEBUG as DEBUG_DEFAULT, mk_ssl_ctx
from klasifikasi_ai import putuskan, load_model

# ─── Konfigurasi runtime ──────────────────────────────────────────────────
IFACE     = IFACE_DEFAULT
PORT      = 443
DEBUG     = DEBUG_DEFAULT
MAX_CACHE = 2000
CACHE_TTL = 300                                  # 5 menit
FIREWALL_SH = os.path.join(BASE, 'aturan_firewall.sh')

# ─── Captive portal sinkhole ─────────────────────────────────────────────
PORTAL_IP = '192.168.1.2'

def _sinkhole_conf_path() -> str:
    """Cari path konfigurasi dnsmasq sinkhole yang benar (OpenWrt vs generic)."""
    import glob
    dirs = glob.glob('/tmp/dnsmasq.*.d')
    d = dirs[0] if dirs else '/tmp/dnsmasq.d'
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'eg_sinkhole.conf')

# Set domain negatif yang terdeteksi oleh AI (in-memory, persisten selama proses hidup)
_negatif_domains: set = set()

def _muat_sinkhole_awal():
    """Baca file sinkhole yang sudah ada ke _negatif_domains saat startup.
    Mencegah domain lama hilang selama 60 detik pertama sebelum sinkhole_sync_loop berjalan."""
    global _negatif_domains
    conf = _sinkhole_conf_path()
    try:
        with open(conf) as f:
            for line in f:
                line = line.strip()
                if line.startswith('address=/'):
                    parts = line.split('/')
                    if len(parts) >= 2 and parts[1]:
                        _negatif_domains.add(parts[1])
        if _negatif_domains and DEBUG:
            print(f"[sinkhole] dimuat dari file: {len(_negatif_domains)} domain")
    except FileNotFoundError:
        pass
    except Exception as e:
        if DEBUG: print(f"[sinkhole] load awal gagal: {e}")

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
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
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

# ── Fallback: hostname dari DHCP lease OpenWrt (mis. "iPhone", "Mac") ──────
_dhcp_mac   = {}      # {mac_upper: hostname}
_dhcp_ip    = {}      # {ip: hostname}
_dhcp_ts    = 0

def _muat_dhcp():
    """Cache 60 detik. Parse /tmp/dhcp.leases sekali → map by MAC & by IP.
    Format lease: <expiry> <mac> <ip> <hostname> <clientid>."""
    global _dhcp_mac, _dhcp_ip, _dhcp_ts
    if time.time() - _dhcp_ts < 60 and (_dhcp_mac or _dhcp_ip):
        return
    mac_map, ip_map = {}, {}
    try:
        with open('/tmp/dhcp.leases') as f:
            for line in f:
                p = line.split()
                if len(p) >= 4 and p[3] != '*':
                    mac_map[p[1].upper()] = p[3]
                    ip_map[p[2]]          = p[3]
    except Exception:
        pass
    _dhcp_mac, _dhcp_ip, _dhcp_ts = mac_map, ip_map, time.time()

def baca_dhcp_hostname(mac: str) -> str:
    _muat_dhcp()
    return _dhcp_mac.get((mac or '').upper(), '')

def hostname_dari_ip(ip: str) -> str:
    _muat_dhcp()
    return _dhcp_ip.get(ip or '', '')

def nama_perangkat(mac: str) -> str:
    """Prioritas nama: (1) terdaftar di VPS → nama anak,
    (2) hostname DHCP router (iPhone/Mac/dll), (3) MAC mentah."""
    mac_u = (mac or '').upper()
    if not mac_u:
        return 'unknown'
    if time.time() - _perangkat_cache_ts > 60 or not _perangkat_cache:
        refresh_perangkat()
    e = _perangkat_cache.get(mac_u)
    if e:
        return e['nama']
    # Fallback hostname DHCP (mis. "iPhone", "Mac")
    host = baca_dhcp_hostname(mac_u)
    return host if host else mac_u

def perangkat_terdaftar(mac: str) -> bool:
    """True bila MAC terdaftar sebagai perangkat anak di VPS.
    Fallback: jika VPS tidak bisa dicapai dan cache kosong, monitor SEMUA
    perangkat agar perlindungan tetap berjalan saat VPS offline."""
    mac_u = (mac or '').upper()
    if not mac_u:
        return False
    if time.time() - _perangkat_cache_ts > 60 or not _perangkat_cache:
        refresh_perangkat()
    # Jika cache masih kosong setelah refresh (VPS unreachable), awasi semua
    if not _perangkat_cache:
        return True
    return mac_u in _perangkat_cache

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
        urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx())
    except Exception as e:
        if DEBUG: print(f"[push] gagal: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# EKSEKUSI FIREWALL
# ═══════════════════════════════════════════════════════════════════════════
PORTAL_SH = os.path.join(BASE, 'captive_portal.sh')

def _tulis_sinkhole():
    """Tulis ulang file dnsmasq sinkhole dari _negatif_domains lalu reload dnsmasq."""
    conf = _sinkhole_conf_path()
    try:
        with open(conf, 'w') as f:
            for d in sorted(_negatif_domains):
                f.write(f"address=/{d}/{PORTAL_IP}\n")
        # HUP = reload conf tanpa restart penuh
        subprocess.run(['killall', '-HUP', 'dnsmasq'], timeout=3, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        if DEBUG: print(f"[sinkhole] tulis gagal: {e}")

def fw_blokir(domain: str):
    """Domain negatif → DNS sinkhole → captive portal.
    nftables di captive_portal.sh sudah menangani:
      • HTTP  (80)  ke PORTAL_IP → DNAT ke portal_server.py (halaman blokir)
      • HTTPS (443) ke PORTAL_IP → DROP senyap (hindari cert warning)
    Dengan sinkhole, IP lama yang ter-cache di browser otomatis digantikan
    saat TTL habis. Hard-drop via ipset tidak dipakai lagi karena tidak
    menampilkan halaman portal."""
    if domain in _negatif_domains:
        return
    _negatif_domains.add(domain)
    _tulis_sinkhole()
    if DEBUG: print(f"[sinkhole] +{domain} ({len(_negatif_domains)} total)")

def _resolve_ips(domain: str):
    """Resolve A-record domain → list IP (pakai resolver router, cepat krn cache)."""
    try:
        import socket
        _, _, ips = socket.gethostbyname_ex(domain)
        return [ip for ip in ips if not ip.startswith('127.')]
    except Exception:
        return []

def tandai_kategori_ip(domain: str, kategori: str):
    """Daftarkan IP domain ke nft set sesuai kategori (utk enforcement &
    pengukuran kuota). EDUKASI → edukasi_ip; HIBURAN → hiburan_ip.
    Negatif/infra/unknown tidak ditandai."""
    if kategori not in ('hiburan', 'edukasi'):
        return
    if not os.path.exists(PORTAL_SH):
        return
    ips = _resolve_ips(domain)
    if not ips:
        return
    sub = 'add-hiburan' if kategori == 'hiburan' else 'add-edukasi'
    try:
        subprocess.run(['sh', PORTAL_SH, sub, *ips], timeout=8, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

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

    # ── HANYA AWASI PERANGKAT TERDAFTAR ────────────────────────────────────
    # Perangkat yang tidak tersimpan di database VPS (mis. HP tamu, laptop
    # ortu) diabaikan total: tidak diklasifikasi, tidak diblokir, tidak
    # di-log, tidak notifikasi.
    if not perangkat_terdaftar(mac_src):
        if DEBUG:
            print(f"  [skip] {domain} ← perangkat tak terdaftar ({mac_src or ip_src or '?'})")
        return

    key = (domain, mac_src)
    cached = cache.get(key)
    if cached:
        if DEBUG: print(f"  [cache] {domain} → {cached}")
        return

    nama = nama_perangkat(mac_src)
    keputusan = putuskan(domain, mac_src)
    cache.set(key, keputusan['aksi'])
    kat = keputusan.get('kategori', 'unknown')

    # Eksekusi firewall + log
    if keputusan['aksi'] == 'blokir':
        fw_blokir(domain)
        ic = '🚫'
    else:
        # Tandai IP domain ke set kategori (hiburan→kuota, edukasi→reward).
        # Hanya untuk yang diizinkan; enforcement hiburan per-MAC dilakukan
        # kuota_tracker. Edukasi & infra tetap selalu lolos.
        tandai_kategori_ip(domain, kat)
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
        # ── RINGAN: capture-filter BPF (disaring kernel) ──────────────────
        # Hanya paket TLS *handshake* (record type 0x16) ke port 443 yang
        # diteruskan ke tshark. Tanpa ini, tshark men-dissect SEMUA trafik
        # lalu baru menyaring dgn -Y → boros CPU di router (mis. AX3000T).
        # Dgn -f, kernel membuang paket tak relevan duluan → beban jauh turun.
        '-f', f'tcp dst port {PORT} and (tcp[((tcp[12:1] & 0xf0) >> 2):1] = 0x16)',
        # Display-filter: pertajam ke ClientHello yang benar2 punya SNI.
        '-Y', f'tls.handshake.extensions_server_name and tcp.dstport=={PORT}',
        '-T', 'fields',
        '-e', 'ip.src', '-e', 'eth.src',
        '-e', 'tls.handshake.extensions_server_name',
    ]
    if DEBUG: print(f"[tshark] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            errors='replace', bufsize=1)
    print(f"[EdgeGuard] Memantau SNI via tshark ({iface})...")
    try:
        for line in iter(proc.stdout.readline, ''):
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
                            stderr=subprocess.DEVNULL, text=True,
                            errors='replace', bufsize=1)
    print(f"[EdgeGuard] Memantau via tcpdump fallback ({iface})...")
    ip_curr = ''
    try:
        for line in iter(proc.stdout.readline, ''):
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
                            stderr=subprocess.DEVNULL, text=True,
                            errors='replace', bufsize=1)
    try:
        for line in iter(proc.stdout.readline, ''):
            parts = line.strip().split('\t')
            if len(parts) >= 3 and parts[2].strip():
                ip_src  = parts[0].strip()
                mac_src = parts[1].strip().upper().replace('-', ':')
                domain  = parts[2].strip().rstrip('.')
                tangani(domain, ip_src, mac_src)
    except KeyboardInterrupt: pass
    finally: proc.terminate()

# ═══════════════════════════════════════════════════════════════════════════
# SINKHOLE SYNC — captive portal (domain blacklist → dnsmasq → halaman blokir)
# ═══════════════════════════════════════════════════════════════════════════
_sinkhole_vps_terakhir: set = set()   # blacklist manual dari VPS (terakhir diambil)

def sinkhole_sync_loop():
    """Tiap 60 dtk: gabungkan blacklist manual VPS + domain AI-detected negatif
    → tulis ke dnsmasq sinkhole. Selalu tulis ulang agar file tetap konsisten
    dengan set in-memory (mencegah gap jika file diubah dari luar).
    Jika VPS tidak bisa dicapai, sinkhole tetap berjalan dengan data lokal AI."""
    global _negatif_domains, _sinkhole_vps_terakhir
    from klasifikasi_ai import ambil_config
    while True:
        try:
            cfg = ambil_config()
            vps_hitam = set(
                d.strip().lower()
                for d in cfg.get('daftar_hitam', []) if d.strip()
            )
            _sinkhole_vps_terakhir = vps_hitam
            _negatif_domains |= vps_hitam   # merge, jangan hapus deteksi AI
        except Exception as e:
            if DEBUG: print(f"[sinkhole] VPS sync gagal (pakai data lokal): {e}")
        # Tulis ulang file setiap siklus untuk konsistensi
        _tulis_sinkhole()
        if DEBUG:
            print(f"[sinkhole] sinkhole diperbarui: {len(_negatif_domains)} domain")
        time.sleep(60)

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
    """Cek ketersediaan binary via PATH (pure-Python).
    CATATAN: jangan pakai `which` — di OpenWrt/BusyBox tertentu `which`
    mengembalikan exit≠0 walau binary ADA (mis. tcpdump di /usr/bin),
    sehingga engine capture salah pilih. shutil.which() andal & tak
    bergantung pada applet `which`."""
    return shutil.which(nama) is not None

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

    # Muat sinkhole domain yang sudah ada (hindari gap saat restart)
    _muat_sinkhole_awal()

    # Sync VPS blacklist segera (tidak menunggu 60 detik siklus pertama)
    try:
        from klasifikasi_ai import ambil_config
        cfg = ambil_config()
        vps_hitam = set(d.strip().lower()
                        for d in cfg.get('daftar_hitam', []) if d.strip())
        if vps_hitam:
            _negatif_domains.update(vps_hitam)
            _tulis_sinkhole()
            print(f"[EdgeGuard] Sinkhole init: {len(_negatif_domains)} domain")
    except Exception as e:
        print(f"[EdgeGuard] Sinkhole init (VPS fallback: {e})")

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

    # Thread sinkhole sync (captive portal: merge VPS blacklist + AI detections)
    threading.Thread(target=sinkhole_sync_loop,
                     daemon=True, name='sinkhole').start()
    print("[EdgeGuard] Sinkhole sync thread aktif (portal router-local).")

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
