"""
engine.py  —  Portföy Optimizatörü
Yalnızca:
  1. Shortlist: ham_girdi_topsis.csv → her kategoriden ilk 3
  2. Markowitz: min-variance optimizasyonu (fiyat_verisi.csv)
  3. Benchmark: gerçekleşen getiri (fiyat_verisi_25.csv)
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

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

HAM_GIRDI_CSV = os.path.join(DATA_DIR, "ham_girdi_topsis.csv")
FIYAT_CSV     = os.path.join(DATA_DIR, "fiyat_verisi.csv")
GERCEK_CSV    = os.path.join(DATA_DIR, "fiyat_verisi_25.csv")

EXCEL_KAT_MAP = {
    "İnşaat GYO":   "İnşaat ve GYO",
    "Kimya Petrol": "Kimya Petrol Plastik",
}


# ─── Shortlist ────────────────────────────────────────────────────────────────
def shortlist_olustur(secilen_kategoriler, zorunlu_hisseler=None, cikartilan_hisseler=None):
    zorunlu    = zorunlu_hisseler    or []
    cikartilan = cikartilan_hisseler or []

    tum_sonuclar = []

    if os.path.exists(HAM_GIRDI_CSV):
        try:
            df_t = pd.read_csv(HAM_GIRDI_CSV)
            df_t["_kat"] = df_t["Unnamed: 3"].ffill().map(lambda k: EXCEL_KAT_MAP.get(k, k) if pd.notna(k) else k)
            for kat in secilen_kategoriler:
                kat_df = df_t[df_t["_kat"] == kat][["Ticker", "C skoru"]].dropna()
                for _, row in kat_df.iterrows():
                    tum_sonuclar.append((str(row["Ticker"]).strip(), kat, float(row["C skoru"])))
        except Exception:
            pass

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

    # FIX: fiyat_path parametresini kullan
    csv_path = fiyat_path if fiyat_path and os.path.exists(fiyat_path) else FIYAT_CSV
    if not os.path.exists(csv_path):
        return None, None, None

    df = pd.read_csv(csv_path, index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.sort_index()

    mevcut = [t for t in tickers if t in df.columns]
    if len(mevcut) < 2:
        return None, None, None

    df  = df[mevcut]
    ret = np.log(df / df.shift(1)).iloc[1:]
    ret = ret.dropna(how="any")
    mevcut = list(ret.columns)
    n = len(mevcut)

    mu    = ret.mean().values * TRADING_DAYS
    Sigma = ret.cov().values  * TRADING_DAYS

    def port_var(w): return float(w @ Sigma @ w)

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: float(w @ mu) - target_return},
    ]
    bounds = [(max(0.0, min_agirlik), max_agirlik)] * n
    w0     = np.ones(n) / n

    # FIX: maxiter düşürüldü
    res = minimize(port_var, w0, method="SLSQP", bounds=bounds,
                   constraints=constraints, options={"ftol": 1e-9, "maxiter": 500})

    if not res.success:
        return None, None, {"optimize_hatasi": res.message}

    w_opt       = res.x
    port_ret    = float(w_opt @ mu)
    port_vol    = float(np.sqrt(w_opt @ Sigma @ w_opt))
    port_sharpe = (port_ret - risksiz_faiz) / port_vol if port_vol > 0 else float("nan")

    return mevcut, w_opt, {
        "getiri":     port_ret,
        "volatilite": port_vol,
        "sharpe":     port_sharpe,
        "mu":         mu.tolist(),
        # corr ve frontier kaldırıldı — hesaplama yükü azaltıldı
    }


# ─── Gerçekleşen getiri ───────────────────────────────────────────────────────
def gerceklesen_zaman(tickers, weights, gercek_path=None):
    # FIX: gercek_path parametresini kullan
    csv_path = gercek_path if gercek_path and os.path.exists(gercek_path) else GERCEK_CSV
    if not os.path.exists(csv_path):
        return []
    try:
        df = pd.read_csv(csv_path, index_col=0)
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df.sort_index()
        pairs = [(t, w) for t, w in zip(tickers, weights) if t in df.columns]
        if not pairs:
            return []
        tks = [t for t, _ in pairs]
        wts = np.array([w for _, w in pairs])
        wts = wts / wts.sum()
        ret = np.log(df[tks] / df[tks].shift(1)).iloc[1:].dropna(how="any")
        port_cum = (np.exp((ret * wts).sum(axis=1).cumsum()) - 1) * 100
        return [{"tarih": str(idx.date()), "deger": round(float(v), 4)} for idx, v in port_cum.items()]
    except Exception:
        return []


def benchmark_getiri(gercek_path=None):
    KOLONLAR = [("XU100","BIST 100"), ("XU030","BIST 30"), ("USDTRY","USD/TRY"), ("ALTIN","Altın")]
    # FIX: gercek_path parametresini kullan
    csv_path = gercek_path if gercek_path and os.path.exists(gercek_path) else GERCEK_CSV
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path, index_col=0)
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df.sort_index()
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
        return results
    except Exception:
        return {}


# ─── Ana pipeline ─────────────────────────────────────────────────────────────
def run_pipeline(
    secilen_kategoriler,
    zorunlu_hisseler,
    data_dir,
    fiyat_path,
    piyasa_path,
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
        fiyat_path=fiyat_path,
        min_agirlik=min_agirlik, max_agirlik=max_agirlik,
        risksiz_faiz=risksiz_faiz, target_return=target_return,
    )

    markowitz_sonuc  = None
    markowitz_uyari  = None

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
            # corr ve frontier kaldırıldı
            "zaman":      gerceklesen_zaman(mk_tickers, mk_weights, gercek_path=gercek_path),
        }

    return {
        "shortlist":       shortlist,
        "markowitz":       markowitz_sonuc,
        "markowitz_uyari": markowitz_uyari,
        # FIX: gercek_path geçiliyor
        "benchmark":       benchmark_getiri(gercek_path=gercek_path),
        "hata":            None,
    }
