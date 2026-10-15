"""Rank every cached keyword and, with --volume, compare finalists' volume against an anchor.

Usage:  .venv/Scripts/python -m scripts.rank_keywords [--volume]
Writes data/ranking.csv.
"""
import sys
from datetime import date

import pandas as pd

from fba_trends import collect
from fba_trends.config import DATA_DIR, load_config
from fba_trends.trends import CONTROL_KEYWORDS, adjust_for_market, analyze, anomalous_weeks

ACTIONABLE = {"Emergente", "Estacional en crecimiento", "Estacional"}
VOLUME_PATH = DATA_DIR / "volume.csv"  # cache: volume never changes for the fixed clean year


def main(with_volume: bool = False, max_volume_terms: int = 8, verbose: bool = True) -> pd.DataFrame:
    cfg = load_config()
    meta = pd.read_csv(DATA_DIR / "keywords.csv").set_index("keyword")
    rows = []
    glitch = anomalous_weeks(collect.load, collect.cached_keywords())
    if len(glitch):
        print(f"Semanas anómalas excluidas: {len(glitch)} ({glitch.min().date()} a {glitch.max().date()})")
    for kw in collect.cached_keywords():
        r = {"keyword": kw, **analyze(collect.load(kw), cfg, exclude=glitch)}
        if kw in meta.index:
            r["categoria"], r["notas"] = meta.loc[kw, "categoria"], meta.loc[kw, "notas"]
        rows.append(r)
    df = adjust_for_market(pd.DataFrame(rows)).sort_values("trend_score", ascending=False)
    beats_market = df["crec_vs_mercado_pct"].fillna(0) >= 10
    df["finalista"] = (df["clasificacion"].isin(ACTIONABLE) & (df["trend_score"] >= 55) & beats_market
                       & ~df["keyword"].isin(CONTROL_KEYWORDS))

    cache = pd.read_csv(VOLUME_PATH) if VOLUME_PATH.exists() else pd.DataFrame(columns=["keyword", "volumen"])
    if with_volume:
        finalists = df.loc[df["finalista"], "keyword"].tolist()
        missing = [k for k in finalists if k not in set(cache["keyword"])][:max_volume_terms]
        if missing:
            try:
                vol = collect.relative_volume(missing)
                cache = pd.concat([cache, pd.DataFrame({"keyword": list(vol), "volumen": list(vol.values())})])
                cache.to_csv(VOLUME_PATH, index=False)
            except collect.TrendsFetchError as e:
                print(f"Volumen no actualizado: {e}")
    df["volumen_vs_yoga_mat_pct"] = df["keyword"].map(dict(zip(cache["keyword"], cache["volumen"])))

    df.to_csv(DATA_DIR / "ranking.csv", index=False)
    cols = [c for c in ["keyword", "categoria", "clasificacion", "trend_score", "crec_anual_pct", "crec_vs_mercado_pct", "yoy_pct", "momentum_pct",
                        "mes_pico", "pedir_antes_de", "volumen_vs_yoga_mat_pct", "finalista"] if c in df]
    if verbose:
        with pd.option_context("display.width", 200, "display.max_rows", 100):
            print(df[cols].to_string(index=False))
        print(f"\nHoy: {date.today()}")
    return df


if __name__ == "__main__":
    main(with_volume="--volume" in sys.argv)
