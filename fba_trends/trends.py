"""Classify a Google Trends interest series (0-100) and score how attractive it is
for FBA given a ~3 month supply lead time.

Thresholds and score weights below are heuristics, not validated against outcomes.
Google Trends is RELATIVE interest: a keyword can grow 300% and still have tiny
volume. Always confirm absolute demand on Amazon (Brand Analytics / Keepa) before buying.
"""
import math
from datetime import date

import numpy as np
import pandas as pd

MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def to_weekly(s: pd.Series) -> pd.Series:
    s = s.dropna().sort_index()
    return s.resample("W").mean().interpolate(limit_direction="both")


def _ratio(a: float, b: float) -> float:
    if b <= 0:
        return 1.0 if a > 0 else 0.0
    return a / b - 1


def lead_days(cfg: dict) -> int:
    t = cfg["tiempos_entrega_dias"]
    return t["produccion"] + t["flete_maritimo"] + t["recepcion_amazon"] + t["margen_rampa"]


def order_deadline(peak_month: int, cfg: dict, today: date | None = None) -> date:
    """Last day to place the factory order to have stock selling before the next peak."""
    today = today or date.today()
    for year in (today.year, today.year + 1, today.year + 2):
        deadline = pd.Timestamp(year, peak_month, 1) - pd.Timedelta(days=lead_days(cfg))
        if deadline.date() >= today:
            return deadline.date()
    raise AssertionError("unreachable")


def analyze(series: pd.Series, cfg: dict, today: date | None = None,
            exclude: pd.DatetimeIndex | None = None) -> dict:
    """`exclude`: weeks with a market-wide data glitch (see `anomalous_weeks`); they are
    interpolated over, and left out of both years when computing yearly growth."""
    raw = to_weekly(series)
    clean = raw.copy()
    if exclude is not None and len(exclude):
        clean[clean.index.isin(exclude)] = np.nan
    w = clean.interpolate(limit_direction="both")
    n = len(w)
    if n < 26:
        return {"clasificacion": "Datos insuficientes", "trend_score": None, "semanas": n}

    if (w.iloc[-104:] < 1).mean() > 0.5:
        # Google reports 0 for weeks below its volume threshold; mostly-zero = too small to read.
        return {"clasificacion": "Volumen insuficiente", "trend_score": 0.0, "semanas": n}

    recent = w.iloc[-8:].mean()
    prior = w.iloc[-16:-8].mean()
    momentum = _ratio(recent, prior)

    yoy = None
    if n >= 60:
        yoy = _ratio(recent, w.iloc[-60:-52].mean())
    # Whole-year growth: robust for seasonal products, where recent weeks may be off-season.
    yoy_52 = None
    if n >= 104:
        last, prev = clean.iloc[-52:].to_numpy(), clean.iloc[-104:-52].to_numpy()
        keep = ~np.isnan(last) & ~np.isnan(prev)  # like-for-like weeks only
        if keep.sum() >= 26:
            yoy_52 = _ratio(last[keep].mean(), prev[keep].mean())

    seasonal_strength = None
    peak_month, peak_ratio = None, None
    if n >= 78:
        seasonal_strength = float(w.autocorr(lag=52))
        if math.isnan(seasonal_strength):
            seasonal_strength = None
        # Detrend by yearly rolling mean so growth doesn't look like seasonality.
        base = w.rolling(52, center=True, min_periods=26).mean()
        profile = (w / base).groupby(w.index.month).mean()
        peak_month = int(profile.idxmax())
        peak_ratio = float(profile.max())

    last12 = w.iloc[-12:]
    spike_ratio = last12.max() / max(w.iloc[-26:].median(), 1e-9)
    fad = bool(spike_ratio > 2.5 and w.iloc[-1] < 0.6 * last12.max())

    is_seasonal = (seasonal_strength or 0) >= 0.5 and (peak_ratio or 0) >= 1.35
    if is_seasonal and yoy_52 is not None:
        growth = yoy_52
    else:
        growth = yoy if yoy is not None else momentum

    if fad:
        label = "Moda pasajera (pico y caída)"
    elif is_seasonal and growth >= 0.2:
        label = "Estacional en crecimiento"
    elif is_seasonal:
        label = "Estacional"
    elif (momentum >= 0.25 and growth >= 0.2) or (growth >= 0.3 and momentum >= 0):
        label = "Emergente"
    elif yoy_52 is not None and yoy_52 >= 0.5 and growth >= 0.2:
        # Strong whole-year growth still running year over year; short-term dip is noise.
        label = "Emergente"
    elif growth <= -0.2 and momentum <= 0:
        label = "En declive"
    else:
        label = "Estable"

    # Momentum is meaningless off-season, so seasonal products are scored on yearly growth only.
    momentum_term = 0 if is_seasonal else 15 * math.tanh(momentum)
    score = 50 + 30 * math.tanh(growth) + momentum_term - (30 if fad else 0)
    deadline = None
    if is_seasonal:
        deadline = order_deadline(peak_month, cfg, today)
        days_left = (deadline - (today or date.today())).days
        if 30 <= days_left <= 150:
            score += 10  # sourcing window: time to find a supplier and sample before the order deadline
    score = float(np.clip(score, 0, 100))

    return {
        "clasificacion": label,
        "trend_score": round(score, 1),
        "momentum_pct": round(float(momentum) * 100, 1),
        "yoy_pct": None if yoy is None else round(float(yoy) * 100, 1),
        "crec_anual_pct": None if yoy_52 is None else round(float(yoy_52) * 100, 1),
        "estacionalidad": None if seasonal_strength is None else round(seasonal_strength, 2),
        "mes_pico": MONTHS_ES[peak_month - 1] if is_seasonal else None,
        "pedir_antes_de": deadline.isoformat() if deadline else None,
        "pico_reciente_x": round(float(spike_ratio), 2),
        "semanas": n,
    }


CONTROL_KEYWORDS = ("yoga mat", "backpack", "umbrella", "water bottle")


def adjust_for_market(table: pd.DataFrame) -> pd.DataFrame:
    """Add `crec_vs_mercado_pct`: yearly growth relative to the median of stable control keywords.

    Google Trends data can shift for everyone at once (methodology changes, more total searches),
    which makes every keyword look like it grew. Dividing by the controls' growth removes that.
    """
    table = table.copy()
    if "crec_anual_pct" not in table:
        table["crec_vs_mercado_pct"] = None
        return table
    controls = table[table["keyword"].isin(CONTROL_KEYWORDS)]["crec_anual_pct"].dropna()
    if controls.empty:
        table["crec_vs_mercado_pct"] = None
        return table
    market = 1 + controls.median() / 100
    table["crec_vs_mercado_pct"] = ((1 + table["crec_anual_pct"] / 100) / market - 1).mul(100).round(1)
    return table


def anomalous_weeks(load, keywords: list[str] | None = None, threshold: float | None = None) -> pd.DatetimeIndex:
    """Weeks with a market-wide Google data glitch (e.g. Mar-Jun 2026), padded around the block.

    With >= 15 usable keywords: median across ALL keywords of (value / its trailing 26-week median).
    Keywords peak in different seasons, so their seasonality cancels out in the median and only
    jumps that hit everything at once remain (threshold 1.3). With fewer keywords it falls back to
    the 4 control keywords (threshold 1.8; two of them are seasonal, so it needs a higher bar).
    """
    series = {}
    for k in (keywords or []):
        s = load(k)
        if s is not None:
            w = to_weekly(s)
            if (w.iloc[-104:] >= 1).mean() > 0.5:
                series[k] = w
    if len(series) >= 15:
        df = pd.concat(series, axis=1)
        baseline = df.rolling(26, min_periods=13).median().shift(4).clip(lower=1)
        threshold = threshold or 1.3
    else:
        series = {k: to_weekly(s) for k in CONTROL_KEYWORDS if (s := load(k)) is not None}
        if len(series) < 2:
            return pd.DatetimeIndex([])
        df = pd.concat(series, axis=1)
        baseline = df.rolling(52, min_periods=26).median().shift(1).clip(lower=1)
        threshold = threshold or 1.8
    ratio = (df / baseline).median(axis=1)
    return widen(ratio[ratio >= threshold].index)


def widen(weeks: pd.DatetimeIndex, min_run: int = 4, before: int = 7, after: int = 3) -> pd.DatetimeIndex:
    """Pad multi-week glitch blocks: Google's data ramps up for weeks before the block clears the
    threshold (Feb-Mar 2026 ran ~1.25x) and settles for a few weeks after. Isolated weeks are kept as is."""
    if weeks is None or not len(weeks):
        return pd.DatetimeIndex([])
    weeks = pd.DatetimeIndex(sorted(weeks))
    out, run = set(), [weeks[0]]
    for d in list(weeks[1:]) + [None]:
        if d is not None and (d - run[-1]).days <= 14:
            run.append(d)
            continue
        if len(run) >= min_run:
            out |= set(pd.date_range(run[0] - pd.Timedelta(weeks=before), run[-1] + pd.Timedelta(weeks=after),
                                     freq="7D"))
        else:
            out |= set(run)
        if d is not None:
            run = [d]
    return pd.DatetimeIndex(sorted(out))
