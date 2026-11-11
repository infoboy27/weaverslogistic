"""Monthly unit sales estimated from the category BSR: units = a * BSR^(-b).

The curve starts from per-category priors in config.yaml (`ventas_bsr`, marked estimado) and is
calibrated with our own evidence: ASINs that show Amazon's "X+ bought in past month" (captured in
Competencia) and that the catalog collector saw with a BSR. That badge is a lower bound
(50+, 100+, 1K+...), so it is scaled by `factor_sobre_minimo` before fitting.

Per category:
- >= min_puntos_calibracion points: full log-log fit (slope clamped to a plausible range).
- 3..min-1 points: keep the prior slope, rescale the prior to the median observed ratio.
- fewer: the prior as is.
Every estimate carries its source, so the UI can say how much to trust it.
"""
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

B_RANGE = (0.5, 1.3)


@dataclass
class Curve:
    a: float
    b: float
    fuente: str  # "calibrado (n=..)", "ajustado (n=..)" or "supuesto"
    n: int = 0

    def units(self, bsr) -> float | None:
        try:
            bsr = float(bsr)
        except (TypeError, ValueError):
            return None
        if math.isnan(bsr) or bsr <= 0:
            return None
        return self.a * bsr ** (-self.b)


def prior(cfg: dict, categoria) -> Curve:
    v = cfg["ventas_bsr"]
    p = (v.get("categorias") or {}).get(categoria) or v["por_defecto"]
    return Curve(float(p["a"]), float(p["b"]), "supuesto")


def calibration_pairs(snapshots: pd.DataFrame, competition: pd.DataFrame, factor: float) -> pd.DataFrame:
    """(asin, categoria, bsr, unidades) from the latest BSR seen for each ASIN with a sales badge."""
    if snapshots.empty or competition.empty:
        return pd.DataFrame(columns=["asin", "categoria", "bsr", "unidades"])
    sold = (competition.dropna(subset=["vendidos_mes"]).query("vendidos_mes > 0")
            .sort_values("fecha").groupby("asin")["vendidos_mes"].last())
    snap = (snapshots.dropna(subset=["bsr_categoria", "categoria"]).sort_values("fecha")
            .groupby("asin")[["categoria", "bsr_categoria"]].last())
    pairs = snap.join(sold, how="inner").reset_index()
    pairs = pairs.rename(columns={"bsr_categoria": "bsr", "vendidos_mes": "unidades"})
    pairs["unidades"] = pairs["unidades"] * factor
    return pairs[pairs["bsr"] > 0][["asin", "categoria", "bsr", "unidades"]]


def fit(pairs: pd.DataFrame, base: Curve, min_points: int) -> Curve:
    n = len(pairs)
    if n >= min_points:
        x, y = np.log(pairs["bsr"].astype(float)), np.log(pairs["unidades"].astype(float))
        slope, intercept = np.polyfit(x, y, 1)
        b = min(max(-slope, B_RANGE[0]), B_RANGE[1])
        a = math.exp(float(np.median(y + b * x)))  # re-center after clamping the slope
        return Curve(a, b, f"calibrado (n={n})", n)
    if n >= 3:
        ratio = float(np.median(pairs["unidades"] / pairs["bsr"].map(base.units)))
        return Curve(base.a * ratio, base.b, f"ajustado (n={n})", n)
    return base


class Estimator:
    def __init__(self, cfg: dict, snapshots: pd.DataFrame, competition: pd.DataFrame):
        v = cfg["ventas_bsr"]
        self.cfg = cfg
        self.min_points = int(v.get("min_puntos_calibracion", 8))
        self.pairs = calibration_pairs(snapshots, competition, float(v.get("factor_sobre_minimo", 1.0)))
        self._curves: dict = {}

    def curve(self, categoria) -> Curve:
        if categoria not in self._curves:
            pairs = self.pairs[self.pairs["categoria"] == categoria]
            self._curves[categoria] = fit(pairs, prior(self.cfg, categoria), self.min_points)
        return self._curves[categoria]

    def units(self, bsr, categoria) -> float | None:
        if categoria is None or (isinstance(categoria, float) and math.isnan(categoria)):
            return None
        return self.curve(categoria).units(bsr)

    def table(self, categorias) -> pd.DataFrame:
        rows = []
        for c in sorted({c for c in categorias if isinstance(c, str)}):
            cv = self.curve(c)
            rows.append({"categoria": c, "fuente": cv.fuente, "a": round(cv.a), "b": round(cv.b, 3),
                         "ventas_bsr_1000": round(cv.units(1000)), "ventas_bsr_10000": round(cv.units(10000)),
                         "ventas_bsr_100000": round(cv.units(100000), 1)})
        return pd.DataFrame(rows)
