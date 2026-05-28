#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  Edge Guard — Start Script                                       ║
# ║  Jalankan: bash start.sh [dashboard|trainer|router|all]         ║
# ╚══════════════════════════════════════════════════════════════════╝

BASE="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-dashboard}"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[EdgeGuard]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo ""
echo "  🛡️  Edge Guard — Smart Parental Control"
echo ""

case "$MODE" in

  # ── VPS: Dashboard + MySQL ──────────────────────────────────────
  dashboard)
    log "Memulai Cloud Dashboard (VPS)..."
    python3 -c "import flask, pymysql" 2>/dev/null || {
      warn "Dependensi belum terinstall. Install sekarang?"
      read -r -p "  [y/N] " yn
      [[ "$yn" =~ ^[Yy]$ ]] && pip install flask pymysql || err "flask + pymysql diperlukan"
    }
    # Cek koneksi MySQL
    python3 -c "
import pymysql, os
try:
    c = pymysql.connect(
        host=os.environ.get('DB_HOST','127.0.0.1'),
        user=os.environ.get('DB_USER','edgeguard'),
        password=os.environ.get('DB_PASS','edgeguard123'),
        db=os.environ.get('DB_NAME','edgeguard'))
    c.close(); print('MySQL OK')
except Exception as e:
    print(f'MySQL ERROR: {e}')
    print('Jalankan dulu: mysql -u root -p < dashboard/schema.sql')
    exit(1)
" || exit 1
    log "Dashboard → http://0.0.0.0:8080"
    cd "$BASE/dashboard" && python3 api_dashboard.py
    ;;

  # ── Laptop: Training model AI ───────────────────────────────────
  trainer)
    log "Memulai pelatihan model AI (Laptop)..."
    python3 -c "import sklearn, numpy" 2>/dev/null || {
      warn "scikit-learn belum ada. Install?"
      read -r -p "  [y/N] " yn
      [[ "$yn" =~ ^[Yy]$ ]] && pip install scikit-learn numpy || err "scikit-learn diperlukan"
    }
    cd "$BASE/model_ai"
    python3 pelatihan_model.py
    log "Selesai! Salin model_export.json ke router:"
    log "  scp model_ai/model_export.json root@<IP_ROUTER>:/root/edgeguard/model_ai/"
    ;;

  # ── Router OpenWrt ──────────────────────────────────────────────
  router)
    [ "$(id -u)" -eq 0 ] || err "Butuh root di router."
    export EG_IFACE="${EG_IFACE:-${EDGEGUARD_IFACE:-br-lan}}"
    export EG_CLOUD_URL="${EG_CLOUD_URL:-${CLOUD_URL:-http://localhost:8080}}"
    log "Inisialisasi firewall..."
    sh "$BASE/sistem_router/aturan_firewall.sh" init
    log "Memulai pemantau trafik + heartbeat (interface: $EG_IFACE)..."
    python3 "$BASE/sistem_router/pemantau_trafik.py" \
      --interface "$EG_IFACE" >> /tmp/eg_pemantau.log 2>&1 &
    log "Memulai kuota tracker..."
    python3 "$BASE/sistem_router/kuota_tracker.py" \
      >> /tmp/eg_kuota.log 2>&1 &
    log "Memulai reward sistem..."
    python3 "$BASE/sistem_router/reward_sistem.py" \
      >> /tmp/eg_reward.log 2>&1 &
    log "Semua service router aktif. Log: /tmp/eg_*.log"
    log "Cloud → $EG_CLOUD_URL"
    ;;

  stop)
    log "Menghentikan router services..."
    pkill -f pemantau_trafik.py 2>/dev/null && log "pemantau dihentikan"
    pkill -f kuota_tracker.py   2>/dev/null && log "kuota dihentikan"
    pkill -f reward_sistem.py   2>/dev/null && log "reward dihentikan"
    pkill -f heartbeat.py       2>/dev/null && log "heartbeat dihentikan"
    sh "$BASE/sistem_router/aturan_firewall.sh" flush 2>/dev/null
    ;;

  *)
    echo "Penggunaan: bash start.sh [dashboard|trainer|router|stop]"
    echo ""
    echo "  dashboard  — Jalankan web dashboard di VPS (port 8080)"
    echo "  trainer    — Latih model AI di laptop (satu kali)"
    echo "  router     — Jalankan semua service di router OpenWrt"
    echo "  stop       — Hentikan semua service router"
    ;;
esac
