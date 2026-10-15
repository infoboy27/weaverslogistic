from datetime import date

import pandas as pd

from fba_trends import alerts as a

TODAY = date(2026, 10, 15)


def prod(keyword, patron, g=None, clas=None, ep=None, lvl=None, **kw):
    return {"keyword": keyword, "patron": patron, "crec_vs_mercado_pct": g, "clasificacion": clas,
            "episodio_fecha": ep, "nivel_vs_pico": lvl, "festividad": kw.get("fest"), "temporada": kw.get("temp")}


PRODUCTS = pd.DataFrame([
    prod("squishy", "Subiendo rápido", 350),
    prod("padel racket", "Creciente", 59, "Emergente"),
    prod("dog cooling mat", "Estacional", 26, fest="Día del Padre"),
    prod("wall pilates", "Shock de mercado", -71, ep="2024-12-01", lvl=0.05),
    prod("weighted vest", "Todo el año", -18, "En declive"),
    prod("sand free beach mat", "Volumen insuficiente"),
    prod("viral now", "Viral", 10, ep="2026-08-01", lvl=0.8),
    prod("yoga mat", "Creciente", 30),  # control keyword: never alerted as a product
])

WINDOWS = pd.DataFrame([
    {"keyword": "garden kneeler", "festividad": "Día de la Madre", "buscar_proveedor_desde": date(2026, 11, 17),
     "pedir_antes_de": date(2027, 1, 16), "pico": date(2027, 5, 10), "dias_para_pedir": 93, "nota": ""},
    {"keyword": "embroidery kit", "festividad": "Navidad", "buscar_proveedor_desde": date(2027, 6, 15),
     "pedir_antes_de": date(2027, 8, 14), "pico": date(2027, 12, 6), "dias_para_pedir": 303,
     "nota": "El pico de nov 2026 ya no se alcanza"},
])
MOMENTS = pd.DataFrame([
    {"momento": "Navidad", "vender_desde": date(2026, 12, 5), "pedir_antes_de": date(2026, 8, 13), "dias_para_pedir": -63},
    {"momento": "Día de la Madre", "vender_desde": date(2027, 4, 25), "pedir_antes_de": date(2027, 1, 1), "dias_para_pedir": 78},
])


def test_deadlines_only_reachable_and_near():
    out = pd.DataFrame(a.deadline_alerts(WINDOWS, MOMENTS))
    assert set(out["elemento"]) == {"garden kneeler", "Día de la Madre"}  # Navidad past, embroidery rolled over
    assert (out["prioridad"] == "Media").all()


def test_momentum_and_discard_rules():
    m = pd.DataFrame(a.momentum_alerts(PRODUCTS, today=TODAY)).set_index("elemento")
    assert m.loc["squishy", "prioridad"] == "Alta"
    assert "padel racket" in m.index and "dog cooling mat" in m.index
    assert m.loc["viral now", "prioridad"] == "Baja"  # recent wave: risky with 3-4 months lead time
    d = pd.DataFrame(a.discard_alerts(PRODUCTS, WINDOWS, TODAY)).set_index("elemento")
    assert d.loc["wall pilates", "prioridad"] == "Alta"
    assert {"weighted vest", "sand free beach mat", "embroidery kit"} <= set(d.index)
    assert "squishy" not in d.index


def test_sectors_and_winners():
    sector_of = {"squishy": "juguetes", "slime": "juguetes", "padel racket": "deporte",
                 "wall pilates": "fitness", "weighted vest": "fitness", "yoga mat": "control"}
    products = pd.concat([PRODUCTS, pd.DataFrame([prod("slime", "Todo el año", 4)])])
    s = a.sector_table(products, sector_of).set_index("sector")
    assert s.loc["juguetes", "ganador"] == "squishy" and s.loc["juguetes", "productos"] == 2
    assert "control" not in s.index
    al = pd.DataFrame(a.sector_alerts(s.reset_index())).set_index("elemento")
    assert al.loc["juguetes", "prioridad"] == "Media" and "squishy" in al.loc["juguetes", "accion"]
    assert al.loc["fitness", "motivo"].startswith("Cae")


def test_build_sorts_by_priority():
    sectors = a.sector_table(PRODUCTS, {})
    out = a.build(PRODUCTS, WINDOWS, MOMENTS, sectors, today=TODAY)
    assert out["prioridad"].tolist() == sorted(out["prioridad"], key=a.PRIORITY_ORDER.get)
    assert "yoga mat" not in set(out["elemento"])


def test_growing_product_with_past_peak_is_not_discarded():
    p = pd.DataFrame([prod("padel racket", "Viral", 59, "Emergente", ep="2025-07-01", lvl=0.19)])
    assert a.discard_alerts(p, pd.DataFrame(), TODAY) == []
    m = a.momentum_alerts(p, today=TODAY)
    assert len(m) == 1 and "confirmar que no sea moda" in m[0]["motivo"]
