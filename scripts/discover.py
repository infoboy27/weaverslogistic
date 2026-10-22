"""Daily discovery run: scan pending terms and explore new seeds, then re-rank.

Usage:  .venv/Scripts/python -m scripts.discover [--seeds 4] [--scans 10]
Google blocks this connection after a handful of calls, so the run is budgeted and stops at the
first block (the next day's run picks up where this one left off). To keep both queues moving,
the order alternates by day: odd days scan the queue first, even days explore seeds first.
"""
import argparse
import json
import random
from datetime import date

import pandas as pd

from fba_trends import collect, competition, criteria, discovery
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


def seeds_first(today: date) -> bool:
    return today.toordinal() % 2 == 0


def scan_phase(table: pd.DataFrame, run: dict, n_scans: int) -> pd.DataFrame:
    """Google Trends for pending terms: competition-ready Amazon types first."""
    for term in discovery.next_to_scan(table, n_scans, priority=competition_ready()):
        row = table.index[table["termino"] == term][0]
        try:
            collect.fetch_google_trends(term)
        except collect.NoTrendsData:
            # too little search volume: mark it and move on (stopping here froze the queue for days)
            table.loc[row, ["estado", "motivo"]] = ["filtrado", "sin volumen en Google"]
            discovery.save(table)
            print(f"sin datos '{term}' (se marca y se sigue)")
            wait()
            continue
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
    return table


def seed_phase(table: pd.DataFrame, state: dict, run: dict, known: set, n_seeds: int) -> pd.DataFrame:
    """Rising related queries for the seeds that are due (new product ideas)."""
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
    return table


def main(n_seeds: int = 4, n_scans: int = 10) -> dict:
    state = load_state()
    table = discovery.refilter(discovery.load())  # filter rules may have changed since the last run
    known = set(pd.read_csv(KEYWORDS_PATH)["keyword"])
    today = date.today()
    run = {"fecha": today.isoformat(), "semillas": 0, "nuevos": 0, "escaneados": 0, "bloqueado": False,
           "orden": "semillas primero" if seeds_first(today) else "cola primero"}

    discarded = set(criteria.load_pipeline().query("etapa_manual == 'Descartado'")["tipo"])
    table.loc[table["termino"].isin(discarded) & (table["estado"] == "pendiente"), ["estado", "motivo"]] = \
        ["filtrado", "descartado en el pipeline"]

    phases = [lambda t: seed_phase(t, state, run, known, n_seeds), lambda t: scan_phase(t, run, n_scans)]
    if not seeds_first(today):
        phases.reverse()
    for phase in phases:
        if run["bloqueado"]:
            break
        table = phase(table)

    # Re-rank; measure volume for at most 4 new finalists (one request) if not blocked
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
