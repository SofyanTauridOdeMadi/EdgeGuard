#!/bin/bash
# =====================================================================
# uji_qos_tiphon.sh — Pengujian QoS berbasis standar TIPHON 1999
# Dijalankan di Mac (sisi klien/anak), router hanya menanggung beban
# Hasil: CSV siap diolah Python → grafik Bab 4
# Penggunaan: ./uji_qos_tiphon.sh <nama_sesi>
# Contoh:    ./uji_qos_tiphon.sh "hari1_pagi_ai_aktif"
# =====================================================================

SESI="${1:-sesi_$(date +%Y%m%d_%H%M)}"
ROUTER="root@192.168.1.1"
KEY="$HOME/.ssh/edgeguard_ax3000t"
VPS="202.10.34.171"            # iperf3 server target
PING_TARGET="8.8.8.8"         # target latency/jitter/loss
PING_COUNT=100                 # jumlah paket ping per sesi
IPERF_DUR=30                   # durasi iperf3 (detik)
OUT_DIR="$HOME/data_qos"
mkdir -p "$OUT_DIR"

CSV_QOS="$OUT_DIR/qos_hasil.csv"
LOG="$OUT_DIR/qos_$(date +%Y%m%d).log"

# Tulis header kalau file baru
if [ ! -f "$CSV_QOS" ]; then
  echo "timestamp,sesi,latency_avg_ms,latency_min_ms,latency_max_ms,jitter_ms,packet_loss_pct,throughput_dl_mbps,throughput_ul_mbps,kategori_tiphon_latency,kategori_tiphon_jitter,kategori_tiphon_loss" > "$CSV_QOS"
fi

echo "=============================="
echo "Sesi: $SESI"
echo "Mulai: $(date)"
echo "=============================="

# ─── 1. Latency, Jitter, Packet Loss (ping ICMP) ───────────────────
echo "[1/3] Mengukur latency, jitter, packet loss ($PING_COUNT paket ke $PING_TARGET)..."
PING_OUT=$(ping -c $PING_COUNT -i 0.2 $PING_TARGET 2>&1)
echo "$PING_OUT" >> "$LOG"

# Parse hasil ping
LOSS=$(echo "$PING_OUT" | grep -oE '[0-9]+(\.[0-9]+)?% packet loss' | grep -oE '[0-9]+(\.[0-9]+)?')
RTT_LINE=$(echo "$PING_OUT" | grep 'round-trip\|rtt min')
LAT_MIN=$(echo "$RTT_LINE" | awk -F'/' '{print $NF}' | awk -F'/' '{print $1}' 2>/dev/null)
LAT_AVG=$(echo "$RTT_LINE" | awk -F'/' '{
  n=split($0,a,"/");
  for(i=1;i<=n;i++) if(a[i]+0>0) {print a[i]; exit}
}' 2>/dev/null)

# macOS ping format: min/avg/max/stddev
STATS=$(echo "$RTT_LINE" | grep -oE '[0-9]+\.[0-9]+/[0-9]+\.[0-9]+/[0-9]+\.[0-9]+/[0-9]+\.[0-9]+')
LAT_MIN=$(echo "$STATS" | cut -d'/' -f1)
LAT_AVG=$(echo "$STATS" | cut -d'/' -f2)
LAT_MAX=$(echo "$STATS" | cut -d'/' -f3)
LAT_STDDEV=$(echo "$STATS" | cut -d'/' -f4)   # stddev ≈ jitter (RFC 3550)

JITTER=$LAT_STDDEV
[ -z "$LOSS" ]    && LOSS="0"
[ -z "$LAT_AVG" ] && LAT_AVG="0"
[ -z "$LAT_MIN" ] && LAT_MIN="0"
[ -z "$LAT_MAX" ] && LAT_MAX="0"
[ -z "$JITTER" ]  && JITTER="0"

echo "  Latency avg: ${LAT_AVG} ms | min: ${LAT_MIN} | max: ${LAT_MAX}"
echo "  Jitter (stddev): ${JITTER} ms"
echo "  Packet Loss: ${LOSS}%"

# ─── 2. Throughput (iperf3) ─────────────────────────────────────────
echo "[2/3] Mengukur throughput via iperf3 (${IPERF_DUR}s)..."

# Download (server→client)
DL_OUT=$(iperf3 -c $VPS -t $IPERF_DUR -R -J 2>/dev/null)
DL_MBPS=$(echo "$DL_OUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    bps=d['end']['sum_received']['bits_per_second']
    print(f'{bps/1e6:.2f}')
except:
    print('0')
")

# Upload (client→server)
UL_OUT=$(iperf3 -c $VPS -t $IPERF_DUR -J 2>/dev/null)
UL_MBPS=$(echo "$UL_OUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    bps=d['end']['sum_sent']['bits_per_second']
    print(f'{bps/1e6:.2f}')
except:
    print('0')
")

echo "  Download: ${DL_MBPS} Mbps"
echo "  Upload:   ${UL_MBPS} Mbps"

# ─── 3. Kategorisasi TIPHON ─────────────────────────────────────────
# TIPHON 1999 kategori: Sangat Layak (SL), Layak (L), Cukup Layak (CL), Tidak Layak (TL)
python3 - <<PYEOF
lat  = float("${LAT_AVG}" or 0)
jit  = float("${JITTER}"  or 0)
loss = float("${LOSS}"    or 0)

def kat_latency(v):
    if v < 150:   return "Sangat Layak"
    if v < 400:   return "Layak"
    if v < 600:   return "Cukup Layak"
    return "Tidak Layak"

def kat_jitter(v):
    if v < 75:    return "Sangat Layak"
    if v < 125:   return "Layak"
    if v < 225:   return "Cukup Layak"
    return "Tidak Layak"

def kat_loss(v):
    if v < 3:     return "Sangat Layak"
    if v < 15:    return "Layak"
    if v < 25:    return "Cukup Layak"
    return "Tidak Layak"

kl = kat_latency(lat)
kj = kat_jitter(jit)
ko = kat_loss(loss)
print(f"  Kategori TIPHON — Latency: {kl} | Jitter: {kj} | Loss: {ko}")
# Tulis ke file temp agar bash bisa baca
with open("/tmp/tiphon_kat.txt","w") as f:
    f.write(f"{kl}|{kj}|ko")
PYEOF

TIPHON_KAT=$(cat /tmp/tiphon_kat.txt 2>/dev/null || echo "?|?|?")
KAT_LAT=$(echo "$TIPHON_KAT" | cut -d'|' -f1)
KAT_JIT=$(echo "$TIPHON_KAT" | cut -d'|' -f2)
KAT_LOS=$(echo "$TIPHON_KAT" | cut -d'|' -f3)

# ─── Simpan ke CSV ──────────────────────────────────────────────────
TS=$(date '+%Y-%m-%d %H:%M:%S')
echo "${TS},${SESI},${LAT_AVG},${LAT_MIN},${LAT_MAX},${JITTER},${LOSS},${DL_MBPS},${UL_MBPS},${KAT_LAT},${KAT_JIT},${KAT_LOS}" >> "$CSV_QOS"

echo ""
echo "[3/3] Hasil disimpan ke $CSV_QOS"
echo "=============================="
echo "SELESAI: $(date)"
