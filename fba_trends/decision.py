"""The 'brain': turns the shortlist + budget into one plain recommendation.

For every candidate it estimates (all marked as estimates until real quotes exist):
- suggested price: median price of the Amazon top 10, rounded to .99;
- landed cost: real quote if entered in candidates.csv, else `costo_pct_precio` x price;
- units/month: what NEW listings (<500 reviews) in that top 10 sell today x `captura_nuevo_vendedor`
  x scenario (that is direct evidence of what a newcomer can reach);
- profit per unit with the same fee model as the Productos tab;
- confidence 0-1: lowered for every piece still unverified (trend, weight, cost, competition 'Media').

It works in 4 layers (see docs/guia_ventas_y_rotacion.md):
1. Knock-outs: loses money per unit; the supplier's MOQ is more than `cobertura_max_dias` of sales
   (slow turn, FBA excess / IPI); a real quote above the target cost; GMROI under the minimum.
2. Ranking (config `decision.prioridad`): "gmroi" (default) = annual margin per dollar in inventory,
   which is margin x turnover; "rotacion" = units/month; "ganancia" = margin filter + monthly profit.
   A candidate under the minimum margin with an estimated cost stays in with the landed cost it
   needs ("costo_objetivo").
3. Tie-breaks and risk: confidence drops for unverified data and concentrated niches; candidates
   within 20% of the leader are flagged as a technical tie; low niche ratings are an opportunity.
4. Operating plan per product: first order, safety stock and reorder point from the supplier's lead
   time (`inventario` in config), within Amazon's healthy band of ~28-90 days of cover.

Then it tries 1..N products with the normal budget rules (reserve, launch cost, MOQ, max months of
stock) and picks the option with the most risk-adjusted profit (or units, for "rotacion") over the
horizon. A product is only added if it improves that by `mejora_minima_para_diversificar`.
"""
import copy
import math

import pandas as pd

from .budget import Candidate, allocate
from .profit import Product, compute, max_landed_cost

TIERS = [(0.45, "large_standard_1lb"), (0.9, "large_standard_2lb"), (1.36, "large_standard_3lb")]


def size_tier(weight_kg: float | None) -> str:
    if weight_kg is None or math.isnan(weight_kg):
        return "large_standard_2lb"  # unknown: assume the middle tier rather than the cheapest
    for limit, tier in TIERS:
        if weight_kg <= limit:
            return tier
    return "large_bulky"


def suggested_price(median: float) -> float:
    return max(0.99, math.floor(median) - 0.01) if median >= 1 else median


def newcomer_units(rows: pd.DataFrame) -> float:
    """Median monthly units of the top-10 listings with < 500 reviews (what a new seller reaches)."""
    sold = rows.dropna(subset=["vendidos_mes"])
    new = sold[sold["resenas"].fillna(0) < 500]
    if not new.empty:
        return float(new["vendidos_mes"].median())
    return float(sold["vendidos_mes"].median()) * 0.1 if not sold.empty else 0.0


Z_BY_SERVICE = {0.9: 1.28, 0.95: 1.65, 0.97: 1.88, 0.98: 2.05, 0.99: 2.33}


def _known(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def stock_plan(units_month: float, unit_cost: float, unit_profit: float, cfg: dict,
               moq: float | None = None, lead_days: float | None = None) -> dict:
    """Order size, safety stock, reorder point, turnover and GMROI for one product.
    Order = max(MOQ, `dias_ciclo_objetivo` of sales); safety stock = Z x sigma_daily x sqrt(lead time);
    average inventory = order/2 + safety stock; GMROI = annual profit / average inventory at cost."""
    inv, t = cfg["inventario"], cfg["tiempos_entrega_dias"]
    moq_known, lead_known = _known(moq), _known(lead_days)
    moq = float(moq) if moq_known else float(cfg["decision"]["moq_por_defecto"]["valor"])
    lead = float(lead_days) if lead_known else float(t["produccion"] + t["flete_maritimo"] + t["recepcion_amazon"])
    base = {"moq": moq, "dias_entrega": lead, "proveedor_estimado": not (moq_known and lead_known)}
    daily = units_month / 30
    if daily <= 0:
        return {**base, "pedido_unidades": int(moq), "stock_seguridad": 0, "punto_reorden": 0,
                "cobertura_pedido_min_dias": None, "cobertura_inicial_dias": None, "rotacion_anual": 0.0, "gmroi": 0.0}
    z = Z_BY_SERVICE.get(inv["nivel_servicio"]["valor"], 1.65)
    safety = z * inv["cv_demanda"]["valor"] * daily * math.sqrt(lead)
    order = max(moq, daily * inv["dias_ciclo_objetivo"]["valor"])
    avg_units = order / 2 + safety
    return {
        **base, "pedido_unidades": math.ceil(order + safety), "stock_seguridad": math.ceil(safety),
        "punto_reorden": math.ceil(daily * lead + safety),
        "cobertura_pedido_min_dias": round(moq / daily), "cobertura_inicial_dias": round((order + safety) / daily),
        "rotacion_anual": round(daily * 365 / avg_units, 1),
        "gmroi": round(unit_profit * daily * 365 / (avg_units * unit_cost), 1) if unit_cost > 0 else 0.0,
    }


def niche_risk(comp_rows: pd.DataFrame) -> tuple[float, list[str], list[str]]:
    """Confidence factor, risks and opportunities read from the Amazon top 10."""
    factor, risks, opps = 1.0, [], []
    if "vendidos_mes" in comp_rows:
        sold = comp_rows["vendidos_mes"].fillna(0)
        if sold.sum() > 0:
            top3 = sold.nlargest(3).sum() / sold.sum()
            if top3 > 0.7:
                factor *= 0.9
                risks.append(f"top 3 se lleva {top3:.0%} de las ventas")
    if "resenas" in comp_rows and comp_rows["resenas"].notna().any() and comp_rows["resenas"].median() > 2000:
        risks.append(f"reseñas altas en el top 10 (mediana {comp_rows['resenas'].median():,.0f})")
    if "rating" in comp_rows and comp_rows["rating"].notna().any() and comp_rows["rating"].mean() < 4.2:
        opps.append(f"rating del nicho bajo ({comp_rows['rating'].mean():.1f}★): mejorar lo que critican las reseñas")
    return factor, risks, opps


def economics(row: pd.Series, comp_rows: pd.DataFrame, cfg: dict, scenario: float = 1.0,
              real_cost: float | None = None, moq: float | None = None, lead_days: float | None = None) -> dict:
    d = cfg["decision"]
    price = suggested_price(float(row["precio_ref"]))
    cost_estimated = real_cost is None or math.isnan(real_cost)
    landed = price * d["costo_pct_precio"]["valor"] if cost_estimated else float(real_cost)
    weight = pd.to_numeric(row.get("peso_kg"), errors="coerce")
    product = Product(sale_price=price, unit_cost=landed, freight_per_unit=0.0,
                      size_tier=size_tier(weight), cuft_per_unit=0.15)
    econ = compute(product, cfg)
    units = newcomer_units(comp_rows) * d["captura_nuevo_vendedor"]["valor"] * scenario

    conf = 1.0
    unknown = []
    if row.get("tendencia") != "✓":
        conf *= 0.8
        unknown.append("tendencia")
    if row.get("peso") != "✓":
        conf *= 0.85
        unknown.append("peso")
    if cost_estimated:
        conf *= 0.8
        unknown.append("costo (sin cotización)")
    if "Media" in str(row.get("competencia_detalle", "")):
        conf *= 0.85
    risk_factor, risks, opps = niche_risk(comp_rows)
    conf *= risk_factor
    plan = stock_plan(units, landed, econ["ganancia_neta"], cfg, moq, lead_days)
    if plan["proveedor_estimado"]:
        unknown.append("pedido mínimo/entrega")
    return {
        "tipo": row["tipo"], "precio_sugerido": round(price, 2), "costo_puesto": round(landed, 2),
        "costo_estimado": cost_estimated, "ganancia_unidad": econ["ganancia_neta"], "margen_pct": econ["margen_pct"],
        "roi_pct": econ["roi_pct"], "costo_objetivo": max_landed_cost(product, cfg),
        "ventas_mes_proy": round(units), "ganancia_mes_proy": round(units * econ["ganancia_neta"], 0),
        "confianza": round(conf, 2), "falta_verificar": ", ".join(unknown),
        "riesgos": "; ".join(risks), "oportunidades": "; ".join(opps), **plan,
    }


def recommend(products: pd.DataFrame, budget: float, cfg: dict, max_products: int = 3,
              timing: dict | None = None, prioridad: str | None = None) -> dict:
    """products: output of economics() for each candidate. timing: tipo -> (dias_para_pedir, fecha).
    prioridad: "gmroi", "rotacion" (units sold) or "ganancia" (margin filter + profit); default from config."""
    d, c, inv = cfg["decision"], cfg["supuestos"], cfg["inventario"]
    mode = prioridad or d.get("prioridad", {}).get("valor", "gmroi")
    by_units = mode == "rotacion"
    min_margin = c["margen_neto_minimo"]["valor"] * 100
    horizon = d["horizonte_meses"]["valor"]
    moq = d["moq_por_defecto"]["valor"]
    timing = timing or {}
    out = {"preliminar": bool(products["costo_estimado"].any()) if not products.empty else True,
           "opciones": pd.DataFrame(), "asignacion": pd.DataFrame(), "ranking": pd.DataFrame(), "esperar": [],
           "descartados": []}

    viable = []
    for _, p in products.iterrows():
        t = timing.get(p["tipo"])
        if t and t[0] > 120:
            out["esperar"].append((p["tipo"], f"Estacional: no hace falta pedir todavía; buscar proveedor desde {t[1]}"))
        elif p["ganancia_unidad"] <= 0:
            out["descartados"].append((p["tipo"], "Pierde dinero por unidad con el costo actual"))
        elif _known(p.get("cobertura_pedido_min_dias")) and \
                p["cobertura_pedido_min_dias"] > inv["cobertura_max_dias"]["valor"]:
            out["descartados"].append((p["tipo"], f"El pedido mínimo ({p['moq']:.0f} u.) son {p['cobertura_pedido_min_dias']:.0f} "
                                                  "días de venta: rotaría lento y contaría como exceso en FBA"))
        elif not p["costo_estimado"] and p["margen_pct"] < min_margin:
            out["descartados"].append((p["tipo"], f"La cotización (${p['costo_puesto']:.2f}) supera el costo objetivo "
                                                  f"(${p['costo_objetivo']:.2f})"))
        elif mode == "gmroi" and p.get("gmroi", 0) < inv["gmroi_minimo"]["valor"]:
            out["descartados"].append((p["tipo"], f"GMROI {p['gmroi']:.1f} bajo el mínimo"))
        elif mode == "ganancia" and p["margen_pct"] < min_margin:
            out["descartados"].append((p["tipo"], f"Margen {p['margen_pct']:.0f}% bajo el mínimo"))
        elif p["ventas_mes_proy"] < 1:
            out["descartados"].append((p["tipo"], "Sin evidencia de ventas para un vendedor nuevo"))
        else:
            viable.append(p)
    if not viable:
        out["veredicto"] = ("ninguno", "No compren nada este mes",
                            "Ningún candidato cumple margen, demanda y momento a la vez con los datos actuales.")
        return out

    v = pd.DataFrame(viable)
    v["condicion"] = [f"Conseguir costo ≤ ${r.costo_objetivo:.2f}" if r.margen_pct < min_margin else ""
                      for r in v.itertuples()]
    metric = {"rotacion": "ventas_mes_proy", "ganancia": "ganancia_mes_proy", "gmroi": "gmroi"}[mode]
    v["valor_ajustado"] = v[metric] * v["confianza"]
    v = v.sort_values(["valor_ajustado", "ganancia_mes_proy"], ascending=False).reset_index(drop=True)
    top_value = max(v["valor_ajustado"].max(), 1e-9)
    v["empate_con_el_1"] = v["valor_ajustado"] >= top_value * 0.8
    out["ranking"] = v
    v["score"] = (v["valor_ajustado"] / top_value * 100).round(1)

    options, plans = [], {}
    for k in range(1, min(max_products, len(v)) + 1):
        cfg_k = copy.deepcopy(cfg)
        cfg_k["presupuesto"]["max_productos"]["valor"] = k
        cfg_k["presupuesto"]["score_minimo"]["valor"] = 0
        cands = [Candidate(r["tipo"], r["score"], r["costo_puesto"], r["ganancia_unidad"], int(r.get("moq", moq)),
                           r["ventas_mes_proy"])
                 for _, r in v.head(k).iterrows()]
        plan = allocate(cands, budget, cfg_k)
        rows = []
        for a in plan["asignacion"]:
            r = v.set_index("tipo").loc[a["producto"]]
            sold = min(a["unidades"], r["ventas_mes_proy"] * horizon)
            rows.append({**a, "precio_sugerido": r["precio_sugerido"], "ventas_mes_proy": r["ventas_mes_proy"],
                         "ganancia_mes_proy": r["ganancia_mes_proy"], "confianza": r["confianza"],
                         "unidades_horizonte": round(sold), "condicion": r["condicion"],
                         "ganancia_horizonte": round(sold * r["ganancia_unidad"], 0),
                         "ganancia_ajustada": round(sold * r["ganancia_unidad"] * r["confianza"], 0),
                         "recupera_inversion_meses": round((a["inversion_inventario"] + a["costo_lanzamiento"])
                                                           / max(r["ganancia_mes_proy"], 1e-9), 1)})
        plans[k] = (plan, rows)
        options.append({"opcion": k, "productos": ", ".join(x["producto"] for x in rows) or "-",
                        "invertido": plan["gastado"], "reserva": plan["reserva"],
                        "unidades_horizonte": sum(x["unidades_horizonte"] for x in rows),
                        "unidades_ajustadas": round(sum(x["unidades_horizonte"] * x["confianza"] for x in rows)),
                        "ganancia_horizonte": sum(x["ganancia_horizonte"] for x in rows),
                        "ganancia_ajustada": sum(x["ganancia_ajustada"] for x in rows)})
    opts = pd.DataFrame(options)
    out["opciones"] = opts

    # Pick: most units (or risk-adjusted profit); a bigger option must beat the smaller by the minimum improvement.
    goal = "unidades_ajustadas" if by_units else "ganancia_ajustada"
    best = 1
    for k in range(2, len(opts) + 1):
        prev, cur = opts.loc[best - 1, goal], opts.loc[k - 1, goal]
        if cur > prev * (1 + d["mejora_minima_para_diversificar"]["valor"]):
            best = k
    plan, rows = plans[best]
    out["asignacion"] = pd.DataFrame(rows)
    out["descartados"] += plan["rechazados"] and [(r["producto"], r["motivo"]) for r in plan["rechazados"]] or []
    if not rows:
        out["veredicto"] = ("ninguno", "No compren nada este mes",
                            "El presupuesto no alcanza el pedido mínimo (MOQ) de los candidatos con el lanzamiento y la reserva.")
    elif len(rows) == 1:
        r = rows[0]
        out["veredicto"] = ("uno", f"Vayan solo con {r['producto']}",
                            f"Inviertan ~${r['inversion_inventario'] + r['costo_lanzamiento']:,.0f} "
                            f"({r['unidades']} unidades) y guarden ${plan['reserva']:,.0f} de reserva. "
                            + ("Sumar otro producto no mejora lo suficiente las ventas esperadas."
                               if by_units else "Sumar un segundo producto no mejora lo suficiente la ganancia esperada.")
                            + (f" Condición: {r['condicion'].lower()} con el proveedor." if r["condicion"] else ""))
    else:
        lead = max(rows, key=lambda x: x["inversion_inventario"])
        out["veredicto"] = ("varios", f"Dividan entre {len(rows)} productos: " + ", ".join(x["producto"] for x in rows),
                            f"El mayor presupuesto va a {lead['producto']} (${lead['inversion_inventario']:,.0f} en inventario). "
                            f"Reserva: ${plan['reserva']:,.0f}.")
    return out
