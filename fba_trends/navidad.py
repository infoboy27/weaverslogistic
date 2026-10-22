"""Christmas: which gift products pass the criteria, and whether they can still reach this December.

Two routes:
- This year by air: ready-to-ship stock + air freight + slower Q4 check-in (config `navidad.aereo`).
  Only possible with an active seller account; the air cost per kg is added to the landed cost.
- Next year by sea: the normal lead time (config `tiempos_entrega_dias`); order deadline = sell-from - lead.
"""
from datetime import date, timedelta

import pandas as pd

from .profit import Product, max_landed_cost
from .trends import lead_days


def candidate_keywords(summary: pd.DataFrame, cfg: dict) -> list[str]:
    """Christmas searches ('christmas ...') plus the gift products listed in config."""
    gift = cfg["navidad"]["keywords_regalo"]["lista"]
    kws = summary["keyword"].tolist()
    return [k for k in kws if "christmas" in k] + [k for k in gift if k in kws]


def _md(year: int, md: list[int]) -> date:
    return date(year, md[0], md[1])


def routes(cfg: dict, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    n = cfg["navidad"]
    air = n["aereo"]
    year = today.year if today < _md(today.year, n["ultimo_dia_util_mes_dia"]) else today.year + 1
    sell_from = _md(year, n["vender_desde_mes_dia"])
    last_day = _md(year, n["ultimo_dia_util_mes_dia"])
    air_days = air["compra_y_preparacion"] + air["flete_aereo"] + air["recepcion_amazon_q4"]
    air_ready = today + timedelta(days=air_days)
    if air_ready <= sell_from:
        air_state = "Posible si pides esta semana"
    elif air_ready < last_day:
        air_state = f"Muy justo: llegarías el {air_ready:%d/%m}, a mitad del pico"
    else:
        air_state = "Ya no llega"
    next_sell = _md(year + 1, n["vender_desde_mes_dia"])
    deadline = next_sell - timedelta(days=lead_days(cfg))
    return pd.DataFrame([
        {"ruta": f"Navidad {year} por aire", "dias_totales": air_days, "pedir_antes_de": sell_from - timedelta(days=air_days),
         "disponible_en_amazon": air_ready, "estado": air_state,
         "requisito": "Cuenta de vendedor activa hoy + proveedor con stock listo; flete aéreo caro"},
        {"ruta": f"Navidad {year + 1} por mar", "dias_totales": lead_days(cfg), "pedir_antes_de": deadline,
         "disponible_en_amazon": next_sell - timedelta(days=cfg["tiempos_entrega_dias"]["margen_rampa"]),
         "estado": f"A tiempo: buscar proveedor desde {deadline - timedelta(days=60):%d/%m/%Y}",
         "requisito": "Ruta normal; da tiempo a muestras, marca y fotos"},
    ])


def evaluate(summary: pd.DataFrame, cfg: dict, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """One row per Christmas candidate with criteria checks and the max landed cost for both routes.
    `weights` = known weight in kg per keyword (else 0.5 kg assumed for the air cost, flagged)."""
    c = cfg["criterios"]
    air_kg = cfg["navidad"]["aereo"]["costo_usd_kg"]["valor"]
    weights = weights or {}
    rows = []
    for kw in candidate_keywords(summary, cfg):
        r = summary[summary["keyword"] == kw].iloc[0]
        price = r["precio_mediana"]
        fails = []
        if not c["precio_min"] <= price <= c["precio_max"]:
            fails.append(f"precio ${price:.0f}")
        if r["vendidos_mes_top10"] < c["min_vendidos_mes_top10"]:
            fails.append(f"demanda {r['vendidos_mes_top10']:.0f}/mes")
        if r["listados_bajo_500_resenas"] < c["min_listados_bajo_500_resenas"]:
            fails.append("pocos nuevos en el top 10")
        if r["veredicto"] == "Difícil":
            fails.append("competencia difícil")
        cap = max_landed_cost(Product(sale_price=float(price), unit_cost=0.0, freight_per_unit=0.0,
                                      size_tier="large_standard_1lb", cuft_per_unit=0.15), cfg)
        kg = weights.get(kw)
        air_cost = (kg if kg else 0.5) * air_kg
        rows.append({
            "keyword": kw, "tipo": "Navideño" if "christmas" in kw else "Regalo (pico en diciembre)",
            "precio_mediana": price, "vendidos_mes_top10": r["vendidos_mes_top10"],
            "listados_bajo_500_resenas": r["listados_bajo_500_resenas"], "veredicto": r["veredicto"],
            "costo_max_mar": cap, "costo_max_aire": round(max(0.0, cap - air_cost), 2),
            "pasa": not fails, "motivo": ", ".join(fails) if fails else "Pasa los criterios",
            "peso_supuesto": not kg,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["pasa", "vendidos_mes_top10"], ascending=[False, False]).reset_index(drop=True)
