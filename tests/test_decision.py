import pandas as pd

from fba_trends import decision as dc
from fba_trends.config import load_config

CFG = load_config()


def comp(units_new, reviews=100):
    return pd.DataFrame({"vendidos_mes": units_new, "resenas": [reviews] * len(units_new)})


def row(tipo, price, tendencia="✓", peso="✓", peso_kg=0.3):
    return pd.Series({"tipo": tipo, "precio_ref": price, "tendencia": tendencia, "peso": peso, "peso_kg": peso_kg,
                      "competencia_detalle": "Accesible"})


def test_helpers():
    assert dc.size_tier(0.25) == "large_standard_1lb"
    assert dc.size_tier(None) == "large_standard_2lb"
    assert dc.size_tier(2.0) == "large_bulky"
    assert dc.suggested_price(28.99) == 27.99
    assert dc.newcomer_units(pd.DataFrame({"vendidos_mes": [1000, 300, 200], "resenas": [9000, 100, 50]})) == 250


def test_economics_flags_estimates_and_lowers_confidence():
    e = dc.economics(row("glove", 28.99, tendencia="?"), comp([300, 300]), CFG)
    assert e["costo_estimado"] and "tendencia" in e["falta_verificar"]
    assert e["confianza"] < 0.7
    real = dc.economics(row("glove", 28.99), comp([300, 300]), CFG, real_cost=5.0)
    assert not real["costo_estimado"] and real["confianza"] == 1.0
    assert real["ventas_mes_proy"] == 150  # 300 x 0.5 captura


def test_recommend_single_vs_split_vs_none():
    strong = dc.economics(row("A", 35.99), comp([600, 600]), CFG, real_cost=6.0)
    weak = dc.economics(row("B", 24.99), comp([60, 60]), CFG, real_cost=6.0)
    one = dc.recommend(pd.DataFrame([strong, weak]), 3500, CFG, max_products=3)
    assert one["veredicto"][0] == "uno" and "A" in one["veredicto"][1]

    # Demand-limited products: one alone can't absorb the budget (max 2 months of stock), so splitting wins
    small_a = dc.economics(row("E", 35.99), comp([200, 200]), CFG, real_cost=6.0)
    small_b = dc.economics(row("F", 33.99), comp([200, 200]), CFG, real_cost=6.0)
    split = dc.recommend(pd.DataFrame([small_a, small_b]), 5000, CFG, max_products=3)
    assert split["veredicto"][0] == "varios"

    bad = dc.economics(row("D", 21.0), comp([100]), CFG)  # 25% cost at $21 leaves little margin
    bad["margen_pct"] = 5.0
    none = dc.recommend(pd.DataFrame([bad]), 3500, CFG)
    assert none["veredicto"][0] == "ninguno"


def test_seasonal_far_deadline_waits():
    mat = dc.economics(row("dog cooling mat", 26.99), comp([300]), CFG, real_cost=5.0)
    out = dc.recommend(pd.DataFrame([mat]), 3500, CFG, timing={"dog cooling mat": (135, "2026-12-29")})
    assert out["veredicto"][0] == "ninguno"
    assert out["esperar"][0][0] == "dog cooling mat"
