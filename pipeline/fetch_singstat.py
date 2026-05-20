import json
import os
import asyncio
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import datetime

import pandas as pd

# ── Constants ─────────────────────────────────────────────

BASE_URL = "https://tablebuilder.singstat.gov.sg/api/table/tabledata"
RAW_DIR  = "data/raw/singstat"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

MAX_CONCURRENT_REQUESTS = 8

os.makedirs(RAW_DIR, exist_ok=True)

# ── YOUR CONFIG (UNCHANGED) ───────────────────────────────

SINGSTAT_TABLES = {
    "gdp_expenditure": {
        "tableId": "M014871",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "total_manufacturing": {
        "tableId": "M354891",
        "seriesNoORrowNo": None,
        "limit": 4000,
        "sortBy": "key asc",
    },
    "IPI (Industrial Production Index)": {
        "tableId": "M355351",
        "seriesNoORrowNo": None,
        "limit": 10000,
        "sortBy": "key asc",
    },
    "Non-Oil Domestic Exports": {
        "tableId": "M450981",
        "seriesNoORrowNo": None,
        "limit": 4000,
        "sortBy": "key asc",
    },
    "merchandise trade by commodity (monthly)": {
        "tableId": "M451002",
        "seriesNoORrowNo": None,
        "limit": 4000,
        "sortBy": "key asc",
    },
    "manufacturing_va_by_industry": {
        "tableId": "M354861",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "services_industry": {
        "tableId": "M601481",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "merchandise_exports": {
        "tableId": "M451031",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "income_FDI_country": {
        "tableId": "M083901",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "return_FDI_country": {
        "tableId": "M084001",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "income_FDI_industry": {
        "tableId": "M084871",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "return_FDI_industry": {
        "tableId": "M084911",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "gdp_growth_sector": {
        "tableId": "M015631",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "gdp_industry": {
        "tableId": "M015652",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc"
    },
    "CPI (monthly)": {
        "tableId": "M213752",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "CPI Percent Change": {
        "tableId": "M213792",
        "seriesNoORrowNo": None,
        "limit": 3000,
        "sortBy": "key asc",
    },
    "FDI flows (Country & Component)": {
        "tableId": "M085821",
        "seriesNoORrowNo": None,
        "limit": 4000,
        "sortBy": "key asc",
    },
    "FDI flows (Country & Industry)": {
        "tableId": "M085811",
        "seriesNoORrowNo": None,
        "limit": 4000,
        "sortBy": "key asc",
    },
}

# ── Helpers ───────────────────────────────────────────────

def _build_url(table_id, params):
    clean = {k: v for k, v in params.items() if v is not None}
    return f"{BASE_URL}/{table_id}?{urlencode(clean)}"


def _get(url, retries=3):
    for i in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            raw = urlopen(req, timeout=30).read()
            return json.loads(raw)
        except Exception as e:
            print(f"[Retry {i+1}] {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch: {url}")


async def _get_async(url, semaphore, retries=3):
    for i in range(retries):
        try:
            async with semaphore:
                return await asyncio.to_thread(_get, url, 1)
        except Exception as e:
            print(f"[Retry {i+1}] {e}")
            await asyncio.sleep(2)
    raise RuntimeError(f"Failed to fetch: {url}")


# ── 🔥 DATE PARSER (CORE FIX) ─────────────────────────────

def parse_singstat_date(date_str):
    date_str = date_str.strip()

    # Monthly: "2019 Jan"
    try:
        return pd.to_datetime(date_str, format="%Y %b")
    except:
        pass

    # Quarterly: "2019 Q1"
    if "Q" in date_str:
        try:
            year = int(date_str[:4])
            quarter = int(date_str[-1])
            month = (quarter - 1) * 3 + 1
            return pd.Timestamp(year=year, month=month, day=1)
        except:
            pass

    # Year: "2019"
    try:
        return pd.to_datetime(date_str, format="%Y")
    except:
        pass

    return None

# ── Core Fetch ────────────────────────────────────────────
def get_table_frequency(table_id):
    url = f"https://tablebuilder.singstat.gov.sg/api/table/metadata/{table_id}"

    try:
        req = Request(url, headers=HEADERS)
        raw = urlopen(req, timeout=30).read()
        data = json.loads(raw)

        freq = (
            data.get("Data", {})
                .get("records", {})
                .get("frequency", "")
                .lower()
        )

        if "month" in freq:
            return "monthly"
        elif "quarter" in freq:
            return "quarterly"
        elif "year" in freq or "annual" in freq:
            return "annual"
        else:
            return "unknown"

    except Exception as e:
        print(f"[WARN] Metadata fetch failed for {table_id}: {e}")
        return "unknown"
    
def _build_time_tokens(frequency, start_year, current_year):
    time_tokens = []

    if frequency == "monthly":
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]

        for year in range(start_year, current_year + 1):
            for m in months:
                time_tokens.append(f"{year}%20{m}")

    elif frequency == "quarterly":
        quarters = ["1Q","2Q","3Q","4Q"]

        for year in range(start_year, current_year + 1):
            for q in quarters:
                time_tokens.append(f"{year}%20{q}")

    elif frequency == "annual":
        for year in range(start_year, current_year + 1):
            time_tokens.append(f"{year}")

    else:
        for year in range(start_year, current_year + 1):
            time_tokens.append(f"{year}")

    return time_tokens


def _build_table_url(table_id, series_no, current_offset, limit, sort_by, token):
    base_url = f"{BASE_URL}/{table_id}?"
    query_parts = []

    if series_no is not None:
        query_parts.append(f"seriesNoORrowNo={series_no}")

    query_parts.append(f"offset={current_offset}")
    query_parts.append(f"limit={limit}")
    query_parts.append(f"sortBy={sort_by.replace(' ', '%20')}")
    query_parts.append(f"timeFilter={token}")

    return base_url + "&".join(query_parts)


def _extract_rows(rows):
    parsed_rows = []

    for row in rows:
        variable = row.get("rowText", "")
        series_no_val = row.get("seriesNo", "")

        for col in row.get("columns", []):
            raw_date = str(col.get("key", "")).strip()

            parsed_date = parse_singstat_date(raw_date)

            if parsed_date is None:
                parsed_date = pd.to_datetime(raw_date, errors="coerce")

            if pd.isna(parsed_date):
                continue

            raw_val = col.get("value", "")

            try:
                value = float(raw_val)
            except:
                value = float("nan")

            parsed_rows.append({
                "date": parsed_date,
                "variable": variable,
                "seriesNo": series_no_val,
                "value": value,
            })

    return parsed_rows


async def _fetch_token_rows(
    table_id,
    dataset_name,
    token,
    semaphore,
    series_no=None,
    limit=3000,
    sort_by="key asc",
):
    token_rows = []
    current_offset = 0
    print(f"Fetching {dataset_name} -> {token}")

    while True:
        url = _build_table_url(
            table_id=table_id,
            series_no=series_no,
            current_offset=current_offset,
            limit=limit,
            sort_by=sort_by,
            token=token,
        )

        data = await _get_async(url, semaphore)
        rows = data.get("Data", {}).get("row", [])

        if not rows:
            break

        token_rows.extend(_extract_rows(rows))
        current_offset += len(rows)

        if len(rows) < limit:
            break

    return token_rows


async def fetch_singstat_table_async(
    table_id,
    dataset_name,
    series_no=None,
    offset=0,
    limit=3000,
    sort_by="key asc",
    start_year=2019
):
    all_rows = []
    current_year = datetime.now().year

    # Detect frequency dynamically.
    frequency = await asyncio.to_thread(get_table_frequency, table_id)
    print(f"[INFO] {dataset_name} -> detected frequency: {frequency}")

    # Optional override (for SingStat inconsistencies).
    FORCE_OVERRIDE = {
        # "IPI (Industrial Production Index)": "monthly"
    }

    if dataset_name in FORCE_OVERRIDE:
        frequency = FORCE_OVERRIDE[dataset_name]
        print(f"[OVERRIDE] {dataset_name} -> forced to {frequency}")

    if frequency == "unknown":
        print(f"[WARN] Unknown frequency -> fallback yearly for {dataset_name}")

    time_tokens = _build_time_tokens(frequency, start_year, current_year)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    tasks = [
        _fetch_token_rows(
            table_id=table_id,
            dataset_name=dataset_name,
            token=token,
            semaphore=semaphore,
            series_no=series_no,
            limit=limit,
            sort_by=sort_by,
        )
        for token in time_tokens
    ]

    for token_rows in await asyncio.gather(*tasks):
        all_rows.extend(token_rows)

    # Finalize.
    if not all_rows:
        print(f"[WARN] No data returned for {dataset_name}")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows).drop_duplicates()

    out_csv = os.path.join(RAW_DIR, f"{dataset_name}.csv")
    out_json = os.path.join(RAW_DIR, f"{dataset_name}.json")
    df.to_csv(out_csv, index=False)
    df.to_json(out_json, orient="records", date_format="iso", indent=2)

    print(f"[OK] {dataset_name}: {len(df)} rows")

    return df


def fetch_singstat_table(*args, **kwargs):
    return asyncio.run(fetch_singstat_table_async(*args, **kwargs))

# ── Fetch All ─────────────────────────────────────────────

def fetch_all():
    results = {}

    for name, cfg in SINGSTAT_TABLES.items():
        print(f"\n--- {name} ({cfg['tableId']}) ---")

        try:
            results[name] = fetch_singstat_table(
                table_id=cfg["tableId"],
                dataset_name=name,
                series_no=cfg.get("seriesNoORrowNo"),
                limit=cfg.get("limit", 3000),
                sort_by=cfg.get("sortBy", "key asc"),
            )
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            results[name] = pd.DataFrame()

    return results


fetch_all_singstat = fetch_all

# ── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    fetch_all()
