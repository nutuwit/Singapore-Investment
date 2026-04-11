"""
MAS (Monetary Authority of Singapore) API fetcher.

Based on the official curl pattern from:
  https://eservices.mas.gov.sg/apimg-gw/server/...

API endpoint pattern:
  GET https://eservices.mas.gov.sg/apimg-gw/server/{publication}/{dataset}/views/{view_name}
  Header: accept: application/json; charset=UTF-8

Query parameters (all optional — each is a column-name filter):
  Any column name from the dataset can be used as a filter, e.g.:
    end_of_month=2025-12      → filter to specific month (YYYY-MM)
    usd_sgd=1.35              → filter rows where usd_sgd = 1.35
  Pagination (Oracle ORDS style):
    offset=0                  → starting record index
    limit=100                 → max records per page (default: 25, check dataset for max)
    rows=100                  → alternative pagination param (some endpoints)

Response JSON structure (Oracle ORDS / apimg-gw format):
  {
    "items": [
      {
        "end_of_month": "2025-12",
        "usd_sgd":      "1.3500",
        "gbp_sgd":      "1.7100",
        "eur_sgd":      "1.4200",
        ...
      },
      ...
    ],
    "hasMore": false,
    "limit":   25,
    "offset":  0,
    "count":   1,
    "links":   [ ... ]
  }

  NOTE: Some endpoints may return a flat list [] instead of {"items": [...]}.
        The fetcher handles both.

Authentication:
  Most MAS statistical (MSB) endpoints are publicly accessible.
  If a 401 is returned, register at https://eservices.mas.gov.sg/apimg-portal/
  and pass your API key via header: keyId: <your-key>
"""

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://eservices.mas.gov.sg/apimg-gw/server"
RAW_DIR  = "data/raw/mas"

# Required header — without Accept the API returns 401.
# Add "keyId": "<your-key>" here if endpoints require authentication.
HEADERS = {
    "accept": "application/json; charset=UTF-8",
}

# Dataset registry: { name: { publication, dataset, view, columns, filters } }
# URL assembled as: BASE_URL/{publication}/{dataset}/views/{view}
MAS_DATASETS = {
    "exchange_rates_monthly": {
        "publication": "monthly_statistical_bulletin_non610ora",
        "dataset":     "exchange_rates_end_of_period_monthly",
        "view":        "exchange_rates_end_of_period_monthly",
        # columns to keep in the output (all others dropped)
        "columns":     ["end_of_month", "usd_sgd", "gbp_sgd", "eur_sgd",
                        "jpy_sgd", "cny_sgd", "aud_sgd", "hkd_sgd"],
        # optional column filters to pass as query params (None = no filter)
        "filters":     {},
    },
    "interest_rates_monthly": {
        "publication": "monthly_statistical_bulletin_non610ora",
        "dataset":     "interest_rates_end_of_period_monthly",
        "view":        "interest_rates_end_of_period_monthly",
        "columns":     ["end_of_month", "comp_sgs_sgd_3m",
                        "prime_lending_rate", "savings_deposit_rate"],
        "filters":     {},
    },
    "sgd_money_supply_monthly": {
        "publication": "monthly_statistical_bulletin_non610ora",
        "dataset":     "money_supply_broad_money_m2_monthly",
        "view":        "money_supply_broad_money_m2_monthly",
        "columns":     ["end_of_month", "m1", "m2", "m3"],
        "filters":     {},
    },
}

os.makedirs(RAW_DIR, exist_ok=True)


# ── Core fetch ─────────────────────────────────────────────────────────────────

def _build_url(publication: str, dataset: str, view: str, params: dict) -> str:
    clean = {k: v for k, v in params.items() if v is not None and v != {}}
    qs    = f"?{urlencode(clean)}" if clean else ""
    return f"{BASE_URL}/{publication}/{dataset}/views/{view}{qs}"


def _get(url: str, retries: int = 3, backoff: float = 2.0) -> dict | list:
    """GET with accept header + retry logic."""
    for attempt in range(1, retries + 1):
        try:
            req  = Request(url, headers=HEADERS)
            raw  = urlopen(req, timeout=30).read()
            return json.loads(raw)
        except HTTPError as e:
            print(f"  [HTTP {e.code}] attempt {attempt}/{retries}: {url}")
            if e.code in (400, 403, 404):
                raise
            if e.code == 401:
                raise RuntimeError(
                    "401 Unauthorized — register at https://eservices.mas.gov.sg/apimg-portal/ "
                    "and add your keyId to HEADERS."
                )
        except (URLError, json.JSONDecodeError) as e:
            print(f"  [Error] {e} attempt {attempt}/{retries}")

        if attempt < retries:
            time.sleep(backoff ** attempt)

    raise RuntimeError(f"Failed after {retries} attempts: {url}")


# ── Table fetcher ──────────────────────────────────────────────────────────────

def fetch_mas_table(
    dataset_name: str,
    publication:  str,
    dataset:      str,
    view:         str,
    columns:      list[str] | None = None,
    filters:      dict             = None,
    limit:        int              = 500,
) -> pd.DataFrame:
    """
    Fetch a MAS APIMG dataset with automatic pagination.

    Pagination:
      The Oracle ORDS response includes "hasMore": true/false.
      When hasMore is true, re-fetch with offset += limit until exhausted.

    Parameters
    ----------
    filters : dict
        Column-name filters passed as query params, e.g. {"end_of_month": "2025-12"}.
        Corresponds to the curl ?end_of_month=2025-12 pattern.
    """
    filters      = filters or {}
    all_records: list[dict] = []
    offset       = 0

    while True:
        params = {**filters, "offset": offset, "limit": limit}
        url    = _build_url(publication, dataset, view, params)
        print(f"  Fetching {dataset_name} (offset={offset}): {url}")

        payload = _get(url)

        # Handle both {"items": [...]} and bare [...]
        if isinstance(payload, list):
            records  = payload
            has_more = False
        else:
            records  = payload.get("items", payload.get("result", {}).get("records", []))
            has_more = payload.get("hasMore", False)

        if not records:
            break

        all_records.extend(records)

        if not has_more:
            break
        offset += limit

    if not all_records:
        print(f"  [WARN] No records for {dataset_name}")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)

    # Keep only requested columns (ignore missing ones gracefully)
    if columns:
        keep = [c for c in columns if c in df.columns]
        df   = df[keep]

    # Convert numeric columns
    date_col = "end_of_month" if "end_of_month" in df.columns else df.columns[0]
    for col in df.columns:
        if col != date_col:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort by date
    df = df.sort_values(date_col).reset_index(drop=True)

    # Save
    out_csv  = os.path.join(RAW_DIR, f"{dataset_name}.csv")
    out_json = os.path.join(RAW_DIR, f"{dataset_name}.json")
    df.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"  [OK] {dataset_name}: {len(df)} rows -> {out_csv}")
    return df


# ── Fetch all ──────────────────────────────────────────────────────────────────

def fetch_all_mas() -> dict[str, pd.DataFrame]:
    results = {}
    for name, cfg in MAS_DATASETS.items():
        print(f"\n--- {name} ---")
        try:
            results[name] = fetch_mas_table(
                dataset_name = name,
                publication  = cfg["publication"],
                dataset      = cfg["dataset"],
                view         = cfg["view"],
                columns      = cfg.get("columns"),
                filters      = cfg.get("filters", {}),
            )
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            results[name] = pd.DataFrame()
    return results


# ── Convenience: fetch with ad-hoc column filter ───────────────────────────────

def fetch_exchange_rates(
    start_month: str | None = None,
    end_month:   str | None = None,
) -> pd.DataFrame:
    """
    Fetch SGD exchange rates, optionally filtered to a date range.

    Mirrors the curl example:
      ?end_of_month=2025-12&eur_sgd=100

    For a date range, fetch all and filter in pandas (the API only supports
    equality filters, not range filters).
    """
    cfg = MAS_DATASETS["exchange_rates_monthly"]
    df  = fetch_mas_table(
        dataset_name = "exchange_rates_monthly",
        publication  = cfg["publication"],
        dataset      = cfg["dataset"],
        view         = cfg["view"],
        columns      = cfg["columns"],
        filters      = {},        # fetch all, then filter below
    )

    if df.empty:
        return df

    df["end_of_month"] = pd.to_datetime(df["end_of_month"], format="%Y-%m", errors="coerce")

    if start_month:
        df = df[df["end_of_month"] >= pd.Timestamp(start_month)]
    if end_month:
        df = df[df["end_of_month"] <= pd.Timestamp(end_month)]

    return df.reset_index(drop=True)


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Replicates the curl example:
    # GET .../exchange_rates_end_of_period_monthly?end_of_month=2025-12&eur_sgd=100
    cfg = MAS_DATASETS["exchange_rates_monthly"]
    df  = fetch_mas_table(
        dataset_name = "exchange_rates_test",
        publication  = cfg["publication"],
        dataset      = cfg["dataset"],
        view         = cfg["view"],
        columns      = cfg["columns"],
        filters      = {"end_of_month": "2025-12"},   # column filter from curl
        limit        = 25,
    )
    print(df.to_string(index=False))
