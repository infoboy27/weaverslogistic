from datetime import date

import numpy as np
import pandas as pd

from fba_trends import seasons


def weekly(values_by_month):
    idx = pd.date_range("2022-01-02", "2026-10-11", freq="W-SUN")
    return pd.Series([values_by_month(d) for d in idx], index=idx, dtype=float)


def test_window_winter_spans_years():
    start, end = seasons.window("Invierno", 2026)
    assert start == pd.Timestamp(2025, 12, 1) and end.month == 2 and end.year == 2026
    assert seasons.label("Invierno", 2026) == "Invierno 2025-26"


def test_summer_product_grows_and_is_market_adjusted():
    flat = weekly(lambda d: 50)
    summer = weekly(lambda d: (80 if d.year >= 2026 else 40) if d.month in (6, 7, 8) else 20)
    t = seasons.season_table({"pool float": summer, "yoga mat": flat, "backpack": flat}, date(2026, 10, 21))
    row = t[(t.keyword == "pool float") & (t.estacion == "Verano")].iloc[0]
    assert row.periodo == "Verano 2026"
    assert row.crec_vs_anio_anterior_pct == 100.0 and row.crec_vs_mercado_pct == 100.0
    assert row.peso_temporada > 1.5
    assert "yoga mat" not in set(t.keyword)
    top = seasons.top_by_season(t)
    assert list(top["Verano"].keyword) == ["pool float"]
    assert top["Invierno"].empty


def test_glitch_season_steps_back_a_year():
    s = weekly(lambda d: 30 + d.month)
    glitch = pd.DatetimeIndex([d for d in s.index if pd.Timestamp(2026, 3, 1) <= d <= pd.Timestamp(2026, 5, 31)])
    t = seasons.season_table({"x": s, "yoga mat": s}, date(2026, 10, 21), glitch)
    assert t[t.estacion == "Primavera"].periodo.iloc[0] == "Primavera 2025"


def test_holiday_windows():
    assert seasons.easter(2025) == date(2025, 4, 20)
    start, end = seasons.window("Día de la Madre", 2026)
    assert end == pd.Timestamp(2026, 5, 10) and (end - start).days == 21
    start, end = seasons.window("Black Friday / Cyber Monday", 2025)
    assert start <= pd.Timestamp(2025, 11, 28) <= end


def test_valentine_product_ranked_in_holidays():
    flat = weekly(lambda d: 50)
    heart = weekly(lambda d: (90 if d.year >= 2025 else 45) if (d.month == 2 and d.day <= 14) or
                   (d.month == 1 and d.day >= 24) else 20)
    t = seasons.season_table({"heart necklace": heart, "yoga mat": flat}, date(2026, 10, 21))
    top = seasons.top_by_season(t, min_weight=1.2, periods=seasons.HOLIDAYS)
    assert list(top["San Valentín"].keyword) == ["heart necklace"]
    assert top["San Valentín"].loc[0, "grupo"] == "Fecha especial"
    assert top["Halloween"].empty


def test_product_growing_all_year_is_not_a_holiday_product():
    flat = weekly(lambda d: 50)
    growing = pd.Series(np.linspace(10, 100, len(flat)), index=flat.index)
    t = seasons.season_table({"weighted vest": growing, "yoga mat": flat}, date(2026, 10, 21))
    tops = seasons.top_by_season(t, min_weight=1.2, periods=seasons.HOLIDAYS)
    assert all(d.empty for d in tops.values())
