"""Overall candidate score (0-100) = trend + margin + competition.

The weights are a starting heuristic, NOT validated against real sales outcomes.
Missing inputs fall back to a neutral 50 and are reported in `faltantes`.
"""
import math

WEIGHTS = {"tendencia": 0.4, "margen": 0.3, "competencia": 0.3}


def competition_score(avg_reviews_top10: float | None) -> float | None:
    """100 at <=100 reviews, 50 at 1,000, 0 at >=10,000 (log scale)."""
    if avg_reviews_top10 is None or math.isnan(avg_reviews_top10):
        return None
    r = max(avg_reviews_top10, 1)
    return max(0.0, min(100.0, 100 - 50 * math.log10(r / 100)))


def margin_score(margin_pct: float) -> float:
    """0 at <=0% net margin, 100 at >=40%."""
    return max(0.0, min(100.0, margin_pct / 40 * 100))


def overall(trend_score: float | None, margin_pct: float, avg_reviews_top10: float | None) -> dict:
    parts = {
        "tendencia": trend_score,
        "margen": margin_score(margin_pct),
        "competencia": competition_score(avg_reviews_top10),
    }
    missing = [k for k, v in parts.items() if v is None]
    total = sum(WEIGHTS[k] * (50.0 if v is None else v) for k, v in parts.items())
    return {"score": round(total, 1), "faltantes": missing}
