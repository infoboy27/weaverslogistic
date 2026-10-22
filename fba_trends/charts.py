"""Plotly figures for the Patrones and Lo que viene views.

Palette validated with the dataviz skill's validator on the brand navy (#010236), all-pairs:
#2F96E0 (brand cyan stepped for data) / #7851EC (brand purple) / #D55181 (magenta) - so charts use
at most 3 colored groups; anything more is split into small multiples.
Heatmap: one-hue ramp navy -> cyan (lightness monotone).
"""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .brand import MUTED, TEXT

C1, C2, C3 = "#2F96E0", "#7851EC", "#D55181"
RAMP = ["#10226B", "#16418F", "#1E64B8", "#2F8BDB", "#51BFFF", "#B5E4FF"]
GRID = "rgba(243,243,245,0.06)"

GROUP_OF = {
    "Estacional": "Estacional",
    "Viral": "Picos (viral / shock / subiendo)", "Shock de mercado": "Picos (viral / shock / subiendo)",
    "Subiendo rápido": "Picos (viral / shock / subiendo)",
    "Todo el año": "Estable o creciente", "Creciente": "Estable o creciente", "Irregular": "Estable o creciente",
}
GROUP_COLOR = {"Estacional": C1, "Picos (viral / shock / subiendo)": C3, "Estable o creciente": C2}


def _base(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), hoverlabel=dict(font_color=TEXT))
    return fig


def season_heatmap(heat: pd.DataFrame) -> go.Figure:
    """heat: index = keyword (sorted by peak month), columns = months, values = x average month."""
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=list(heat.columns), y=list(heat.index), colorscale=[[i / 5, c] for i, c in enumerate(RAMP)],
        xgap=2, ygap=2, zmin=0.5, zmax=2.0,  # cap: >= 2x the average month is "peak season"
        colorbar=dict(tickvals=[0.5, 1, 1.5, 2], ticktext=["0.5×", "1×", "1.5×", "≥2×"], title=dict(text="vs mes<br>promedio", font=dict(color=MUTED)), tickfont=dict(color=MUTED)),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.2f}× un mes promedio<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False)
    return _base(fig, max(260, 26 * len(heat) + 80))


def pattern_map(t: pd.DataFrame) -> go.Figure:
    """Seasonality strength vs volatility; 3 colored groups (validated cap for scatter)."""
    fig = go.Figure()
    t = t[t["patron"].isin(GROUP_OF)].copy()
    t["grupo"] = t["patron"].map(GROUP_OF)
    for g, color in GROUP_COLOR.items():
        d = t[t["grupo"] == g]
        fig.add_trace(go.Scatter(
            x=d["fuerza_estacional"], y=d["variabilidad"], mode="markers", name=g,
            marker=dict(size=11, color=color, line=dict(width=2, color="#010236")),
            customdata=d[["keyword", "patron"]],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                          "estacionalidad %{x:.2f} · variabilidad %{y:.2f}<extra></extra>",
        ))
    for x, y, txt in [(0.05, 0.08, "TODO EL AÑO"), (0.92, 0.08, "ESTACIONAL"), (0.05, 0.97, "PICOS SUELTOS")]:
        fig.add_annotation(x=x, y=y, xref="paper", yref="paper", text=txt, showarrow=False,
                           font=dict(color=MUTED, size=11), xanchor="left" if x < 0.5 else "right")
    fig.update_xaxes(title="Fuerza estacional (se repite cada año →)", gridcolor=GRID, zeroline=False)
    fig.update_yaxes(title="Variabilidad (picos y caídas →)", gridcolor=GRID, zeroline=False)
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    return _base(fig, 440)


def small_multiples(series: dict[str, pd.Series], glitch: pd.DatetimeIndex, cols: int = 3) -> go.Figure:
    """One mini line per keyword (single series each: no legend); glitch weeks shaded."""
    names = list(series)
    rows = max(1, -(-len(names) // cols))
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=names, vertical_spacing=0.12, horizontal_spacing=0.05)
    for i, k in enumerate(names):
        r, c = i // cols + 1, i % cols + 1
        s = series[k].astype(float).copy()
        if len(glitch):  # leave a gap: the glitch peak would flatten the real curve
            s[s.index.normalize().isin(glitch.normalize())] = float("nan")
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=C1, width=2),
                                 connectgaps=False,
                                 hovertemplate=f"<b>{k}</b><br>%{{x|%d %b %Y}}: %{{y:.0f}}<extra></extra>",
                                 showlegend=False), row=r, col=c)
        if len(glitch):
            fig.add_vrect(x0=glitch.min(), x1=glitch.max(), fillcolor="rgba(243,243,245,0.07)", line_width=0,
                          row=r, col=c)
    fig.update_xaxes(showgrid=False, tickformat="%Y", dtick="M12")
    fig.update_yaxes(showgrid=True, gridcolor=GRID, rangemode="tozero")
    for a in fig.layout.annotations:
        a.font = dict(color=TEXT, size=12)
    return _base(fig, 210 * rows + 40)


def season_timeline(w: pd.DataFrame, today: date) -> go.Figure:
    """Sourcing window -> order deadline (bar) and the sales peak (marker) per seasonal keyword."""
    w = w.sort_values("pedir_antes_de", ascending=False)
    start = pd.to_datetime(w["buscar_proveedor_desde"])
    end = pd.to_datetime(w["pedir_antes_de"])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=w["keyword"], x=(end - start).dt.days * 86_400_000, base=start, orientation="h",
        marker=dict(color=C1, cornerradius=4), name="Buscar proveedor → fecha límite de pedido",
        customdata=w[["pedir_antes_de", "estado"]].astype(str),
        hovertemplate="<b>%{y}</b><br>Pedir antes de %{customdata[0]}<br>%{customdata[1]}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        y=w["keyword"], x=pd.to_datetime(w["pico"]), mode="markers", name="Pico de ventas",
        marker=dict(symbol="diamond", size=11, color=C2, line=dict(width=2, color="#010236")),
        customdata=w[["festividad"]].fillna("").astype(str),
        hovertemplate="<b>%{y}</b><br>Pico: %{x|%d %b %Y}<br>%{customdata[0]}<extra></extra>",
    ))
    fig.add_vline(x=pd.Timestamp(today), line=dict(color=TEXT, width=1, dash="dot"))
    fig.add_annotation(x=pd.Timestamp(today), y=1.02, yref="paper", text="hoy", showarrow=False,
                       font=dict(color=MUTED, size=11))
    fig.update_xaxes(type="date", gridcolor=GRID, tickformat="%b %Y")
    fig.update_yaxes(showgrid=False)
    fig.update_layout(barmode="overlay", legend=dict(orientation="h", y=-0.15))
    return _base(fig, max(260, 34 * len(w) + 120))


def growth_bars(t: pd.DataFrame, value: str, label: str) -> go.Figure:
    t = t.sort_values(value)
    fig = go.Figure(go.Bar(
        y=t["keyword"], x=t[value], orientation="h", marker=dict(color=C1, cornerradius=4),
        text=[f"{v:+.0f}%" for v in t[value]], textposition="outside", textfont=dict(color=TEXT),
        customdata=t[["patron"]].fillna(""),
        hovertemplate="<b>%{y}</b><br>" + label + ": %{x:.0f}%<br>%{customdata[0]}<extra></extra>",
    ))
    lo, hi = min(0.0, float(t[value].min())), max(0.0, float(t[value].max()))
    pad = (hi - lo) * 0.18 or 1  # room for the outside labels
    fig.update_xaxes(title=label, gridcolor=GRID, zeroline=False, range=[lo - (pad if lo < 0 else 0), hi + pad])
    fig.update_yaxes(showgrid=False)
    fig.update_layout(bargap=0.35)
    return _base(fig, max(240, 30 * len(t) + 90))


# Diverging: magenta (falls) <- neutral gray-navy -> cyan (grows). Midpoint = market (0%).
DIVERGING = [[0.0, C3], [0.5, "#3B3E66"], [1.0, "#51BFFF"]]


def sector_treemap(products: pd.DataFrame, sectors: pd.DataFrame, sector_of: dict[str, str],
                   cap: float = 60) -> go.Figure:
    """Sectors sized by product count, colored by median growth vs market; click a sector to see
    its products (winners first)."""
    t = products.dropna(subset=["crec_vs_mercado_pct"]).copy()
    t["sector"] = t["keyword"].map(sector_of)
    t = t[t["sector"].isin(set(sectors["sector"]))]
    ids, labels, parents, values, colors, text = [], [], [], [], [], []
    for _, s in sectors.iterrows():
        ids.append(f"s:{s['sector']}")
        labels.append(s["sector"].upper())
        parents.append("")
        values.append(int(s["productos"]))
        colors.append(max(-cap, min(cap, s["crec_sector_pct"])))
        text.append(f"{s['crec_sector_pct']:+.0f}% · {int(s['productos'])} productos")
    for _, p in t.iterrows():
        ids.append(f"p:{p['keyword']}")
        labels.append(p["keyword"])
        parents.append(f"s:{p['sector']}")
        values.append(1)
        g = float(p["crec_vs_mercado_pct"])
        colors.append(max(-cap, min(cap, g)))
        text.append(f"{g:+.0f}%")
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total", text=text,
        texttemplate="<b>%{label}</b><br>%{text}", textfont=dict(color=TEXT),
        marker=dict(colors=colors, colorscale=DIVERGING, cmid=0, cmin=-cap, cmax=cap, line=dict(width=2, color="#010236"),
                    colorbar=dict(title=dict(text="Crec. vs<br>mercado", font=dict(color=MUTED)),
                                  tickvals=[-cap, -30, 0, 30, cap],
                                  ticktext=[f"≤-{cap:.0f}%", "-30%", "0%", "+30%", f"≥+{cap:.0f}%"],
                                  tickfont=dict(color=MUTED))),
        hovertemplate="<b>%{label}</b><br>%{text}<extra></extra>", pathbar=dict(visible=True),
        sort=True,
    ))
    return _base(fig, 520)


def funnel_chart(f: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Funnel(
        y=f["etapa"], x=f["cantidad"], marker=dict(color=C1, line=dict(width=2, color="#010236")),
        connector=dict(fillcolor="rgba(47,150,224,0.12)", line=dict(width=0)),
        textinfo="value", textfont=dict(color=TEXT),
        hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>",
    ))
    fig.update_yaxes(showgrid=False)
    return _base(fig, 60 * len(f) + 60)


def rejection_bars(counts: pd.DataFrame) -> go.Figure:
    """Why listings drop out, per sector. 3 groups = the validated categorical cap."""
    g = counts.groupby("sector")[["total", "precio_fuera", "restringido", "voluminoso", "sin_precio",
                                  "pasan_filtro_pagina"]].sum()
    parts = {
        "Pasa precio y restricciones": g["pasan_filtro_pagina"],
        "Precio fuera de $20-50": g["precio_fuera"],
        "Restringido, voluminoso o sin precio": g["restringido"] + g["voluminoso"] + g["sin_precio"],
    }
    colors = [C1, C2, C3]
    fig = go.Figure()
    for (name, vals), color in zip(parts.items(), colors):
        pct = vals / g["total"] * 100
        fig.add_trace(go.Bar(y=g.index, x=pct, name=name, orientation="h",
                             marker=dict(color=color, line=dict(width=2, color="#010236")),
                             customdata=vals, hovertemplate="<b>%{y}</b><br>" + name + ": %{customdata} (%{x:.0f}%)<extra></extra>"))
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.18, x=0, yanchor="bottom"))
    fig.update_xaxes(title="% de los listados revisados", range=[0, 100], gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    return _base(fig, 300)


def allocation_bar(alloc: pd.DataFrame, reserve: float) -> go.Figure:
    """Where the money goes: inventory + launch per product, and what stays in reserve."""
    names = list(alloc["producto"]) + ["Reserva"]
    inv = list(alloc["inversion_inventario"]) + [0]
    launch = list(alloc["costo_lanzamiento"]) + [0]
    res = [0] * len(alloc) + [reserve]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=inv, name="Inventario", orientation="h", marker=dict(color=C1, cornerradius=4),
                         hovertemplate="<b>%{y}</b><br>Inventario: $%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(y=names, x=launch, name="Lanzamiento", orientation="h", marker=dict(color=C2),
                         hovertemplate="<b>%{y}</b><br>Lanzamiento: $%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(y=names, x=res, name="Reserva (PPC, imprevistos, recompra)", orientation="h",
                         marker=dict(color="#3B3E66"), hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>"))
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.15, x=0, yanchor="bottom"))
    fig.update_xaxes(title="USD", gridcolor=GRID, tickprefix="$")
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return _base(fig, 70 * len(names) + 120)


def options_bar(opts: pd.DataFrame, chosen: int) -> go.Figure:
    """Risk-adjusted profit of buying 1, 2, 3... products; the recommended option highlighted."""
    labels = [f"{int(o)} producto{'s' if o > 1 else ''}" for o in opts["opcion"]]
    colors = [C2 if int(o) == chosen else C1 for o in opts["opcion"]]
    fig = go.Figure(go.Bar(
        x=labels, y=opts["ganancia_ajustada"], marker=dict(color=colors, cornerradius=4),
        text=[f"${v:,.0f}" for v in opts["ganancia_ajustada"]], textposition="outside", textfont=dict(color=TEXT),
        customdata=opts[["productos", "invertido"]],
        hovertemplate="<b>%{x}</b><br>%{customdata[0]}<br>Invertido $%{customdata[1]:,.0f}<br>"
                      "Ganancia ajustada $%{y:,.0f}<extra></extra>"))
    fig.update_yaxes(title="Ganancia ajustada por confianza (USD)", gridcolor=GRID, tickprefix="$")
    fig.update_xaxes(showgrid=False)
    fig.add_annotation(x=labels[chosen - 1], y=float(opts["ganancia_ajustada"].iloc[chosen - 1]), yshift=28,
                       text="recomendada", showarrow=False, font=dict(color=MUTED, size=11))
    return _base(fig, 320)
