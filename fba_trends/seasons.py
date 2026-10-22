"""Strongest products per season, last year vs the year before (Google Trends searches, not sales).

For each US season (meteorological) we take the latest completed one and compare it with the same
season a year earlier. Weeks flagged as a Google data glitch are dropped; when too few weeks remain
the comparison steps back one year (e.g. spring 2026 falls inside the 2026 glitch -> 2025 vs 2024).

- peso_temporada: season average / the keyword's 12-month average (1.0 = a normal season).
- crec_vs_anio_anterior_pct: season average vs the same season one year earlier.
- crec_vs_mercado_pct: the same growth divided by the control keywords' growth in that season.
"""
from datetime import date

import pandas as pd

from .trends import CONTROL_KEYWORDS

SEASONS = {"Invierno": (12, 2), "Primavera": (3, 5), "Verano": (6, 8), "Otoño": (9, 11)}
MIN_COVERAGE = 0.75


def window(season: str, year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Season window labelled by the year it ends in (Invierno 2026 = Dec 2025 - Feb 2026)."""
    start_m, end_m = SEASONS[season]
    start = pd.Timestamp(year - 1 if start_m > end_m else year, start_m, 1)
    end = pd.Timestamp(year, end_m, 1) + pd.offsets.MonthEnd(0)
    return start, end


def label(season: str, year: int) -> str:
    return f"{season} {year - 1}-{str(year)[2:]}" if season == "Invierno" else f"{season} {year}"


def _mean(s: pd.Series, start, end, exclude) -> float | None:
    part = s[(s.index >= start) & (s.index <= end)]
    if part.empty:
        return None
    kept = part[~part.index.isin(exclude)]
    if len(kept) < MIN_COVERAGE * len(part):
        return None
    return float(kept.mean())


def comparable_year(series: dict[str, pd.Series], season: str, today: date, exclude) -> int | None:
    """Latest year whose season is complete and, with the year before, has enough clean weeks."""
    ref = next(iter(series.values()), None)
    if ref is None:
        return None
    for year in range(today.year, today.year - 4, -1):
        start, end = window(season, year)
        if end.date() >= today:
            continue
        p_start, p_end = window(season, year - 1)
        if _mean(ref, start, end, exclude) is not None and _mean(ref, p_start, p_end, exclude) is not None:
            return year
    return None


def season_table(series: dict[str, pd.Series], today: date | None = None,
                 exclude: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    today = today or date.today()
    exclude = exclude if exclude is not None else pd.DatetimeIndex([])
    rows = []
    for season in SEASONS:
        year = comparable_year(series, season, today, exclude)
        if year is None:
            continue
        start, end = window(season, year)
        p_start, p_end = window(season, year - 1)
        for kw, s in series.items():
            cur, prev = _mean(s, start, end, exclude), _mean(s, p_start, p_end, exclude)
            base = _mean(s, end - pd.DateOffset(years=1), end, exclude)
            if cur is None or prev is None or not prev or not base:
                continue
            rows.append({"estacion": season, "periodo": label(season, year), "comparado_con": label(season, year - 1),
                         "keyword": kw, "peso_temporada": round(cur / base, 2),
                         "crec_vs_anio_anterior_pct": round((cur / prev - 1) * 100, 1)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    market = (df[df["keyword"].isin(CONTROL_KEYWORDS)].groupby("estacion")["crec_vs_anio_anterior_pct"].median()
              .rename("mercado"))
    df = df.merge(market, on="estacion", how="left")
    df["crec_vs_mercado_pct"] = ((1 + df["crec_vs_anio_anterior_pct"] / 100) / (1 + df["mercado"].fillna(0) / 100) - 1)\
        .mul(100).round(1)
    return df.drop(columns="mercado")[~df["keyword"].isin(CONTROL_KEYWORDS)].reset_index(drop=True)


def top_by_season(table: pd.DataFrame, n: int = 10, min_weight: float = 1.1) -> dict[str, pd.DataFrame]:
    """Per season: products whose demand concentrates in it (peso >= min_weight), most grown first."""
    out = {}
    for season in SEASONS:
        part = table[(table["estacion"] == season) & (table["peso_temporada"] >= min_weight)]
        out[season] = part.sort_values("crec_vs_mercado_pct", ascending=False).head(n).reset_index(drop=True)
    return out
