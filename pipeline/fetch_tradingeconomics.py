"""
Trading Economics API fetcher.

Portal:
  https://tradingeconomics.com/singapore/interest-rate

API endpoints:
  GET https://api.tradingeconomics.com/historical/country/{country}/indicator/{indicator}
  GET https://api.tradingeconomics.com/country/{country}/indicator/{indicator}   (latest only)

Auth:
  Pass `c=<key>:<secret>` as a query parameter. The free guest key
  `guest:guest` is rate-limited and only exposes a small set of indicators
  (interest rate, inflation, GDP growth, unemployment) with truncated
  history. Set TE_API_KEY in the environment for full access, e.g.:
      export TE_API_KEY="abcd1234:xyz5678"

Response JSON structure (historical):
  [
    {
      "Country":      "Singapore",
      "Category":     "Interest Rate",
      "DateTime":     "2024-01-31T00:00:00",
      "Value":        3.71,
      "Frequency":    "Monthly",
      "HistoricalDataSymbol": "SINGAPOREINTRAT",
      "LastUpdate":   "2024-02-15T12:00:00"
    },
    ...
  ]
"""

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError

import pandas as pd

BASE_URL = "https://api.tradingeconomics.com"
COUNTRY  = "singapore"
RAW_DIR  = "data/raw/tradingeconomics"

API_KEY  = os.environ.get("TE_API_KEY", "guest:guest")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept":     "application/json",
}

# Mapping of dataset name -> Trading Economics indicator label.
# Indicator names must match TE's Category strings (case-insensitive).
TE_INDICATORS = {
    "interest_rate":  "interest rate",
    "inflation_cpi":  "inflation rate",
    "gdp_growth":     "gdp growth rate",
    "unemployment":   "unemployment rate",
}

# ISO3 mapping for the `country` column in the tidy output.
COUNTRY_ISO3 = "SGP"

os.makedirs(RAW_DIR, exist_ok=True)


def _get(url: str, retries: int = 3, backoff: float = 2.0):
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            raw = urlopen(req, timeout=30).read()
            return json.loads(raw)
        except HTTPError as e:
            print(f"  [HTTP {e.code}] attempt {attempt}/{retries}")
            if e.code in (400, 401, 403, 404):
                raise
        except (URLError, json.JSONDecodeError) as e:
            print(f"  [Error] {e} attempt {attempt}/{retries}")
        if attempt < retries:
            time.sleep(backoff ** attempt)
    raise RuntimeError(f"Failed after {retries} attempts: {url}")


def fetch_te_indicator(
    indicator:    str,
    dataset_name: str,
    country:      str = COUNTRY,
    start_date:   str | None = None,
    end_date:     str | None = None,
) -> pd.DataFrame:
    """
    Fetch full historical series for one Trading Economics indicator.

    Args:
        indicator:    TE category label, e.g. "interest rate"
        dataset_name: filename stem for the cached CSV/JSON
        start_date:   optional ISO date "YYYY-MM-DD"
        end_date:     optional ISO date "YYYY-MM-DD"

    Returns tidy DataFrame: [date, country, indicator, value]
    """
    path = f"/historical/country/{quote(country)}/indicator/{quote(indicator)}"
    if start_date and end_date:
        path += f"/{start_date}/{end_date}"
    elif start_date:
        path += f"/{start_date}"

    params = {"c": API_KEY, "format": "json"}
    url = f"{BASE_URL}{path}?{urlencode(params)}"
    print(f"  Fetching {dataset_name}: {url}")

    data = _get(url)

    if not isinstance(data, list) or not data:
        print(f"  [WARN] No data for {dataset_name}")
        return pd.DataFrame()

    records = []
    for entry in data:
        value = entry.get("Value")
        dt    = entry.get("DateTime")
        if value is None or dt is None:
            continue
        records.append({
            "date":      str(dt)[:10],
            "country":   COUNTRY_ISO3,
            "indicator": entry.get("Category", indicator),
            "value":     float(value),
        })

    if not records:
        print(f"  [WARN] No usable rows for {dataset_name}")
        return pd.DataFrame()

    df = (pd.DataFrame(records)
            .sort_values("date")
            .reset_index(drop=True))

    out_csv  = os.path.join(RAW_DIR, f"{dataset_name}.csv")
    out_json = os.path.join(RAW_DIR, f"{dataset_name}.json")
    df.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(records, f, indent=2)

    print(f"  [OK] {dataset_name}: {len(df)} rows -> {out_csv}")
    return df


def fetch_all_tradingeconomics() -> dict[str, pd.DataFrame]:
    results = {}
    for name, indicator in TE_INDICATORS.items():
        print(f"\n--- {name} ({indicator}) ---")
        try:
            results[name] = fetch_te_indicator(indicator, name)
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            results[name] = pd.DataFrame()
    return results


if __name__ == "__main__":
    print("=== Trading Economics: Singapore Interest Rate ===")
    if API_KEY == "guest:guest":
        print("  [INFO] Using guest:guest credentials (history is truncated).")
        print("         Set TE_API_KEY=<key>:<secret> for full access.")
    df = fetch_te_indicator("interest rate", "interest_rate")
    if not df.empty:
        print(df.tail(10).to_string(index=False))
