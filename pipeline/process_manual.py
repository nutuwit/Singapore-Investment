"""
Manual data loader for sources that don't have a usable API:
  - UNCTAD FDI inflows (Excel download)
  - Transparency International CPI (Excel download)

Download instructions:
  UNCTAD : https://unctadstat.unctad.org  → FDI → Inward → Download Excel
           Save as: data/raw/manual/unctad_fdi.xlsx
  TI CPI : https://www.transparency.org/en/cpi → Download CPI Timeseries Excel
           Save as: data/raw/manual/ti_cpi.xlsx
"""

import os
import pandas as pd

RAW_DIR       = "data/raw/manual"
PROCESSED_DIR = "data/processed"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


def load_unctad_fdi(filepath: str = "data/raw/manual/unctad_fdi.xlsx") -> pd.DataFrame:
    """
    Parse UNCTAD FDI inflows Excel and extract Singapore row.
    Returns tidy DataFrame: [date, fdi_inflows_usd_mn]
    """
    if not os.path.exists(filepath):
        print(f"[SKIP] UNCTAD file not found: {filepath}")
        print("       Download from https://unctadstat.unctad.org and save to that path.")
        return pd.DataFrame()

    df_raw = pd.read_excel(filepath, sheet_name=0, header=2)
    mask   = df_raw.iloc[:, 0].astype(str).str.contains("Singapore", case=False, na=False)
    sg_row = df_raw[mask]

    if sg_row.empty:
        print("[WARN] Singapore not found in UNCTAD file — check sheet/header layout.")
        return pd.DataFrame()

    sg_row = sg_row.set_index(df_raw.columns[0]).T
    sg_row.index = pd.to_datetime(sg_row.index.astype(str), format="%Y", errors="coerce")
    sg_row.columns = ["fdi_inflows_usd_mn"]
    sg_row = sg_row.dropna(subset=["fdi_inflows_usd_mn"])
    sg_row["fdi_inflows_usd_mn"] = pd.to_numeric(sg_row["fdi_inflows_usd_mn"], errors="coerce")
    sg_row.index.name = "date"
    df = sg_row.reset_index()
    df["date"] = df["date"].dt.strftime("%Y")

    out = os.path.join(PROCESSED_DIR, "unctad_fdi_singapore.csv")
    df.to_csv(out, index=False)
    print(f"[OK] UNCTAD FDI: {len(df)} rows -> {out}")
    return df


def load_ti_cpi(filepath: str = "data/raw/manual/ti_cpi.xlsx") -> pd.DataFrame:
    """
    Parse Transparency International CPI timeseries Excel and extract Singapore row.
    Returns tidy DataFrame: [date, cpi_score]
    """
    if not os.path.exists(filepath):
        print(f"[SKIP] TI CPI file not found: {filepath}")
        print("       Download from https://www.transparency.org/en/cpi and save to that path.")
        return pd.DataFrame()

    sheets = pd.read_excel(filepath, sheet_name=None)
    sheet_name = next(
        (k for k in sheets if "timeseries" in k.lower() or "cpi" in k.lower()),
        list(sheets.keys())[0]
    )
    df = sheets[sheet_name]

    mask   = df.iloc[:, 0].astype(str).str.contains("Singapore", case=False, na=False)
    sg_row = df[mask]

    if sg_row.empty:
        print("[WARN] Singapore not found in TI CPI file.")
        return pd.DataFrame()

    year_cols = [c for c in sg_row.columns if str(c).isdigit()]
    records   = [
        {"date": str(yr), "cpi_score": float(sg_row[yr].values[0])}
        for yr in year_cols
        if pd.notna(sg_row[yr].values[0])
    ]

    df_out = pd.DataFrame(records)
    out    = os.path.join(PROCESSED_DIR, "ti_cpi_singapore.csv")
    df_out.to_csv(out, index=False)
    print(f"[OK] TI CPI: {len(df_out)} rows -> {out}")
    return df_out


def load_all_manual() -> dict[str, pd.DataFrame]:
    return {
        "unctad_fdi": load_unctad_fdi(),
        "ti_cpi":     load_ti_cpi(),
    }


if __name__ == "__main__":
    load_all_manual()
