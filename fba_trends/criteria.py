"""Funnel: Amazon universe -> product types -> criteria checks -> stage.

Product type = a short keyword grouping similar listings (e.g. "dog grooming hammock").
Each check is ✓ (pasa), ✗ (no pasa) or ? (falta dato). A type is:
- "No apto" if any check fails,
- "Apto" if every automatic check passes,
- "Falta dato" otherwise (usually: Google Trends or Amazon top-10 not captured yet).
Weight / size is always a manual check (needs the supplier's spec sheet).

Stage (automatic, can be overridden by hand in data/pipeline.csv):
Universo -> Pasa reglas -> Tendencia OK -> Competencia OK -> (manual) Cotizando -> Muestra -> Pedido / Descartado
"""
import pandas as pd

from .config import DATA_DIR

UNIVERSE_PATH = DATA_DIR / "universe.csv"
COUNTS_PATH = DATA_DIR / "universe_counts.csv"
PIPELINE_PATH = DATA_DIR / "pipeline.csv"
STAGES = ["Universo", "Pasa reglas", "Tendencia OK", "Competencia OK", "Cotizando", "Muestra", "Pedido"]
MANUAL_STAGES = ["", "Cotizando", "Muestra", "Pedido", "Descartado"]
PIPELINE_COLUMNS = ["tipo", "etapa_manual", "notas", "peso_kg"]
PASS, FAIL, UNKNOWN = "✓", "✗", "?"


def product_types(universe: pd.DataFrame) -> pd.DataFrame:
    g = universe.groupby("tipo")
    out = pd.DataFrame({
        "sector": g["sector"].agg(lambda s: s.mode().iloc[0]),
        "listados": g.size(),
        "lanzamientos_nuevos": g["lista"].agg(lambda s: int((s == "New Releases").sum())),
        "precio_mediana": g["precio_usd"].median().round(2),
        "resenas_min": g["resenas"].min(),
        "mejor_puesto": g["rank"].min(),
        "ejemplo": g["titulo"].first(),
    }).reset_index()
    # Several different sellers launching the same thing at once = demand forming (and competition coming)
    out["senal"] = out["lanzamientos_nuevos"].map(lambda n: "Varios lanzamientos nuevos" if n >= 3 else "")
    return out.sort_values(["lanzamientos_nuevos", "listados"], ascending=False).reset_index(drop=True)


def _check(ok: bool | None) -> str:
    return UNKNOWN if ok is None else PASS if ok else FAIL


def evaluate(types: pd.DataFrame, cfg: dict, trends: pd.DataFrame | None = None,
             patterns: pd.DataFrame | None = None, competition: pd.DataFrame | None = None) -> pd.DataFrame:
    c = cfg["criterios"]
    tr = trends.set_index("keyword") if trends is not None and not trends.empty else pd.DataFrame()
    pt = patterns.set_index("keyword") if patterns is not None and not patterns.empty else pd.DataFrame()
    cp = competition.set_index("keyword") if competition is not None and not competition.empty else pd.DataFrame()
    rows = []
    for _, t in types.iterrows():
        k = t["tipo"]
        price = t["precio_mediana"]
        if k in cp.index and pd.notna(cp.loc[k, "precio_mediana"]):
            price = cp.loc[k, "precio_mediana"]  # the real top-10 median beats the universe sample
        price_ok = c["precio_min"] <= price <= c["precio_max"]

        trend_ok, trend_txt = None, "sin escanear"
        if k in tr.index:
            cl = tr.loc[k, "clasificacion"]
            pat = pt.loc[k, "patron"] if k in pt.index else None
            trend_txt = cl + (f" · {pat}" if isinstance(pat, str) else "")
            trend_ok = cl not in c["tendencias_descartadas"] and pat not in c["patrones_descartados"]

        comp_ok = demand_ok = None
        comp_txt = "sin top 10"
        if k in cp.index:
            low = cp.loc[k, "listados_bajo_500_resenas"]
            sold = cp.loc[k, "vendidos_mes_top10"]
            comp_ok = bool(low >= c["min_listados_bajo_500_resenas"])
            demand_ok = bool(sold >= c["min_vendidos_mes_top10"])
            comp_txt = f"{cp.loc[k, 'veredicto']} · {int(low)} con <500 reseñas · {int(sold):,} vendidos/mes"

        if trend_txt.startswith("Volumen insuficiente") and demand_ok:
            # Niche searched on Amazon, not on Google: no Google signal is not evidence of no demand.
            trend_ok, trend_txt = None, "Sin volumen en Google (nicho de Amazon)"

        checks = {"precio": _check(price_ok), "tendencia": _check(trend_ok),
                  "competencia": _check(comp_ok), "demanda": _check(demand_ok), "peso": UNKNOWN}
        auto = [v for kk, v in checks.items() if kk != "peso"]
        estado = "No apto" if FAIL in auto else "Apto" if all(v == PASS for v in auto) else "Falta dato"

        if not price_ok:
            stage = "Universo"
        elif trend_ok is not True:
            stage = "Pasa reglas"
        elif not (comp_ok and demand_ok):
            stage = "Tendencia OK"
        else:
            stage = "Competencia OK"
        rows.append({**t.to_dict(), "precio_ref": round(float(price), 2), **checks, "estado": estado,
                     "tendencia_detalle": trend_txt, "competencia_detalle": comp_txt, "etapa_auto": stage})
    return pd.DataFrame(rows)


def load_pipeline() -> pd.DataFrame:
    if PIPELINE_PATH.exists():
        return pd.read_csv(PIPELINE_PATH, dtype=str).fillna("")
    return pd.DataFrame(columns=PIPELINE_COLUMNS)


def with_manual(evaluated: pd.DataFrame, pipeline: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """Merge hand-entered stage, notes and weight. A known weight over the limit makes the type 'No apto'."""
    pipeline = pipeline.reindex(columns=PIPELINE_COLUMNS)
    df = evaluated.merge(pipeline, on="tipo", how="left").fillna({"etapa_manual": "", "notas": "", "peso_kg": ""})
    df["etapa"] = df["etapa_manual"].where(df["etapa_manual"] != "", df["etapa_auto"])
    if cfg is not None:
        limit = cfg["criterios"]["peso_max_kg"]
        weight = pd.to_numeric(df["peso_kg"], errors="coerce")
        df.loc[weight.notna(), "peso"] = (weight[weight.notna()] <= limit).map({True: PASS, False: FAIL})
        df.loc[df["peso"] == FAIL, "estado"] = "No apto"
    return df


def shortlist(df: pd.DataFrame) -> pd.DataFrame:
    """Best candidates: price, competition and demand pass, nothing failed, not discarded by hand.
    Ordered by how many of them are already verified (trend and weight), then by demand."""
    ok = df[(df["precio"] == PASS) & (df["competencia"] == PASS) & (df["demanda"] == PASS)
            & (df["estado"] != "No apto") & (df["etapa"] != "Descartado")].copy()
    ok["_verificados"] = (ok[["tendencia", "peso"]] == PASS).sum(axis=1)
    return ok.sort_values(["_verificados", "lanzamientos_nuevos"], ascending=False).drop(columns="_verificados")


def special_opportunities(comp_summary: pd.DataFrame, competition_rows: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Two cases the normal rules would miss:
    - Clientes insatisfechos: listings rated < 3.6 that still sell >= the demand minimum (summed per brand).
    - Ola barata: huge demand (>= 50k/month in the top 10) but the median price is under the minimum;
      only a premium version could fit."""
    rows = []
    c = cfg["criterios"]
    for _, s in comp_summary.iterrows():
        k = s["keyword"]
        top = competition_rows[competition_rows["keyword"] == k].dropna(subset=["vendidos_mes", "rating"])
        weak = top[top["rating"] < 3.6]
        if not weak.empty and weak["vendidos_mes"].sum() >= c["min_vendidos_mes_top10"]:
            # same brand often lists several sizes: add them up
            key = weak["marca"].astype(str).str.replace(r"[^\w]", "", regex=True).str.lower()  # "Dr" == "Dr."
            by_brand = weak.groupby(key).agg(v=("vendidos_mes", "sum"), r=("rating", "mean"), p=("precio_usd", "median"),
                                             name=("marca", "first")).sort_values("v", ascending=False)
            b = by_brand.iloc[0]
            brand = b["name"]
            rows.append({"tipo": k, "oportunidad": "Clientes insatisfechos",
                         "detalle": f"{brand}: {b['r']:.1f} estrellas y aun así vende ~{int(b['v']):,}/mes"
                                    + (f" a ${b['p']:.0f}" if pd.notna(b["p"]) else ""),
                         "que_hacer": "Leer reseñas de 1-3 estrellas y pedir al proveedor la versión mejorada"})
        if s["vendidos_mes_top10"] >= 50_000 and s["precio_mediana"] < c["precio_min"]:
            rows.append({"tipo": k, "oportunidad": "Ola fuerte pero barata",
                         "detalle": f"~{int(s['vendidos_mes_top10']):,} vendidos/mes en el top 10, precio mediano "
                                    f"${s['precio_mediana']:.0f}",
                         "que_hacer": f"Solo entra una versión premium de ${c['precio_min']}+ (kit más completo)"})
    return pd.DataFrame(rows, columns=["tipo", "oportunidad", "detalle", "que_hacer"])


def funnel_counts(evaluated: pd.DataFrame, counts: pd.DataFrame | None, universe: pd.DataFrame) -> pd.DataFrame:
    """Rows for the funnel chart: raw listings first, then product types by furthest stage reached."""
    rows = []
    if counts is not None and not counts.empty:
        rows.append(("Listados revisados en Amazon", int(counts["total"].sum())))
        rows.append(("Pasan precio y restricciones", len(universe)))
    rows.append(("Tipos de producto", len(evaluated)))
    reached = evaluated[evaluated["etapa"] != "Descartado"]["etapa"].map(
        lambda s: STAGES.index(s) if s in STAGES else 0)
    for i, name in enumerate(STAGES[1:], start=1):
        rows.append((name, int((reached >= i).sum())))
    return pd.DataFrame(rows, columns=["etapa", "cantidad"])
