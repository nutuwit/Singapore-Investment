"""
World Bank API fetcher.

API endpoint:
  GET https://api.worldbank.org/v2/country/{countryCode}/indicator/{indicatorCode}

Query parameters:
  format     str   "json" (required)
  per_page   int   Records per page (max 1000)
  page       int   Page number (1-based)
  date       str   Year range, e.g. "2000:2024"
  mrv        int   Most recent N values (alternative to date)

Response JSON structure:
  [
    { "page": 1, "pages": 3, "per_page": 100, "total": 250 },
    [
      {
        "indicator": { "id": "NY.GDP.MKTP.KD.ZG", "value": "GDP growth (annual %)" },
        "country":   { "id": "SG", "value": "Singapore" },
        "date":      "2023",
        "value":     1.1
      },
      ...
    ]
  ]
"""

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import pandas as pd

BASE_URL   = "https://api.worldbank.org/v2/country/SGP/indicator"
RAW_DIR    = "data/raw/worldbank"
COUNTRY    = "SGP"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept":     "application/json",
}

WB_INDICATORS = {
    "gdp_growth":                    "NY.GDP.MKTP.KD.ZG",
    "trade_openness":                "NE.TRD.GNFS.ZS",
    "manufacturing_va_pct":          "NV.IND.MANF.ZS",
    "services_va_pct":               "NV.SRV.TOTL.ZS",
    "fdi_inflows_pct_gdp":           "BX.KLT.DINV.WD.GD.ZS",
    "governance_control_corruption": "CC.EST",
    "rule_of_law":                   "RL.EST",
}

os.makedirs(RAW_DIR, exist_ok=True)


def _get(url: str, retries: int = 3, backoff: float = 2.0):
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            raw = urlopen(req, timeout=30).read()
            return json.loads(raw)
        except HTTPError as e:
            print(f"  [HTTP {e.code}] attempt {attempt}/{retries}")
            if e.code in (400, 403, 404):
                raise
        except (URLError, json.JSONDecodeError) as e:
            print(f"  [Error] {e} attempt {attempt}/{retries}")
        if attempt < retries:
            time.sleep(backoff ** attempt)
    raise RuntimeError(f"Failed after {retries} attempts: {url}")


def fetch_wb_indicator(
    indicator_code: str,
    dataset_name:   str,
    start_year:     int = 2000,
    end_year:       int = 2024,
    per_page:       int = 100,
) -> pd.DataFrame:
    """
    Fetch a World Bank indicator for Singapore with automatic pagination.
    Returns tidy DataFrame: [date, country, indicator, value]
    """
    all_records = []
    page        = 1

    while True:
        params = {
            "format":   "json",
            "per_page": per_page,
            "page":     page,
            "date":     f"{start_year}:{end_year}",
        }
        url = f"{BASE_URL}/{indicator_code}?{urlencode(params)}"
        print(f"  Fetching {dataset_name} (page {page}): {url}")

        data = _get(url)

        # WB returns [metadata_dict, records_list]
        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            break

        meta    = data[0]
        records = data[1]

        for entry in records:
            if entry.get("value") is not None:
                all_records.append({
                    "date":      entry["date"],
                    "country":   COUNTRY,
                    "indicator": indicator_code,
                    "value":     float(entry["value"]),
                })

        if page >= meta.get("pages", 1):
            break
        page += 1

    if not all_records:
        print(f"  [WARN] No data for {dataset_name}")
        return pd.DataFrame()

    df = (pd.DataFrame(all_records)
            .sort_values("date")
            .reset_index(drop=True))

    out_csv  = os.path.join(RAW_DIR, f"{dataset_name}.csv")
    out_json = os.path.join(RAW_DIR, f"{dataset_name}.json")
    df.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"  [OK] {dataset_name}: {len(df)} rows -> {out_csv}")
    return df


def fetch_all_worldbank() -> dict[str, pd.DataFrame]:
    results = {}
    for name, code in WB_INDICATORS.items():
        print(f"\n--- {name} ({code}) ---")
        try:
            results[name] = fetch_wb_indicator(code, name)
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            results[name] = pd.DataFrame()
    return results


if __name__ == "__main__":
    print("=== World Bank test (GDP growth) ===")
    df = fetch_wb_indicator("NY.GDP.MKTP.KD.ZG", "gdp_growth_test")
    print(df.tail(10).to_string(index=False))
