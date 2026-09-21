"""
fetch_mockaroo.py — Pulls "live" datasets from your Mockaroo endpoints and saves
them as CSVs under backend/mockaroo_pull/, which is exactly where main.py's
/customer_history/{customer_id} endpoint reads from.

Run it locally (not on a server without internet):
    python fetch_mockaroo.py
    python fetch_mockaroo.py --count 200

Requires these vars in your .env (already present):
    MOCKAROO_URL_LOGIN_EVENTS
    MOCKAROO_URL_USAGE_EVENTS
    MOCKAROO_URL_SUPPORT_TICKETS
    MOCKAROO_URL_PAYMENT_EVENTS

IMPORTANT: main.py's /customer_history endpoint filters each CSV on a
'customer_id' column. Make sure each Mockaroo schema you've configured
(https://mockaroo.com -> your schema -> Fields) includes a field literally
named `customer_id`, ideally reusing the same Customer_ID values as your
Database/test_.csv so lookups actually match. If a Mockaroo field is named
differently, either rename it in the Mockaroo schema editor or set
RENAME_MAP below.
"""

import os
import sys
import argparse
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "mockaroo_pull")

ENDPOINTS = {
    "login_events.csv": "MOCKAROO_URL_LOGIN_EVENTS",
    "usage_events.csv": "MOCKAROO_URL_USAGE_EVENTS",
    "support_tickets.csv": "MOCKAROO_URL_SUPPORT_TICKETS",
    "payment_events.csv": "MOCKAROO_URL_PAYMENT_EVENTS",
}

# If a Mockaroo schema uses a different column name for the customer id,
# map it here, e.g. {"login_events.csv": {"Customer_ID": "customer_id"}}
RENAME_MAP = {}


def fetch_one(filename: str, env_key: str, count: int) -> bool:
    url_template = os.environ.get(env_key)
    if not url_template:
        print(f"  SKIP {filename}: {env_key} not set in .env")
        return False

    url = url_template.replace("{count}", str(count))
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  FAILED {filename}: {e}")
        return False

    try:
        data = resp.json()
    except ValueError:
        print(f"  FAILED {filename}: response wasn't valid JSON (check your Mockaroo key/quota)")
        return False

    if not data:
        print(f"  WARNING {filename}: Mockaroo returned an empty payload")
        return False

    df = pd.DataFrame(data)
    if filename in RENAME_MAP:
        df = df.rename(columns=RENAME_MAP[filename])

    if "customer_id" not in df.columns:
        print(f"  WARNING {filename}: no 'customer_id' column in the response "
              f"(columns found: {list(df.columns)}). /customer_history won't be "
              f"able to filter this file until the Mockaroo schema has one.")

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, filename)
    df.to_csv(out_path, index=False)
    print(f"  OK {filename}: {len(df)} rows -> {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50, help="Rows to request per endpoint")
    args = parser.parse_args()

    print(f"Pulling live Mockaroo data (count={args.count}) into {OUT_DIR} ...")
    results = [fetch_one(fname, key, args.count) for fname, key in ENDPOINTS.items()]

    if not any(results):
        print("\nNothing was pulled. Check that MOCKAROO_URL_* keys in .env are valid "
              "and that this machine has internet access to mockaroo.com.")
        sys.exit(1)


if __name__ == "__main__":
    main()
