"""
MAS API Fetcher — SORA (Daily Domestic Interest Rates)
Fixes applied: Uses VQL $filter and $orderby to prevent empty table returns.
"""

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError
import pandas as pd
from datetime import datetime, timedelta

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://eservices.mas.gov.sg/apimg-gw/server"
RAW_DIR  = "data/raw/mas"

HEADERS = {
    "accept": "application/json; charset=UTF-8",
    "keyId": "74034675-4957-4ee4-8797-783bd5077459",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

os.makedirs(RAW_DIR, exist_ok=True)


# ── Core Fetcher ──────────────────────────────────────────────────────────────

def fetch_sora_data(days_back: int = 30, limit: int = 100) -> pd.DataFrame:
    """
    Fetches daily SORA rates using explicit VQL filtering to avoid empty responses.
    """
    publication = "monthly_statistical_bulletin_non610mssql"
    dataset     = "domestic_interest_rates_daily"
    view        = "domestic_interest_rates_daily"
    
    sora_columns = [
        "end_of_day", "sora", "sora_index", "comp_sora_1m", 
        "comp_sora_3m", "comp_sora_6m", "aggregate_volume"
    ]

    all_records = []
    offset = 0

    # Calculate date range to force the database to return data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    # Create the VQL Filter: end_of_day >= '2024-01-01' AND end_of_day <= '2024-02-01'
    vql_filter = f"end_of_day >= '{start_str}' AND end_of_day <= '{end_str}'"

    while True:
        # We construct the query string manually to ensure the $ variables format correctly
        params = {
            "offset": offset,
            "limit": limit,
            "$orderby": "end_of_day DESC", # Get newest first
            "$filter": vql_filter
        }
        
        # urlencode handles spaces and special characters safely
        qs = urlencode(params)
        url = f"{BASE_URL}/{publication}/{dataset}/views/{view}?{qs}"
        
        print(f"Fetching data from {start_str} to {end_str} (offset={offset})...")
        
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as e:
            print(f"  [HTTP {e.code}] {e.reason}")
            break
        except Exception as e:
            print(f"  [Error] {e}")
            break

        # Extract records
        records = payload.get("items", payload.get("result", {}).get("records", []))
        has_more = payload.get("hasMore", False)

        if not records:
            break

        all_records.extend(records)

        if not has_more:
            break
            
        offset += limit
        time.sleep(0.5)

    if not all_records:
        print("\nNo records retrieved. The API returned empty for this date range.")
        return pd.DataFrame()

    # Load into pandas
    df = pd.DataFrame(all_records)

    # Filter columns locally
    keep_cols = [col for col in sora_columns if col in df.columns]
    df = df[keep_cols]

    # Convert formatting
    if "end_of_day" in df.columns:
        df["end_of_day"] = pd.to_datetime(df["end_of_day"], errors="coerce")
    
    for col in df.columns:
        if col != "end_of_day":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort chronological
    if "end_of_day" in df.columns:
        df = df.sort_values("end_of_day").reset_index(drop=True)
        
    # Save
    out_csv = os.path.join(RAW_DIR, "sora_rates.csv")
    df.to_csv(out_csv, index=False)
    
    print(f"\n[OK] Success! {len(df)} rows saved to {out_csv}")
    return df


# ── Execution ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Fetch the last 90 days of data by default. 
    # Change this number to fetch more or less history.
    df_sora = fetch_sora_data(days_back=90)
    
    if not df_sora.empty:
        print("\nLatest 5 rows of SORA data:")
        print(df_sora.tail().to_string(index=False))