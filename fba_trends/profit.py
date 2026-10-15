"""Unit economics for one FBA product.

Every fee that falls back to a config default (instead of a value the user entered)
is recorded in `estimated_fields`, so the UI can show which numbers are not verified.
"""
import math
from dataclasses import dataclass


@dataclass
class Product:
    sale_price: float
    unit_cost: float               # factory price per unit
    freight_per_unit: float        # freight + duties to the Amazon warehouse, per unit
    fba_fee: float | None = None   # exact fee from Amazon's Revenue Calculator, if known
    size_tier: str = "large_standard_1lb"
    cuft_per_unit: float = 0.1
    months_in_storage: float = 2.0
    q4_storage: bool = False
    referral_pct: float | None = None
    ppc_pct: float | None = None
    return_rate: float | None = None


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def compute(p: Product, cfg: dict) -> dict:
    fees, sup = cfg["fees"], cfg["supuestos"]
    estimated = []

    def pick(value, default, name):
        if _blank(value):
            estimated.append(name)
            return default
        return value

    referral_pct = pick(p.referral_pct, fees["referral_pct"]["valor"], "referral_pct")
    ppc_pct = pick(p.ppc_pct, sup["ppc_pct_del_precio"]["valor"], "ppc_pct")
    return_rate = pick(p.return_rate, sup["tasa_devolucion"]["valor"], "tasa_devolucion")
    tier_fees = fees["fba_fee_por_tier"]["valores"]
    fba_fee = pick(p.fba_fee, tier_fees.get(p.size_tier, tier_fees["large_standard_1lb"]), "fba_fee")
    estimated.append("storage")  # storage rates always come from config

    rate = fees["storage_por_cuft_mes"]["oct_dic" if p.q4_storage else "ene_sep"]
    storage = p.cuft_per_unit * rate * p.months_in_storage
    landed = p.unit_cost + p.freight_per_unit
    returns_cost = return_rate * landed  # conservative: a returned unit is written off

    referral = p.sale_price * referral_pct
    ppc = p.sale_price * ppc_pct
    net = p.sale_price - referral - ppc - fba_fee - storage - landed - returns_cost

    fixed = landed + fba_fee + storage + returns_cost
    variable_share = 1 - referral_pct - ppc_pct
    breakeven = fixed / variable_share if variable_share > 0 else float("inf")

    margin = net / p.sale_price if p.sale_price else 0.0
    roi = net / landed if landed else 0.0
    ok = margin >= sup["margen_neto_minimo"]["valor"] and roi >= sup["roi_minimo"]["valor"]
    verdict = "OK" if ok else ("Débil" if net > 0 else "Pierde dinero")

    return {
        "costo_puesto": round(landed, 2),
        "comision_referral": round(referral, 2),
        "fba_fee": round(fba_fee, 2),
        "ppc": round(ppc, 2),
        "almacenaje": round(storage, 2),
        "devoluciones": round(returns_cost, 2),
        "ganancia_neta": round(net, 2),
        "margen_pct": round(margin * 100, 1),
        "roi_pct": round(roi * 100, 1),
        "precio_equilibrio": round(breakeven, 2),
        "veredicto": verdict,
        "campos_estimados": estimated,
    }


def max_landed_cost(p: Product, cfg: dict, target_margin: float | None = None) -> float:
    """Highest factory + freight cost per unit that still reaches the target net margin.
    Uses the same fees as `compute` (p.unit_cost and p.freight_per_unit are ignored)."""
    sup = cfg["supuestos"]
    target = sup["margen_neto_minimo"]["valor"] if target_margin is None else target_margin
    base = compute(Product(**{**p.__dict__, "unit_cost": 0.0, "freight_per_unit": 0.0}), cfg)
    # net = revenue_after_fees - landed * (1 + return_rate); solve net = target * price
    rr = sup["tasa_devolucion"]["valor"] if _blank(p.return_rate) else p.return_rate
    after_fees = p.sale_price - base["comision_referral"] - base["ppc"] - base["fba_fee"] - base["almacenaje"]
    return round(max(0.0, (after_fees - target * p.sale_price) / (1 + rr)), 2)
