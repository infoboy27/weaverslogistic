"""Fetch Google Trends for every keyword in data/keywords.csv that isn't cached yet.

Usage:  .venv/Scripts/python -m scripts.scan_keywords [--refresh]
Google rate-limits hard, so requests are spaced out and 429s back off for a minute.
"""
import random
import sys
import time

import pandas as pd

from fba_trends import collect
from fba_trends.config import DATA_DIR
from fba_trends.trends import CONTROL_KEYWORDS


def main(refresh: bool = False) -> None:
    keywords = pd.read_csv(DATA_DIR / "keywords.csv")["keyword"].tolist()
    todo = [k for k in keywords if refresh or collect.load(k) is None]
    todo.sort(key=lambda k: k not in CONTROL_KEYWORDS)  # controls first: every growth number depends on them
    print(f"{len(todo)} keywords por consultar", flush=True)
    failed = []
    for i, kw in enumerate(todo, 1):
        for attempt in range(2):
            try:
                s = collect.fetch_google_trends(kw)
                print(f"[{i}/{len(todo)}] ok   {kw} ({len(s)} semanas)", flush=True)
                break
            except collect.TrendsFetchError as e:
                if attempt == 0:
                    print(f"[{i}/{len(todo)}] 429? {kw}: espero 180 s", flush=True)
                    time.sleep(180)
                else:
                    print(f"[{i}/{len(todo)}] FAIL {kw}: {e}", flush=True)
                    failed.append(kw)
        time.sleep(random.uniform(30, 45))
    print(f"Listo. Fallidas: {failed or 'ninguna'}", flush=True)


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
