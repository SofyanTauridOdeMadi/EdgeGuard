#!/usr/bin/env python3
"""
Baca CSV hasil QoS, buat semua grafik
Output: PNG 300 DPI siap masuk Word

Penggunaan:
  python3 buat_grafik_bab4.py [--csv PATH] [--out DIR]

Default:
  --csv  ~/data_qos/qos_hasil.csv
  --out  ~/data_qos/grafik/
"""

import argparse, os, sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

DPI = 300
FONT = {'family': 'serif', 'size': 10}
matplotlib.rc('font', **FONT)

# Batas TIPHON 1999
TIPHON = {
    'latency':  [150, 400, 600],
    'jitter':   [75,  125, 225],
    'loss':     [3,   15,  25],
}
TIPHON_LABELS = ['Sangat Layak', 'Layak', 'Cukup Layak', 'Tidak Layak']
TIPHON_COLORS = ['#22c55e', '#84cc16', '#f59e0b', '#ef4444']

def warna_kategori(nilai, metrik):
    batas = TIPHON[metrik]
    if nilai < batas[0]: return TIPHON_COLORS[0]
    if nilai < batas[1]: return TIPHON_COLORS[1]
    if nilai < batas[2]: return TIPHON_COLORS[2]
    return TIPHON_COLORS[3]

def simpan(fig, nama, out_dir):
    path = os.path.join(out_dir, nama)
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ {path}')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=os.path.expanduser('~/data_qos/qos_hasil.csv'))
    ap.add_argument('--out', default=os.path.expanduser('~/data_qos/grafik'))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if not os.path.exists(args.csv):
        print(f'CSV tidak ditemukan: {args.csv}')
        sys.exit(1)

    df = pd.read_csv(args.csv)
    print(f'Data dimuat: {len(df)} baris, kolom: {list(df.columns)}')

    sesi = df['sesi'].tolist()
    x = np.arange(len(sesi))

    # ─── Grafik 1: Latency per sesi + garis batas TIPHON ───────────
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = [warna_kategori(v, 'latency') for v in df['latency_avg_ms']]
    bars = ax.bar(x, df['latency_avg_ms'], color=colors, width=0.6, zorder=3)
    ax.errorbar(x, df['latency_avg_ms'],
                yerr=[df['latency_avg_ms']-df['latency_min_ms'],
                      df['latency_max_ms']-df['latency_avg_ms']],
                fmt='none', color='#334155', capsize=4, linewidth=1.2, zorder=4)

    for batas, style, label in zip(TIPHON['latency'],
                                   ['--', ':', '-.'],
                                   ['Batas SL (150 ms)', 'Batas L (400 ms)', 'Batas CL (600 ms)']):
        ax.axhline(batas, linestyle=style, color='#64748b', linewidth=0.9, label=label)

    ax.set_xticks(x)
    ax.set_xticklabels(sesi, rotation=30, ha='right', fontsize=8)
    ax.set_ylabel('Latency (ms)')
    ax.set_title('Gambar 4.x — Hasil Pengukuran Latency per Sesi (TIPHON 1999)')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(axis='y', alpha=0.4, zorder=0)

    patch_legend = [mpatches.Patch(color=c, label=l)
                    for c, l in zip(TIPHON_COLORS, TIPHON_LABELS)]
    ax.legend(handles=patch_legend,
              title='Kategori TIPHON', fontsize=7,
              loc='upper left', framealpha=0.8)
    simpan(fig, 'latency_per_sesi.png', args.out)

    # ─── Grafik 2: Jitter ───────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = [warna_kategori(v, 'jitter') for v in df['jitter_ms']]
    ax.bar(x, df['jitter_ms'], color=colors, width=0.6, zorder=3)
    for batas, style in zip(TIPHON['jitter'], ['--', ':', '-.']):
        ax.axhline(batas, linestyle=style, color='#64748b', linewidth=0.9)
    ax.set_xticks(x); ax.set_xticklabels(sesi, rotation=30, ha='right', fontsize=8)
    ax.set_ylabel('Jitter (ms)')
    ax.set_title('Gambar 4.x — Hasil Pengukuran Jitter per Sesi (TIPHON 1999)')
    ax.grid(axis='y', alpha=0.4, zorder=0)
    patch_legend = [mpatches.Patch(color=c, label=l)
                    for c, l in zip(TIPHON_COLORS, TIPHON_LABELS)]
    ax.legend(handles=patch_legend, title='Kategori TIPHON', fontsize=7, loc='upper left')
    simpan(fig, 'jitter_per_sesi.png', args.out)

    # ─── Grafik 3: Packet Loss ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = [warna_kategori(v, 'loss') for v in df['packet_loss_pct']]
    ax.bar(x, df['packet_loss_pct'], color=colors, width=0.6, zorder=3)
    for batas, style in zip(TIPHON['loss'], ['--', ':', '-.']):
        ax.axhline(batas, linestyle=style, color='#64748b', linewidth=0.9)
    ax.set_xticks(x); ax.set_xticklabels(sesi, rotation=30, ha='right', fontsize=8)
    ax.set_ylabel('Packet Loss (%)')
    ax.set_title('Gambar 4.x — Hasil Pengukuran Packet Loss per Sesi (TIPHON 1999)')
    ax.grid(axis='y', alpha=0.4, zorder=0)
    patch_legend = [mpatches.Patch(color=c, label=l)
                    for c, l in zip(TIPHON_COLORS, TIPHON_LABELS)]
    ax.legend(handles=patch_legend, title='Kategori TIPHON', fontsize=7, loc='upper right')
    simpan(fig, 'loss_per_sesi.png', args.out)

    # ─── Grafik 4: Throughput DL vs UL ─────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 4))
    w = 0.35
    ax.bar(x - w/2, df['throughput_dl_mbps'], w, label='Download', color='#3b82f6', zorder=3)
    ax.bar(x + w/2, df['throughput_ul_mbps'], w, label='Upload',   color='#10b981', zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(sesi, rotation=30, ha='right', fontsize=8)
    ax.set_ylabel('Throughput (Mbps)')
    ax.set_title('Gambar 4.x — Throughput Download & Upload per Sesi')
    ax.legend(); ax.grid(axis='y', alpha=0.4, zorder=0)
    simpan(fig, 'throughput_per_sesi.png', args.out)

    # ─── Grafik 5: Radar/Spider chart ringkasan rata-rata ──────────
    avg = {
        'Latency (ms)':   df['latency_avg_ms'].mean(),
        'Jitter (ms)':    df['jitter_ms'].mean(),
        'Packet Loss (%)': df['packet_loss_pct'].mean(),
        'Throughput DL':  df['throughput_dl_mbps'].mean(),
        'Throughput UL':  df['throughput_ul_mbps'].mean(),
    }
    labels = list(avg.keys())
    vals   = list(avg.values())

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(labels, vals, color=['#ef4444','#f59e0b','#f97316','#3b82f6','#10b981'])
    ax.set_xlabel('Nilai rata-rata')
    ax.set_title('Gambar 4.x — Ringkasan Rata-rata Metrik QoS Seluruh Sesi')
    for i, v in enumerate(vals):
        ax.text(v + max(vals)*0.01, i, f'{v:.2f}', va='center', fontsize=8)
    ax.grid(axis='x', alpha=0.4)
    simpan(fig, 'ringkasan_rata2.png', args.out)

    print(f'\nSemua grafik tersimpan di: {args.out}')
    print('\n=== Tabel Rata-rata ===')
    print(df[['sesi','latency_avg_ms','jitter_ms','packet_loss_pct',
              'throughput_dl_mbps','throughput_ul_mbps']].to_string(index=False))

if __name__ == '__main__':
    main()
