"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — Konfigurasi Router (shared antar script)               ║
║                                                                       ║
║  Default sudah cocok untuk pengembangan lokal (Mac/Laptop dev).      ║
║  Override saat deploy ke router via /etc/edgeguard.env:               ║
║                                                                       ║
║    export EG_CLOUD_URL='https://202.10.34.171'                        ║
║    export EG_IFACE='br-lan'                                           ║
║    export EG_HEARTBEAT=60                                             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import ssl as _ssl

# ── Endpoint VPS Cloud Dashboard ──────────────────────────────────────────
CLOUD_URL    = os.environ.get('EG_CLOUD_URL', 'https://202.10.34.171').rstrip('/')

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

# ── SSL context untuk HTTPS self-signed cert di VPS ──────────────────────
def mk_ssl_ctx():
    """Return SSLContext unverified untuk self-signed cert, atau None jika HTTP."""
    if CLOUD_URL.startswith('https://'):
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = _ssl.CERT_NONE
        return ctx
    return None
