from datetime import date

import pandas as pd

from fba_trends import calendar as cal
from fba_trends.config import load_config

CFG = load_config()
TODAY = date(2026, 10, 15)


def test_retail_moments_known_dates():
    m = dict(cal.retail_moments(2026))
    assert m["Black Friday / Cyber Monday"] == date(2026, 11, 27)  # Thanksgiving 2026 = Nov 26
    assert m["Día de la Madre"] == date(2026, 4, 26)               # Mother's Day May 10, minus 2 weeks


def test_christmas_is_too_late_by_sea_in_october():
    df = cal.upcoming_moments(CFG, TODAY)
    xmas = df[(df["momento"] == "Navidad") & (pd.to_datetime(df["vender_desde"]).dt.year == 2026)].iloc[0]
    assert xmas["estado"].startswith("Tarde")


def test_status_bands():
    assert cal.status(date(2026, 10, 1), TODAY).startswith("Tarde")
    assert cal.status(date(2026, 11, 1), TODAY).startswith("Urgente")
    assert cal.status(date(2027, 1, 20), TODAY).startswith("Buscar")
    assert cal.status(date(2027, 6, 1), TODAY) == "A tiempo"


def test_seasonal_window_rolls_to_next_reachable_peak():
    t = pd.DataFrame([
        {"keyword": "ugly christmas sweater", "patron": "Estacional", "semana_pico": 50,
         "temporada": "Invierno", "festividad": "Navidad"},
        {"keyword": "cooling towel", "patron": "Estacional", "semana_pico": 26,
         "temporada": "Verano", "festividad": "Verano / 4 de julio"},
        {"keyword": "slime", "patron": "Todo el año", "semana_pico": None, "temporada": None, "festividad": None},
    ])
    w = cal.seasonal_windows(t, CFG, TODAY).set_index("keyword")
    assert list(w.index) == ["cooling towel", "ugly christmas sweater"]
    assert w.loc["ugly christmas sweater", "pico"].year == 2027
    assert "ya no se alcanza" in w.loc["ugly christmas sweater", "nota"]
    assert w.loc["cooling towel", "nota"] == ""
