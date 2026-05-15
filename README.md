# Portföy Optimizatörü — MEREC + TOPSIS + Markowitz

BİST hisseleri için adım adım portföy optimizasyonu yapan web uygulaması.

## Yöntemler

| Yöntem | Ne yapar? |
|--------|-----------|
| **MEREC** | Finansal kriterlerin (ROE, ROA, P/E…) önem ağırlıklarını veriden öğrenir |
| **TOPSIS** | Her hisseyi "ideal portföye uzaklığı" bazında sıralar |
| **Markowitz** | Verilen getiri hedefini sağlarken portföy riskini minimize eder |

## Kategoriler ve Hisseler

| Kategori | Hisseler |
|----------|----------|
| Bankacılık | AKBNK, ALBRK, GARAN, HALKB, ISCTR, QNBTR, SKBNK, TSKB, VAKBN, YKBNK |
| Holding ve Yatırım | AGHOL, ALARK, BRYAT, DOHOL, ECZYT, IEYHO, KCHOL, KLRHO, SAHOL, TAVHL |
| Bilişim ve Teknoloji | ARDYZ, ASELS, EDATA, HTTBT, INDES, KAREL, LOGO, MANAS, MIATK, PAPIL |
| Ulaştırma | BEYAZ, CLEBI, GRSEL, GSDDE, DOAS, PGSUS, RYSAS, THYAO, TLMAN, TUREX |
| Gıda ve İçecek | AEFES, BANVT, CCOLA, KENT, KNFRT, PNSUT, TATGD, TBORG, TUKAS, ULKER |
| Hizmetler | BIGTK, BIMAS, MAALT, MAVI, MGROS, MPARK, PENTA, TCELL, TTKOM, YATAS |
| Sanayi | ARCLK, EREGL, FROTO, KRDMD, OTKAR, SISE, TOASO, TRALT, TTRAK, TUPRS |
| Kimya Petrol Plastik | AKSA, AYGAZ, BRSAN, EUREN, GUBRF, HEKTS, ISKPL, IZFAS, PETKM, SASA |
| İnşaat ve GYO | ALGYO, EKGYO, ENKAI, ISGYO, KUYAS, ORGE, PEKGY, TRGYO, TURGG, ZRGYO |
| Enerji | AKENR, AKSEN, AYDEM, BIOEN, ENJSA, GESAN, GWIND, KONTR, ODAS, ZOREN |

## Finansal Kriterler

**Bankacılık** (özel kriterler):
- R1: Net Profit Growth · R2: ROA · R3: ROE · R4: P/E · R5: MV/BV
- R6: Beta · R7: Non-int Rev/Non-int Exp · R8: Liquid Assets/Debt
- R9: Equity/Loans · R10: Equity/Total Assets

**Diğer kategoriler**:
- R1: Net Profit Growth · R2: ROA · R3: ROE · R4: P/E · R5: MV/BV
- R6: Beta · R7: Current Ratio · R8: Acid-Test Ratio · R9: ST Liab/Total Liab · R10: Debt/Equity

## Proje Yapısı

```
portfolio-optimizer/
├── backend/
│   ├── app.py       
│   └── engine.py     
├── frontend/
│   └── index.html    
├── data/                   
├── requirements.txt
└── README.md
