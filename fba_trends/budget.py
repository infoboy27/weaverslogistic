"""Split a small starting budget across the best-scoring candidates.

Rules (see `presupuesto` in config.yaml):
- A reserve (PPC launch, surprises, reorder) is held back from inventory.
- Each selected product pays a fixed launch cost (samples, photos, labels).
- Only profitable candidates above the minimum score, at most `max_productos`.
- Inventory money is split by score, capped per product when there is more than one, and never buys more than
  `meses_de_prueba` months of estimated sales.
- A product whose MOQ does not fit its share is dropped and the next one is tried.
- Whatever is not spent goes back to the reserve.
"""
from dataclasses import dataclass


@dataclass
class Candidate:
    name: str
    score: float
    landed_cost: float
    net_profit: float
    moq: int
    est_monthly_units: float


def allocate(candidates: list[Candidate], total_budget: float, cfg: dict) -> dict:
    b = cfg["presupuesto"]
    reserve = total_budget * b["reserva_pct"]["valor"]
    launch_cost = b["costo_lanzamiento_por_producto"]["valor"]
    max_products = b["max_productos"]["valor"]
    cap_pct = b["max_pct_por_producto"]["valor"]
    test_months = b["meses_de_prueba"]["valor"]

    rejected = []
    pool = []
    for c in sorted(candidates, key=lambda c: c.score, reverse=True):
        if c.net_profit <= 0:
            rejected.append((c.name, "No es rentable con los supuestos actuales"))
        elif c.score < b["score_minimo"]["valor"]:
            rejected.append((c.name, f"Score {c.score:.0f} bajo el mínimo"))
        else:
            pool.append(c)

    selected = pool[:max_products]
    waiting = pool[max_products:]
    rows = []
    while selected:
        inventory_budget = total_budget - reserve - launch_cost * len(selected)
        if inventory_budget <= 0:
            dropped = selected.pop()
            rejected.append((dropped.name, "No alcanza el presupuesto para el costo de lanzamiento"))
            continue
        total_score = sum(c.score for c in selected)
        cap = cap_pct if len(selected) > 1 else 1.0  # the cap only exists to diversify
        rows, misfit = [], None
        for c in selected:
            share = min(inventory_budget * c.score / total_score, inventory_budget * cap)
            units = min(int(share // c.landed_cost), int(c.est_monthly_units * test_months))
            if units < c.moq:
                if c.moq * c.landed_cost <= share:
                    units = c.moq  # MOQ above the test-months cap but affordable
                else:
                    misfit = c
                    break
            rows.append({
                "producto": c.name,
                "score": round(c.score, 1),
                "unidades": units,
                "inversion_inventario": round(units * c.landed_cost, 2),
                "costo_lanzamiento": launch_cost,
                "ganancia_esperada_si_vende_todo": round(units * c.net_profit, 2),
                "meses_de_stock_est": round(units / c.est_monthly_units, 1) if c.est_monthly_units else None,
            })
        if misfit is None:
            break
        rows = []
        moq_cost = misfit.moq * misfit.landed_cost
        best_alone = total_budget - reserve - launch_cost
        if moq_cost <= best_alone and len(selected) > 1:
            # It would fit with fewer products: keep the higher score, drop the lowest (it may be the misfit
            # itself; excluding it here used to drop the best product instead).
            lowest = min(selected, key=lambda c: c.score)
            selected.remove(lowest)
            rejected.append((lowest.name, "El presupuesto no alcanza para tantos productos; se prioriza mayor score"))
        else:
            selected.remove(misfit)
            rejected.append((misfit.name, f"MOQ {misfit.moq} u. (${moq_cost:,.0f}) no cabe en el presupuesto"))
            if waiting:
                selected.append(waiting.pop(0))

    spent = sum(r["inversion_inventario"] + r["costo_lanzamiento"] for r in rows)
    return {
        "asignacion": rows,
        "rechazados": [{"producto": n, "motivo": m} for n, m in rejected],
        "reserva": round(total_budget - spent, 2),
        "gastado": round(spent, 2),
        "total": total_budget,
    }
