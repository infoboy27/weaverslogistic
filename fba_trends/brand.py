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
h1, h2, h3, h4, [data-testid="stMetricLabel"], [data-testid="stTab"] {{ font-family: {head}; }}
[data-testid="stIconMaterial"], .material-symbols-rounded {{ font-family: "Material Symbols Rounded" !important; }}

/* Background: flat brand navy with the logo's beam glow in the corners */
.stApp {{
  background:
    radial-gradient(900px 420px at 100% 0%, rgba(120,81,236,.20), transparent 60%),
    radial-gradient(700px 380px at 0% 100%, rgba(81,191,255,.10), transparent 60%),
    {NAVY};
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}

/* Header */
.wv-hero {{ display:flex; align-items:center; gap:28px; padding: 6px 0 4px 0; flex-wrap:wrap; }}
.wv-hero img {{ height: 92px; width:auto; display:block; }}
.wv-hero .div {{ width:1px; align-self:stretch; background: rgba(243,243,245,.14); }}
.wv-title {{ font-family:{head}; font-weight:700; font-size:1.9rem; color:{TEXT}; letter-spacing:.01em; line-height:1.1; }}
.wv-title span {{ background:{GRADIENT}; -webkit-background-clip:text; background-clip:text; color:transparent; }}
.wv-sub {{ color:{MUTED}; font-size:.9rem; margin-top:6px; }}
.wv-bar {{ height:3px; border-radius:3px; background:{GRADIENT}; margin:18px 0 22px 0; }}

/* Brandbook pill labels ("CONCEPTO", "PANTONES") */
.wv-pill {{ display:inline-block; font-family:{head}; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; color:{MUTED}; font-size:.95rem; padding:5px 22px;
  border:1px solid rgba(163,166,180,.55); border-radius:999px; margin:18px 0 12px 0; }}

/* Tabs: uppercase pills, active one in brand gradient */
.stTabs [role="tablist"] {{ gap:8px; flex-wrap:wrap; border:0; box-shadow:none; }}
.stTabs [data-testid="stTab"] {{ height:auto; border-radius:999px; padding:7px 18px; background:transparent;
  border:1px solid rgba(87,195,255,.28); color:{TEXT}; }}
.stTabs [data-testid="stTab"] p {{ font-family:{head}; font-weight:600; font-size:.78rem;
  letter-spacing:.07em; text-transform:uppercase; }}
.stTabs [data-testid="stTab"]:hover {{ border-color:{CYAN}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background:linear-gradient(90deg, {CYAN}, {PURPLE});
  border-color:transparent; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color:white; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}
/* Decision verdict */
.wv-verdict {{ border-radius:20px; padding:22px 26px; margin:6px 0 18px 0; background:{NAVY_2};
  border:1px solid transparent; background-image:linear-gradient({NAVY_2},{NAVY_2}), {GRADIENT};
  background-origin:border-box; background-clip:padding-box, border-box; }}
.wv-v-label {{ font-family:{head}; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:{MUTED};
  font-size:.8rem; }}
.wv-v-title {{ font-family:{head}; font-weight:800; font-size:2rem; color:{TEXT}; margin:8px 0 6px 0; line-height:1.15; }}
.wv-verdict.ninguno .wv-v-title {{ color:#E7A3BF; }}
.wv-v-text {{ color:{TEXT}; font-size:1rem; opacity:.9; }}
.wv-badge {{ margin-left:10px; padding:3px 10px; border-radius:999px; font-size:.72rem; letter-spacing:.04em;
  background:rgba(213,81,129,.18); color:#F3B6CC; text-transform:none; }}
.wv-badge.ok {{ background:rgba(47,150,224,.18); color:{CYAN}; }}
/* Metrics as cards */
[data-testid="stMetric"] {{ background:{NAVY_2}; border:1px solid rgba(87,195,255,.18); border-radius:16px; padding:14px 18px; }}
[data-testid="stMetricValue"] {{ color:{CYAN_LOGO}; font-family:{head}; font-weight:700; }}
[data-testid="stMetricLabel"] p {{ color:{MUTED}; text-transform:uppercase; letter-spacing:.06em; font-size:.75rem; }}

/* Buttons */
.stButton button {{ border-radius:999px; border:1px solid {CYAN}; color:{TEXT};
  font-family:{head}; font-weight:600; letter-spacing:.03em; background:transparent; }}
.stButton button:hover {{ background:rgba(87,195,255,.12); border-color:{CYAN}; color:white; }}
.stButton button[kind="primary"] {{ background:linear-gradient(90deg, {CYAN}, {PURPLE}); border:0; color:white; }}

/* Inputs, tables, expanders */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border:1px solid rgba(87,195,255,.16); border-radius:14px; overflow:hidden; }}
[data-testid="stExpander"] details {{ border:1px solid rgba(87,195,255,.2); border-radius:14px; background:{NAVY_2}; }}
[data-testid="stAlert"] {{ border-radius:14px; }}
[data-testid="stFileUploaderDropzone"] {{ background:{NAVY_2}; border:1px dashed rgba(87,195,255,.35); border-radius:14px; }}
[data-testid="stCaptionContainer"] {{ color:{MUTED}; }}
</style>
"""


def header(subtitle: str) -> str:
    return f"""
<div class="wv-hero">
  <img src="{LOGO_URL}" alt="weavers">
  <div class="div"></div>
  <div><div class="wv-title">FBA <span>Trends</span></div><div class="wv-sub">{subtitle}</div></div>
</div><div class="wv-bar"></div>
"""


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
