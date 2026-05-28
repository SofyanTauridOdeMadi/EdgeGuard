"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — NOTIFIKASI TELEGRAM                                   ║
║                                                                       ║
║  Kirim alert ke HP orang tua via Telegram Bot.                       ║
║                                                                       ║
║  Setup sekali (cara pakai):                                          ║
║    1. @BotFather → /newbot → dapatkan TOKEN                          ║
║    2. Chat bot lalu jalankan:                                        ║
║         python3 notifikasi_telegram.py --get-chatid                  ║
║    3. Export env (sekali, di /etc/edgeguard.env atau .profile):      ║
║         export TG_BOT_TOKEN='...:...'                                ║
║         export TG_CHAT_ID='12345678'                                 ║
║    4. Test:                                                          ║
║         python3 notifikasi_telegram.py --test                        ║
║                                                                       ║
║  Fitur: cooldown per domain (5 menit), batching burst (3 detik),    ║
║          rate limit antar pesan (5 detik), retry 429.               ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time
import urllib.request, urllib.error
from datetime import datetime
from collections import deque

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from config import TG_BOT_TOKEN, TG_CHAT_ID, HTTP_TIMEOUT, DEBUG

BASE_URL = f'https://api.telegram.org/bot{TG_BOT_TOKEN}' if TG_BOT_TOKEN else ''

MIN_INTERVAL    = 5      # detik antar pesan
BATCH_WINDOW    = 3      # detik untuk batching burst
MAX_QUEUE       = 50
COOLDOWN_DOMAIN = 300    # 5 menit per-domain

_last_sent       = 0.0
_domain_cooldown = {}
_batch_buffer    = []
_batch_ts        = 0.0

# ═══════════════════════════════════════════════════════════════════════════
# HTTP request dengan retry
# ═══════════════════════════════════════════════════════════════════════════
def _kirim(payload: dict, retries: int = 3) -> bool:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        if DEBUG: print("[Telegram] ⚠️  TG_BOT_TOKEN / TG_CHAT_ID belum di-set")
        return False
    url  = f'{BASE_URL}/sendMessage'
    data = json.dumps({**payload, 'chat_id': TG_CHAT_ID}).encode('utf-8')
    req  = urllib.request.Request(url, data=data,
                                  headers={'Content-Type':'application/json'},
                                  method='POST')
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT * 2) as r:
                resp = json.loads(r.read().decode())
                if resp.get('ok'): return True
                if DEBUG: print(f"[Telegram] error: {resp.get('description','?')}")
                return False
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get('Retry-After', 5))
                if DEBUG: print(f"[Telegram] rate-limit, tunggu {wait}d")
                time.sleep(wait)
            else:
                if DEBUG: print(f"[Telegram] HTTP {e.code}: {e.reason}")
                return False
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else:
                if DEBUG: print(f"[Telegram] kirim gagal: {e}")
    return False

# ═══════════════════════════════════════════════════════════════════════════
# Helper cooldown
# ═══════════════════════════════════════════════════════════════════════════
def _bersihkan_cooldown():
    now = time.time()
    for d in [d for d, ts in _domain_cooldown.items() if now - ts > COOLDOWN_DOMAIN]:
        del _domain_cooldown[d]

EMOJI = {'negatif':'🚫', 'blacklist':'⛔', 'hiburan':'🎬',
         'edukasi':'📚', 'jeda':'⏸', 'unknown':'❓'}

# ═══════════════════════════════════════════════════════════════════════════
# Format pesan
# ═══════════════════════════════════════════════════════════════════════════
def _fmt_blokir(d, alasan, kat, perangkat, conf):
    em   = EMOJI.get(kat, '🔴')
    now  = datetime.now().strftime('%H:%M:%S')
    kat_label = {
        'negatif':'Konten Negatif (Judi/Porno/Scam)',
        'blacklist':'Daftar Hitam Manual',
        'jeda':'Perangkat Sedang Dijeda',
    }.get(kat, kat.capitalize())
    return (
        f"{em} *SITUS DIBLOKIR*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 Domain     : `{d}`\n"
        f"📱 Perangkat  : {perangkat or 'Tidak diketahui'}\n"
        f"📂 Kategori   : {kat_label}\n"
        f"🎯 Confidence : {conf:.0f}%\n"
        f"⚙️ Alasan     : {alasan.replace('_',' ').title()}\n"
        f"🕐 Waktu      : {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Tap 'Minta Izin' di layar anak untuk membuka akses._"
    )

def _fmt_batch(items):
    now = datetime.now().strftime('%H:%M:%S')
    baris = [f"  • `{it['domain']}` — {it['perangkat'] or '?'} "
             f"({EMOJI.get(it['kategori'],'🔴')} {it['kategori']})"
             for it in items]
    return (
        f"🚫 *{len(items)} SITUS DIBLOKIR* dalam {BATCH_WINDOW}d terakhir\n"
        f"━━━━━━━━━━━━━━━━━━━━\n" + '\n'.join(baris) +
        f"\n━━━━━━━━━━━━━━━━━━━━\n🕐 {now}"
    )

def _fmt_jeda(nama, status):
    em, aksi, info = ('⏸','Dijeda','Internet perangkat ini diblokir sementara.') if status=='jeda' \
                     else ('▶️','Dilanjutkan','Internet perangkat ini kembali aktif.')
    now = datetime.now().strftime('%H:%M:%S')
    return (
        f"{em} *PERANGKAT {aksi.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Perangkat  : {nama}\n"
        f"📡 Status     : {aksi}\n"
        f"ℹ️  Info       : {info}\n"
        f"🕐 Waktu      : {now}"
    )

def _fmt_minta_izin(d, nama):
    now = datetime.now().strftime('%H:%M:%S')
    return (
        f"🙋 *PERMINTAAN IZIN AKSES*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 Domain     : `{d}`\n"
        f"📱 Perangkat  : {nama or '?'}\n"
        f"🕐 Waktu      : {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Buka dashboard untuk memberikan izin atau tolak._"
    )

# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════
def notif_blokir(domain, alasan='klasifikasi_ai', kategori='negatif',
                 perangkat='', confidence=0.0):
    """Kirim notif blokir. Fitur: cooldown per-domain, batching, rate-limit."""
    global _last_sent, _batch_buffer, _batch_ts
    now = time.time()
    _bersihkan_cooldown()
    if domain in _domain_cooldown: return False
    _domain_cooldown[domain] = now

    _batch_buffer.append({'domain':domain,'alasan':alasan,'kategori':kategori,
                          'perangkat':perangkat,'confidence':float(confidence)})

    if now - _batch_ts > BATCH_WINDOW:
        _batch_ts = now
        batch = _batch_buffer.copy(); _batch_buffer.clear()
        elapsed = now - _last_sent
        if elapsed < MIN_INTERVAL: time.sleep(MIN_INTERVAL - elapsed)
        if len(batch) == 1:
            teks = _fmt_blokir(batch[0]['domain'], batch[0]['alasan'],
                               batch[0]['kategori'], batch[0]['perangkat'],
                               batch[0]['confidence'])
        else:
            teks = _fmt_batch(batch)
        ok = _kirim({'text':teks, 'parse_mode':'Markdown'})
        if ok: _last_sent = time.time()
        return ok
    return True

def notif_jeda(nama, status='jeda'):
    return _kirim({'text':_fmt_jeda(nama, status), 'parse_mode':'Markdown'})

def notif_minta_izin(domain, nama=''):
    return _kirim({
        'text':_fmt_minta_izin(domain, nama),
        'parse_mode':'Markdown',
        'reply_markup': json.dumps({'inline_keyboard':[[
            {'text':'✅ Izinkan','callback_data':f'izin:{domain}'},
            {'text':'❌ Tolak','callback_data':f'tolak:{domain}'},
        ]]})
    })

# ═══════════════════════════════════════════════════════════════════════════
# Utility CLI
# ═══════════════════════════════════════════════════════════════════════════
def test_koneksi():
    teks = (
        "🛡️ *Edge Guard — Test Koneksi*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Bot Telegram terhubung!\n"
        "📱 Notifikasi akan dikirim ke chat ini.\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    ok = _kirim({'text':teks, 'parse_mode':'Markdown'})
    print("✅ Test sukses — cek Telegram" if ok
          else "❌ Test gagal — cek TG_BOT_TOKEN & TG_CHAT_ID")
    return ok

def get_chatid():
    if not TG_BOT_TOKEN:
        print("⚠️  Set TG_BOT_TOKEN dulu (export TG_BOT_TOKEN='…')")
        return
    try:
        with urllib.request.urlopen(f'{BASE_URL}/getUpdates', timeout=8) as r:
            data = json.loads(r.read().decode())
        if data.get('ok') and data.get('result'):
            for upd in data['result']:
                msg = upd.get('message') or upd.get('edited_message', {})
                if msg:
                    chat = msg.get('chat', {})
                    print(f"Chat ID : {chat.get('id')}")
                    print(f"Nama    : {chat.get('first_name','')} {chat.get('last_name','')}")
                    print(f"Username: @{chat.get('username','?')}")
                    return
            print("Kirim /start ke bot Anda dulu, lalu jalankan ulang.")
        else:
            print(f"Error: {data}")
    except Exception as e:
        print(f"Gagal: {e}")

# ─── CLI ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--test',       action='store_true')
    p.add_argument('--get-chatid', action='store_true')
    p.add_argument('--blokir',     metavar='DOMAIN')
    p.add_argument('--izin',       metavar='DOMAIN')
    args = p.parse_args()

    if args.test:                test_koneksi()
    elif args.get_chatid:        get_chatid()
    elif args.blokir:
        notif_blokir(args.blokir, kategori='negatif',
                     perangkat='Test', confidence=95.5)
        print(f"Notif blokir dikirim: {args.blokir}")
    elif args.izin:
        notif_minta_izin(args.izin, 'Test Anak')
        print(f"Notif izin dikirim: {args.izin}")
    else:
        p.print_help()
