from datetime import date

import numpy as np
import pandas as pd
import pytest

from fba_trends.budget import Candidate, allocate
from fba_trends.collect import parse_trends_csv
from fba_trends.config import load_config
from fba_trends.profit import Product, compute
from fba_trends.scoring import overall
from fba_trends.trends import analyze, order_deadline

CFG = load_config()


def weekly(values):
    return pd.Series(values, index=pd.date_range("2021-10-03", periods=len(values), freq="W"))


# ---------------------------------------------------------------- profit
def test_profit_breakdown_adds_up_and_flags_defaults():
    r = compute(Product(sale_price=40, unit_cost=8, freight_per_unit=2, fba_fee=5.0), CFG)
    costs = (r["costo_puesto"] + r["comision_referral"] + r["fba_fee"] + r["ppc"]
             + r["almacenaje"] + r["devoluciones"])
    assert r["ganancia_neta"] == pytest.approx(40 - costs, abs=0.02)
    assert "fba_fee" not in r["campos_estimados"]  # user gave it
    assert "referral_pct" in r["campos_estimados"]


def test_breakeven_price_gives_zero_profit():
    p = Product(sale_price=30, unit_cost=6, freight_per_unit=1.5)
    be = compute(p, CFG)["precio_equilibrio"]
    p.sale_price = be
    assert compute(p, CFG)["ganancia_neta"] == pytest.approx(0, abs=0.02)


def test_losing_product_verdict():
    assert compute(Product(sale_price=10, unit_cost=8, freight_per_unit=2), CFG)["veredicto"] == "Pierde dinero"


# ---------------------------------------------------------------- budget
def test_budget_respects_reserve_caps_and_test_months():
    cands = [
        Candidate("A", 80, landed_cost=10, net_profit=8, moq=100, est_monthly_units=200),
        Candidate("B", 60, landed_cost=5, net_profit=4, moq=100, est_monthly_units=100),
        Candidate("C", 90, landed_cost=10, net_profit=-1, moq=50, est_monthly_units=100),
    ]
    plan = allocate(cands, 5000, CFG)
    names = [r["producto"] for r in plan["asignacion"]]
    assert names == ["A", "B"]
    assert plan["gastado"] + plan["reserva"] == pytest.approx(5000)
    assert plan["reserva"] >= 5000 * CFG["presupuesto"]["reserva_pct"]["valor"]
    b_row = plan["asignacion"][1]
    assert b_row["unidades"] <= 100 * CFG["presupuesto"]["meses_de_prueba"]["valor"]
    assert any(r["producto"] == "C" for r in plan["rechazados"])


def test_budget_prefers_fewer_products_over_dropping_the_best():
    # With $3,000 both don't fit A's MOQ share, but A alone does: keep A, drop B.
    cands = [
        Candidate("A", 80, landed_cost=10, net_profit=8, moq=100, est_monthly_units=200),
        Candidate("B", 60, landed_cost=5, net_profit=4, moq=100, est_monthly_units=100),
    ]
    plan = allocate(cands, 3000, CFG)
    assert [r["producto"] for r in plan["asignacion"]] == ["A"]


def test_budget_drops_moq_misfit_and_tries_next():
    cands = [
        Candidate("Caro", 90, landed_cost=50, net_profit=20, moq=500, est_monthly_units=300),
        Candidate("X", 70, landed_cost=5, net_profit=4, moq=100, est_monthly_units=200),
        Candidate("Y", 60, landed_cost=5, net_profit=4, moq=100, est_monthly_units=200),
    ]
    plan = allocate(cands, 3000, CFG)
    assert [r["producto"] for r in plan["asignacion"]] == ["X", "Y"]
    assert "MOQ" in plan["rechazados"][0]["motivo"]


# ---------------------------------------------------------------- trends
def test_seasonal_series_detected_with_peak_month():
    idx = pd.date_range("2021-10-03", periods=260, freq="W")
    values = 30 + 60 * np.exp(-((idx.dayofyear - 340) % 365 - 0) ** 2 / 400.0) + \
        60 * np.exp(-((idx.dayofyear - 340 + 365) % 365) ** 2 / 400.0)
    r = analyze(pd.Series(values, index=idx), CFG, today=date(2026, 10, 14))
    assert r["clasificacion"].startswith("Estacional")
    assert r["mes_pico"] == "dic"


def test_emerging_series():
    values = [20] * 200 + list(np.linspace(20, 60, 60))
    r = analyze(weekly(values), CFG)
    assert r["clasificacion"] == "Emergente"
    assert r["trend_score"] > 70


def test_fad_series_penalized():
    values = [20] * 240 + [25, 40, 80, 100, 90, 60, 40, 30, 25, 22, 20, 20]
    r = analyze(weekly(values), CFG)
    assert r["clasificacion"].startswith("Moda pasajera")
    assert r["trend_score"] < 50


def test_order_deadline_rolls_to_next_year_when_late():
    # Dec peak, today mid-October: too late for this December
    d = order_deadline(12, CFG, today=date(2026, 10, 14))
    assert d.year == 2027 and d < date(2027, 12, 1)


def test_parse_google_trends_export():
    text = "Category: All categories\n\nWeek,heated vest: (United States)\n2025-01-05,40\n2025-01-12,<1\n"
    out = parse_trends_csv(text)
    assert list(out) == ["heated vest"]
    assert out["heated vest"].tolist() == [40.0, 0.5]


# ---------------------------------------------------------------- scoring
def test_overall_score_neutral_when_missing():
    r = overall(None, 20.0, None)
    assert r["faltantes"] == ["tendencia", "competencia"]
    assert 0 <= r["score"] <= 100


def test_zero_series_flagged_as_no_volume():
    assert analyze(weekly([0] * 260), CFG)["clasificacion"] == "Volumen insuficiente"


def test_strong_yearly_growth_with_recent_dip_is_emerging():
    values = [10] * 156 + list(np.linspace(10, 40, 96)) + [36, 34, 33, 32, 31, 30, 30, 29]
    assert analyze(weekly(values), CFG)["clasificacion"] == "Emergente"


def test_market_glitch_weeks_are_excluded_from_growth():
    flat = [20.0] * 260
    glitchy = flat.copy()
    for i in range(220, 233):  # 13-week market-wide spike inside the last year
        glitchy[i] = 100.0
    s = weekly(glitchy)
    exclude = s.index[220:233]
    assert analyze(s, CFG)["crec_anual_pct"] > 30  # glitch inflates growth
    assert abs(analyze(s, CFG, exclude=exclude)["crec_anual_pct"]) < 1


def test_max_landed_cost_hits_target_margin():
    from fba_trends.profit import max_landed_cost
    p = Product(sale_price=26.99, unit_cost=0, freight_per_unit=0, size_tier="large_standard_2lb", cuft_per_unit=0.25)
    cap = max_landed_cost(p, CFG)
    r = compute(Product(sale_price=26.99, unit_cost=cap, freight_per_unit=0,
                        size_tier="large_standard_2lb", cuft_per_unit=0.25), CFG)
    assert r["margen_pct"] == pytest.approx(25.0, abs=0.2)


def test_widen_pads_blocks_not_single_weeks():
    from fba_trends.trends import widen
    block = pd.date_range("2026-03-22", "2026-06-21", freq="7D")
    lone = pd.DatetimeIndex(["2024-08-04"])
    out = widen(block.append(lone))
    assert pd.Timestamp("2026-02-01") in out and pd.Timestamp("2026-07-12") in out  # 7 before, 3 after
    assert pd.Timestamp("2024-08-04") in out and pd.Timestamp("2024-07-28") not in out
