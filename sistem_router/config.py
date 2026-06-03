"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — Konfigurasi Router (shared antar script)               ║
║                                                                       ║
║  Default sudah cocok untuk pengembangan lokal (Mac/Laptop dev).      ║
║  Override saat deploy ke router via /etc/edgeguard.env:               ║
║                                                                       ║
║    export EG_CLOUD_URL='https://edgeguard.my.id'                      ║
║    export EG_IFACE='br-lan'                                           ║
║    export EG_HEARTBEAT=60                                             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import ssl as _ssl

# ── Endpoint VPS Cloud Dashboard ──────────────────────────────────────────
CLOUD_URL    = os.environ.get('EG_CLOUD_URL', 'https://edgeguard.my.id').rstrip('/')

# ── Network interface yang akan disniff ───────────────────────────────────
IFACE        = os.environ.get('EG_IFACE',     'br-lan')

# ── Interval & timeout ────────────────────────────────────────────────────
HEARTBEAT     = int(os.environ.get('EG_HEARTBEAT',     '60'))   # detik
CONFIG_TTL    = int(os.environ.get('EG_CONFIG_TTL',    '30'))
HTTP_TIMEOUT  = int(os.environ.get('EG_HTTP_TIMEOUT',  '4'))
KUOTA_INTERVAL= int(os.environ.get('EG_KUOTA_INTERVAL','60'))   # detik antar sampling

# ── Threshold "perangkat aktif" untuk perhitungan kuota ───────────────────
KBPS_AKTIF    = float(os.environ.get('EG_KBPS_AKTIF',  '10'))

# ── Debug ────────────────────────────────────────────────────────────────
DEBUG         = bool(int(os.environ.get('EG_DEBUG',    '0')))

# ── SSL context ───────────────────────────────────────────────────────────
def mk_ssl_ctx():
    """Return SSLContext yang sesuai:
    - Domain resmi (edgeguard.my.id) → verifikasi penuh (Let's Encrypt valid)
    - IP langsung (self-signed)       → skip verifikasi
    - HTTP                            → None
    """
    if not CLOUD_URL.startswith('https://'):
        return None
    host = CLOUD_URL.replace('https://', '').split('/')[0].split(':')[0]
    # Jika host adalah IP → self-signed, skip verify
    import re as _re
    if _re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host):
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = _ssl.CERT_NONE
        return ctx
    # Domain → verifikasi sertifikat normal (Let's Encrypt)
    return _ssl.create_default_context()
