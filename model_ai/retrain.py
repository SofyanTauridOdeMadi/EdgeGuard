#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — Penggabung Koreksi Manual → Dataset (untuk retrain)    ║
║                                                                      ║
║  Mengambil koreksi kategori manual orang tua dari VPS                ║
║  (GET /api/config → "koreksi_kategori"), lalu meng-UPSERT-nya        ║
║  sebagai baris berlabel ke datasetkumpulanweb.xlsx. Dengan begitu    ║
║  setiap koreksi yang dibuat lewat dashboard otomatis menjadi data    ║
║  latih untuk model berikutnya (closed-loop).                         ║
║                                                                      ║
║  Pakai:                                                               ║
║    python3 retrain.py                # gabungkan koreksi → dataset    ║
║    python3 retrain.py --train        # gabungkan + latih (nbconvert) ║
║    EG_CLOUD_URL=https://edgeguard.my.id python3 retrain.py           ║
║                                                                      ║
║  Jadwalkan otomatis (cron, tiap Minggu 02:00) di Trainer Node:       ║
║    0 2 * * 0  cd /path/EdgeGuard/model_ai && python3 retrain.py --train ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, ssl, json, shutil, argparse, subprocess, re
import urllib.request
from datetime import datetime

BASE      = os.path.dirname(os.path.abspath(__file__))
XLSX      = os.path.join(BASE, 'datasetkumpulanweb.xlsx')
NOTEBOOK  = os.path.join(BASE, 'AI_LATIH.ipynb')
CLOUD_URL = os.environ.get('EG_CLOUD_URL', 'https://edgeguard.my.id').rstrip('/')


def _ssl_ctx():
    """Verifikasi penuh untuk domain resmi; lewati untuk IP/self-signed."""
    if not CLOUD_URL.startswith('https://'):
        return None
    ctx  = ssl.create_default_context()
    host = CLOUD_URL.split('//', 1)[1].split('/')[0].split(':')[0]
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host):     # IP → self-signed
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
    return ctx


def ambil_koreksi() -> dict:
    """Return dict {domain: kategori} koreksi manual dari VPS."""
    req = urllib.request.Request(CLOUD_URL + '/api/config',
                                 headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as r:
        data = json.loads(r.read().decode())
    return data.get('koreksi_kategori', {}) or {}


def main():
    ap = argparse.ArgumentParser(description='Gabungkan koreksi manual ke dataset')
    ap.add_argument('--train', action='store_true',
                    help='Jalankan AI_LATIH.ipynb via nbconvert setelah merge')
    args = ap.parse_args()

    try:
        import pandas as pd
    except ImportError:
        print('❌ Butuh pandas + openpyxl:  pip install pandas openpyxl'); sys.exit(1)

    try:
        koreksi = ambil_koreksi()
    except Exception as e:
        print(f'❌ Gagal mengambil koreksi dari {CLOUD_URL}: {e}'); sys.exit(1)
    print(f'📥 {len(koreksi)} koreksi manual diambil dari {CLOUD_URL}')

    df   = pd.read_excel(XLSX)
    cols = {c.upper(): c for c in df.columns}
    SNI  = cols.get('SNI', 'SNI');         KAT = cols.get('KATEGORI', 'KATEGORI')
    DESK = cols.get('DESK_SITUS', 'DESK_SITUS'); TRA = cols.get('TRAFIK', 'TRAFIK')

    added = updated = 0
    for domain, kat in koreksi.items():
        domain = str(domain).lower().strip()
        if not domain or kat not in ('edukasi', 'hiburan', 'negatif', 'netral'):
            continue
        mask = df[SNI].astype(str).str.lower() == domain
        if mask.any():
            if (df.loc[mask, KAT].astype(str).str.lower() != kat).any():
                df.loc[mask, KAT] = kat; updated += 1
        else:
            df = pd.concat([df, pd.DataFrame([{
                SNI: domain, KAT: kat,
                DESK: 'koreksi manual orang tua', TRA: 'MEDIUM'}])],
                ignore_index=True)
            added += 1

    if added or updated:
        bak = XLSX + '.bak-' + datetime.now().strftime('%Y%m%d%H%M%S')
        shutil.copy2(XLSX, bak)
        df.to_excel(XLSX, index=False)
        print(f'✅ Dataset diperbarui: +{added} baris baru, {updated} dikoreksi.')
        print(f'   Backup: {os.path.basename(bak)}')
    else:
        print('✅ Dataset sudah sinkron dengan koreksi (tidak ada perubahan).')

    if args.train:
        print('🔁 Melatih ulang model (jupyter nbconvert --execute)...')
        rc = subprocess.call(['jupyter', 'nbconvert', '--to', 'notebook',
                              '--execute', '--inplace', NOTEBOOK])
        if rc == 0:
            print('✅ Model dilatih ulang. Salin ke router:')
            print('   scp -O model_export.json '
                  'root@192.168.1.1:/root/edgeguard/sistem_router/ && '
                  'ssh root@192.168.1.1 "/etc/init.d/edgeguard restart"')
        else:
            print('⚠️  nbconvert gagal / belum terpasang. Jalankan AI_LATIH.ipynb manual.')


if __name__ == '__main__':
    main()
