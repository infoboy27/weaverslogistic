"""Daily discovery run: rising queries from a few seeds, scan a few pending terms, re-rank.

Usage:  .venv/Scripts/python -m scripts.discover [--seeds 4] [--scans 10]
Google blocks this connection after ~15-20 calls, so the run is budgeted and stops at the
first block (the next day's run picks up where this one left off).
"""
import argparse
import json
import random
from datetime import date

import pandas as pd

from fba_trends import collect, competition, discovery
from fba_trends.config import DATA_DIR, load_config
from scripts import rank_keywords

STATE_PATH = DATA_DIR / "discovery_state.json"
KEYWORDS_PATH = DATA_DIR / "keywords.csv"


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"seed_log": {}, "runs": []}


def wait() -> None:
    discovery.pause(random.uniform(30, 45))


def competition_ready() -> list[str]:
    """Keywords whose Amazon top 10 is captured, price and demand pass and the verdict is not 'Difícil'."""
    table = competition.summary_table()
    if table.empty:
        return []
    c = load_config(with_settings=True)["criterios"]
    ok = table[(table["precio_mediana"].between(c["precio_min"], c["precio_max"]))
               & (table["veredicto"] != "Difícil")
               & (table["vendidos_mes_top10"] >= c["min_vendidos_mes_top10"])]
    return ok.sort_values("listados_bajo_500_resenas", ascending=False)["keyword"].tolist()


def main(n_seeds: int = 4, n_scans: int = 10) -> dict:
    state = load_state()
    table = discovery.refilter(discovery.load())  # filter rules may have changed since the last run
    known = set(pd.read_csv(KEYWORDS_PATH)["keyword"])
    run = {"fecha": date.today().isoformat(), "semillas": 0, "nuevos": 0, "escaneados": 0, "bloqueado": False}

    # 1) Scan first: product types already selling on Amazon are worth more than new seed ideas.
    #    Within the queue, types that already passed price + competition go first.
    for term in discovery.next_to_scan(table, n_scans, priority=competition_ready()):
        row = table.index[table["termino"] == term][0]
        try:
            collect.fetch_google_trends(term)
        except collect.TrendsFetchError as e:
            print(f"BLOQUEADO escaneando '{term}': {e}")
            run["bloqueado"] = True
            break
        table.loc[row, "estado"] = "escaneado"
        discovery.save(table)
        kw = pd.read_csv(KEYWORDS_PATH)
        if term not in set(kw["keyword"]):
            note = f"seed: {table.loc[row, 'seed']}; +{table.loc[row, 'subida_pct']:.0f}%"
            kw.loc[len(kw)] = [term, f"descubierto: {table.loc[row, 'categoria']}", note]
            kw.to_csv(KEYWORDS_PATH, index=False)
        run["escaneados"] += 1
        print(f"escaneado '{term}'")
        wait()

    # 2) Discover: rising queries for the seeds that are due, with whatever budget is left
    if not run["bloqueado"]:
        for seed, cat in discovery.seeds_due(state["seed_log"])[:n_seeds]:
            try:
                rising = discovery.rising_queries(seed)
            except collect.TrendsFetchError as e:
                print(f"BLOQUEADO en semilla '{seed}': {e}")
                run["bloqueado"] = True
                break
            table, new = discovery.add_rising(table, seed, cat, rising, known)
            state["seed_log"][seed] = date.today().isoformat()
            run["semillas"] += 1
            run["nuevos"] += new
            print(f"semilla '{seed}': {len(rising)} en aumento, {new} nuevos útiles")
            discovery.save(table)
            wait()

    # 3) Re-rank; measure volume for at most 4 new finalists (one request) if not blocked
    rank_keywords.main(with_volume=not run["bloqueado"], max_volume_terms=4, verbose=False)
    state["runs"].append(run)
    STATE_PATH.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Resumen: {run}")
    return run


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--scans", type=int, default=10)
    a = ap.parse_args()
    main(a.seeds, a.scans)
