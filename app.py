import os
import secrets
from functools import wraps
from flask import request, Response

PASSWORD = os.environ.get("APP_PASSWORD", "markowitz123")

def check_auth(password):
    return secrets.compare_digest(password, PASSWORD)

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return Response("Giriş gerekli", 401,
                {"WWW-Authenticate": 'Basic realm="Portföy Optimizatörü"'})
        return f(*args, **kwargs)
    return decorated

import os, json
from flask import Flask, request, jsonify, send_from_directory
from engine import run_pipeline, KATEGORI_HISSELER

app = Flask(__name__, static_folder="frontend", static_url_path="")

# ─────────────────────────────────────────────────────────────────────────────
# VERİ KLASÖRÜ  —  Excel dosyalarının bulunduğu yer
# Varsayılan: backend/ ile aynı dizindeki  data/  klasörü
# Farklı bir klasör kullanmak istersen DATA_DIR ortam değişkenini ayarla.
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.environ.get("DATA_DIR",    os.path.join(BASE_DIR, "..", "data"))
FIYAT_PATH  = os.environ.get("FIYAT_PATH",  os.path.join(DATA_DIR, "fiyat_verisi.xlsx"))
PIYASA_PATH = os.environ.get("PIYASA_PATH", os.path.join(DATA_DIR, "piyasa_degeri.xlsx"))
GERCEK_PATH = os.environ.get("GERCEK_PATH", os.path.join(DATA_DIR, "fiyat_verisi_25.xlsx"))


@app.route("/")
@requires_auth
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/api/kategoriler")
@requires_auth
def api_kategoriler():
    """Tüm kategoriler ve hisse listeleri"""
    return jsonify({kat: hisseler for kat, hisseler in KATEGORI_HISSELER.items()})


@app.route("/api/hesapla", methods=["POST"])
@requires_auth
def api_hesapla():
    """
    Body (JSON):
    {
      "kategoriler":          ["Bankacılık", "Enerji", ...],
      "zorunlu_hisseler":     ["THYAO", "SISE"],
      "cikartilan_hisseler":  ["AKBNK"],        ← shortlist düzeltme aşaması
      "hisse_sayisi":         30,
      "min_agirlik":          0.005,
      "max_agirlik":          0.40,
      "risksiz_faiz":         0.45,
      "target_return":        0.60              ← null = min varyans
    }
    """
    body = request.get_json(silent=True) or {}

    kategoriler         = body.get("kategoriler", [])
    zorunlu             = body.get("zorunlu_hisseler", [])
    cikartilan          = body.get("cikartilan_hisseler", [])
    hisse_sayisi        = int(body.get("hisse_sayisi", 30))
    min_agirlik         = float(body.get("min_agirlik", 0.005))
    max_agirlik         = float(body.get("max_agirlik", 0.40))
    risksiz_faiz        = float(body.get("risksiz_faiz", 0.45))
    target_return_raw   = body.get("target_return", 0.40)
    target_return       = float(target_return_raw) if target_return_raw is not None else 0.40

    if not kategoriler:
        return jsonify({"hata": "En az bir kategori seçin."}), 400

    result = run_pipeline(
        secilen_kategoriler  = kategoriler,
        zorunlu_hisseler     = zorunlu,
        data_dir             = DATA_DIR,
        fiyat_path           = FIYAT_PATH,
        piyasa_path          = PIYASA_PATH,
        hissec_sayisi        = hisse_sayisi,
        min_agirlik          = min_agirlik,
        max_agirlik          = max_agirlik,
        risksiz_faiz         = risksiz_faiz,
        target_return        = target_return,
        cikartilan_hisseler  = cikartilan,
        gercek_path          = GERCEK_PATH,
    )

    if result.get("hata"):
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/markowitz_guncelle", methods=["POST"])
@requires_auth
def api_markowitz_guncelle():
    """
    Shortlist sabitken sadece Markowitz parametrelerini değiştir.
    (slider hareketi gibi hızlı güncellemeler için)
    Body:
    {
      "tickers":        ["AKBNK", "THYAO", ...],
      "min_agirlik":    0.005,
      "max_agirlik":    0.40,
      "risksiz_faiz":   0.45,
      "target_return":  0.70
    }
    """
    from engine import markowitz, benchmark_getiri
    body = request.get_json(silent=True) or {}

    tickers       = body.get("tickers", [])
    min_agirlik   = float(body.get("min_agirlik", 0.005))
    max_agirlik   = float(body.get("max_agirlik", 0.40))
    risksiz_faiz  = float(body.get("risksiz_faiz", 0.45))
    target_raw    = body.get("target_return", 0.40)
    target_return = float(target_raw) if target_raw is not None else 0.40

    if not tickers:
        return jsonify({"hata": "Ticker listesi boş."}), 400

    mk_tickers, mk_weights, mk_stats = markowitz(
        tickers, FIYAT_PATH,
        min_agirlik=min_agirlik,
        max_agirlik=max_agirlik,
        risksiz_faiz=risksiz_faiz,
        target_return=target_return,
    )

    if mk_tickers is None:
        return jsonify({"hata": "Markowitz hesaplanamadı."}), 500

    from engine import gerceklesen_zaman
    return jsonify({
        "tickers":    mk_tickers,
        "weights":    [round(float(w), 6) for w in mk_weights],
        "getiri":     round(mk_stats["getiri"] * 100, 2),
        "volatilite": round(mk_stats["volatilite"] * 100, 2),
        "sharpe":     round(mk_stats["sharpe"], 4),
        "mu":         [round(x * 100, 2) for x in mk_stats["mu"]],
        "corr":       [[round(v, 4) for v in row] for row in mk_stats["corr"]],
        "frontier":   mk_stats["frontier"],
        "zaman":      gerceklesen_zaman(mk_tickers, mk_weights, GERCEK_PATH),
        "benchmark":  benchmark_getiri(GERCEK_PATH),
    })


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Portföy Optimizatörü — Flask Sunucusu")
    print(f"  Veri klasörü : {DATA_DIR}")
    print(f"  Fiyat verisi : {FIYAT_PATH}")
    print(f"  Piyasa değeri: {PIYASA_PATH}")
    print("="*55)
    print("  Tarayıcıda aç: http://localhost:5000\n")
    app.run(debug=True, port=5000)
