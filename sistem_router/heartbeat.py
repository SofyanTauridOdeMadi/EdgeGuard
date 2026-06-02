"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — HEARTBEAT (Router → VPS)                              ║
║                                                                      ║
║  Setiap N detik (default 60), baca ARP table di OpenWrt              ║
║  (/proc/net/arp) → kirim ke VPS satu request per MAC aktif:          ║
║                                                                      ║
║    POST {EG_CLOUD_URL}/api/heartbeat  {"mac": "...", "ip": "..."}    ║
║                                                                      ║
║  Dashboard akan menandai perangkat 'online' jika last_seen ≤ ambang  ║
║  (default 120 detik di konfigurasi VPS).                             ║
║                                                                      ║
║  Jalankan sebagai daemon (init.d) atau standalone:                   ║
║    python3 heartbeat.py                                              ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time
import urllib.request, urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CLOUD_URL, HEARTBEAT, HTTP_TIMEOUT, DEBUG, mk_ssl_ctx


def baca_arp():
    """Return list of (ip, mac_upper) dari /proc/net/arp."""
    out = []
    try:
        with open('/proc/net/arp') as f:
            lines = f.read().strip().split('\n')[1:]
        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            ip   = parts[0]
            mac  = parts[3].upper()
            flag = parts[2]
            if mac in ('00:00:00:00:00:00', '') or flag == '0x0':
                continue
            out.append((ip, mac))
    except FileNotFoundError:
        try:
            import subprocess
            res = subprocess.check_output(['arp', '-n'], timeout=2, text=True)
            for line in res.split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 3 and ':' in parts[2]:
                    out.append((parts[0], parts[2].upper()))
        except Exception:
            pass
    except Exception as e:
        if DEBUG: print(f"[Heartbeat] baca_arp error: {e}")
    return out


def baca_dhcp_clients():
    """Baca /tmp/dhcp.leases → list device {mac, ip, hostname}.
    Hanya menggunakan DHCP leases agar tidak ikut membaca perangkat
    dari jaringan upstream (mesh/ISP) yang muncul di ARP table.
    Format lease: <expiry> <mac> <ip> <hostname> <clientid>"""
    clients = {}
    try:
        with open('/tmp/dhcp.leases') as f:
            for line in f:
                p = line.strip().split()
                if len(p) < 4:
                    continue
                mac      = p[1].upper()
                ip       = p[2]
                hostname = p[3] if p[3] != '*' else ''
                if mac and mac != '00:00:00:00:00:00':
                    clients[mac] = {'mac': mac, 'ip': ip, 'hostname': hostname}
    except Exception:
        pass
    return list(clients.values())


def kirim(mac: str, ip: str = '') -> bool:
    """POST /api/heartbeat dengan {mac, ip}. Return True jika 200 OK."""
    try:
        payload = json.dumps({'mac': mac, 'ip': ip}).encode()
        req = urllib.request.Request(
            CLOUD_URL + '/api/heartbeat',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            data = json.loads(r.read().decode())
            return data.get('status') == 'ok'
    except urllib.error.URLError:
        return False
    except Exception as e:
        if DEBUG: print(f"[Heartbeat] kirim error: {e}")
        return False


def kirim_dhcp_clients(clients: list) -> bool:
    """POST /api/dhcp-clients — kirim semua client DHCP sekaligus ke VPS."""
    if not clients:
        return True
    try:
        payload = json.dumps({'clients': clients}).encode()
        req = urllib.request.Request(
            CLOUD_URL + '/api/dhcp-clients',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            return json.loads(r.read().decode()).get('status') == 'ok'
    except Exception as e:
        if DEBUG: print(f"[Heartbeat] kirim_dhcp error: {e}")
        return False


def loop():
    print(f"[Heartbeat] Mulai, interval={HEARTBEAT}d → {CLOUD_URL}")
    _tick = 0
    while True:
        try:
            macs = baca_arp()
            sent = sum(1 for ip, mac in macs if kirim(mac, ip))
            ts   = datetime.now().strftime('%H:%M:%S')
            print(f"[Heartbeat {ts}] {sent}/{len(macs)} MAC dikirim")
            # Kirim DHCP clients setiap 3 tick (± 3 menit) agar tidak terlalu sering
            _tick += 1
            if _tick % 3 == 1:
                clients = baca_dhcp_clients()
                kirim_dhcp_clients(clients)
                if DEBUG: print(f"[Heartbeat] DHCP clients: {len(clients)} dikirim")
        except Exception as e:
            print(f"[Heartbeat] loop error: {e}")
        time.sleep(HEARTBEAT)


if __name__ == '__main__':
    loop()
