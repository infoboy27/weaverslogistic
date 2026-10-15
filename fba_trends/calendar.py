"""What is coming: US retail moments and seasonal keywords, with the factory order deadline.

Deadline = target date - lead time (production + sea freight + Amazon check-in + ramp, config.yaml).
If the deadline already passed, the season can only be reached by air freight (much more
expensive, not modeled here) or planned for the following year.
"""
from datetime import date, timedelta

import pandas as pd

from .trends import MONTHS_ES, lead_days


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def retail_moments(year: int) -> list[tuple[str, date]]:
    """Date by which the products must already be selling (sales peak, not the holiday itself)."""
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    return [
        ("Año nuevo / propósitos", date(year, 1, 2)),
        ("San Valentín", date(year, 2, 1)),
        ("Día de la Madre", _nth_weekday(year, 5, 6, 2) - timedelta(days=14)),
        ("Día del Padre", _nth_weekday(year, 6, 6, 3) - timedelta(days=14)),
        ("Verano / 4 de julio", date(year, 6, 15)),
        ("Regreso a clases", date(year, 7, 20)),
        ("Halloween", date(year, 10, 10)),
        ("Black Friday / Cyber Monday", thanksgiving + timedelta(days=1)),
        ("Navidad", date(year, 12, 5)),
    ]


def status(deadline: date, today: date) -> str:
    days = (deadline - today).days
    if days < 0:
        return "Tarde: aéreo o próximo año"
    if days <= 45:
        return "Urgente: pedir ya"
    if days <= 120:
        return "Buscar proveedor ahora"
    return "A tiempo"


def upcoming_moments(cfg: dict, today: date | None = None, months: int = 14) -> pd.DataFrame:
    today = today or date.today()
    lead = lead_days(cfg)
    rows = []
    for year in (today.year, today.year + 1, today.year + 2):
        for name, when in retail_moments(year):
            if today <= when <= today + timedelta(days=30 * months):
                deadline = when - timedelta(days=lead)
                rows.append({"momento": name, "vender_desde": when, "pedir_antes_de": deadline,
                             "dias_para_pedir": (deadline - today).days, "estado": status(deadline, today)})
    return pd.DataFrame(rows).sort_values("vender_desde").reset_index(drop=True)


def peak_date(iso_week: int, year: int) -> date:
    week = min(max(int(iso_week), 1), 52)
    return date.fromisocalendar(year, week, 1)


def seasonal_windows(patterns_table: pd.DataFrame, cfg: dict, today: date | None = None) -> pd.DataFrame:
    """Next reachable peak for every seasonal keyword: sourcing window -> order deadline -> peak.
    A peak whose deadline already passed this year moves to next year (flagged)."""
    today = today or date.today()
    lead = lead_days(cfg)
    rows = []
    seasonal = patterns_table[patterns_table["patron"] == "Estacional"].dropna(subset=["semana_pico"])
    for _, r in seasonal.iterrows():
        this_year = None
        for year in (today.year, today.year + 1, today.year + 2):
            peak = peak_date(r["semana_pico"], year)
            if peak < today:
                continue
            if this_year is None:
                this_year = peak
            deadline = peak - timedelta(days=lead)
            if deadline >= today:
                rows.append({
                    "keyword": r["keyword"], "temporada": r["temporada"], "festividad": r["festividad"],
                    "buscar_proveedor_desde": deadline - timedelta(days=60), "pedir_antes_de": deadline,
                    "pico": peak, "dias_para_pedir": (deadline - today).days,
                    "estado": status(deadline, today),
                    "nota": "" if peak == this_year
                    else f"El pico de {MONTHS_ES[this_year.month - 1]} {this_year.year} ya no se alcanza",
                })
                break
    return pd.DataFrame(rows).sort_values("pedir_antes_de").reset_index(drop=True) if rows else pd.DataFrame()
