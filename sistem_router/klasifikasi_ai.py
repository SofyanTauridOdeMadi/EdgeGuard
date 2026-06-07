"""
╔══════════════════════════════════════════════════════════════════════╗
║  EDGE GUARD — KLASIFIKASI AI (Pure-Python, NO scikit-learn)         ║
║                                                                      ║
║  Replikasi 1:1 pipeline pelatihan (AI_LATIH.ipynb):                  ║
║    1) normalize_domain(domain)  — bersihkan SNI                      ║
║    2) augment_keyword(...)      — boost via keyword global           ║
║    3) char_wb n-gram (3..5)                                          ║
║    4) TF-IDF dengan sublinear_tf  (tf = 1 + log(tf))                 ║
║    5) L2 normalize vector                                            ║
║    6) MultinomialNB log-proba scoring                                ║
║                                                                      ║
║  Input  : domain SNI (mis. 'youtube.com')                            ║
║  Output : {'kategori':..., 'confidence':..., 'aksi':...}             ║
║                                                                      ║
║  Test:                                                               ║
║    python3 klasifikasi_ai.py khanacademy.org youtube.com bet365.com  ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, math, time, re
import urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CLOUD_URL, CONFIG_TTL, HTTP_TIMEOUT, DEBUG, mk_ssl_ctx

BASE        = os.path.dirname(os.path.abspath(__file__))
MODEL_JSON  = os.path.join(BASE, 'model_export.json')

# ─── ANTI OVER-BLOCK ───────────────────────────────────────────────────────
# Model v2.10 punya 4 kelas: negatif / edukasi / hiburan / netral.
# Kelas 'netral' menangkap subdomain teknis (CDN, sertifikat, telemetri).
# Dua pengaman tambahan tetap dipertahankan sebagai lapisan perlindungan:
#   1) _INFRA_WHITELIST → domain & subdomain ini TIDAK PERNAH diblokir.
#   2) BLOCK_THRESHOLD  → 'negatif' hanya diblokir bila confidence >= ambang.
BLOCK_THRESHOLD = float(os.environ.get('EG_BLOCK_THRESHOLD', '80'))

_INFRA_WHITELIST = {
    # Apple
    'icloud.com','apple.com','mzstatic.com','cdn-apple.com','aaplimg.com',
    'apple-cloudkit.com','push.apple.com',
    # Google (infra/CDN/ads/analytics)
    'googleapis.com','gstatic.com','google.com','googleusercontent.com','ggpht.com',
    'doubleclick.net','googlesyndication.com','google-analytics.com','googletagmanager.com',
    'gvt1.com','gvt2.com','app-measurement.com','crashlytics.com','firebaseio.com',
    # Microsoft / Bing
    'microsoft.com','bing.com','live.com','office.com','windows.com','msftncsi.com',
    'msedge.net','windowsupdate.com','azureedge.net',
    # CDN umum
    'cloudflare.com','cloudfront.net','akamai.net','akamaihd.net','akamaized.net',
    'fastly.net','jsdelivr.net','fontawesome.com','fbcdn.net','cdninstagram.com',
    'gcore.com','unpkg.com','cloudflareinsights.com',
    # Sertifikat / OCSP / trust
    'globalsign.com','digicert.com','letsencrypt.org','sectigo.com','usertrust.com',
    'entrust.net','amazontrust.com','godaddy.com',
    # Telemetri / dev / analytics (tidak berbahaya untuk anak)
    'github.com','githubusercontent.com','githubassets.com','datadoghq.com','sentry.io',
    'hubspot.com','hs-banner.com','hs-analytics.net','appsflyersdk.com','appsflyer.com',
    'exp-tas.com','snssdk.com','doubao.com','byteoversea.com','ibyteimg.com',
    'sgpstatic.com',
    # Banking & payment Indonesia — JANGAN PERNAH diblokir
    'bca.co.id','klikbca.com','halonasabah.bca.co.id',
    'bri.co.id','brimo.bri.co.id','ibank.bri.co.id',
    'bni.co.id','ocbc.id','mandiri.co.id','livin.mandiri.co.id',
    'cimbniaga.co.id','danamon.co.id','permatabank.com',
    'gopay.co.id','dana.id','ovo.id','linkaja.id',
    'shopeepay.co.id','sakuku.bca.co.id',
    # Analytics / monitoring / ad-tech (infrastruktur teknis, bukan konten)
    'mixpanel.com','mix.panel.com',
    'newrelic.com','nr-data.net',
    'imrworldwide.com','scorecardresearch.com',
    'doubleverify.com','ias.com','integralads.com',
    'adnxs.com','appnexus.com',
    'amplitude.com','segment.com','heap.io',
    'optimizely.com','vwo.com',
    'intercom.com','intercom.io','intercomcdn.com',
    'hotjar.com','fullstory.com','logrocket.com',
    'revenuecat.com','appsflyer.com',
    # Streaming sah (sementara sampai model di-retrain)
    'wetvinfo.com','wetv.vip',
    # CDN / device system
    'avcdn.net','heytapmobile.com','heytapdl.com','oppomobile.com',
    'coloros.com','oneplus.com',
    'xiaomipush.com','micloud.xiaomi.net',
    # Samsung
    'samsungcloud.com','samsungelectronics.com','samsungdm.com',
}

def _is_infra(domain: str) -> bool:
    """True bila domain sama dengan, atau subdomain dari, entri whitelist infra."""
    d = (domain or '').lower()
    for suf in _INFRA_WHITELIST:
        if d == suf or d.endswith('.' + suf):
            return True
    return False

# ─── KOREKSI KATEGORI MANUAL ───────────────────────────────────────────────
# Lapisan domain-knowledge untuk domain populer yang sering keliru diklasifikasi
# model. Mencegah konten hiburan lolos sebagai 'netral' (tak terhitung kuota)
# dan situs sah salah dicap 'negatif'. Dicek SEBELUM inferensi AI.
_OVERRIDE_KATEGORI = {
    # Hiburan (sering salah → netral/negatif). WAJIB hiburan agar kena kuota.
    'douyin.com':      'hiburan',
    'xiaohongshu.com': 'hiburan',
    'xhscdn.com':      'hiburan',
    'bilibili.com':    'hiburan',
    'iqiyi.com':       'hiburan',
    'bigo.tv':         'hiburan',
    'likee.video':     'hiburan',
    # Donasi/sosial sah (sering salah → negatif). netral = diizinkan, tak dimeter.
    'kitabisa.com':    'netral',
    'benihbaik.com':   'netral',
}
def _override_kategori(domain: str):
    """Kembalikan kategori paksa untuk domain populer yang sering salah, atau None."""
    d = (domain or '').lower()
    for suf, kat in _OVERRIDE_KATEGORI.items():
        if d == suf or d.endswith('.' + suf):
            return kat
    return None

def _match_koreksi(domain: str, koreksi: dict):
    """Cocokkan domain dgn koreksi manual orang tua (dict {domain: kategori})
    dari VPS — exact match atau subdomain. Kembalikan kategori atau None."""
    d = (domain or '').lower()
    if not koreksi:
        return None
    if d in koreksi:
        return koreksi[d]
    for dom, kat in koreksi.items():
        if dom and d.endswith('.' + dom):
            return kat
    return None

# ─── Cache model & config ─────────────────────────────────────────────────
_MODEL           = None
_config_cache    = {}
_config_cache_ts = 0
_kategori_aksi   = {}

# ═══════════════════════════════════════════════════════════════════════════
# 1. LOAD MODEL
# ═══════════════════════════════════════════════════════════════════════════
def load_model():
    global _MODEL
    if _MODEL is not None: return _MODEL
    if not os.path.exists(MODEL_JSON):
        raise FileNotFoundError(
            f"Model tidak ditemukan: {MODEL_JSON}\n"
            f"Latih dulu di laptop lalu salin model_export.json ke router.")
    with open(MODEL_JSON, encoding='utf-8') as f:
        data = json.load(f)
    _MODEL = {
        'vocab':     data['vocabulary'],
        'idf':       data['idf'],
        'log_prob':  data['log_prob'],
        'log_prior': data['log_prior'],
        'label_map': {int(k): v for k, v in data['label_map'].items()},
        'ngram':     tuple(data['meta'].get('ngram', [3, 5])),
        'keyword':   data.get('keyword_global', {}) or {},
        'meta':      data['meta'],
    }
    m = _MODEL['meta']
    print(f"[AI] Model dimuat: v{m.get('versi','?')} | "
          f"akurasi {m.get('akurasi','?')}% | "
          f"{len(_MODEL['vocab'])} fitur | "
          f"n-gram {_MODEL['ngram']}")
    return _MODEL

# ═══════════════════════════════════════════════════════════════════════════
# 2. PRE-PROCESSING  (REPLIKA dari AI_LATIH.ipynb)
# ═══════════════════════════════════════════════════════════════════════════
_TLD = {
    # Generic TLD
    'com','net','org','id','co','io','info','biz','gov','edu','ac','tv','me',
    'xyz','cc','cam','cf','tk','online','site','store','link','app',
    # Country-code TLD (ccTLD) — sering muncul di SNI sebagai bagian domain pendek
    'in','au','jp','sg','uk','de','fr','cn','ru','nl','br','us','ca',
    'my','th','vn','ph','nz','za','eu','it','es','pl','kr','hk','tw',
    'tr','sa','ae','pk','bd','lk','mm','kh','la','mn','az','kz',
}
_PREFIX = {'www.','m.','api.','cdn.','en.','ads.','static.','web.','mobile.'}

# Token minimum 3 karakter agar n-gram bermakna (a, ab, 8d, vr, uk, sg, dll)
_MIN_TOKEN_LEN = 3

def normalize_domain(domain: str) -> str:
    """Tokenisasi SNI — identik dengan training.
    Perubahan v2.11: min token 3 char + ccTLD difilter → kurangi noise domain pendek.
    """
    d = str(domain).lower().strip()
    for pfx in _PREFIX:
        if d.startswith(pfx):
            d = d[len(pfx):]
            break
    parts = []
    for seg in re.split(r'[\.\-_]', d):
        if seg and seg not in _TLD and not seg.isdigit() and len(seg) >= _MIN_TOKEN_LEN:
            parts.append(seg)
            # Token alternatif tanpa digit di akhir (slot88 → slot)
            stripped = seg.rstrip('0123456789')
            if stripped and stripped != seg and len(stripped) >= _MIN_TOKEN_LEN:
                parts.append(stripped)
    result = ' '.join(list(dict.fromkeys(parts)))
    # Safety net: jika hasil normalisasi kosong/terlalu pendek,
    # kembalikan segmen domain terpanjang dari domain asli sebagai fallback.
    if len(result) < _MIN_TOKEN_LEN:
        segs = [s for s in re.split(r'[\.\-_]', d) if len(s) >= _MIN_TOKEN_LEN]
        result = ' '.join(segs) if segs else d.replace('.', ' ')
    return result

def augment_keyword(text_combined: str, keyword_global: dict) -> str:
    """Tambahkan token kw_<kategori>_<keyword> (repeat 2x) — identik training."""
    t = text_combined.lower()
    found = []
    for kat, keywords in (keyword_global or {}).items():
        for kw in keywords:
            if kw and kw in t:
                tok = f"kw_{kat}_{kw.replace(' ', '_')}"
                found.extend([tok, tok])
    return text_combined + (' ' + ' '.join(found) if found else '')

def build_features(domain: str, keyword_global: dict) -> str:
    """Saat inference kita HANYA punya SNI. DESK_SITUS & TRAFIK tidak ada
    di routing realtime → fallback 'traf_unk' (sama seperti encode_trafik
    untuk nilai tak dikenal)."""
    sni_tokens   = normalize_domain(domain)
    trafik_token = 'traf_unk'
    combined     = f"{sni_tokens} {trafik_token}".strip()
    return augment_keyword(combined, keyword_global)

# ═══════════════════════════════════════════════════════════════════════════
# 3. CHAR_WB N-GRAM  (replika TfidfVectorizer analyzer='char_wb')
#    sklearn 'char_wb' = char n-gram TAPI hanya dalam word boundary
#    (pad tiap WORD dengan spasi, lalu n-gram di dalam word saja)
# ═══════════════════════════════════════════════════════════════════════════
def char_wb_ngrams(text: str, n_min: int, n_max: int) -> dict:
    """char_wb n-gram: tiap word dipad dengan spasi di kiri/kanan,
    lalu char n-gram diambil dari padded word saja (tidak melintasi spasi)."""
    grams = {}
    for word in text.split():
        if not word: continue
        padded = ' ' + word + ' '
        L = len(padded)
        for n in range(n_min, n_max + 1):
            if L < n: continue
            for i in range(L - n + 1):
                g = padded[i:i+n]
                grams[g] = grams.get(g, 0) + 1
    return grams

# ═══════════════════════════════════════════════════════════════════════════
# 4. INFERENSI MULTINOMIAL NAIVE BAYES (dengan TF-IDF sublinear + L2)
# ═══════════════════════════════════════════════════════════════════════════
def klasifikasi(domain: str) -> dict:
    m = load_model()
    ng_min, ng_max = m['ngram']

    # 1) Pre-process identik training
    feat_text  = build_features(domain, m['keyword'])

    # 2) char_wb n-gram → raw count
    raw_grams  = char_wb_ngrams(feat_text, ng_min, ng_max)

    # 3) sublinear TF (1 + log(tf)) × IDF, hanya untuk ngram yang ada di vocab
    vocab = m['vocab']
    idf   = m['idf']
    tfidf = {}    # {col_idx: weight}
    for gram, cnt in raw_grams.items():
        col = vocab.get(gram)
        if col is not None and cnt > 0:
            tf = 1.0 + math.log(cnt)             # sublinear_tf=True
            tfidf[col] = tf * idf[col]

    # 4) L2 normalize (sklearn TfidfVectorizer default norm='l2')
    norm = math.sqrt(sum(v*v for v in tfidf.values()))
    if norm > 0:
        for k in tfidf:
            tfidf[k] /= norm

    # 5) Naive Bayes scoring: log P(c|x) ∝ log_prior + Σ x_i * log_prob[c][i]
    n_kelas = len(m['log_prior'])
    scores  = list(m['log_prior'])
    for col, val in tfidf.items():
        for k in range(n_kelas):
            scores[k] += val * m['log_prob'][k][col]

    # 6) Softmax → probabilitas
    max_s     = max(scores)
    exp_s     = [math.exp(s - max_s) for s in scores]
    total_exp = sum(exp_s) or 1.0
    proba     = [e / total_exp for e in exp_s]

    pred_idx   = proba.index(max(proba))
    label      = m['label_map'][pred_idx]
    confidence = round(proba[pred_idx] * 100, 1)

    return {
        'domain':      domain,
        'kategori':    label,
        'confidence':  confidence,
        'skor_kelas':  {m['label_map'][i]: round(p*100, 1) for i, p in enumerate(proba)},
    }

# ═══════════════════════════════════════════════════════════════════════════
# 5. SYNC CONFIG dari VPS  (whitelist/blacklist/jeda)
# ═══════════════════════════════════════════════════════════════════════════
def ambil_config() -> dict:
    global _config_cache, _config_cache_ts, _kategori_aksi
    now = time.time()
    if now - _config_cache_ts < CONFIG_TTL and _config_cache:
        return _config_cache
    try:
        req = urllib.request.Request(
            CLOUD_URL + '/api/config',
            headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=mk_ssl_ctx()) as r:
            data = json.loads(r.read().decode())
        _config_cache    = data
        _config_cache_ts = now
        _kategori_aksi   = {
            k.get('nama',''): k.get('aksi','netral')
            for k in data.get('kategori_ai', [])
        }
        return data
    except Exception:
        return _config_cache or {
            'ai_aktif': True,
            'daftar_putih': [], 'daftar_hitam': [],
            'perangkat_jeda': [], 'kategori_ai': [],
        }

def aksi_kategori(nama: str) -> str:
    """Kembalikan aksi untuk kategori AI.
    'netral' = domain infrastruktur/CDN (model v2.1+) → selalu izinkan.
    'unknown' = alias lama, diperlakukan sama dgn netral → izinkan."""
    if not _kategori_aksi: ambil_config()
    aksi = _kategori_aksi.get(nama)
    if aksi and aksi != 'netral': return aksi   # 'blokir'/'izinkan' eksplisit
    # Fallback deterministik: hanya negatif yang diblokir
    if nama == 'negatif':  return 'blokir'
    return 'izinkan'  # edukasi, hiburan, netral, unknown → izinkan

# ═══════════════════════════════════════════════════════════════════════════
# 6. KEPUTUSAN TERPADU  (jeda > whitelist > blacklist > AI)
# ═══════════════════════════════════════════════════════════════════════════
def putuskan(domain: str, mac_src: str = '') -> dict:
    d   = domain.lower().strip()
    if d.startswith('www.'): d = d[4:]
    cfg = ambil_config()

    # Catatan: penjedaan / kuota-habis TIDAK lagi ditangani di sini.
    # Enforcement per-perangkat dilakukan di level jaringan (kuota_tracker.py →
    # captive_portal.sh block-mac → redirect SEMUA web MAC tsb ke portal).
    # putuskan() murni klasifikasi konten domain, sehingga aktivitas perangkat
    # yang dijeda tetap tercatat (untuk audit) tanpa meracuni blocklist global.

    # 1) Blacklist domain — paling tinggi untuk AKSES (keamanan menang).
    hitam = cfg.get('daftar_hitam', [])
    if any(d == e or d.endswith('.' + e) for e in hitam if e):
        return {'domain': d, 'aksi':'blokir', 'alasan':'blacklist',
                'kategori':'negatif', 'confidence':100}

    # 2) Koreksi MANUAL orang tua dari dashboard — override TERTINGGI atas
    # kategori. WAJIB dicek SEBELUM whitelist: domain whitelist diberi label
    # 'edukasi' bawaan, jadi kalau koreksi dicek belakangan (mis. whatsapp.com
    # → netral) hasilnya selalu ditimpa balik ke 'edukasi'. Dibaca dari
    # /api/config; tanpa perlu edit kode/retrain.
    kk = _match_koreksi(d, cfg.get('koreksi_kategori', {}))
    if kk:
        return {'domain': d, 'aksi':('blokir' if kk == 'negatif' else 'izinkan'),
                'alasan':'koreksi_manual', 'kategori':kk, 'confidence':100}

    # 3) Whitelist domain (cek exact match DAN subdomain) → selalu izinkan,
    # label default 'edukasi'.
    putih = cfg.get('daftar_putih', [])
    if any(d == e or d.endswith('.' + e) for e in putih if e):
        return {'domain': d, 'aksi':'izinkan', 'alasan':'whitelist',
                'kategori':'edukasi', 'confidence':100}

    # 3c) Domain infrastruktur/CDN/sertifikat → selalu izinkan (safety net).
    if _is_infra(d):
        return {'domain': d, 'aksi':'izinkan', 'alasan':'infrastruktur',
                'kategori':'netral', 'confidence':0}

    # 3d) Koreksi kategori bawaan (domain populer yang sering salah model).
    ov = _override_kategori(d)
    if ov:
        return {'domain': d, 'aksi':('blokir' if ov == 'negatif' else 'izinkan'),
                'alasan':'override', 'kategori':ov, 'confidence':100}

    # 4) Klasifikasi AI
    if cfg.get('ai_aktif', True):
        try:
            h    = klasifikasi(d)
            kat  = h['kategori']
            conf = h['confidence']
            aksi = aksi_kategori(kat)
            if aksi == 'netral': aksi = 'izinkan'

            # Anti over-block: 'negatif' hanya diblokir bila yakin (>= ambang).
            # Confidence rendah → AI ragu → JANGAN blokir DAN jangan beri label
            # 'negatif' (cegah inkonsistensi "negatif tapi diizinkan" di riwayat).
            # Diperlakukan 'netral' agar konsisten dengan cache_domain.
            if aksi == 'blokir' and conf < BLOCK_THRESHOLD:
                return {'domain': d, 'aksi':'izinkan', 'alasan':'confidence_rendah',
                        'kategori':'netral', 'confidence':conf}

            return {'domain': d, 'aksi':aksi, 'alasan':'klasifikasi_ai',
                    'kategori':kat, 'confidence':conf}
        except Exception as e:
            if DEBUG: print(f"[AI] error {d}: {e}")

    return {'domain': d, 'aksi':'izinkan', 'alasan':'ai_nonaktif',
            'kategori':'unknown', 'confidence':0}

# ═══════════════════════════════════════════════════════════════════════════
# 7. CLI TEST
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    load_model()
    domains = sys.argv[1:] or [
        'khanacademy.org','duolingo.com','wikipedia.org','ruangguru.com',
        'youtube.com','tiktok.com','instagram.com','spotify.com',
        'bet365.com','pornhub.com','dewa777slot.net','xnxx.com',
        'google.com','facebook.com',
    ]
    print(f"\n{'DOMAIN':<28} {'KATEGORI':<10} {'CONF':>6}  {'SKOR':<30}")
    print('─' * 80)
    for d in domains:
        r = klasifikasi(d)
        aksi = aksi_kategori(r['kategori'])
        if aksi == 'netral': aksi = 'izinkan'
        ic = '🚫' if aksi == 'blokir' else '✅'
        sk = '  '.join(f"{k[:3]}:{v:.0f}" for k,v in r['skor_kelas'].items())
        print(f"{d:<28} {r['kategori']:<10} {r['confidence']:>5}%  {ic} {sk}")
