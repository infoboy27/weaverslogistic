"""Demand pattern of a keyword: seasonal (which season / holiday), all-year, viral, market shock,
growing, or rising fast right now.

Works on the 5-year weekly series (glitch weeks excluded) and, when available, the monthly series
since 2004 (data/trends_long/) so that old shocks like toilet paper in March 2020 are visible.

Definitions (heuristics, not validated against sales):
- Episode: a peak >= 2.5x the median of the half-year before it (and >= 15 on Google's 0-100 scale)
  that later fell to <= half its peak. Peaks that repeat at the same time every year are seasonality,
  not episodes.
- Shock: the episode's climb took <= 2 weeks (<= 1 month on monthly data) -> an external event.
- Viral: a slower climb (social/pop-culture spread), then a fall.
- Rising fast: the last 13 weeks are >= 2x the half-year before and still near their high: too early
  to know whether it will hold (growing) or fade (viral).
"""
import math
from datetime import date

import numpy as np
import pandas as pd

from .trends import to_weekly

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
SEASON_OF_MONTH = {12: "Invierno", 1: "Invierno", 2: "Invierno", 3: "Primavera", 4: "Primavera", 5: "Primavera",
                   6: "Verano", 7: "Verano", 8: "Verano", 9: "Otoño", 10: "Otoño", 11: "Otoño"}
# US retail moments by ISO week of the seasonal peak.
HOLIDAYS = [
    (1, 3, "Año nuevo / propósitos"), (5, 7, "San Valentín"), (12, 16, "Pascua / primavera"),
    (18, 20, "Día de la Madre"), (23, 25, "Día del Padre / graduaciones"), (26, 29, "Verano / 4 de julio"),
    (30, 35, "Regreso a clases"), (41, 44, "Halloween"), (45, 48, "Black Friday"), (49, 52, "Navidad"),
]
PATTERNS = ["Estacional", "Todo el año", "Viral", "Shock de mercado", "Creciente", "Subiendo rápido",
            "Irregular", "Volumen insuficiente"]


def holiday_for_week(week: int) -> str | None:
    for lo, hi, name in HOLIDAYS:
        if lo <= week <= hi:
            return name
    return None


def seasonal_profile(w: pd.Series) -> pd.Series:
    """Average level by ISO week relative to the yearly mean (1.0 = normal week), smoothed."""
    base = w.rolling(52, center=True, min_periods=26).mean()
    ratio = (w / base.replace(0, np.nan)).dropna()
    prof = ratio.groupby(ratio.index.isocalendar().week.astype(int)).mean().reindex(range(1, 54))
    prof = prof.interpolate(limit_direction="both")
    padded = pd.concat([prof.iloc[-2:], prof, prof.iloc[:2]])  # circular smoothing
    return padded.rolling(5, center=True).mean().iloc[2:-2]


def month_profile(w: pd.Series) -> pd.Series:
    base = w.rolling(52, center=True, min_periods=26).mean()
    ratio = (w / base.replace(0, np.nan)).dropna()
    return ratio.groupby(ratio.index.month).mean().reindex(range(1, 13))


def episodes(s: pd.Series, per_year: int, seasonal_months: set[int] | None = None) -> list[dict]:
    """Spike-and-fall episodes. per_year = 52 (weekly) or 12 (monthly)."""
    v = s.to_numpy(dtype=float)
    n = len(v)
    half, quarter = per_year // 2, max(per_year // 4, 1)
    gap = max(per_year // 26, 1)          # skip the weeks right before the peak when measuring "before"
    window = max(per_year // 6, 1)        # local-max neighbourhood
    fast = 2 if per_year >= 52 else 1     # climb length that counts as a shock
    out = []
    i = half + gap
    while i < n:
        lo, hi = max(0, i - window), min(n, i + window + 1)
        if v[i] < v[lo:hi].max() or v[i] < 15:
            i += 1
            continue
        pre = float(np.median(v[i - half - gap:i - gap]))
        ratio = v[i] / max(pre, 1.0)
        after = v[i + quarter:i + per_year] if i + quarter < n else np.array([])
        fell = after.size > 0 and float(np.median(after)) <= 0.5 * v[i]
        month = s.index[i].month
        recurring = seasonal_months is not None and month in seasonal_months
        if ratio >= 2.5 and fell and not recurring:
            start = i
            while start > 0 and v[start - 1] > max(pre, 1.0) * 1.5:
                start -= 1
            climb = i - start + 1
            out.append({"fecha": s.index[i].date(), "veces": round(ratio, 1), "valor": float(v[i]),
                        "semanal": per_year >= 52,
                        "tipo": "Shock de mercado" if climb <= fast else "Viral", "subida_periodos": climb})
            i += window
        else:
            i += 1
    return out


def classify(series: pd.Series, exclude: pd.DatetimeIndex | None = None,
             long_series: pd.Series | None = None, today: date | None = None) -> dict:
    raw = to_weekly(series)
    if exclude is not None and len(exclude):
        raw[raw.index.normalize().isin(exclude.normalize())] = np.nan
    w = raw.interpolate(limit_direction="both")
    if len(w) < 104 or (w.iloc[-104:] < 1).mean() > 0.5:
        return {"patron": "Volumen insuficiente"}

    mprof = month_profile(w)
    seasonal_strength = w.autocorr(lag=52)
    seasonal_strength = 0.0 if math.isnan(seasonal_strength) else float(seasonal_strength)
    is_seasonal = seasonal_strength >= 0.5 and mprof.max() >= 1.35
    peak_months = set(mprof[mprof >= 0.85 * mprof.max()].index) if is_seasonal else None

    eps = episodes(w, 52, peak_months)
    if long_series is not None and len(long_series) > 36:
        ls = long_series.copy().astype(float)
        if exclude is not None and len(exclude):
            ls[ls.index.to_period("M").isin(exclude.to_period("M"))] = np.nan
        ls = ls.interpolate(limit_direction="both")
        seen = {(e["fecha"].year, e["fecha"].month) for e in eps}
        for e in episodes(ls, 12, peak_months):
            if (e["fecha"].year, e["fecha"].month) not in seen and not any(
                    abs((e["fecha"] - x["fecha"]).days) < 120 for x in eps):
                eps.append(e)
    eps.sort(key=lambda e: e["fecha"])

    recent = w.iloc[-13:].mean()
    before = float(np.median(w.iloc[-39:-13]))
    rising_fast = recent >= 2 * max(before, 1.0) and w.iloc[-4:].mean() >= 0.7 * w.iloc[-13:].max() and recent >= 10
    last, prev = raw.iloc[-52:].to_numpy(), raw.iloc[-104:-52].to_numpy()
    keep = ~np.isnan(last) & ~np.isnan(prev)  # like-for-like weeks, glitch left out of both years
    yoy = last[keep].mean() / max(prev[keep].mean(), 1e-9) - 1 if keep.sum() >= 26 else 0.0
    cv = float(w.iloc[-104:].std() / max(w.iloc[-104:].mean(), 1e-9))

    season = festividad = peak_week = None
    if is_seasonal:
        wprof = seasonal_profile(w)
        peak_week = int(wprof.idxmax())
        festividad = holiday_for_week(peak_week)
        season = SEASON_OF_MONTH[int(mprof.idxmax())]

    if is_seasonal:  # a seasonal product climbing before its peak is not a new trend
        patron = "Estacional"
    elif rising_fast:
        patron = "Subiendo rápido"
    elif eps and eps[-1]["tipo"] == "Shock de mercado":
        patron = "Shock de mercado"
    elif eps:
        patron = "Viral"
    elif yoy >= 0.3:
        patron = "Creciente"
    elif cv < 0.35:
        patron = "Todo el año"
    else:
        patron = "Irregular"

    last = eps[-1] if eps else None
    return {
        "patron": patron,
        "temporada": season,
        "festividad": festividad,
        "mes_pico": MONTHS[int(mprof.idxmax()) - 1] if is_seasonal else None,
        "semana_pico": peak_week,
        "fuerza_estacional": round(seasonal_strength, 2),
        "variabilidad": round(cv, 2),
        "crec_anual_pct": round(float(yoy) * 100, 1),
        "ultimo_episodio": f"{last['tipo']} {last['fecha']:%Y-%m} (x{last['veces']})" if last else None,
        "episodios": len(eps),
        "episodio_fecha": last["fecha"].isoformat() if last else None,
        # today's level vs that peak (same weekly scale only): <= 0.5 means the wave is over
        "nivel_vs_pico": round(float(w.iloc[-4:].mean()) / last["valor"], 2) if last and last["semanal"] else None,
    }


def month_heat(series: pd.Series, exclude: pd.DatetimeIndex | None = None) -> pd.Series:
    """Month-of-year index (1.0 = average month) for the seasonal calendar heatmap."""
    raw = to_weekly(series)
    if exclude is not None and len(exclude):
        raw[raw.index.isin(exclude)] = np.nan
    prof = month_profile(raw.interpolate(limit_direction="both"))
    prof.index = MONTHS
    return prof
