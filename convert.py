import pandas as pd

pd.read_excel("data/fiyat_verisi.xlsx", index_col=0).to_csv("data/fiyat_verisi.csv")
pd.read_excel("data/fiyat_verisi_25.xlsx", index_col=0).to_csv("data/fiyat_verisi_25.csv")
pd.read_excel("data/ham_girdi_degerleri.xlsx", sheet_name="TOPSIS").to_csv("data/ham_girdi_topsis.csv")

print("Dönüştürme tamamlandı!")
