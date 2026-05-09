"""
Transparency International CPI fetcher.

Source:
  https://images.transparencycdn.org/images/CPI2025_Results.xlsx

The latest CPI release ships a "CPI Timeseries 2012 - 2025" sheet that
contains every year's score in one file, so we fetch only the most recent
publication and slice out the Singapore row.

The file uses strict OOXML and must be read with the calamine engine
(openpyxl returns empty sheets).
"""

import json
import os
from urllib.request import Request, urlopen

import pandas as pd

CPI_URL        = "https://images.transparencycdn.org/images/CPI2025_Results.xlsx"
SHEET_NAME     = "CPI Timeseries 2012 - 2025"
COUNTRY_NAME   = "Singapore"
RAW_DIR        = "data/raw/manual"
PROCESSED_DIR  = "data/processed"
RAW_XLSX       = os.path.join(RAW_DIR, "CPI2025_Results.xlsx")

HEADERS = {"User-Agent": "Mozilla/5.0"}

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


def download_cpi(url: str = CPI_URL, out_path: str = RAW_XLSX) -> str:
    print(f"  Downloading {url}")
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=60) as r:
        data = r.read()
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"  [OK] saved {len(data):,} bytes -> {out_path}")
    return out_path


def fetch_ti_cpi(country: str = COUNTRY_NAME) -> pd.DataFrame:
    """
    Fetch TI CPI timeseries and extract one country.
    Returns tidy DataFrame: [date, country, indicator, value]
    """
    if not os.path.exists(RAW_XLSX):
        download_cpi()

    df = pd.read_excel(RAW_XLSX, sheet_name=SHEET_NAME, header=3, engine="calamine")

    mask = df["Country / Territory"].astype(str).str.strip().str.casefold() == country.casefold()
    row  = df[mask]
    if row.empty:
        raise ValueError(f"{country} not found in CPI timeseries sheet")

    score_cols = [c for c in df.columns if str(c).lower().startswith("cpi score ")]
    records = []
    for col in score_cols:
        year  = str(col).split()[-1].strip()
        value = row[col].iloc[0]
        if pd.notna(value):
            records.append({
                "date":      year,
                "country":   "SGP",
                "indicator": "TI.CPI",
                "value":     float(value),
            })

    out = (pd.DataFrame(records)
             .sort_values("date")
             .reset_index(drop=True))

    out_csv  = os.path.join(RAW_DIR, "ti_cpi.csv")
    out_json = os.path.join(RAW_DIR, "ti_cpi.json")
    out.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(records, f, indent=2)

    print(f"  [OK] TI CPI: {len(out)} rows -> {out_csv}")
    return out


if __name__ == "__main__":
    print("=== TI CPI (Singapore) ===")
    df = fetch_ti_cpi()
    print(df.to_string(index=False))