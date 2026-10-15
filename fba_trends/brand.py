"""Weavers brand (brandbook WEAVERS.pdf).

Colors are taken from the brandbook palette page and from the vector logo itself:
navy background #010236, logo dots #51BFFF, wordmark #F3F3F5, palette #57C3FF / #192633 / #7851EC.
Logo files in static/brand/ are rendered straight from the brandbook PDF (not redrawn).

Font: the brand typeface is Coolvetica. If `static/coolvetica.otf` exists it is used;
otherwise Montserrat (headings/labels, close to the brandbook's label style) and Inter (body).
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .config import ROOT

NAVY = "#010236"        # brandbook cover / logo background
NAVY_2 = "#080A4A"      # raised surfaces
CYAN = "#57C3FF"        # palette
CYAN_LOGO = "#51BFFF"   # logo dots
INK = "#192633"
PURPLE = "#7851EC"
TEXT = "#F3F3F5"
MUTED = "#A3A6B4"       # brandbook label gray
GRADIENT = f"linear-gradient(90deg, #E9F8FF 0%, {CYAN} 45%, {PURPLE} 100%)"
COLORWAY = [CYAN_LOGO, PURPLE, "#B9A6F7", "#A8E1FF", "#3E8FD6", "#5B3BC4", "#E4E6EE"]

LOGO_URL = "app/static/brand/weavers_logo.png"
ICON_PATH = ROOT / "static" / "brand" / "weavers_icon.png"
LOGO_PATH = ROOT / "static" / "brand" / "weavers_logo.png"
PURPLE_ALERT = "#D55181"


def _fonts() -> tuple[str, str, str]:
    """(@font-face css, heading family, body family)"""
    if (ROOT / "static" / "coolvetica.otf").exists():
        face = "@font-face { font-family: 'Coolvetica'; src: url('app/static/coolvetica.otf'); }"
        return face, "'Coolvetica', 'Montserrat', sans-serif", "'Coolvetica', 'Inter', sans-serif"
    return "", "'Montserrat', sans-serif", "'Inter', sans-serif"


def css() -> str:
    # Blank lines would end Streamlit's markdown HTML block and print the CSS as text.
    return "\n".join(line for line in _css().splitlines() if line.strip())


def _css() -> str:
    face, head, body = _fonts()
    return f"""
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
{face}
html, body, .stMarkdown, p, label, li, input, textarea, button {{ font-family: {body}; }}
h1, h2, h3, h4, [data-testid="stMetricLabel"] {{ font-family: {head}; }}
[data-testid="stIconMaterial"], .material-symbols-rounded {{ font-family: "Material Symbols Rounded" !important; }}

/* Canvas */
.stApp {{
  background:
    radial-gradient(1000px 480px at 105% -5%, rgba(120,81,236,.16), transparent 60%),
    radial-gradient(800px 420px at -5% 105%, rgba(81,191,255,.08), transparent 60%),
    {NAVY};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu {{ display:none !important; }}
.block-container {{ padding-top: 2.4rem; padding-bottom: 4rem; max-width: 1240px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: #010236; border-right: 1px solid rgba(87,195,255,.10); }}
[data-testid="stSidebarLogo"] {{ height: 72px !important; max-height: 72px !important; width:auto !important;
  max-width: 100% !important; margin: 8px 0 6px 2px; }}
[data-testid="stSidebarHeader"] {{ height:auto !important; padding-top: 18px; }}
[data-testid="stSidebarNav"] a {{ border-radius: 10px; margin: 1px 6px; padding: 6px 10px; }}
[data-testid="stSidebarNav"] a span {{ font-family:{body}; font-weight:500; color:{TEXT}; opacity:.82; }}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(87,195,255,.08); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: linear-gradient(90deg, rgba(87,195,255,.18), rgba(120,81,236,.18));
  box-shadow: inset 3px 0 0 {CYAN}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ opacity:1; font-weight:600; }}
[data-testid="stNavSectionHeader"], [data-testid="stSidebarNav"] header {{
  font-family:{head}; font-size:.68rem; letter-spacing:.12em; text-transform:uppercase; color:{MUTED};
  margin-top: 12px; }}

/* Page title */
.wv-page {{ margin: 0 0 22px 0; }}
.wv-page h1 {{ font-family:{head}; font-weight:800; font-size:2.05rem; color:{TEXT}; letter-spacing:-.01em;
  margin:0; padding:0; line-height:1.15; }}
.wv-page .sub {{ color:{MUTED}; font-size:.95rem; margin-top:6px; }}
.wv-page .rule {{ width:56px; height:3px; border-radius:3px; background:{GRADIENT}; margin-top:14px; }}

/* Section titles (was the brandbook pill) */
.wv-pill {{ display:flex; align-items:center; gap:10px; font-family:{head}; font-weight:700;
  letter-spacing:.1em; text-transform:uppercase; color:{TEXT}; font-size:.78rem; margin:26px 0 12px 0; }}
.wv-pill::before {{ content:""; width:4px; height:16px; border-radius:3px; background:linear-gradient({CYAN}, {PURPLE}); }}

/* Tabs (sub-sections) */
.stTabs [role="tablist"] {{ gap:6px; border:0; box-shadow:none; }}
.stTabs [data-testid="stTab"] {{ height:auto; border-radius:10px; padding:6px 14px; background:transparent;
  border:1px solid rgba(87,195,255,.18); }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background:rgba(87,195,255,.14); border-color:rgba(87,195,255,.45); }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}

/* Decision verdict */
.wv-verdict {{ border-radius:20px; padding:24px 28px; margin:4px 0 20px 0; background:{NAVY_2};
  border:1px solid transparent; background-image:linear-gradient(#0A0C50,#070944), {GRADIENT};
  background-origin:border-box; background-clip:padding-box, border-box;
  box-shadow: 0 20px 60px -30px rgba(120,81,236,.55); }}
.wv-v-label {{ font-family:{head}; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:{MUTED};
  font-size:.72rem; }}
.wv-v-title {{ font-family:{head}; font-weight:800; font-size:2rem; color:{TEXT}; margin:10px 0 8px 0; line-height:1.15; }}
.wv-verdict.ninguno .wv-v-title {{ color:#F0B4CB; }}
.wv-v-text {{ color:{TEXT}; font-size:1rem; opacity:.85; }}
.wv-badge {{ margin-left:10px; padding:3px 10px; border-radius:999px; font-size:.7rem; letter-spacing:.02em;
  background:rgba(213,81,129,.16); color:#F3B6CC; text-transform:none; font-weight:600; }}
.wv-badge.ok {{ background:rgba(47,150,224,.16); color:{CYAN}; }}

/* Metric cards */
[data-testid="stMetric"] {{ background:linear-gradient(180deg, #0A0C4E, #07093F); border:1px solid rgba(87,195,255,.12);
  border-radius:16px; padding:16px 18px; position:relative; overflow:hidden; }}
[data-testid="stMetric"]::before {{ content:""; position:absolute; left:0; right:0; top:0; height:2px; background:{GRADIENT}; opacity:.8; }}
[data-testid="stMetricValue"] {{ color:{TEXT}; font-family:{head}; font-weight:700;
  font-size:clamp(1.15rem, 1.9vw, 1.7rem); }}
[data-testid="stMetricValue"] > div {{ overflow:visible; text-overflow:clip; }}
[data-testid="stMetricLabel"] p {{ color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; font-size:.68rem;
  white-space:normal; line-height:1.3; }}
[data-testid="stMetricLabel"] > div {{ overflow:visible; }}

/* Alert rows */
.wv-alert {{ display:flex; gap:12px; align-items:flex-start; padding:12px 14px; border-radius:12px;
  background:#07093F; border:1px solid rgba(87,195,255,.10); margin-bottom:8px; }}
.wv-alert .dot {{ width:9px; height:9px; border-radius:50%; margin-top:6px; flex:none; }}
.wv-alert .dot.Alta {{ background:{PURPLE_ALERT}; box-shadow:0 0 0 4px rgba(213,81,129,.18); }}
.wv-alert .dot.Media {{ background:{CYAN}; box-shadow:0 0 0 4px rgba(87,195,255,.16); }}
.wv-alert .dot.Baja {{ background:{MUTED}; }}
.wv-alert .t {{ font-weight:600; color:{TEXT}; font-size:.92rem; }}
.wv-alert .k {{ color:{MUTED}; font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; }}
.wv-alert .a {{ color:{TEXT}; opacity:.8; font-size:.85rem; margin-top:2px; }}

/* Buttons, links */
.stButton button, [data-testid="stFormSubmitButton"] button {{ border-radius:10px; border:1px solid rgba(87,195,255,.45);
  color:{TEXT}; font-family:{head}; font-weight:600; background:transparent; }}
.stButton button:hover {{ background:rgba(87,195,255,.10); border-color:{CYAN}; color:white; }}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {{
  background:linear-gradient(90deg, {CYAN}, {PURPLE}); border:0; color:white; }}
[data-testid="stPageLink"] a {{ border-radius:10px; }}
[data-testid="stPageLink"] p {{ color:{CYAN}; font-weight:600; }}

/* Inputs, tables, expanders, forms */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border:1px solid rgba(87,195,255,.12); border-radius:14px; overflow:hidden; }}
[data-testid="stExpander"] details {{ border:1px solid rgba(87,195,255,.14); border-radius:14px; background:#07093F; }}
[data-testid="stForm"] {{ border:1px solid rgba(87,195,255,.14); border-radius:18px; background:#06083C; padding:8px 20px 20px; }}
[data-testid="stAlert"] {{ border-radius:14px; }}
[data-testid="stFileUploaderDropzone"] {{ background:#07093F; border:1px dashed rgba(87,195,255,.3); border-radius:14px; }}
[data-testid="stCaptionContainer"] {{ color:{MUTED}; }}
</style>
"""


def page_title(title: str, subtitle: str = "") -> str:
    sub = f'<div class="sub">{subtitle}</div>' if subtitle else ""
    return f'<div class="wv-page"><h1>{title}</h1>{sub}<div class="rule"></div></div>'


def alert_row(priority: str, kind: str, element: str, action: str) -> str:
    return (f'<div class="wv-alert"><div class="dot {priority}"></div><div><div class="k">{kind} · {priority}</div>'
            f'<div class="t">{element}</div><div class="a">{action}</div></div></div>')


def header(subtitle: str) -> str:  # kept for compatibility; the app now uses page_title + sidebar logo
    return page_title("FBA Trends", subtitle)


def pill(text: str) -> str:
    return f'<div class="wv-pill">{text}</div>'


# Display names for table columns (data files keep their snake_case names).
LABELS = {
    "keyword": "Keyword", "clasificacion": "Clasificación", "trend_score": "Score tendencia",
    "momentum_pct": "Momentum %", "yoy_pct": "Interanual %", "crec_anual_pct": "Crec. anual %",
    "crec_vs_mercado_pct": "Crec. vs mercado %", "volumen_vs_yoga_mat_pct": "Volumen (% yoga mat)",
    "estacionalidad": "Estacionalidad", "mes_pico": "Mes pico", "pedir_antes_de": "Pedir antes de",
    "pico_reciente_x": "Pico reciente (x)", "semanas": "Semanas",
    "n": "N", "precio_mediana": "Precio mediana $", "precio_min": "Precio mín $", "precio_max": "Precio máx $",
    "resenas_mediana": "Reseñas (mediana)", "resenas_prom": "Reseñas (prom.)",
    "listados_bajo_500_resenas": "< 500 reseñas", "rating_prom": "Rating prom.",
    "vendidos_mes_top10": "Vendidos/mes top 10", "pct_ventas_top3": "% ventas top 3",
    "marca_dominante": "Marca dominante", "puestos_marca_dominante": "Puestos marca dom.",
    "anuncios_en_pagina": "Anuncios", "veredicto": "Veredicto",
    "nombre": "Producto", "producto": "Producto", "score": "Score", "tendencia": "Tendencia",
    "competencia": "Competencia", "resenas_competencia": "Reseñas competencia", "fuente_resenas": "Fuente reseñas",
    "precio_mediana_mercado": "Precio mercado $", "vendidos_mes_mercado": "Vendidos/mes mercado",
    "bsr_cambio_mercado_pct": "Cambio BSR mercado %", "costo_puesto": "Costo puesto $",
    "comision_referral": "Comisión $", "fba_fee": "Tarifa FBA $", "ppc": "PPC $", "almacenaje": "Almacenaje $",
    "devoluciones": "Devoluciones $", "ganancia_neta": "Ganancia neta $", "margen_pct": "Margen %",
    "roi_pct": "ROI %", "precio_equilibrio": "Precio equilibrio $", "datos_estimados": "Datos estimados",
    "datos_faltantes_score": "Faltan para score", "precio_venta": "Precio venta $",
    "costo_max_puesto_en_amazon": "Costo máx. puesto $", "unidades": "Unidades",
    "inversion_inventario": "Inversión inventario $", "costo_lanzamiento": "Lanzamiento $",
    "ganancia_esperada_si_vende_todo": "Ganancia si vende todo $", "meses_de_stock_est": "Meses de stock",
    "motivo": "Motivo", "supuesto": "Supuesto", "nota": "Nota",
    "asin": "ASIN", "titulo": "Título", "marca": "Marca", "bsr_actual": "BSR actual", "bsr_prom_90d": "BSR prom. 90d",
    "bsr_cambio_30v60_pct": "Cambio BSR %", "precio_actual": "Precio $", "precio_prom_90d": "Precio prom. 90d $",
    "vendedores": "Vendedores", "vendedores_cambio_pct": "Cambio vendedores %", "resenas": "Reseñas",
    "rating": "Rating", "vendidos_mes": "Vendidos/mes", "posicion": "Posición", "precio_usd": "Precio $",
    "patrocinados_pagina": "Anuncios en página", "fecha": "Fecha", "costo_fabrica": "Costo fábrica $",
    "flete_unidad": "Flete/unidad $", "size_tier": "Tamaño FBA", "cuft_unidad": "Pies³/unidad", "moq": "MOQ",
    "ventas_mes_est": "Ventas/mes est.", "resenas_top10": "Reseñas top 10", "asins_competidores": "ASINs competidores",
    "fuente": "Fuente", "termino": "Término", "seed": "Semilla", "categoria": "Categoría",
    "subida_pct": "Subida %", "breakout": "Breakout", "descubierto": "Descubierto", "estado": "Estado",
    "finalista": "Finalista", "patron": "Patrón", "temporada": "Temporada", "festividad": "Fecha comercial",
    "semana_pico": "Semana pico", "fuerza_estacional": "Fuerza estacional", "variabilidad": "Variabilidad",
    "ultimo_episodio": "Último pico", "episodios": "Picos", "momento": "Momento", "vender_desde": "Vender desde",
    "dias_para_pedir": "Días para pedir", "buscar_proveedor_desde": "Buscar proveedor desde", "pico": "Pico",
    "prioridad": "Prioridad", "elemento": "Producto / fecha / sector", "accion": "Qué hacer", "sector": "Sector",
    "productos": "Productos", "crec_sector_pct": "Crec. sector vs mercado %", "ganador": "Producto ganador",
    "crec_ganador_pct": "Crec. ganador %", "top_3": "Top 3", "episodio_fecha": "Fecha último pico",
    "nivel_vs_pico": "Nivel vs pico", "tipo": "Producto", "etapa": "Etapa", "senal": "Señal",
    "listados": "Listados", "lanzamientos_nuevos": "Lanzamientos nuevos", "precio_ref": "Precio ref. $",
    "precio": "Precio", "tendencia": "Tendencia", "demanda": "Demanda", "peso": "Peso",
    "tendencia_detalle": "Detalle tendencia", "competencia_detalle": "Detalle competencia", "ejemplo": "Ejemplo",
    "cantidad": "Cantidad", "peso_kg": "Peso kg", "oportunidad": "Oportunidad", "detalle": "Detalle",
    "que_hacer": "Qué hacer", "notas": "Notas", "precio_sugerido": "Precio sugerido $", "costo_estimado": "Costo estimado",
    "ganancia_unidad": "Ganancia/unidad $", "ventas_mes_proy": "Ventas/mes proy.", "ganancia_mes_proy": "Ganancia/mes proy. $",
    "confianza": "Confianza", "falta_verificar": "Falta verificar", "opcion": "Opción", "invertido": "Invertido $",
    "reserva": "Reserva $", "ganancia_horizonte": "Ganancia horizonte $", "ganancia_ajustada": "Ganancia ajustada $",
    "recupera_inversion_meses": "Recupera inversión (meses)",
}


def pretty(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=lambda c: LABELS.get(c, c.replace("_", " ").capitalize()))


def register_plotly_template() -> None:
    _, head, body = _fonts()
    t = go.layout.Template(pio.templates["plotly_dark"])
    t.layout.update(
        colorway=COLORWAY,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=body.replace("'", ""), color=TEXT),
        title=dict(font=dict(family=head.replace("'", ""), size=15, color=MUTED)),
        xaxis=dict(gridcolor="rgba(243,243,245,0.06)", zerolinecolor="rgba(243,243,245,0.1)"),
        yaxis=dict(gridcolor="rgba(243,243,245,0.06)", zerolinecolor="rgba(243,243,245,0.1)"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    pio.templates["weavers"] = t
    pio.templates.default = "weavers"
