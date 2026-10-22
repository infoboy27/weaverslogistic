from datetime import date

import pandas as pd

from fba_trends import navidad
from fba_trends.config import load_config


def summary(rows):
    cols = ["keyword", "precio_mediana", "vendidos_mes_top10", "listados_bajo_500_resenas", "veredicto"]
    return pd.DataFrame(rows, columns=cols)


def test_routes_air_possible_in_october_and_sea_deadline_next_year():
    cfg = load_config()
    rt = navidad.routes(cfg, date(2026, 10, 21))
    assert rt.loc[0, "ruta"] == "Navidad 2026 por aire"
    assert rt.loc[0, "estado"].startswith("Posible")
    assert rt.loc[1, "pedir_antes_de"].year == 2027


def test_routes_air_too_late_in_december():
    rt = navidad.routes(load_config(), date(2026, 12, 10))
    assert rt.loc[0, "estado"] == "Ya no llega"


def test_evaluate_flags_cheap_and_low_demand():
    cfg = load_config()
    s = summary([
        ["christmas ornament kit", 12.99, 9000, 8, "Accesible"],
        ["christmas crochet kit", 24.99, 150, 7, "Media"],
        ["needlepoint kit", 24.99, 8000, 4, "Accesible"],
        ["dog bed", 30, 9000, 5, "Accesible"],  # not a Christmas keyword: ignored
    ])
    ev = navidad.evaluate(s, cfg)
    assert list(ev["keyword"]) == ["needlepoint kit", "christmas ornament kit", "christmas crochet kit"]
    assert ev.loc[0, "pasa"]
    assert "precio" in ev.loc[1, "motivo"]
    assert "demanda" in ev.loc[2, "motivo"]
    assert (ev["costo_max_aire"] <= ev["costo_max_mar"]).all()
