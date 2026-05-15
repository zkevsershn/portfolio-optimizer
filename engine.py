"""
engine.py  —  Portföy Optimizatörü
Yalnızca:
  1. Shortlist: ham_girdi_degerleri.xlsx → her kategoriden ilk 3
  2. Markowitz: min-variance optimizasyonu (fiyat_verisi.xlsx)
  3. Benchmark: gerçekleşen getiri (fiyat_verisi_25.xlsx)
"""

import os, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

# ─── Sabitler ────────────────────────────────────────────────────────────────
RISKSIZ_FAIZ = 0.45          # yıllık
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

# Ham girdi Excel → TOPSIS C skoru + kategori eşlemesi
HAM_GIRDI_PATH = os.environ.get(
    "HAM_GIRDI_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ham_girdi_degerleri.xlsx"),
)
EXCEL_KAT_MAP = {
    "İnşaat GYO":   "İnşaat ve GYO",
    "Kimya Petrol": "Kimya Petrol Plastik",
}

# ─── Shortlist ────────────────────────────────────────────────────────────────
def shortlist_olustur(secilen_kategoriler, zorunlu_hisseler=None, cikartilan_hisseler=None):
    """Ham girdi Excel'inden her kategoride ilk 3 hisseyi al."""
    zorunlu    = zorunlu_hisseler    or []
    cikartilan = cikartilan_hisseler or []

    tum_sonuclar = []   # [(ticker, kat, c_skor)]

    if os.path.exists(HAM_GIRDI_PATH):
        try:
            df_t = pd.read_excel(HAM_GIRDI_PATH, sheet_name="TOPSIS", engine="openpyxl")
            df_t["_kat"] = df_t["Unnamed: 3"].ffill().map(lambda k: EXCEL_KAT_MAP.get(k, k) if pd.notna(k) else k)
            for kat in secilen_kategoriler:
                kat_df = df_t[df_t["_kat"] == kat][["Ticker", "C skoru"]].dropna()
                for _, row in kat_df.iterrows():
                    tum_sonuclar.append((str(row["Ticker"]).strip(), kat, float(row["C skoru"])))
        except Exception:
            pass

    shortlist = []
    eklenen   = set()

    # Zorunlu hisseler
    for ticker in zorunlu:
        entry = next((x for x in tum_sonuclar if x[0] == ticker), None)
        if entry and ticker not in eklenen and ticker not in cikartilan:
            shortlist.append({"ticker": ticker, "kategori": entry[1], "zorunlu": True})
            eklenen.add(ticker)

    # Toplam 30 olacak şekilde her kategoriden eşit pay
    n_kat      = len(secilen_kategoriler)
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
def markowitz(tickers, fiyat_path,
              min_agirlik=MIN_AGIRLIK,
              max_agirlik=MAX_AGIRLIK,
              risksiz_faiz=RISKSIZ_FAIZ,
              target_return=0.50):
    if not os.path.exists(fiyat_path):
        return None, None, None

    df = pd.read_excel(fiyat_path, index_col=0, engine="openpyxl")
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
    std   = np.sqrt(np.diag(Sigma))
    Corr  = np.clip(Sigma / np.outer(std, std), -1, 1)

    def port_var(w): return float(w @ Sigma @ w)

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: float(w @ mu) - target_return},
    ]
    bounds = [(max(0.0, min_agirlik), max_agirlik)] * n
    w0     = np.ones(n) / n

    res = minimize(port_var, w0, method="SLSQP", bounds=bounds,
                   constraints=constraints, options={"ftol": 1e-12, "maxiter": 3000})

    if not res.success:
        return None, None, {"optimize_hatasi": res.message}

    w_opt       = res.x
    port_ret    = float(w_opt @ mu)
    port_vol    = float(np.sqrt(w_opt @ Sigma @ w_opt))
    port_sharpe = (port_ret - RISKSIZ_FAIZ) / port_vol if port_vol > 0 else float("nan")

    # Efficient frontier — ret_lo: min varyans portföyü ile hedef arasındaki minimum
    res_mv = minimize(port_var, w0, method="SLSQP", bounds=bounds,
                      constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
                      options={"ftol": 1e-12, "maxiter": 1000})
    mv_ret = float(res_mv.x @ mu) if res_mv.success else float(np.min(mu))
    ret_lo = min(mv_ret, target_return)   # portföy noktası her zaman frontier üzerinde
    ret_hi = float(np.max(mu)) * 0.97
    frontier = []
    for tr in np.linspace(ret_lo, ret_hi, 30):
        c2 = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
              {"type": "eq", "fun": lambda w, tr=tr: float(w @ mu) - tr}]
        r2 = minimize(port_var, w0, method="SLSQP", bounds=bounds, constraints=c2,
                      options={"ftol": 1e-10, "maxiter": 800})
        if r2.success:
            frontier.append({"vol": round(float(np.sqrt(r2.x @ Sigma @ r2.x)) * 100, 2),
                             "ret": round(float(tr) * 100, 2)})  # float() → np.float64 değil

    return mevcut, w_opt, {
        "getiri":     port_ret,
        "volatilite": port_vol,
        "sharpe":     port_sharpe,
        "mu":         mu.tolist(),
        "Sigma":      Sigma.tolist(),
        "corr":       Corr.tolist(),
        "frontier":   frontier,
    }


# ─── Gerçekleşen getiri (fiyat_verisi_25) ────────────────────────────────────
def gerceklesen_zaman(tickers, weights, gercek_path):
    if not gercek_path or not os.path.exists(gercek_path):
        return []
    try:
        df = pd.read_excel(gercek_path, index_col=0, engine="openpyxl")
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


def benchmark_getiri(gercek_path):
    KOLONLAR = [("XU100","BIST 100"), ("XU030","BIST 30"), ("USDTRY","USD/TRY"), ("ALTIN","Altın")]
    if not gercek_path or not os.path.exists(gercek_path):
        return {}
    try:
        df = pd.read_excel(gercek_path, index_col=0, engine="openpyxl")
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
        return {"hata": "Shortlist oluşturulamadı. ham_girdi_degerleri.xlsx dosyasını kontrol edin."}

    sl_tickers = [s["ticker"] for s in shortlist]
    mk_tickers, mk_weights, mk_stats = markowitz(
        sl_tickers, fiyat_path,
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
            "corr":       [[round(v, 4) for v in row] for row in mk_stats["corr"]],
            "frontier":   mk_stats["frontier"],
            "zaman":      gerceklesen_zaman(mk_tickers, mk_weights, gercek_path),
        }

    return {
        "shortlist":       shortlist,
        "markowitz":       markowitz_sonuc,
        "markowitz_uyari": markowitz_uyari,
        "benchmark":       benchmark_getiri(gercek_path),
        "hata":            None,
    }
