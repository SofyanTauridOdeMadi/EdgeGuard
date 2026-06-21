"""EdgeGuard — helper nft 'measure' bersama (dipakai kuota_tracker & reward_sistem
yang kini jalan sebagai thread di satu proses pemantau).
- read_measure(ttl): output 'read-measure' di-cache singkat → hindari spawn nft 2x/siklus.
- ensure_measure(mac): pasang counter measure SEKALI per-MAC (bukan tiap siklus),
  lewati MAC kosong/invalid."""
import os, time, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
PORTAL_SH = os.path.join(BASE, 'captive_portal.sh')

def _portal(*args):
    if not os.path.exists(PORTAL_SH): return ''
    try:
        return subprocess.run(['sh', PORTAL_SH, *args], timeout=15, check=False,
                              text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout
    except Exception:
        return ''

_rm = {'ts': 0.0, 'raw': ''}
def read_measure(ttl=4):
    now = time.time()
    if now - _rm['ts'] < ttl and _rm['raw']:
        return _rm['raw']
    raw = _portal('read-measure')
    if raw:
        _rm['ts'] = now; _rm['raw'] = raw
    return raw

_done = set()
def ensure_measure(mac):
    mac = (mac or '').upper()
    if not mac or mac == '00:00:00:00:00:00' or mac in _done:
        return
    _portal('measure-mac', mac)
    _done.add(mac)
