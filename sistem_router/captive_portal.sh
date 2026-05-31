#!/bin/sh
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  EDGE GUARD — CAPTIVE PORTAL (DNS sinkhole → halaman blokir)         ║
# ║                                                                       ║
# ║  Mekanisme (TIDAK mengganggu LuCI/uhttpd utama):                     ║
# ║   1. IP alias 192.168.1.2 di br-lan  → IP khusus portal.             ║
# ║   2. dnsmasq sinkhole: domain blacklist → 192.168.1.2.              ║
# ║   3. uhttpd instance "egportal" (TLS bawaan) di 192.168.1.1:8880/8843║
# ║      docroot /root/edgeguard/sistem_router/portal (catch-all blokir).║
# ║   4. nft DNAT: 192.168.1.2:80→:8880, :443→:8843.                    ║
# ║                                                                       ║
# ║  Pakai:                                                               ║
# ║    sh captive_portal.sh init                 # pasang portal         ║
# ║    sh captive_portal.sh sinkhole <d1> <d2>…  # set domain blacklist  ║
# ║    sh captive_portal.sh status               # cek kondisi           ║
# ║    sh captive_portal.sh teardown             # bongkar semua         ║
# ╚══════════════════════════════════════════════════════════════════════╝

PORTAL_IP="192.168.1.2"
LAN_IP="192.168.1.1"
HTTP_PORT="8880"
HTTPS_PORT="8843"
IFACE="br-lan"
BASE="$(cd "$(dirname "$0")" && pwd)"
DOCROOT="$BASE/portal"
# dnsmasq OpenWrt memakai confdir ber-suffix instance (mis.
# /tmp/dnsmasq.cfg01411c.d). Deteksi otomatis; fallback ke /tmp/dnsmasq.d.
SINKHOLE_DIR="$(ls -d /tmp/dnsmasq.*.d 2>/dev/null | head -1)"
[ -z "$SINKHOLE_DIR" ] && SINKHOLE_DIR="/tmp/dnsmasq.d"
SINKHOLE_CONF="$SINKHOLE_DIR/eg_sinkhole.conf"
NFT_TABLE="ip eg_portal"

log() { echo "[portal] $*"; }

# ─── 1. IP ALIAS ───────────────────────────────────────────────────────────
pasang_alias() {
    if ip addr show "$IFACE" | grep -q "$PORTAL_IP/"; then
        log "alias $PORTAL_IP sudah ada"
    else
        ip addr add "$PORTAL_IP/24" dev "$IFACE" 2>/dev/null \
            && log "alias $PORTAL_IP ditambahkan ke $IFACE" \
            || log "gagal menambah alias (mungkin sudah ada)"
    fi
}

# ─── 2. UHTTPD INSTANCE PORTAL ─────────────────────────────────────────────
pasang_uhttpd() {
    # Catch-all: index + error_page → index.html (apa pun path → blokir)
    uci -q delete uhttpd.egportal
    uci set uhttpd.egportal=uhttpd
    uci add_list uhttpd.egportal.listen_http="${LAN_IP}:${HTTP_PORT}"
    uci add_list uhttpd.egportal.listen_https="${LAN_IP}:${HTTPS_PORT}"
    uci set uhttpd.egportal.home="$DOCROOT"
    uci set uhttpd.egportal.cert='/etc/uhttpd.crt'
    uci set uhttpd.egportal.key='/etc/uhttpd.key'
    uci set uhttpd.egportal.index_page='index.html'
    uci set uhttpd.egportal.error_page='/index.html'
    uci set uhttpd.egportal.redirect_https='0'
    uci set uhttpd.egportal.max_requests='5'
    uci commit uhttpd
    /etc/init.d/uhttpd restart >/dev/null 2>&1
    log "uhttpd instance 'egportal' aktif di ${LAN_IP}:${HTTP_PORT}/${HTTPS_PORT}"
}

# ─── 3. NFT DNAT 80/443 → portal ───────────────────────────────────────────
pasang_nft() {
    nft delete table $NFT_TABLE 2>/dev/null
    nft -f - <<EOF
table $NFT_TABLE {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        ip daddr $PORTAL_IP tcp dport 80  dnat ip to ${LAN_IP}:${HTTP_PORT}
        ip daddr $PORTAL_IP tcp dport 443 dnat ip to ${LAN_IP}:${HTTPS_PORT}
    }
}
EOF
    [ $? -eq 0 ] && log "nft DNAT 80→$HTTP_PORT, 443→$HTTPS_PORT siap" \
                 || log "gagal pasang nft DNAT"
}

# ─── 4. DNSMASQ SINKHOLE ───────────────────────────────────────────────────
set_sinkhole() {
    mkdir -p "$SINKHOLE_DIR"
    : > "$SINKHOLE_CONF"
    n=0
    for d in "$@"; do
        [ -z "$d" ] && continue
        # address=/domain/IP → domain & semua subdomain → portal
        echo "address=/$d/$PORTAL_IP" >> "$SINKHOLE_CONF"
        n=$((n+1))
    done
    log "$n domain di-sinkhole → $PORTAL_IP"
    /etc/init.d/dnsmasq restart >/dev/null 2>&1
    log "dnsmasq di-reload"
}

# ─── STATUS ────────────────────────────────────────────────────────────────
status() {
    echo "── Edge Guard Captive Portal ──"
    echo -n "alias $PORTAL_IP : "; ip addr show "$IFACE" | grep -q "$PORTAL_IP/" && echo "ADA" || echo "TIDAK"
    echo -n "uhttpd egportal  : "; pgrep -f "egportal\|${LAN_IP}:${HTTP_PORT}" >/dev/null 2>&1 && echo "?" ; uci -q get uhttpd.egportal >/dev/null && echo "TERKONFIG" || echo "TIDAK"
    echo -n "nft DNAT         : "; nft list table $NFT_TABLE >/dev/null 2>&1 && echo "ADA" || echo "TIDAK"
    echo -n "sinkhole domains : "; [ -f "$SINKHOLE_CONF" ] && wc -l < "$SINKHOLE_CONF" || echo 0
    echo "isi sinkhole:"; cat "$SINKHOLE_CONF" 2>/dev/null | sed 's/^/  /'
}

# ─── TEARDOWN ──────────────────────────────────────────────────────────────
teardown() {
    nft delete table $NFT_TABLE 2>/dev/null && log "nft table dihapus"
    rm -f "$SINKHOLE_CONF" && /etc/init.d/dnsmasq restart >/dev/null 2>&1 && log "sinkhole dihapus + dnsmasq reload"
    uci -q delete uhttpd.egportal && uci commit uhttpd && /etc/init.d/uhttpd restart >/dev/null 2>&1 && log "uhttpd egportal dihapus"
    ip addr del "$PORTAL_IP/24" dev "$IFACE" 2>/dev/null && log "alias $PORTAL_IP dihapus"
}

case "${1:-}" in
    init)     pasang_alias; pasang_uhttpd; pasang_nft ;;
    sinkhole) shift; set_sinkhole "$@" ;;
    status)   status ;;
    teardown) teardown ;;
    *) echo "Usage: $0 {init|sinkhole <domain...>|status|teardown}"; exit 1 ;;
esac
