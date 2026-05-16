import os
import secrets
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response

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

from engine import run_pipeline, KATEGORI_HISSELER, markowitz, gerceklesen_zaman, benchmark_getiri

app = Flask(__name__, static_folder="frontend", static_url_path="")


@app.route("/")
@requires_auth
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/api/kategoriler")
@requires_auth
def api_kategoriler():
    return jsonify({kat: hisseler for kat, hisseler in KATEGORI_HISSELER.items()})


@app.route("/api/hesapla", methods=["POST"])
@requires_auth
def api_hesapla():
    body = request.get_json(silent=True) or {}

    kategoriler       = body.get("kategoriler", [])
    zorunlu           = body.get("zorunlu_hisseler", [])
    cikartilan        = body.get("cikartilan_hisseler", [])
    hisse_sayisi      = int(body.get("hisse_sayisi", 30))
    min_agirlik       = float(body.get("min_agirlik", 0.0))
    max_agirlik       = float(body.get("max_agirlik", 0.25))
    risksiz_faiz      = float(body.get("risksiz_faiz", 0.45))
    target_return_raw = body.get("target_return", 0.50)
    target_return     = float(target_return_raw) if target_return_raw is not None else 0.50

    if not kategoriler:
        return jsonify({"hata": "En az bir kategori seçin."}), 400

    result = run_pipeline(
        secilen_kategoriler  = kategoriler,
        zorunlu_hisseler     = zorunlu,
        hissec_sayisi        = hisse_sayisi,
        min_agirlik          = min_agirlik,
        max_agirlik          = max_agirlik,
        risksiz_faiz         = risksiz_faiz,
        target_return        = target_return,
        cikartilan_hisseler  = cikartilan,
    )

    if result.get("hata"):
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/markowitz_guncelle", methods=["POST"])
@requires_auth
def api_markowitz_guncelle():
    body = request.get_json(silent=True) or {}

    tickers       = body.get("tickers", [])
    min_agirlik   = float(body.get("min_agirlik", 0.0))
    max_agirlik   = float(body.get("max_agirlik", 0.25))
    risksiz_faiz  = float(body.get("risksiz_faiz", 0.45))
    target_raw    = body.get("target_return", 0.50)
    target_return = float(target_raw) if target_raw is not None else 0.50

    if not tickers:
        return jsonify({"hata": "Ticker listesi boş."}), 400

    mk_tickers, mk_weights, mk_stats = markowitz(
        tickers,
        min_agirlik=min_agirlik,
        max_agirlik=max_agirlik,
        risksiz_faiz=risksiz_faiz,
        target_return=target_return,
    )

    if mk_tickers is None:
        return jsonify({"hata": "Markowitz hesaplanamadı."}), 500

    if isinstance(mk_stats, dict) and mk_stats.get("optimize_hatasi"):
        return jsonify({"uyari": mk_stats["optimize_hatasi"]}), 200

    return jsonify({
        "tickers":       mk_tickers,
        "weights":       [round(float(w), 6) for w in mk_weights],
        "getiri":        round(mk_stats["getiri"] * 100, 2),
        "volatilite":    round(mk_stats["volatilite"] * 100, 2),
        "sharpe":        round(mk_stats["sharpe"], 4),
        "mu":            [round(x * 100, 2) for x in mk_stats["mu"]],
        "frontier":      mk_stats["frontier"],
        "target_gercek": mk_stats.get("target_gercek"),
        "zaman":         gerceklesen_zaman(mk_tickers, mk_weights),
        "benchmark":     benchmark_getiri(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", debug=False, port=port)
