#!/usr/bin/env python3
"""
Edge Guard — Portal Server (router-local, tanpa ketergantungan VPS)

Menggantikan uhttpd 'egportal'. Menangani:
  GET  /*           → sajikan portal/index.html
  POST /minta-izin  → kirim notifikasi ke Telegram langsung (jika token ada)
                      atau teruskan ke VPS sebagai fallback

Konfigurasi via /etc/edgeguard.env:
  EG_PORTAL_HOST  (default: 192.168.1.1)
  EG_PORTAL_PORT  (default: 8880)
  EG_TG_TOKEN     — bot token Telegram (opsional, untuk kirim langsung)
  EG_TG_CHAT      — chat/group ID Telegram (opsional)
  EG_CLOUD_URL    — URL VPS untuk fallback (default: https://202.10.34.171)
"""
import os, sys, json, ssl, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request

BASE        = os.path.dirname(os.path.abspath(__file__))
DOCROOT     = os.path.join(BASE, 'portal')

PORTAL_HOST = os.environ.get('EG_PORTAL_HOST', '192.168.1.1')
PORTAL_PORT = int(os.environ.get('EG_PORTAL_PORT', '8880'))
CLOUD_URL   = os.environ.get('EG_CLOUD_URL', 'https://202.10.34.171').rstrip('/')
TG_TOKEN    = os.environ.get('EG_TG_TOKEN', '')
TG_CHAT     = os.environ.get('EG_TG_CHAT', '')
DEBUG       = bool(int(os.environ.get('EG_DEBUG', '0')))

def _ssl_ctx():
    """SSLContext unverified untuk self-signed cert VPS, atau None jika HTTP."""
    if CLOUD_URL.startswith('https://'):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        return ctx
    return None


# ═══════════════════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════════════════
class PortalHandler(BaseHTTPRequestHandler):
    server_version = 'EdgeGuard-Portal/1.0'
    sys_version    = ''

    def log_message(self, fmt, *args):
        if DEBUG:
            print(f"[portal] {self.address_string()} - {fmt % args}")

    # ── Helpers ──────────────────────────────────────────────────
    def _send_html(self):
        html_path = os.path.join(DOCROOT, 'index.html')
        try:
            with open(html_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f'Portal error: {e}')

    def _send_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            raw    = self.rfile.read(length) if length > 0 else b'{}'
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}

    # ── Verbs ─────────────────────────────────────────────────────
    # URL yang dicek OS untuk deteksi captive portal
    _CAPTIVE_PATHS = {
        '/generate_204',                     # Android / Chrome
        '/hotspot-detect.html',              # iOS / macOS
        '/library/test/success.html',        # iOS lama
        '/connecttest.txt',                  # Windows
        '/ncsi.txt',                         # Windows lama
        '/success.txt',                      # macOS
        '/canonical.html',                   # Ubuntu
    }

    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/')
        if path == '/status':
            self._send_status()
        elif path in self._CAPTIVE_PATHS or path == '':
            # OS captive portal check → redirect ke portal agar notifikasi muncul
            self._redirect_portal()
        else:
            self._send_html()

    def _redirect_portal(self):
        """Redirect OS captive portal check ke halaman portal.
        OS mendeteksi respons tidak sesuai → muncul notifikasi 'Login ke jaringan'."""
        target = f'http://{PORTAL_HOST}:{PORTAL_PORT}/'
        self.send_response(302)
        self.send_header('Location', target)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _send_status(self):
        """Kembalikan JSON alasan blokir untuk perangkat yang meminta."""
        client_ip  = self.client_address[0]
        host_header = (self.headers.get('Host') or '').split(':')[0].strip()

        # Cek apakah Host header adalah domain sinkhole (bukan IP)
        import re as _re
        is_ip = bool(_re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host_header))
        domain = host_header if not is_ip else ''

        # Apakah domain ini ada di sinkhole? → negatif
        alasan = 'negatif' if (domain and _domain_in_sinkhole(domain)) else 'kuota'

        # Kalau bukan sinkhole, cek status perangkat dari VPS
        if alasan != 'negatif':
            mac = _hostname_dari_ip(client_ip)   # coba DHCP
            alasan = _cek_alasan_vps(client_ip, mac) or 'kuota'

        self._send_json(200, {'alasan': alasan, 'domain': domain})

    def do_OPTIONS(self):
        # CORS preflight — browser bisa POST dari "domain yang diblokir"
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if self.path.rstrip('/') == '/minta-izin':
            data      = self._read_body()
            domain    = (data.get('domain') or 'tidak diketahui').strip()
            perangkat = data.get('perangkat', '')
            client_ip = self.client_address[0]

            # Cari nama perangkat dari DHCP jika belum diisi portal
            if not perangkat:
                perangkat = _hostname_dari_ip(client_ip) or client_ip

            threading.Thread(
                target=_kirim_notif,
                args=(domain, perangkat, client_ip),
                daemon=True
            ).start()

            self._send_json(200, {
                'ok': True,
                'pesan': 'Permintaan terkirim ke orang tua.'
            })
        else:
            self.send_error(404)


# ═══════════════════════════════════════════════════════════════════
# DHCP: IP → hostname perangkat
# ═══════════════════════════════════════════════════════════════════
def _hostname_dari_ip(ip: str) -> str:
    try:
        with open('/tmp/dhcp.leases') as f:
            for line in f:
                p = line.split()
                if len(p) >= 4 and p[2] == ip and p[3] != '*':
                    return p[3]
    except Exception:
        pass
    return ''

def _mac_dari_ip(ip: str) -> str:
    try:
        with open('/proc/net/arp') as f:
            for line in f.read().strip().split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip:
                    mac = parts[3].upper()
                    if mac != '00:00:00:00:00:00':
                        return mac
    except Exception:
        pass
    return ''

def _domain_in_sinkhole(domain: str) -> bool:
    import glob as _glob
    paths = ['/tmp/dnsmasq.d/eg_sinkhole.conf']
    paths += _glob.glob('/tmp/dnsmasq.*.d/eg_sinkhole.conf')
    d = (domain or '').lower()
    if d.startswith('www.'): d = d[4:]
    for p in paths:
        try:
            with open(p) as f:
                for line in f:
                    if ('/' + d + '/') in line:
                        return True
        except Exception:
            pass
    return False

def _cek_alasan_vps(client_ip: str, mac: str = '') -> str:
    mac = mac or _mac_dari_ip(client_ip)
    if not mac:
        return 'kuota'
    try:
        ctx = _ssl_ctx()
        req = urllib.request.Request(
            CLOUD_URL + '/api/perangkat',
            headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=4, context=ctx) as r:
            data = json.loads(r.read().decode())
        for dev in data.get('perangkat', []):
            if (dev.get('mac') or '').upper() == mac.upper():
                if dev.get('jeda'):
                    return 'jeda'
                if dev.get('blokir_jadwal'):
                    return 'jadwal'
                kT = int(dev.get('kuota_harian', 120))
                kU = int(dev.get('kuota_terpakai', 0))
                bonus = int(dev.get('sisa_hiburan', 0))
                if kU >= (kT + bonus):
                    return 'kuota'
                return 'kuota'
    except Exception:
        pass
    return 'kuota'


# ═══════════════════════════════════════════════════════════════════
# NOTIFIKASI
# ═══════════════════════════════════════════════════════════════════
def _kirim_notif(domain: str, perangkat: str, client_ip: str):
    """
    Urutan pengiriman:
    1. Langsung ke Telegram (jika EG_TG_TOKEN & EG_TG_CHAT diset di env router)
    2. Teruskan ke VPS /minta-izin sebagai fallback (server-to-server, tanpa CORS)
    3. Log lokal jika keduanya gagal
    """
    if DEBUG:
        print(f"[portal] minta-izin: domain={domain} perangkat={perangkat} ip={client_ip}")

    # ── 1. Telegram langsung ──────────────────────────────────────
    if TG_TOKEN and TG_CHAT:
        try:
            pesan = (
                f"🙋 <b>Permintaan Izin Akses</b>\n\n"
                f"👤 Perangkat : {perangkat}\n"
                f"🌐 Domain    : <code>{domain}</code>\n\n"
                f"Anak meminta izin mengakses situs yang diblokir.\n"
                f"Buka dashboard Edge Guard untuk merespons."
            )
            payload = json.dumps({
                'chat_id':    TG_CHAT,
                'text':       pesan,
                'parse_mode': 'HTML'
            }).encode()
            req = urllib.request.Request(
                f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=10)
            if DEBUG: print(f"[portal] Telegram terkirim ✓")
            return
        except Exception as e:
            if DEBUG: print(f"[portal] Telegram langsung gagal: {e}")

    # ── 2. Teruskan ke VPS (server-to-server) ────────────────────
    try:
        payload = json.dumps({
            'domain':    domain,
            'perangkat': perangkat
        }).encode()
        req = urllib.request.Request(
            CLOUD_URL + '/minta-izin',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=6, context=_ssl_ctx())
        if DEBUG: print(f"[portal] Diteruskan ke VPS ✓")
        return
    except Exception as e:
        if DEBUG: print(f"[portal] VPS fallback gagal: {e}")

    # ── 3. Log lokal ──────────────────────────────────────────────
    print(f"[portal] Permintaan izin DICATAT LOKAL — {domain} dari {perangkat} ({client_ip})")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    server = HTTPServer((PORTAL_HOST, PORTAL_PORT), PortalHandler)
    print(f"[EdgeGuard] Portal server aktif: http://{PORTAL_HOST}:{PORTAL_PORT}")
    print(f"[EdgeGuard] Telegram langsung : {'Ya' if TG_TOKEN else 'Tidak (fallback VPS)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
