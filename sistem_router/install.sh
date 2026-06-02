#!/bin/sh
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  EDGE GUARD — Installer untuk Router OpenWrt (Xiaomi AX3000T dll.)   ║
# ║                                                                       ║
# ║  Cara pakai (dari laptop):                                            ║
# ║    scp -r sistem_router/ root@<IP_ROUTER>:/root/edgeguard/            ║
# ║    ssh root@<IP_ROUTER>                                               ║
# ║    cd /root/edgeguard/sistem_router                                   ║
# ║    sh install.sh                                                      ║
# ║                                                                       ║
# ║  Yang dipasang:                                                       ║
# ║    1. Dependensi opkg (python3, tshark, ipset, iptables)              ║
# ║    2. /etc/edgeguard.env (config CLOUD_URL + Telegram)                ║
# ║    3. /etc/init.d/edgeguard (autostart 4 daemon)                      ║
# ║    4. Init firewall ipset & chain                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

set -e

BASE="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="/etc/edgeguard.env"
INIT_FILE="/etc/init.d/edgeguard"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { printf "${GREEN}[install]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC}    %s\n" "$*"; }
err()  { printf "${RED}[error]${NC}   %s\n" "$*"; exit 1; }

[ "$(id -u)" -eq 0 ] || err "Jalankan sebagai root: sudo sh install.sh"

# ── 1. Install dependensi opkg ────────────────────────────────────────────
if command -v opkg >/dev/null 2>&1; then
  log "Update package list (opkg update)…"
  opkg update >/dev/null 2>&1 || warn "opkg update gagal — cek koneksi internet"
  for pkg in python3 python3-urllib3 tshark ipset iptables; do
    if opkg list-installed | grep -q "^$pkg "; then
      log "✓ $pkg sudah terpasang"
    else
      log "→ install $pkg"
      opkg install "$pkg" >/dev/null 2>&1 || warn "Gagal install $pkg"
    fi
  done
else
  warn "Bukan OpenWrt (opkg tidak ada) — skip install paket"
fi

# ── 2. Buat /etc/edgeguard.env (skip jika sudah ada) ──────────────────────
if [ ! -f "$ENV_FILE" ]; then
  log "Membuat $ENV_FILE (template)…"
  cat > "$ENV_FILE" <<'EOF'
# ── Edge Guard — Config Router ──────────────────────────────────────────
# Edit nilai di bawah lalu reboot router atau:
#   /etc/init.d/edgeguard restart

# Endpoint VPS Cloud Dashboard
export EG_CLOUD_URL='https://202.10.34.171'

# Network interface LAN (br-lan untuk default OpenWrt)
export EG_IFACE='br-lan'

# Threshold "perangkat aktif" (Kbps)
export EG_KBPS_AKTIF='10'

# Interval (detik)
export EG_HEARTBEAT='60'
export EG_KUOTA_INTERVAL='60'
export EG_CONFIG_TTL='30'

# Debug (1 = verbose)
export EG_DEBUG='0'
EOF
  chmod 600 "$ENV_FILE"
  log "✅ $ENV_FILE dibuat — EDIT EG_CLOUD_URL sesuai milikmu!"
else
  log "✓ $ENV_FILE sudah ada (tidak ditimpa)"
fi

# ── 3. Install init.d script ──────────────────────────────────────────────
log "Memasang $INIT_FILE …"
cp "$BASE/edgeguard.init" "$INIT_FILE"
chmod +x "$INIT_FILE"

if command -v /etc/init.d/edgeguard >/dev/null 2>&1; then
  /etc/init.d/edgeguard enable
  log "✅ Service edgeguard ter-enable di startup"
fi

# ── 4. Init firewall (ipset + chain) ──────────────────────────────────────
log "Inisialisasi firewall (ipset + chain EG_FORWARD)…"
sh "$BASE/aturan_firewall.sh" init || warn "Init firewall gagal — cek log"

# ── 5. Selesai ────────────────────────────────────────────────────────────
log ""
log "════════════════════════════════════════════════════"
log "✅ INSTALASI SELESAI"
log ""
log "Selanjutnya:"
log "  1. Edit $ENV_FILE → set EG_CLOUD_URL"
log "  2. Test klasifikasi:  python3 $BASE/klasifikasi_ai.py youtube.com"
log "  3. Mulai semua daemon: /etc/init.d/edgeguard start"
log "  4. Lihat status:       /etc/init.d/edgeguard status"
log "  5. Lihat log:          tail -f /tmp/eg_*.log"
log "════════════════════════════════════════════════════"
