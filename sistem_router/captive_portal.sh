#!/bin/sh
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  EDGE GUARD — CAPTIVE PORTAL + ENFORCEMENT KATEGORI-AWARE            ║
# ║                                                                       ║
# ║  Prinsip "edge-AI cerdas":                                           ║
# ║   • EDUKASI & INFRA  → SELALU boleh (tak pernah diblokir).           ║
# ║   • NEGATIF          → SELALU blok: DNS sinkhole domain → portal.    ║
# ║   • HIBURAN          → dikontrol per-MAC. MAC masuk 'blok_mac' bila  ║
# ║        dijeda / jam jadwal-blokir / kuota hiburan habis. Efek:       ║
# ║          - HTTP (80) ke situs hiburan → captive portal.             ║
# ║          - HTTPS (443) & lainnya → DROP senyap (tanpa warning cert). ║
# ║        Saat MAC tidak diblok → hiburan jalan normal.                 ║
# ║                                                                       ║
# ║  nft table ip eg_portal:                                             ║
# ║     set hiburan_ip  (timeout) — IP situs hiburan  (diisi pemantau)   ║
# ║     set edukasi_ip  (timeout) — IP situs edukasi  (diisi pemantau)   ║
# ║     set blok_mac              — MAC yg hiburannya sedang dibatasi    ║
# ║     chain measure            — counter byte hiburan/edukasi per MAC  ║
# ║                                                                       ║
# ║  Subcommand: init | sinkhole <dom...> | add-hiburan <ip...> |        ║
# ║   add-edukasi <ip...> | measure-mac <MAC> | read-measure |           ║
# ║   blok-hiburan <MAC> | buka-hiburan <MAC> | status | teardown        ║
# ╚══════════════════════════════════════════════════════════════════════╝

PORTAL_IP="192.168.1.2"
LAN_IP="192.168.1.1"
HTTP_PORT="8880"
HTTPS_PORT="8843"
IFACE="br-lan"
IP_TTL="3h"
BASE="$(cd "$(dirname "$0")" && pwd)"
DOCROOT="$BASE/portal"
NFT_TABLE="ip eg_portal"

SINKHOLE_DIR="$(ls -d /tmp/dnsmasq.*.d 2>/dev/null | head -1)"
[ -z "$SINKHOLE_DIR" ] && SINKHOLE_DIR="/tmp/dnsmasq.d"
SINKHOLE_CONF="$SINKHOLE_DIR/eg_sinkhole.conf"

log() { echo "[portal] $*"; }

# ─── 1. IP ALIAS ───────────────────────────────────────────────────────────
pasang_alias() {
    if ip addr show "$IFACE" | grep -q "$PORTAL_IP/"; then
        log "alias $PORTAL_IP sudah ada"
    else
        ip addr add "$PORTAL_IP/24" dev "$IFACE" 2>/dev/null \
            && log "alias $PORTAL_IP ditambahkan" || log "alias gagal (mungkin sudah ada)"
    fi
}

# ─── 2. PORTAL SERVER (Python, menggantikan uhttpd egportal) ───────────────
pasang_portal_server() {
    # Hentikan instance lama jika ada
    pkill -f 'portal_server\.py' 2>/dev/null || true
    sleep 1
    # Hapus config uhttpd egportal lama + restart uhttpd agar port 8880 bebas
    uci -q delete uhttpd.egportal && uci commit uhttpd 2>/dev/null || true
    /etc/init.d/uhttpd restart >/dev/null 2>&1 || true
    sleep 1

    # Muat env agar EG_TG_TOKEN/EG_TG_CHAT terbaca oleh server
    [ -f /etc/edgeguard.env ] && . /etc/edgeguard.env

    # setsid: buat sesi baru agar proses tidak mati saat shell parent selesai
    setsid python3 "$BASE/portal_server.py" \
        >>/tmp/eg_portal.log 2>&1 &
    sleep 1
    if pgrep -f 'portal_server\.py' >/dev/null 2>&1; then
        log "portal_server.py aktif (${LAN_IP}:${HTTP_PORT})"
    else
        log "⚠️  portal_server.py gagal start — cek /tmp/eg_portal.log"
    fi
}

# ─── 3. NFT: sets + chains ─────────────────────────────────────────────────
pasang_nft() {
    nft delete table $NFT_TABLE 2>/dev/null
    nft -f - <<EOF
table $NFT_TABLE {
    set hiburan_ip {
        type ipv4_addr
        flags timeout
    }
    set edukasi_ip {
        type ipv4_addr
        flags timeout
    }
    set blok_mac {
        type ether_addr
    }
    set jadwal_mac {
        type ether_addr
    }
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        # Paksa semua DNS LAN lewat dnsmasq router (override DNS ISP/Kominfo/DoH).
        ip saddr 192.168.1.0/24 ip daddr != 192.168.1.1 udp dport 53 redirect
        ip saddr 192.168.1.0/24 ip daddr != 192.168.1.1 tcp dport 53 redirect
        # Negatif sinkhole (domain → $PORTAL_IP): HTTP → portal.
        ip daddr $PORTAL_IP tcp dport 80 dnat to ${LAN_IP}:${HTTP_PORT}
        # Jadwal blokir: SEMUA HTTP → portal (informasikan jam istirahat).
        ether saddr @jadwal_mac tcp dport 80 dnat to ${LAN_IP}:${HTTP_PORT}
        # Kuota habis: semua HTTP → portal (agar notif OS muncul & portal tampil).
        ether saddr @blok_mac tcp dport 80 dnat to ${LAN_IP}:${HTTP_PORT}
    }
    chain input {
        type filter hook input priority filter; policy accept;
        # Negatif via sinkhole: HTTPS ke portal-IP → reject cepat
        # (browser langsung tahu ditolak, tidak hang menunggu timeout).
        ip daddr $PORTAL_IP tcp dport 443 reject with tcp reset
    }
    chain measure {
        type filter hook forward priority -10; policy accept;
        # Diisi dinamis (measure-mac): counter byte hiburan & edukasi per MAC.
    }
    chain forward {
        type filter hook forward priority filter; policy accept;
        # Jadwal blokir total: semua trafik dari MAC → drop.
        ether saddr @jadwal_mac counter drop
        # Kuota habis: blokir trafik ke IP hiburan (non-HTTP sudah kena di prerouting).
        ether saddr @blok_mac ip daddr @hiburan_ip counter drop
    }
}
EOF
    [ $? -eq 0 ] && log "nft eg_portal siap (hiburan_ip/edukasi_ip/blok_mac/measure)" \
                 || log "gagal pasang nft"
}

# ─── TANDAI IP per kategori (dipanggil pemantau) ───────────────────────────
_add_ip_to_set() {
    set_name="$1"; shift
    nft list table $NFT_TABLE >/dev/null 2>&1 || pasang_nft
    n=0
    for ip in "$@"; do
        case "$ip" in
            [0-9]*.[0-9]*.[0-9]*.[0-9]*)
                nft add element $NFT_TABLE "$set_name" "{ $ip timeout $IP_TTL }" 2>/dev/null && n=$((n+1)) ;;
        esac
    done
    [ "$n" -gt 0 ] && log "+$n IP → $set_name"
}
add_hiburan() { _add_ip_to_set hiburan_ip "$@"; }
add_edukasi() { _add_ip_to_set edukasi_ip "$@"; }

# ─── COUNTER pemakaian per MAC (idempoten) ─────────────────────────────────
measure_mac() {
    mac="$1"; [ -z "$mac" ] && return 1
    nft list table $NFT_TABLE >/dev/null 2>&1 || pasang_nft
    cur="$(nft list chain $NFT_TABLE measure 2>/dev/null)"
    echo "$cur" | grep -qi "ether saddr $mac ip daddr @hiburan_ip" \
        || nft add rule $NFT_TABLE measure ether saddr "$mac" ip daddr @hiburan_ip counter comment "\"hib_$mac\"" 2>/dev/null
    echo "$cur" | grep -qi "ether saddr $mac ip daddr @edukasi_ip" \
        || nft add rule $NFT_TABLE measure ether saddr "$mac" ip daddr @edukasi_ip counter comment "\"edu_$mac\"" 2>/dev/null
}

# ─── BACA COUNTER (JSON) → dipakai kuota_tracker & reward ───────────────────
read_measure() {
    nft -j list chain $NFT_TABLE measure 2>/dev/null
}

# ─── BLOK / BUKA HIBURAN per MAC ───────────────────────────────────────────
blok_hiburan() {
    mac="$1"; [ -z "$mac" ] && { echo "Usage: blok-hiburan <MAC>"; return 1; }
    nft list table $NFT_TABLE >/dev/null 2>&1 || pasang_nft
    nft add element $NFT_TABLE blok_mac "{ $mac }" 2>/dev/null \
        && log "⛔ hiburan $mac dibatasi" || log "= $mac sudah dibatasi"
}
buka_hiburan() {
    mac="$1"; [ -z "$mac" ] && { echo "Usage: buka-hiburan <MAC>"; return 1; }
    nft delete element $NFT_TABLE blok_mac "{ $mac }" 2>/dev/null \
        && log "✅ hiburan $mac dibuka" || log "= $mac memang tidak dibatasi"
}

# ─── BLOK / BUKA JADWAL per MAC (blokir SEMUA internet) ────────────────────
blok_jadwal() {
    mac="$1"; [ -z "$mac" ] && { echo "Usage: blok-jadwal <MAC>"; return 1; }
    nft list table $NFT_TABLE >/dev/null 2>&1 || pasang_nft
    nft add element $NFT_TABLE jadwal_mac "{ $mac }" 2>/dev/null \
        && log "🌙 jadwal $mac diblokir total" || log "= $mac sudah di-jadwal"
}
buka_jadwal() {
    mac="$1"; [ -z "$mac" ] && { echo "Usage: buka-jadwal <MAC>"; return 1; }
    nft delete element $NFT_TABLE jadwal_mac "{ $mac }" 2>/dev/null \
        && log "☀️ jadwal $mac dibuka" || log "= $mac memang tidak di-jadwal"
}

# ─── DNSMASQ SINKHOLE (negatif global) ─────────────────────────────────────
set_sinkhole() {
    mkdir -p "$SINKHOLE_DIR"
    : > "$SINKHOLE_CONF"
    n=0
    for d in "$@"; do
        [ -z "$d" ] && continue
        echo "address=/$d/$PORTAL_IP" >> "$SINKHOLE_CONF"
        n=$((n+1))
    done
    log "$n domain negatif di-sinkhole → $PORTAL_IP"
    /etc/init.d/dnsmasq restart >/dev/null 2>&1
}

# ─── STATUS / TEARDOWN ─────────────────────────────────────────────────────
status() {
    echo "── Edge Guard Captive Portal ──"
    echo -n "alias $PORTAL_IP  : "; ip addr show "$IFACE" | grep -q "$PORTAL_IP/" && echo ADA || echo TIDAK
    echo -n "portal_server.py  : "; pgrep -f 'python3.*portal_server\.py' >/dev/null 2>&1 && echo BERJALAN || echo TIDAK
    echo -n "nft table         : "; nft list table $NFT_TABLE >/dev/null 2>&1 && echo ADA || echo TIDAK
    echo -n "IP hiburan        : "; nft list set $NFT_TABLE hiburan_ip 2>/dev/null | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | wc -l
    echo -n "IP edukasi        : "; nft list set $NFT_TABLE edukasi_ip 2>/dev/null | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | wc -l
    echo -n "MAC dibatasi      : "; nft list set $NFT_TABLE blok_mac 2>/dev/null | grep -oE '([0-9a-f]{2}:){5}[0-9a-f]{2}' | tr '\n' ' '; echo
    echo -n "MAC jadwal blokir : "; nft list set $NFT_TABLE jadwal_mac 2>/dev/null | grep -oE '([0-9a-f]{2}:){5}[0-9a-f]{2}' | tr '\n' ' '; echo
    echo -n "sinkhole negatif  : "; [ -f "$SINKHOLE_CONF" ] && wc -l < "$SINKHOLE_CONF" || echo 0
}

teardown() {
    nft delete table $NFT_TABLE 2>/dev/null && log "nft table dihapus"
    rm -f "$SINKHOLE_CONF" /tmp/dnsmasq.d/eg_sinkhole.conf 2>/dev/null
    /etc/init.d/dnsmasq restart >/dev/null 2>&1
    pkill -f 'python3.*portal_server\.py' 2>/dev/null && log "portal_server.py dihentikan"
    ip addr del "$PORTAL_IP/24" dev "$IFACE" 2>/dev/null
    log "portal dibongkar"
}

case "${1:-}" in
    init)          pasang_alias; pasang_portal_server; pasang_nft ;;
    sinkhole)      shift; set_sinkhole "$@" ;;
    add-hiburan)   shift; add_hiburan "$@" ;;
    add-edukasi)   shift; add_edukasi "$@" ;;
    measure-mac)   measure_mac "$2" ;;
    read-measure)  read_measure ;;
    blok-hiburan)  blok_hiburan "$2" ;;
    buka-hiburan)  buka_hiburan "$2" ;;
    blok-jadwal)   blok_jadwal "$2" ;;
    buka-jadwal)   buka_jadwal "$2" ;;
    status)        status ;;
    teardown)      teardown ;;
    *) echo "Usage: $0 {init|sinkhole|add-hiburan|add-edukasi|measure-mac|read-measure|blok-hiburan|buka-hiburan|blok-jadwal|buka-jadwal|status|teardown}"; exit 1 ;;
esac
