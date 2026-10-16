"""Decision-support metrics with explicit evidence labels.

Not a sales forecast or a competitor-sales extractor.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Economics:
    price: float
    landed_unit_cost: float
    referral_fee: float
    fulfillment_fee: float
    advertising_cost: float
    returns_reserve: float
    monthly_storage: float

    def evaluate(self):
        if any(v < 0 for v in vars(self).values()) or self.price <= 0:
            raise ValueError("Precio positivo y costos no negativos requeridos")
        total = (self.landed_unit_cost + self.referral_fee + self.fulfillment_fee
                 + self.advertising_cost + self.returns_reserve + self.monthly_storage)
        profit = self.price - total
        return {"unit_profit":round(profit, 2),
                "net_margin_pct":round(100 * profit / self.price, 2),
                "roi_pct":round(100 * profit / self.landed_unit_cost, 2)
                if self.landed_unit_cost else None,
                "break_even_price":round(total, 2),
                "evidence_status":"scenario_only",
                "disclaimer":"Escenario hipotético. No equivale a ventas verificadas."}
