import numpy as np
import pandas as pd

from fba_trends import patterns as p

IDX = pd.date_range("2021-10-03", periods=262, freq="W")
rng = np.random.default_rng(0)


def series(values):
    return pd.Series(np.clip(values, 0, 100), index=IDX[:len(values)])


def noise(level=40, sd=2):
    return level + rng.normal(0, sd, len(IDX))


def test_all_year():
    assert p.classify(series(noise()))["patron"] == "Todo el año"


def test_christmas_seasonal():
    week = IDX.isocalendar().week.to_numpy().astype(int)
    v = 20 + 70 * np.exp(-((week - 51) ** 2) / 6.0) + rng.normal(0, 1, len(IDX))
    r = p.classify(series(v))
    assert r["patron"] == "Estacional"
    assert r["festividad"] == "Navidad" and r["temporada"] == "Invierno" and r["mes_pico"] == "dic"


def test_summer_seasonal():
    month = IDX.month.to_numpy()
    v = np.where(np.isin(month, [6, 7]), 80.0, 20.0) + rng.normal(0, 1, len(IDX))
    r = p.classify(series(v))
    assert r["patron"] == "Estacional" and r["temporada"] == "Verano"


def test_market_shock():
    v = noise(20, 1)
    v[100:103] = [100, 90, 60]  # jumps in one week, gone in three
    r = p.classify(series(v))
    assert r["patron"] == "Shock de mercado"
    assert r["ultimo_episodio"].startswith("Shock de mercado")


def test_viral_past():
    v = noise(10, 1)
    v[120:132] = np.linspace(12, 100, 12)    # 12-week climb
    v[132:160] = np.linspace(100, 15, 28)    # then fades
    assert p.classify(series(v))["patron"] == "Viral"


def test_rising_fast_now():
    v = noise(10, 1)
    v[-13:] = np.linspace(25, 60, 13)
    assert p.classify(series(v))["patron"] == "Subiendo rápido"


def test_growing_not_viral():
    v = 10 * 1.008 ** np.arange(len(IDX)) + rng.normal(0, 0.5, len(IDX))  # ~50% a year
    assert p.classify(series(v))["patron"] == "Creciente"


def test_shock_found_in_long_history_only():
    weekly = series(noise(30, 1))  # 5-year window: nothing special
    months = pd.date_range("2004-01-01", "2026-09-01", freq="MS")
    lv = 20 + rng.normal(0, 1, len(months))
    lv[months.get_loc(pd.Timestamp("2020-03-01"))] = 100  # toilet paper, March 2020
    r = p.classify(weekly, long_series=pd.Series(lv, index=months))
    assert r["patron"] == "Shock de mercado"
    assert "2020-03" in r["ultimo_episodio"]


def test_holiday_lookup():
    assert p.holiday_for_week(43) == "Halloween"
    assert p.holiday_for_week(6) == "San Valentín"
    assert p.holiday_for_week(38) is None


def test_seasonal_ramp_is_not_rising_fast():
    week = IDX.isocalendar().week.to_numpy().astype(int)
    v = 10 + 80 * np.exp(-((week - 51) ** 2) / 20.0) + rng.normal(0, 1, len(IDX))
    s = series(v)[:-8]  # cut in the middle of the pre-Christmas climb
    assert p.classify(s)["patron"] == "Estacional"
