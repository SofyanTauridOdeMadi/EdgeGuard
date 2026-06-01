#!/bin/sh
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  EDGE GUARD — Wrapper Firewall OpenWrt (iptables + ipset)            ║
# ║                                                                       ║
# ║  Subcommand:                                                          ║
# ║    init                       — buat ipset & chain awal               ║
# ║    blokir <domain>            — resolve domain → tambah IP ke set     ║
# ║    izinkan <domain>           — hapus IP domain dari set              ║
# ║    jeda <MAC>                 — blokir SEMUA trafik dari MAC ini      ║
# ║    lanjutkan <MAC>            — buka kembali MAC ini                  ║
# ║    blokir-hiburan-untuk <MAC> — drop akses set 'eg_hiburan' utk MAC   ║
# ║    buka-hiburan-untuk <MAC>   — hapus drop di atas                    ║
# ║    flush                      — bersihkan semua rule EdgeGuard        ║
# ║    status                     — tampilkan kondisi saat ini            ║
# ║                                                                       ║
# ║  Dipakai oleh: klasifikasi_ai.py, reward_sistem.py, kuota_tracker.py ║
# ╚══════════════════════════════════════════════════════════════════════╝

set -e

CMD="$1"; shift || true

# ─── Nama ipset & chain ────────────────────────────────────────────────
SET_BLOKIR="eg_blokir"        # IP terdeteksi negatif → DROP
SET_HIBURAN="eg_hiburan"      # IP situs hiburan → drop saat reward mode
CHAIN="EG_FORWARD"

# ═══════════════════════════════════════════════════════════════════════
# helper
# ═══════════════════════════════════════════════════════════════════════
ada_perintah() { command -v "$1" >/dev/null 2>&1; }

resolve_ips() {
  # Resolve domain ke daftar IP (A record). Pakai `nslookup` (busybox) atau `dig`.
  local domain="$1"
  if ada_perintah dig; then
    dig +short A "$domain" 2>/dev/null | grep -E '^[0-9.]+$'
  elif ada_perintah nslookup; then
    nslookup "$domain" 2>/dev/null \
      | awk '/^Address[^:]*: / { print $NF }' \
      | grep -E '^[0-9.]+$' \
      | grep -v '127.0.0.1'
  else
    return 1
  fi
}

# ═══════════════════════════════════════════════════════════════════════
# init — buat ipset + chain & sambungkan ke FORWARD
# ═══════════════════════════════════════════════════════════════════════
init() {
  if ! ada_perintah ipset; then
    echo "[firewall] ⚠️  'ipset' tidak ada — opkg install ipset" >&2
    exit 1
  fi
  if ! ada_perintah iptables; then
    echo "[firewall] ⚠️  'iptables' tidak ada — opkg install iptables" >&2
    exit 1
  fi
  ipset create "$SET_BLOKIR"   hash:ip family inet hashsize 1024 maxelem 65536 -exist
  ipset create "$SET_HIBURAN"  hash:ip family inet hashsize 1024 maxelem 65536 -exist

  iptables -N "$CHAIN" 2>/dev/null || true
  iptables -F "$CHAIN"
  iptables -C FORWARD -j "$CHAIN" 2>/dev/null || iptables -I FORWARD -j "$CHAIN"

  # Default: drop semua trafik tujuan IP di set blokir
  iptables -A "$CHAIN" -m set --match-set "$SET_BLOKIR" dst -j DROP

  echo "[firewall] ✅ init OK (set: $SET_BLOKIR, $SET_HIBURAN | chain: $CHAIN)"
}

# ═══════════════════════════════════════════════════════════════════════
# blokir / izinkan domain
# ═══════════════════════════════════════════════════════════════════════
blokir_domain() {
  local domain="$1"; [ -z "$domain" ] && { echo "Usage: blokir <domain>"; exit 1; }
  local n=0
  for ip in $(resolve_ips "$domain"); do
    ipset add "$SET_BLOKIR" "$ip" -exist
    n=$((n+1))
  done
  echo "[firewall] 🚫 BLOKIR $domain → $n IP ditambahkan ke $SET_BLOKIR"
}

izinkan_domain() {
  local domain="$1"; [ -z "$domain" ] && { echo "Usage: izinkan <domain>"; exit 1; }
  local n=0
  for ip in $(resolve_ips "$domain"); do
    ipset del "$SET_BLOKIR" "$ip" 2>/dev/null && n=$((n+1)) || true
  done
  echo "[firewall] ✅ IZINKAN $domain → $n IP dihapus dari $SET_BLOKIR"
}

# ═══════════════════════════════════════════════════════════════════════
# jeda / lanjutkan per MAC
# ═══════════════════════════════════════════════════════════════════════
# Jeda / lanjutkan kini DELEGASI ke captive_portal.sh: alih-alih DROP total
# (blackout), MAC diarahkan ke halaman portal untuk web (80/443) sehingga anak
# TAHU kenapa aksesnya berhenti; trafik non-web di-DROP. DNS tetap hidup.
PORTAL_SH="$(dirname "$0")/captive_portal.sh"

jeda_mac() {
  local mac="$1"; [ -z "$mac" ] && { echo "Usage: jeda <MAC>"; exit 1; }
  # Enforcement utama (jeda/jadwal/kuota) dilakukan kuota_tracker via
  # captive_portal.sh blok-hiburan. Subcommand ini hanya jalan pintas manual.
  if [ -f "$PORTAL_SH" ]; then
    sh "$PORTAL_SH" blok-hiburan "$mac"
  fi
  echo "[firewall] ⏸  JEDA (hiburan) $mac"
}

lanjutkan_mac() {
  local mac="$1"; [ -z "$mac" ] && { echo "Usage: lanjutkan <MAC>"; exit 1; }
  if [ -f "$PORTAL_SH" ]; then
    sh "$PORTAL_SH" buka-hiburan "$mac"
  fi
  # Bersihkan rule DROP MAC lama (warisan versi blackout sebelumnya)
  while iptables -D "$CHAIN" -m mac --mac-source "$mac" -j DROP 2>/dev/null; do :; done
  echo "[firewall] ▶  LANJUTKAN $mac"
}

# ═══════════════════════════════════════════════════════════════════════
# blokir/buka HIBURAN per MAC (untuk reward sistem)
# ═══════════════════════════════════════════════════════════════════════
blokir_hiburan_untuk() {
  local mac="$1"; [ -z "$mac" ] && { echo "Usage: blokir-hiburan-untuk <MAC>"; exit 1; }
  iptables -C "$CHAIN" -m mac --mac-source "$mac" \
                       -m set --match-set "$SET_HIBURAN" dst -j DROP 2>/dev/null \
    || iptables -I "$CHAIN" 1 -m mac --mac-source "$mac" \
                       -m set --match-set "$SET_HIBURAN" dst -j DROP
  echo "[firewall] 🎬 BLOKIR hiburan utk $mac"
}

buka_hiburan_untuk() {
  local mac="$1"; [ -z "$mac" ] && { echo "Usage: buka-hiburan-untuk <MAC>"; exit 1; }
  while iptables -D "$CHAIN" -m mac --mac-source "$mac" \
                             -m set --match-set "$SET_HIBURAN" dst -j DROP 2>/dev/null; do :; done
  echo "[firewall] 🎉 BUKA hiburan utk $mac"
}

# ═══════════════════════════════════════════════════════════════════════
# flush / status
# ═══════════════════════════════════════════════════════════════════════
flush() {
  iptables -D FORWARD -j "$CHAIN" 2>/dev/null || true
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true
  ipset destroy "$SET_BLOKIR"   2>/dev/null || true
  ipset destroy "$SET_HIBURAN"  2>/dev/null || true
  echo "[firewall] 🧹 Semua rule EdgeGuard dibersihkan."
}

status() {
  echo "═══ ipset ══════════════════════════════════════"
  ipset list "$SET_BLOKIR"  2>/dev/null | head -20 || echo "(set $SET_BLOKIR tidak ada)"
  echo
  ipset list "$SET_HIBURAN" 2>/dev/null | head -10 || echo "(set $SET_HIBURAN tidak ada)"
  echo "═══ iptables $CHAIN ════════════════════════════"
  iptables -L "$CHAIN" -n -v --line-numbers 2>/dev/null || echo "(chain $CHAIN tidak ada)"
}

# ═══════════════════════════════════════════════════════════════════════
case "$CMD" in
  init)                  init ;;
  blokir)                blokir_domain "$@" ;;
  izinkan)               izinkan_domain "$@" ;;
  jeda)                  jeda_mac "$@" ;;
  lanjutkan)             lanjutkan_mac "$@" ;;
  blokir-hiburan-untuk)  blokir_hiburan_untuk "$@" ;;
  buka-hiburan-untuk)    buka_hiburan_untuk "$@" ;;
  flush)                 flush ;;
  status)                status ;;
  *)
    echo "Usage: $0 {init|blokir <dom>|izinkan <dom>|jeda <mac>|lanjutkan <mac>|"
    echo "          blokir-hiburan-untuk <mac>|buka-hiburan-untuk <mac>|flush|status}"
    exit 1
    ;;
esac
