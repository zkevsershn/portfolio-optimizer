"""
engine.py  —  Portföy Optimizatörü
  1. Shortlist: ham_girdi_topsis.csv → TOPSIS C skoru
  2. Markowitz: min-variance optimizasyonu (fiyat_verisi.csv)
  3. Benchmark: fiyat_verisi_25.csv — uygulama başında bir kez okunur, cache'lenir
"""

import os, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

# ─── Sabitler ────────────────────────────────────────────────────────────────
RISKSIZ_FAIZ = 0.45
MIN_AGIRLIK  = 0.0
MAX_AGIRLIK  = 0.25
TRADING_DAYS = 249

KATEGORI_HISSELER = {
    "Bankacılık":           ["AKBNK","ALBRK","GARAN","HALKB","ISCTR","QNBTR","SKBNK","TSKB","VAKBN","YKBNK"],
    "Holding ve Yatırım":   ["AGHOL","ALARK","BRYAT","DOHOL","ECZYT","IEYHO","KCHOL","KLRHO","SAHOL","TAVHL"],
    "Bilişim ve Teknoloji": ["ARDYZ","ASELS","EDATA","HTTBT","INDES","KAREL","LOGO","MANAS","MIATK","PAPIL"],
    "Ulaştırma":            ["BEYAZ","CLEBI","GRSEL","GSDDE","DOAS","PGSUS","RYSAS","THYAO","TLMAN","TUREX"],
    "Gıda ve İçecek":       ["AEFES","BANVT","CCOLA","KENT","KNFRT","PNSUT","TATGD","TBORG","TUKAS","ULKER"],
    "Hizmetler":            ["BIGTK","BIMAS","MAALT","MAVI","MGROS","MPARK","PENTA","TCELL","TTKOM","YATAS"],
    "Sanayi":               ["ARCLK","EREGL","FROTO","TRALT","KRDMD","OTKAR","SISE","TOASO","TUPRS","TTRAK"],
    "Kimya Petrol Plastik": ["AKSA","AYGAZ","BRSAN","EUREN","GUBRF","HEKTS","ISKPL","IZFAS","PETKM","SASA"],
    "İnşaat ve GYO":        ["ALGYO","EKGYO","ENKAI","ISGYO","KUYAS","ORGE","PEKGY","TRGYO","TURGG","ZRGYO"],
    "Enerji":               ["AKENR","AKSEN","AYDEM","BIOEN","ENJSA","GESAN","GWIND","KONTR","ODAS","ZOREN"],
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))

HAM_GIRDI_PATH = os.environ.get("HAM_GIRDI_PATH", os.path.join(DATA_DIR, "ham_girdi_topsis.csv"))
FIYAT_PATH     = os.environ.get("FIYAT_PATH",     os.path.join(DATA_DIR, "fiyat_verisi.csv"))
GERCEK_PATH    = os.environ.get("GERCEK_PATH",    os.path.join(DATA_DIR, "fiyat_verisi_25.csv"))

EXCEL_KAT_MAP = {
    "İnşaat GYO":   "İnşaat ve GYO",
    "Kimya Petrol": "Kimya Petrol Plastik",
}

# ─── Uygulama başında bir kez oku, bellekte tut ──────────────────────────────
_fiyat_df  = None
_gercek_df = None
_ham_df    = None

def _fiyat_yukle():
    global _fiyat_df
    if _fiyat_df is None and os.path.exists(FIYAT_PATH):
        try:
            df = pd.read_csv(FIYAT_PATH, index_col=0)
            df.index = pd.to_datetime(df.index, errors="coerce")
            _fiyat_df = df.sort_index()
            print(f"[OK] fiyat_verisi yüklendi: {_fiyat_df.shape}")
        except Exception as e:
            print(f"[HATA] fiyat_verisi okunamadı: {e}")
    return _fiyat_df

def _gercek_yukle():
    global _gercek_df
    if _gercek_df is None and os.path.exists(GERCEK_PATH):
        try:
            df = pd.read_csv(GERCEK_PATH, index_col=0)
            df.index = pd.to_datetime(df.index, errors="coerce")
            _gercek_df = df.sort_index()
            print(f"[OK] fiyat_verisi_25 yüklendi: {_gercek_df.shape}")
        except Exception as e:
            print(f"[HATA] fiyat_verisi_25 okunamadı: {e}")
    return _gercek_df

def _ham_yukle():
    global _ham_df
    if _ham_df is None and os.path.exists(HAM_GIRDI_PATH):
        try:
            _ham_df = pd.read_csv(HAM_GIRDI_PATH)
            print(f"[OK] ham_girdi yüklendi: {_ham_df.shape}")
        except Exception as e:
            print(f"[HATA] ham_girdi okunamadı: {e}")
    return _ham_df

# Sunucu başlarken hepsini yükle
_fiyat_yukle()
_gercek_yukle()
_ham_yukle()

# ─── Benchmark: sabit veri, bir kez hesaplanır ───────────────────────────────
_benchmark_cache = None

def benchmark_getiri(_unused=None):
    global _benchmark_cache
    if _benchmark_cache is not None:
        return _benchmark_cache

    df = _gercek_yukle()
    if df is None:
        return {}

    KOLONLAR = [("XU100","BIST 100"), ("XU030","BIST 30"), ("USDTRY","USD/TRY"), ("ALTIN","Altın")]
    results = {}
    for col, label in KOLONLAR:
        if col not in df.columns:
            continue
        prices = df[col].dropna()
        cum    = (prices / prices.iloc[0] - 1) * 100
        results[label] = {
            "ret":   round(float(cum.iloc[-1]), 2),
            "zaman": [{"tarih": str(idx.date()), "deger": round(float(v), 4)} for idx, v in cum.items()],
        }

    _benchmark_cache = results
    return _benchmark_cache

# ─── Shortlist ────────────────────────────────────────────────────────────────
def shortlist_olustur(secilen_kategoriler, zorunlu_hisseler=None, cikartilan_hisseler=None):
    zorunlu    = zorunlu_hisseler    or []
    cikartilan = cikartilan_hisseler or []
    tum_sonuclar = []

    df_t = _ham_yukle()
    if df_t is not None:
        try:
            df_t = df_t.copy()
            # Unnamed: 3 kolonu kategori adını tutuyor, ffill ile doldur
            df_t["_kat"] = df_t["Unnamed: 3"].ffill().map(
                lambda k: EXCEL_KAT_MAP.get(str(k).strip(), str(k).strip()) if pd.notna(k) else k
            )
            for kat in secilen_kategoriler:
                kat_df = df_t[df_t["_kat"] == kat][["Ticker", "C skoru"]].dropna()
                for _, row in kat_df.iterrows():
                    tum_sonuclar.append((str(row["Ticker"]).strip(), kat, float(row["C skoru"])))
        except Exception as e:
            print(f"[HATA] shortlist: {e}")

    shortlist = []
    eklenen   = set()

    for ticker in zorunlu:
        entry = next((x for x in tum_sonuclar if x[0] == ticker), None)
        if entry and ticker not in eklenen and ticker not in cikartilan:
            shortlist.append({"ticker": ticker, "kategori": entry[1], "zorunlu": True})
            eklenen.add(ticker)

    n_kat       = len(secilen_kategoriler)
    zorunlu_say = len(shortlist)
    kota        = (30 - zorunlu_say) // n_kat if n_kat else 0

    for kat in secilen_kategoriler:
        adet = 0
        for ticker, k, _ in tum_sonuclar:
            if k != kat or ticker in eklenen or ticker in cikartilan:
                continue
            shortlist.append({"ticker": ticker, "kategori": kat, "zorunlu": False})
            eklenen.add(ticker)
            adet += 1
            if adet == kota:
                break

    return shortlist


# ─── Markowitz ────────────────────────────────────────────────────────────────
def markowitz(tickers, fiyat_path=None,
              min_agirlik=MIN_AGIRLIK,
              max_agirlik=MAX_AGIRLIK,
              risksiz_faiz=RISKSIZ_FAIZ,
              target_return=0.50):

    df = _fiyat_yukle()
    if df is None:
        return None, None, None

    mevcut = [t for t in tickers if t in df.columns]
    if len(mevcut) < 2:
        return None, None, None

    ret    = np.log(df[mevcut] / df[mevcut].shift(1)).iloc[1:].dropna(how="any")
    mevcut = list(ret.columns)
    n      = len(mevcut)

    mu    = ret.mean().values * TRADING_DAYS
    Sigma = ret.cov().values  * TRADING_DAYS

    def port_var(w): return float(w @ Sigma @ w)

    bounds = [(max(0.0, min_agirlik), max_agirlik)] * n
    w0     = np.ones(n) / n

    res = minimize(port_var, w0, method="SLSQP", bounds=bounds,
                   constraints=[
                       {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
                       {"type": "eq", "fun": lambda w: float(w @ mu) - target_return},
                   ],
                   options={"ftol": 1e-9, "maxiter": 500})

    if not res.success:
        return None, None, {"optimize_hatasi": res.message}

    w_opt       = res.x
    port_ret    = float(w_opt @ mu)
    port_vol    = float(np.sqrt(w_opt @ Sigma @ w_opt))
    port_sharpe = (port_ret - risksiz_faiz) / port_vol if port_vol > 0 else float("nan")

    # Frontier — 10 nokta
    res_mv = minimize(port_var, w0, method="SLSQP", bounds=bounds,
                      constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
                      options={"ftol": 1e-9, "maxiter": 300})
    mv_ret = float(res_mv.x @ mu) if res_mv.success else float(np.min(mu))
    ret_lo = min(mv_ret, target_return)
    ret_hi = float(np.max(mu)) * 0.97
    frontier = []
    for tr in np.linspace(ret_lo, ret_hi, 10):
        r2 = minimize(port_var, w0, method="SLSQP", bounds=bounds,
                      constraints=[
                          {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
                          {"type": "eq", "fun": lambda w, tr=tr: float(w @ mu) - tr},
                      ],
                      options={"ftol": 1e-8, "maxiter": 300})
        if r2.success:
            frontier.append({
                "vol": round(float(np.sqrt(r2.x @ Sigma @ r2.x)) * 100, 2),
                "ret": round(float(tr) * 100, 2),
            })

    return mevcut, w_opt, {
        "getiri":     port_ret,
        "volatilite": port_vol,
        "sharpe":     port_sharpe,
        "mu":         mu.tolist(),
        "frontier":   frontier,
    }


# ─── Gerçekleşen getiri — model portföyü için her seferinde hesaplanır ───────
def gerceklesen_zaman(tickers, weights, _unused=None):
    df = _gercek_yukle()
    if df is None:
        return []
    try:
        pairs = [(t, w) for t, w in zip(tickers, weights) if t in df.columns]
        if not pairs:
            return []
        tks = [t for t, _ in pairs]
        wts = np.array([w for _, w in pairs])
        wts = wts / wts.sum()
        ret = np.log(df[tks] / df[tks].shift(1)).iloc[1:].dropna(how="any")
        port_cum = (np.exp((ret * wts).sum(axis=1).cumsum()) - 1) * 100
        return [{"tarih": str(idx.date()), "deger": round(float(v), 4)} for idx, v in port_cum.items()]
    except Exception as e:
        print(f"[HATA] gerceklesen_zaman: {e}")
        return []


# ─── Ana pipeline ─────────────────────────────────────────────────────────────
def run_pipeline(
    secilen_kategoriler,
    zorunlu_hisseler,
    data_dir=None,
    fiyat_path=None,
    piyasa_path=None,
    hissec_sayisi=30,
    min_agirlik=MIN_AGIRLIK,
    max_agirlik=MAX_AGIRLIK,
    risksiz_faiz=RISKSIZ_FAIZ,
    target_return=0.50,
    cikartilan_hisseler=None,
    gercek_path=None,
):
    shortlist = shortlist_olustur(secilen_kategoriler, zorunlu_hisseler, cikartilan_hisseler)

    if not shortlist:
        return {"hata": "Shortlist oluşturulamadı. ham_girdi_topsis.csv dosyasını kontrol edin."}

    sl_tickers = [s["ticker"] for s in shortlist]
    mk_tickers, mk_weights, mk_stats = markowitz(
        sl_tickers,
        min_agirlik=min_agirlik,
        max_agirlik=max_agirlik,
        risksiz_faiz=risksiz_faiz,
        target_return=target_return,
    )

    markowitz_sonuc = None
    markowitz_uyari = None

    if isinstance(mk_stats, dict) and mk_stats.get("optimize_hatasi"):
        markowitz_uyari = mk_stats["optimize_hatasi"]
    elif mk_tickers and mk_weights is not None:
        markowitz_sonuc = {
            "tickers":    mk_tickers,
            "weights":    [round(float(w), 6) for w in mk_weights],
            "getiri":     round(mk_stats["getiri"] * 100, 2),
            "volatilite": round(mk_stats["volatilite"] * 100, 2),
            "sharpe":     round(mk_stats["sharpe"], 4),
            "mu":         [round(x * 100, 2) for x in mk_stats["mu"]],
            "frontier":   mk_stats["frontier"],
            "zaman":      gerceklesen_zaman(mk_tickers, mk_weights),
        }

    return {
        "shortlist":       shortlist,
        "markowitz":       markowitz_sonuc,
        "markowitz_uyari": markowitz_uyari,
        "benchmark":       benchmark_getiri(),
        "hata":            None,
    }
