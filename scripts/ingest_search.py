"""Turn raw Amazon search snapshots (data/raw_search/*.json) into data/competition.csv.

Snapshot format: {"keyword", "captured", "dop_per_usd", "fields": [...], "items": [[...], ...]}
Usage:  .venv/Scripts/python -m scripts.ingest_search
"""
import json

import pandas as pd

from fba_trends import competition
from fba_trends.config import DATA_DIR


def main() -> pd.DataFrame:
    for path in sorted((DATA_DIR / "raw_search").glob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))
        if "keywords" in snap:  # compact format: already-filtered organic top 10 per keyword
            for kw, d in snap["keywords"].items():
                df = pd.DataFrame([{
                    "keyword": kw, "posicion": i + 1, "asin": r[0], "titulo": r[5], "marca": r[5],
                    "precio_usd": r[1], "rating": r[4], "resenas": r[2], "vendidos_mes": r[3],
                    "patrocinados_pagina": d["ads"], "fecha": snap["captured"],
                } for i, r in enumerate(d["rows"])], columns=competition.COLUMNS)
                competition.save_keyword(df)
                print(f"{kw}: {len(df)} orgánicos, {d['ads']} anuncios")
            continue
        items = [dict(zip(snap["fields"], row)) for row in snap["items"]]
        df, ads = competition.from_search_results(snap["keyword"], items, snap.get("dop_per_usd"))
        df["fecha"] = snap.get("captured", df["fecha"])
        competition.save_keyword(df)
        print(f"{snap['keyword']}: {len(df)} orgánicos, {ads} anuncios")
    table = competition.summary_table()
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(table.T.to_string(header=False))
    return table


if __name__ == "__main__":
    main()
