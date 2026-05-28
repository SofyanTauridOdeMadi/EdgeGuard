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
from config import CLOUD_URL, HEARTBEAT, HTTP_TIMEOUT, DEBUG


def baca_arp():
    """Return list of (ip, mac_upper) dari /proc/net/arp.
    Skip MAC 00:00:00:00:00:00 dan IP yang tidak resolved."""
    out = []
    try:
        with open('/proc/net/arp') as f:
            lines = f.read().strip().split('\n')[1:]   # skip header
        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            ip   = parts[0]
            mac  = parts[3].upper()
            flag = parts[2]
            # flag 0x0 = invalid/incomplete; hanya ambil yg 0x2 (resolved)
            if mac in ('00:00:00:00:00:00', '') or flag == '0x0':
                continue
            out.append((ip, mac))
    except FileNotFoundError:
        # Bukan di OpenWrt — coba `arp -n` (untuk dev di Mac/Linux)
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
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            return data.get('status') == 'ok'
    except urllib.error.URLError:
        return False
    except Exception as e:
        if DEBUG: print(f"[Heartbeat] kirim error: {e}")
        return False


def loop():
    print(f"[Heartbeat] Mulai, interval={HEARTBEAT}d → {CLOUD_URL}")
    while True:
        try:
            macs = baca_arp()
            sent  = sum(1 for ip, mac in macs if kirim(mac, ip))
            ts = datetime.now().strftime('%H:%M:%S')
            print(f"[Heartbeat {ts}] {sent}/{len(macs)} MAC dikirim")
        except Exception as e:
            print(f"[Heartbeat] loop error: {e}")
        time.sleep(HEARTBEAT)


if __name__ == '__main__':
    loop()
