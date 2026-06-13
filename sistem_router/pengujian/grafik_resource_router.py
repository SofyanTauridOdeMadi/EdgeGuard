#!/usr/bin/env python3
"""
grafik_resource_router.py
─────────────────────────
Ukur CPU & RAM router via SSH dalam dua kondisi (AI Nonaktif vs AI Aktif).

Penggunaan:
  python3 grafik_resource_router.py collect   # ukur & simpan data
  python3 grafik_resource_router.py plot      # buat grafik dari data
  python3 grafik_resource_router.py all       # collect + plot sekaligus

Hasil: ~/data_qos/grafik/resource_router.png  (300 DPI)
"""

import subprocess, time, json, os, sys, argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ─── Konfigurasi SSH ────────────────────────────────────────────────
ROUTER      = 'root@192.168.1.1'
SSH_KEY     = os.path.expanduser('~/.ssh/edgeguard_ax3000t')
SSH_OPTS    = ['-i', SSH_KEY, '-o', 'ConnectTimeout=10',
               '-o', 'StrictHostKeyChecking=no']

# ─── Direktori output ───────────────────────────────────────────────
OUT_DIR  = os.path.expanduser('~/data_qos')
DATA_FILE = os.path.join(OUT_DIR, 'resource_data.json')
GRAPH_OUT = os.path.join(OUT_DIR, 'grafik', 'gambar_resource_router.png')
os.makedirs(os.path.join(OUT_DIR, 'grafik'), exist_ok=True)

N_SAMPLES = 5       # pengukuran per kondisi
INTERVAL  = 3       # detik antar sampel


# ════════════════════════════════════════════════════════════════════
# BAGIAN 1 — PENGUKURAN (collect)
# ════════════════════════════════════════════════════════════════════

def ssh_run(cmd):
    """Jalankan perintah di router via SSH, kembalikan stdout string."""
    result = subprocess.run(
        ['ssh'] + SSH_OPTS + [ROUTER, cmd],
        capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip()

def baca_cpu():
    """Baca utilisasi CPU (%) — rata-rata 2 core dari /proc/stat."""
    # Snapshot 1
    s1 = ssh_run("cat /proc/stat | grep '^cpu '")
    time.sleep(1)
    # Snapshot 2
    s2 = ssh_run("cat /proc/stat | grep '^cpu '")

    def parse(line):
        parts = list(map(int, line.split()[1:]))
        idle = parts[3]
        total = sum(parts)
        return idle, total

    idle1, tot1 = parse(s1)
    idle2, tot2 = parse(s2)
    cpu_pct = 100.0 * (1 - (idle2 - idle1) / (tot2 - tot1))
    return round(cpu_pct, 1)

def baca_ram():
    """Baca RAM terpakai (MB) dari /proc/meminfo."""
    out = ssh_run("cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'")
    lines = out.splitlines()
    total = available = 0
    for line in lines:
        k, v = line.split(':')
        val = int(v.strip().split()[0])  # kB
        if 'MemTotal' in k:     total = val
        if 'MemAvailable' in k: available = val
    used_mb = round((total - available) / 1024, 1)
    total_mb = round(total / 1024, 1)
    return used_mb, total_mb

def baca_cpu_per_core():
    """Baca CPU per core (0 dan 1) dari /proc/stat."""
    s1 = ssh_run("cat /proc/stat | grep '^cpu[01] '")
    time.sleep(1)
    s2 = ssh_run("cat /proc/stat | grep '^cpu[01] '")

    def parse_lines(text):
        result = {}
        for line in text.splitlines():
            parts = line.split()
            name = parts[0]
            vals = list(map(int, parts[1:]))
            result[name] = (vals[3], sum(vals))  # (idle, total)
        return result

    d1, d2 = parse_lines(s1), parse_lines(s2)
    cores = {}
    for core in ['cpu0', 'cpu1']:
        if core in d1 and core in d2:
            idle1, tot1 = d1[core]
            idle2, tot2 = d2[core]
            pct = 100.0 * (1 - (idle2 - idle1) / max(tot2 - tot1, 1))
            cores[core] = round(pct, 1)
        else:
            cores[core] = 0.0
    return cores

def ukur_kondisi(label):
    """Ambil N_SAMPLES pengukuran untuk satu kondisi."""
    print(f"\n  Mengukur kondisi: {label} ({N_SAMPLES} sampel × {INTERVAL}s)...")
    cpu_list, cpu0_list, cpu1_list, ram_list = [], [], [], []

    for i in range(N_SAMPLES):
        print(f"    Sampel {i+1}/{N_SAMPLES}...", end=' ', flush=True)
        try:
            cpu     = baca_cpu()
            cores   = baca_cpu_per_core()
            ram, _  = baca_ram()
            cpu_list.append(cpu)
            cpu0_list.append(cores.get('cpu0', 0))
            cpu1_list.append(cores.get('cpu1', 0))
            ram_list.append(ram)
            print(f"CPU={cpu:.1f}% (C0={cores.get('cpu0',0):.1f}% C1={cores.get('cpu1',0):.1f}%) RAM={ram:.0f}MB")
        except Exception as e:
            print(f"ERROR: {e}")
        if i < N_SAMPLES - 1:
            time.sleep(INTERVAL)

    avg  = lambda lst: round(sum(lst)/len(lst), 1) if lst else 0
    peak = lambda lst: round(max(lst), 1) if lst else 0

    return {
        'label':      label,
        'cpu_avg':    avg(cpu_list),
        'cpu_peak':   peak(cpu_list),
        'cpu0_avg':   avg(cpu0_list),
        'cpu0_peak':  peak(cpu0_list),
        'cpu1_avg':   avg(cpu1_list),
        'cpu1_peak':  peak(cpu1_list),
        'ram_avg':    avg(ram_list),
        'ram_peak':   peak(ram_list),
        'samples_cpu': cpu_list,
        'samples_ram': ram_list,
    }

def collect():
    """Prosedur pengukuran dua kondisi secara interaktif."""
    print("═" * 60)
    print("PENGUKURAN SUMBER DAYA ROUTER")
    print("═" * 60)

    # Kondisi A — AI Nonaktif
    print("\n[KONDISI A] Pastikan AI sudah DINONAKTIFKAN di router.")
    print("  Jalankan perintah ini di terminal lain jika belum:")
    print("  ssh -i ~/.ssh/edgeguard_ax3000t root@192.168.1.1 \\")
    print("    \"pgrep -f pemantau_trafik | xargs kill -9 2>/dev/null; echo done\"")
    input("\n  Tekan ENTER jika sudah siap...")

    data_a = ukur_kondisi("AI Nonaktif (Baseline)")

    # Kondisi B — AI Aktif
    print("\n[KONDISI B] Aktifkan AI di router:")
    print("  ssh -i ~/.ssh/edgeguard_ax3000t root@192.168.1.1 \\")
    print("    \"/etc/init.d/edgeguard start\"")
    input("  Tekan ENTER setelah AI aktif dan tunggu ~15 detik...")
    time.sleep(15)

    data_b = ukur_kondisi("AI Aktif")

    # Simpan
    hasil = {'A': data_a, 'B': data_b}
    with open(DATA_FILE, 'w') as f:
        json.dump(hasil, f, indent=2)
    print(f"\n✓ Data disimpan ke {DATA_FILE}")
    return hasil


# ════════════════════════════════════════════════════════════════════
# BAGIAN 2 — GRAFIK (plot)
# ════════════════════════════════════════════════════════════════════

def plot(hasil=None):
    if hasil is None:
        if not os.path.exists(DATA_FILE):
            print(f"File data tidak ditemukan: {DATA_FILE}")
            print("Jalankan dulu: python3 grafik_resource_router.py collect")
            sys.exit(1)
        with open(DATA_FILE) as f:
            hasil = json.load(f)

    A = hasil['A']
    B = hasil['B']

    # ─── Warna ──────────────────────────────────────────────────────
    CLR_A     = '#3B82F6'   # biru — Baseline
    CLR_B     = '#EF4444'   # merah — AI Aktif
    CLR_PEAK  = '#1D4ED8'   # biru gelap — peak A
    CLR_PEAK2 = '#B91C1C'   # merah gelap — peak B
    CLR_LIMIT = '#F59E0B'   # kuning — batas aman
    ALPHA_BG  = 0.08

    # ─── Layout: 1 baris × 3 kolom ──────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.patch.set_facecolor('#FAFAFA')
    fig.suptitle(
        'Perbandingan Utilisasi Sumber Daya Router\n'
        'Kondisi Baseline (AI Nonaktif) vs. Sistem AI Aktif',
        fontsize=12, fontweight='bold', y=1.02, color='#1E293B'
    )

    bar_w = 0.32
    x = np.array([0.0])

    def draw_bar_pair(ax, val_a, val_b, peak_a, peak_b,
                      ylabel, title, unit='%', limit=None, limit_label=''):
        """Gambar sepasang bar grouped + error bar peak."""
        xa, xb = x - bar_w/2, x + bar_w/2
        ba = ax.bar(xa, val_a, bar_w, color=CLR_A,
                    label=f'A: {A["label"]}', zorder=3, linewidth=0)
        bb = ax.bar(xb, val_b, bar_w, color=CLR_B,
                    label=f'B: {B["label"]}', zorder=3, linewidth=0)

        # Garis peak
        ax.hlines(peak_a, xa[0]-bar_w/2+0.02, xa[0]+bar_w/2-0.02,
                  colors=CLR_PEAK, linewidths=2, zorder=4)
        ax.hlines(peak_b, xb[0]-bar_w/2+0.02, xb[0]+bar_w/2-0.02,
                  colors=CLR_PEAK2, linewidths=2, zorder=4)

        # Label nilai di atas bar
        ax.text(xa[0], val_a + (ax.get_ylim()[1]*0.02 if ax.get_ylim()[1] > 0 else 2),
                f'{val_a}{unit}', ha='center', va='bottom', fontsize=9,
                fontweight='bold', color=CLR_PEAK)
        ax.text(xb[0], val_b + (ax.get_ylim()[1]*0.02 if ax.get_ylim()[1] > 0 else 2),
                f'{val_b}{unit}', ha='center', va='bottom', fontsize=9,
                fontweight='bold', color=CLR_PEAK2)

        # Garis batas aman
        if limit is not None:
            ax.axhline(limit, color=CLR_LIMIT, linewidth=1.8,
                       linestyle='--', zorder=2, label=f'Batas aman ({limit_label})')
            ax.fill_between([-0.5, 0.5], limit, ax.get_ylim()[1],
                            color=CLR_LIMIT, alpha=ALPHA_BG, zorder=1)

        ax.set_xlim(-0.5, 0.5)
        ax.set_xticks([])
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=10.5, fontweight='bold', pad=8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_facecolor('#F8FAFC')
        ax.grid(axis='y', alpha=0.35, zorder=0)
        return ba, bb

    # ─── Panel 1: CPU Total (rata-rata) ─────────────────────────────
    ax1 = axes[0]
    y_max_cpu = max(B['cpu_peak'], 85) + 10
    ax1.set_ylim(0, y_max_cpu)
    ba1, bb1 = draw_bar_pair(
        ax1,
        A['cpu_avg'], B['cpu_avg'],
        A['cpu_peak'], B['cpu_peak'],
        ylabel='Utilisasi CPU (%)',
        title='CPU Total\n(Rata-rata ± Puncak)',
        unit='%', limit=80, limit_label='80% ISO 25010'
    )

    # ─── Panel 2: CPU per Core ──────────────────────────────────────
    ax2 = axes[1]
    x2 = np.array([0.0, 1.0])
    ys_a = [A['cpu0_avg'], A['cpu1_avg']]
    ys_b = [B['cpu0_avg'], B['cpu1_avg']]
    peaks_a = [A['cpu0_peak'], A['cpu1_peak']]
    peaks_b = [B['cpu0_peak'], B['cpu1_peak']]

    ax2.bar(x2 - bar_w/2, ys_a, bar_w, color=CLR_A, zorder=3, linewidth=0, label='Baseline')
    ax2.bar(x2 + bar_w/2, ys_b, bar_w, color=CLR_B, zorder=3, linewidth=0, label='AI Aktif')
    for xi, ya, yb, pa, pb in zip(x2, ys_a, ys_b, peaks_a, peaks_b):
        ax2.hlines(pa, xi-bar_w+0.02, xi-0.02, colors=CLR_PEAK, linewidths=2, zorder=4)
        ax2.hlines(pb, xi+0.02, xi+bar_w-0.02, colors=CLR_PEAK2, linewidths=2, zorder=4)
        ax2.text(xi-bar_w/2, ya+1.5, f'{ya}%', ha='center', va='bottom', fontsize=8,
                 fontweight='bold', color=CLR_PEAK)
        ax2.text(xi+bar_w/2, yb+1.5, f'{yb}%', ha='center', va='bottom', fontsize=8,
                 fontweight='bold', color=CLR_PEAK2)

    ax2.axhline(80, color=CLR_LIMIT, linewidth=1.8, linestyle='--', zorder=2)
    ax2.set_ylim(0, max(max(peaks_b)+15, 90))
    ax2.set_xticks(x2)
    ax2.set_xticklabels(['Core 0', 'Core 1'], fontsize=10)
    ax2.set_ylabel('Utilisasi CPU (%)', fontsize=10)
    ax2.set_title('CPU per Core\n(Rata-rata ± Puncak)', fontsize=10.5,
                  fontweight='bold', pad=8)
    ax2.spines[['top', 'right']].set_visible(False)
    ax2.set_facecolor('#F8FAFC')
    ax2.grid(axis='y', alpha=0.35, zorder=0)

    # ─── Panel 3: RAM ───────────────────────────────────────────────
    ax3 = axes[2]
    total_ram = 234  # MB (dari HTOP: 234M)
    y_max_ram = total_ram + 20
    ax3.set_ylim(0, y_max_ram)
    draw_bar_pair(
        ax3,
        A['ram_avg'], B['ram_avg'],
        A['ram_peak'], B['ram_peak'],
        ylabel='RAM Terpakai (MB)',
        title=f'Utilisasi RAM\n(Total: {total_ram} MB)',
        unit='MB', limit=total_ram * 0.8,
        limit_label=f'{int(total_ram*0.8)} MB (80%)'
    )
    # Garis total RAM
    ax3.axhline(total_ram, color='#94A3B8', linewidth=1.2,
                linestyle=':', zorder=2, label=f'Total RAM ({total_ram} MB)')

    # ─── Legend bersama ─────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(color=CLR_A,    label=f'Kondisi A — {A["label"]}'),
        mpatches.Patch(color=CLR_B,    label=f'Kondisi B — {B["label"]}'),
        plt.Line2D([0],[0], color=CLR_LIMIT, linewidth=2, linestyle='--',
                   label='Ambang batas aman (ISO 25010)'),
        plt.Line2D([0],[0], color='#475569', linewidth=2.5,
                   label='Nilai puncak (peak)'),
    ]
    fig.legend(handles=legend_handles, loc='lower center', ncol=4,
               fontsize=8.5, framealpha=0.9,
               bbox_to_anchor=(0.5, -0.08))

    # ─── Anotasi degradasi di atas figure ───────────────────────────
    cpu_delta = round(B['cpu_avg'] - A['cpu_avg'], 1)
    ram_delta = round(B['ram_avg'] - A['ram_avg'], 1)
    sign_cpu = '+' if cpu_delta >= 0 else ''
    sign_ram = '+' if ram_delta >= 0 else ''
    note = (f'Δ CPU rata-rata: {sign_cpu}{cpu_delta}%  |  '
            f'Δ RAM rata-rata: {sign_ram}{ram_delta} MB  |  '
            f'Pengukuran: {N_SAMPLES} sampel per kondisi, interval {INTERVAL}s')
    fig.text(0.5, 1.06, note, ha='center', fontsize=8.5, color='#475569',
             style='italic')

    plt.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(GRAPH_OUT, dpi=300, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f'\n✓ Grafik tersimpan: {GRAPH_OUT}')
    print(f'  Ukuran file: {os.path.getsize(GRAPH_OUT)//1024} KB')

    # ─── Ringkasan tabel ────────────────────────────────────────────
    print('\n╔══════════════════════════════════════════════════════════╗')
    print('║           RINGKASAN HASIL PENGUKURAN                    ║')
    print('╠══════════════════════════════╦═════════════╦════════════╣')
    print(f'║ Metrik                       ║ Kondisi A   ║ Kondisi B  ║')
    print('╠══════════════════════════════╬═════════════╬════════════╣')
    metrics = [
        ('CPU Total Rata-rata (%)',  A['cpu_avg'],   B['cpu_avg']),
        ('CPU Total Puncak (%)',     A['cpu_peak'],  B['cpu_peak']),
        ('CPU Core 0 Rata-rata (%)', A['cpu0_avg'],  B['cpu0_avg']),
        ('CPU Core 1 Rata-rata (%)', A['cpu1_avg'],  B['cpu1_avg']),
        ('RAM Rata-rata (MB)',        A['ram_avg'],   B['ram_avg']),
        ('RAM Puncak (MB)',           A['ram_peak'],  B['ram_peak']),
    ]
    for label, va, vb in metrics:
        delta = round(vb - va, 1)
        sign = '+' if delta >= 0 else ''
        print(f'║ {label:<28} ║ {str(va):<11} ║ {str(vb):<8} ({sign}{delta}) ║')
    print('╚══════════════════════════════╩═════════════╩════════════╝')


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Resource router benchmark & grafik')
    ap.add_argument('mode', nargs='?', default='all',
                    choices=['collect', 'plot', 'all'],
                    help='collect=ukur saja | plot=grafik saja | all=keduanya')
    args = ap.parse_args()

    if args.mode == 'collect':
        collect()
    elif args.mode == 'plot':
        plot()
    else:
        hasil = collect()
        plot(hasil)
