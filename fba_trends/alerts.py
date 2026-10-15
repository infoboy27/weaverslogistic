"""Alerts: deadlines coming up, products/sectors with momentum, and what to drop.

Every rule below is a heuristic (thresholds not validated against sales). Growth is always
"vs mercado": yearly growth relative to the control keywords, glitch weeks excluded.
"""
from datetime import date, timedelta

import pandas as pd

from .trends import CONTROL_KEYWORDS

COLUMNS = ["tipo", "prioridad", "elemento", "motivo", "accion", "fecha"]
PRIORITY_ORDER = {"Alta": 0, "Media": 1, "Baja": 2}


def _row(tipo, prioridad, elemento, motivo, accion, fecha=None):
    return {"tipo": tipo, "prioridad": prioridad, "elemento": elemento, "motivo": motivo,
            "accion": accion, "fecha": fecha}


def deadline_alerts(windows: pd.DataFrame, moments: pd.DataFrame, horizon_days: int = 180) -> list[dict]:
    out = []
    for _, w in windows.iterrows() if not windows.empty else []:
        d = int(w["dias_para_pedir"])
        if d > horizon_days or w.get("nota"):
            continue  # far away, or already rolled to next year's peak
        if d <= 45:
            pr, acc = "Alta", f"Pedir a fábrica ya (quedan {d} días)"
        elif d <= 120:
            pr, acc = "Media", f"Buscar proveedor y muestras ahora (pedido en {d} días)"
        else:
            pr, acc = "Baja", f"Empezar a buscar proveedor desde {w['buscar_proveedor_desde']}"
        fest = f" · {w['festividad']}" if isinstance(w.get("festividad"), str) and w["festividad"] else ""
        out.append(_row("Plazo", pr, w["keyword"], f"Pico de ventas {w['pico']}{fest}", acc, w["pedir_antes_de"]))
    for _, m in moments.iterrows() if not moments.empty else []:
        d = int(m["dias_para_pedir"])
        if 0 <= d <= horizon_days:
            pr = "Alta" if d <= 45 else "Media" if d <= 120 else "Baja"
            out.append(_row("Plazo", pr, m["momento"], f"Vender desde {m['vender_desde']}",
                            f"Si vas a vender para esta fecha, pedir antes de {m['pedir_antes_de']} ({d} días)",
                            m["pedir_antes_de"]))
    return out


def momentum_alerts(products: pd.DataFrame, discovery: pd.DataFrame | None = None,
                    today: date | None = None) -> list[dict]:
    """products: one row per keyword with patron, clasificacion, crec_vs_mercado_pct, episodio_fecha, nivel_vs_pico."""
    today = today or date.today()
    out = []
    recent = today - timedelta(weeks=26)
    for _, p in products.iterrows():
        g = p.get("crec_vs_mercado_pct")
        g = None if pd.isna(g) else float(g)
        if p["patron"] == "Subiendo rápido":
            out.append(_row("Oportunidad", "Alta", p["keyword"],
                            "Subiendo rápido: los últimos 3 meses duplican el semestre anterior",
                            "Validar en Amazon (top 10) antes de que se llene; puede ser moda pasajera"))
        elif g is not None and g >= 25 and (p["patron"] in ("Creciente", "Viral", "Shock de mercado")
                                             or p.get("clasificacion") == "Emergente"):
            had_peak = p["patron"] in ("Viral", "Shock de mercado") and isinstance(p.get("episodio_fecha"), str)
            note = f" (tuvo un pico en {p['episodio_fecha'][:7]}: confirmar que no sea moda)" if had_peak else ", sostenido"
            out.append(_row("Oportunidad", "Media", p["keyword"], f"Crece {g:+.0f}% vs mercado{note}",
                            "Revisar competencia y margen"))
        elif g is not None and g >= 20 and p["patron"] == "Estacional":
            out.append(_row("Oportunidad", "Media", p["keyword"],
                            f"Estacional que crece {g:+.0f}% vs mercado ({p.get('festividad') or p.get('temporada')})",
                            "Planear para la próxima temporada"))
        ep = p.get("episodio_fecha")
        if p["patron"] in ("Viral", "Shock de mercado") and isinstance(ep, str) and date.fromisoformat(ep) >= recent:
            lvl = p.get("nivel_vs_pico")
            if lvl is not None and not pd.isna(lvl) and lvl > 0.5:
                out.append(_row("Oportunidad", "Baja", p["keyword"],
                                f"{p['patron']} reciente ({ep[:7]}), todavía al {lvl:.0%} de su pico",
                                "Riesgoso: con 3-4 meses de entrega probablemente llegas tarde"))
    if discovery is not None and not discovery.empty:
        new = discovery[(discovery["estado"] == "escaneado") & (discovery.get("finalista", False) == True)]  # noqa: E712
        for _, d in new.iterrows():
            out.append(_row("Oportunidad", "Media", d["termino"], f"Descubierto vía '{d['seed']}' y pasó a finalista",
                            "Revisar en Amazon"))
    return out


def discard_alerts(products: pd.DataFrame, windows: pd.DataFrame, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out = []
    for _, p in products.iterrows():
        g = p.get("crec_vs_mercado_pct")
        g = None if pd.isna(g) else float(g)
        lvl = p.get("nivel_vs_pico")
        lvl = None if lvl is None or pd.isna(lvl) else float(lvl)
        if p["patron"] == "Volumen insuficiente":
            out.append(_row("Descartar", "Baja", p["keyword"], "Casi nadie lo busca", "Descartar"))
        elif p["patron"] in ("Viral", "Shock de mercado") and lvl is not None and lvl <= 0.5 and (g is None or g < 10):
            out.append(_row("Descartar", "Alta", p["keyword"],
                            f"Ya pasó su pico ({str(p.get('episodio_fecha'))[:7]}); hoy está al {lvl:.0%}",
                            "Descartar: la ola terminó"))
        elif p.get("clasificacion") == "Moda pasajera (pico y caída)":
            out.append(_row("Descartar", "Media", p["keyword"], "Moda pasajera: subió y ya está cayendo", "Descartar"))
        elif p.get("clasificacion") == "En declive" or (g is not None and g <= -15):
            out.append(_row("Descartar", "Media", p["keyword"],
                            f"Bajando ({g:+.0f}% vs mercado)" if g is not None else "Bajando", "Descartar"))
    if not windows.empty:
        for _, w in windows[windows["nota"] != ""].iterrows():
            out.append(_row("Descartar", "Baja", w["keyword"], w["nota"],
                            f"No intentar esta temporada; replanificar para {w['pico']}", w["pico"]))
    return out


def sector_table(products: pd.DataFrame, sector_of: dict[str, str]) -> pd.DataFrame:
    """Median growth vs market per sector, with its winners (best growth first)."""
    t = products[~products["keyword"].isin(CONTROL_KEYWORDS)].copy()
    t["sector"] = t["keyword"].map(sector_of).fillna("otros")
    t = t.dropna(subset=["crec_vs_mercado_pct"])
    rows = []
    for sector, g in t.groupby("sector"):
        g = g.sort_values("crec_vs_mercado_pct", ascending=False)
        rows.append({"sector": sector, "productos": len(g),
                     "crec_sector_pct": round(float(g["crec_vs_mercado_pct"].median()), 1),
                     "ganador": g["keyword"].iloc[0], "crec_ganador_pct": float(g["crec_vs_mercado_pct"].iloc[0]),
                     "top_3": ", ".join(g["keyword"].head(3))})
    return pd.DataFrame(rows).sort_values("crec_sector_pct", ascending=False).reset_index(drop=True)


def sector_alerts(sectors: pd.DataFrame) -> list[dict]:
    out = []
    for _, s in sectors.iterrows():
        few = s["productos"] < 2
        if s["crec_sector_pct"] >= 10:
            out.append(_row("Sector", "Baja" if few else "Media", s["sector"],
                            f"Crece {s['crec_sector_pct']:+.0f}% vs mercado ({s['productos']} productos)"
                            + (" · pocos datos" if few else ""),
                            f"Ganadores: {s['top_3']}"))
        elif s["crec_sector_pct"] <= -10 and not few:
            out.append(_row("Sector", "Baja", s["sector"], f"Cae {s['crec_sector_pct']:+.0f}% vs mercado",
                            "Evitar productos nuevos aquí"))
    return out


def build(products, windows, moments, sectors, discovery=None, today=None) -> pd.DataFrame:
    products = products[~products["keyword"].isin(CONTROL_KEYWORDS)]  # reference keywords, not products
    if not windows.empty:
        windows = windows[~windows["keyword"].isin(CONTROL_KEYWORDS)]
    rows = (deadline_alerts(windows, moments) + momentum_alerts(products, discovery, today)
            + discard_alerts(products, windows, today) + sector_alerts(sectors))
    df = pd.DataFrame(rows, columns=COLUMNS)
    if df.empty:
        return df
    df["_o"] = df["prioridad"].map(PRIORITY_ORDER)
    return df.sort_values(["_o", "fecha"], na_position="last").drop(columns="_o").reset_index(drop=True)
