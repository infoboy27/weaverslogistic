"""Brands and market share per niche, from the catalog snapshots + BSR sales estimate.

A "niche" here is what we captured for a keyword: the catalog search results plus the organic top 10,
so revenue is that of the top of the search, not of the whole category.

Concentration uses the HHI (sum of squared shares in %, 0-10,000) with the US DOJ/FTC thresholds:
< 1,500 fragmented, 1,500-2,500 moderately concentrated, > 2,500 concentrated.
"""
import re
from datetime import date, timedelta

import pandas as pd

from . import catalogo
from .ventas_bsr import Estimator


def norm_brand(name) -> str:
    if not isinstance(name, str) or not name.strip():
        return "(sin marca)"
    name = re.sub(r"^visit the\s+|\s+store$", "", name.strip(), flags=re.I)
    return name.strip().lower()


def concentration_label(hhi) -> str:
    if hhi is None or hhi != hhi:
        return "Sin datos"
    if hhi < 1500:
        return "Fragmentado"
    if hhi <= 2500:
        return "Moderado"
    return "Concentrado"


def with_estimates(snap: pd.DataFrame, est: Estimator, competition: pd.DataFrame | None = None) -> pd.DataFrame:
    """Adds ventas_mes_est, ingresos_mes_est and marca_norm. Missing prices fall back to Competencia's."""
    df = snap.copy()
    if competition is not None and not competition.empty:
        price = competition.dropna(subset=["precio_usd"]).sort_values("fecha").groupby("asin")["precio_usd"].last()
        df["precio"] = df["precio"].fillna(df["asin"].map(price))
    df["ventas_mes_est"] = [est.units(b, c) for b, c in zip(df["bsr_categoria"], df["categoria"])]
    df["ingresos_mes_est"] = pd.to_numeric(df["ventas_mes_est"], errors="coerce") * pd.to_numeric(df["precio"], errors="coerce")
    df["marca_norm"] = df["marca"].map(norm_brand)
    return df


def brands_in_niche(df_kw: pd.DataFrame) -> pd.DataFrame:
    """One keyword's latest snapshot (with estimates) -> brand table sorted by revenue."""
    if df_kw.empty:
        return pd.DataFrame()
    g = df_kw.groupby("marca_norm")
    out = pd.DataFrame({
        "marca": g["marca"].agg(lambda s: s.dropna().mode().iloc[0] if s.notna().any() else "(sin marca)"),
        "listados": g["asin"].nunique(),
        "ventas_mes_est": g["ventas_mes_est"].sum(min_count=1),
        "ingresos_mes_est": g["ingresos_mes_est"].sum(min_count=1),
        "mejor_bsr": g["bsr_categoria"].min(),
        "precio_mediana": g["precio"].median(),
        "amazon_vende": g["amazon_vende"].agg(lambda s: bool(s.fillna(False).astype(bool).any())),
    }).reset_index(drop=True)
    total = out["ingresos_mes_est"].sum()
    out["cuota_pct"] = (out["ingresos_mes_est"] / total * 100).round(1) if total else None
    out = out.sort_values("ingresos_mes_est", ascending=False, na_position="last").reset_index(drop=True)
    for c in ("ventas_mes_est", "ingresos_mes_est"):
        out[c] = out[c].round(0)
    return out


def niche_metrics(df_kw: pd.DataFrame) -> dict:
    brands = brands_in_niche(df_kw)
    shares = brands["cuota_pct"].dropna() if not brands.empty else pd.Series(dtype=float)
    hhi = round(float((shares ** 2).sum())) if not shares.empty else None
    cum = shares.cumsum()
    sellers = pd.to_numeric(df_kw.get("vendedores"), errors="coerce")
    fba = pd.to_numeric(df_kw.get("vendedores_fba"), errors="coerce")
    return {
        "keyword": df_kw["keyword"].iloc[0],
        "fecha": df_kw["fecha"].max(),
        "listados": df_kw["asin"].nunique(),
        "marcas": len(brands),
        "ventas_mes_est": round(float(df_kw["ventas_mes_est"].sum())) if df_kw["ventas_mes_est"].notna().any() else None,
        "ingresos_mes_est": round(float(df_kw["ingresos_mes_est"].sum())) if df_kw["ingresos_mes_est"].notna().any() else None,
        "precio_mediana": round(float(df_kw["precio"].median()), 2) if df_kw["precio"].notna().any() else None,
        "marca_lider": brands["marca"].iloc[0] if not shares.empty else None,
        "cuota_lider_pct": float(shares.iloc[0]) if not shares.empty else None,
        "cuota_top3_pct": round(float(shares.head(3).sum()), 1) if not shares.empty else None,
        "marcas_80pct": int((cum < 80).sum() + 1) if not shares.empty else None,
        "hhi": hhi,
        "concentracion": concentration_label(hhi),
        "vendedores_prom": round(float(sellers.mean()), 1) if sellers is not None and sellers.notna().any() else None,
        "pct_ofertas_fba": round(float(fba.sum() / sellers.sum() * 100), 1)
        if fba is not None and sellers is not None and sellers.sum() else None,
        "amazon_vende_listados": int(df_kw["amazon_vende"].fillna(False).astype(bool).sum()),
    }


def niche_summary(df: pd.DataFrame, history: pd.DataFrame | None = None, est: Estimator | None = None) -> pd.DataFrame:
    """Latest metrics per keyword; with history+est also the revenue change vs ~30 days earlier."""
    if df.empty:
        return pd.DataFrame()
    rows = [niche_metrics(g) for _, g in df.groupby("keyword", sort=False)]
    out = pd.DataFrame(rows)
    if history is not None and est is not None and not history.empty:
        out["cambio_ingresos_30d_pct"] = [revenue_change(history, est, r["keyword"], r["fecha"], r["ingresos_mes_est"])
                                          for r in rows]
    return out.sort_values("ingresos_mes_est", ascending=False, na_position="last").reset_index(drop=True)


def revenue_change(history, est, keyword, last_day, last_revenue, days: int = 30, tolerance: int = 10):
    """% change in estimated niche revenue vs the snapshot closest to `days` before (± tolerance)."""
    if not last_revenue:
        return None
    h = history[history["keyword"] == keyword]
    target = date.fromisoformat(last_day) - timedelta(days=days)
    dates = pd.to_datetime(h["fecha"].unique())
    if len(dates) < 2:
        return None
    closest = min(dates, key=lambda d: abs((d.date() - target).days))
    if abs((closest.date() - target).days) > tolerance:
        return None
    old = with_estimates(h[h["fecha"] == closest.date().isoformat()], est)["ingresos_mes_est"].sum()
    return round((last_revenue / old - 1) * 100, 1) if old else None


def brands_across_niches(df: pd.DataFrame) -> pd.DataFrame:
    """Brands present in several niches: where they sell and how much (estimated)."""
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("marca_norm")
    out = pd.DataFrame({
        "marca": g["marca"].agg(lambda s: s.dropna().mode().iloc[0] if s.notna().any() else "(sin marca)"),
        "nichos": g["keyword"].nunique(),
        "listados": g["asin"].nunique(),
        "ingresos_mes_est": g["ingresos_mes_est"].sum(min_count=1).round(0),
        "keywords": g["keyword"].agg(lambda s: ", ".join(sorted(set(s)))[:200]),
    }).reset_index(drop=True)
    out = out[out["marca"] != "(sin marca)"]
    return out.sort_values(["nichos", "ingresos_mes_est"], ascending=False).reset_index(drop=True)


def build(cfg: dict, competition: pd.DataFrame, months: int = 3):
    """Everything the Marcas page needs: (latest snapshots with estimates, history, estimator)."""
    history = catalogo.load(months)
    est = Estimator(cfg, history, competition)
    latest = with_estimates(catalogo.latest(history), est, competition) if not history.empty else history
    return latest, history, est
