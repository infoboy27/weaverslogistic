"""FBA Trends — panel de tendencias, rentabilidad y presupuesto.

Ejecutar:  .venv/Scripts/streamlit run app.py
"""
import math

import pandas as pd
import plotly.express as px
import streamlit as st

import json
from datetime import date

from fba_trends import (alerts, brand, charts, collect, competition, criteria, decision, discovery, keepa,
                        navidad, patterns, seasons)
from fba_trends import calendar as cal
from fba_trends.budget import Candidate, allocate
from fba_trends.config import (DATA_DIR, estimated_assumptions, load_config, load_settings, save_settings,
                               settings_from_config)
from fba_trends.profit import Product, compute, max_landed_cost
from fba_trends.scoring import WEIGHTS, overall
from fba_trends.trends import adjust_for_market, analyze, anomalous_weeks, lead_days

CANDIDATES_PATH = DATA_DIR / "candidates.csv"

st.set_page_config(page_title="Weavers · FBA Trends", page_icon=str(brand.ICON_PATH), layout="wide",
                   initial_sidebar_state="expanded")
from fba_trends.auth import require_login
require_login()
brand.register_plotly_template()
st.markdown(brand.css(), unsafe_allow_html=True)
cfg = load_config(with_settings=True)
SETTINGS = load_settings()


def num(v, default=None):
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


@st.cache_data(show_spinner=False, ttl=600)
def trend_table(keywords: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    glitch = anomalous_weeks(collect.load, collect.cached_keywords())
    for k in keywords:
        s = collect.load(k)
        if s is not None:
            rows.append({"keyword": k, **analyze(s, cfg, exclude=glitch)})
    return adjust_for_market(pd.DataFrame(rows)) if rows else pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl=600)
def pattern_table(keywords: tuple[str, ...]):
    glitch = anomalous_weeks(collect.load, list(keywords))
    rows = [{"keyword": k, **patterns.classify(collect.load(k), glitch, collect.load(k, long=True))}
            for k in keywords if collect.load(k) is not None]
    return pd.DataFrame(rows), glitch


def page_title(title: str, subtitle: str = "") -> None:
    st.markdown(brand.page_title(title, subtitle), unsafe_allow_html=True)


def editor_labels(columns, **overrides) -> dict:
    """Readable headers for st.data_editor without renaming the columns saved to CSV."""
    cfg_ = {c: st.column_config.Column(brand.LABELS.get(c, c)) for c in columns}
    cfg_.update(overrides)
    return cfg_


def split_asins(v) -> list[str]:
    return [a for a in str(v or "").replace(",", " ").replace(";", " ").upper().split() if a and a != "NAN"]

# ---------------------------------------------------------------- Tendencias
def page_trends():
    page_title("Tendencias", "Google Trends: crecimiento real frente al mercado")
    c1, c2 = st.columns([2, 1])
    with c1:
        kw_text = st.text_input("Keywords (en inglés, separadas por coma)", placeholder="heated vest, pool float")
        geo = st.selectbox("País", ["US", "", "MX", "ES", "GB", "CA"], format_func=lambda g: g or "Mundial")
        if st.button("Consultar Google Trends (5 años)", type="primary") and kw_text.strip():
            for kw in [k.strip() for k in kw_text.split(",") if k.strip()]:
                with st.spinner(f"Consultando '{kw}'..."):
                    try:
                        collect.fetch_google_trends(kw, geo=geo)
                        st.success(f"'{kw}' guardado.")
                    except collect.TrendsFetchError as e:
                        st.error(f"{kw}: {e}")
            trend_table.clear()
    with c2:
        up = st.file_uploader("…o sube el CSV descargado de trends.google.com", type="csv")
        if up is not None:
            try:
                for kw, s in collect.parse_trends_csv(up.getvalue().decode("utf-8")).items():
                    collect.save(kw, s)
                    st.success(f"'{kw}' importado ({len(s)} puntos).")
                trend_table.clear()
            except ValueError as e:
                st.error(str(e))

    keywords = tuple(collect.cached_keywords())
    if not keywords:
        st.info("Todavía no hay keywords. Consulta o sube un CSV.")
    else:
        table = trend_table(keywords)
        ranking = DATA_DIR / "ranking.csv"  # written by scripts/rank_keywords.py --volume
        if ranking.exists():
            vol = pd.read_csv(ranking)
            if "volumen_vs_yoga_mat_pct" in vol:
                table = table.merge(vol[["keyword", "volumen_vs_yoga_mat_pct"]], on="keyword", how="left")
        st.markdown(brand.pill("Clasificación"), unsafe_allow_html=True)
        st.dataframe(brand.pretty(table.sort_values("trend_score", ascending=False)), hide_index=True, width="stretch")
        st.caption(
            "Google Trends es interés RELATIVO (0-100), no volumen. Una keyword puede crecer mucho y vender poco: "
            "confirma la demanda en Amazon (Brand Analytics / Keepa) antes de comprar. "
            "Momentum = últimas 8 semanas vs 8 anteriores · YoY = vs mismo periodo del año pasado · "
            "crec_vs_mercado = crecimiento anual dividido por el de keywords de control estables "
            "(yoga mat, backpack, umbrella, water bottle), para descontar cambios generales de Google. "
            "Las semanas donde todas las keywords de control saltan a la vez (error de datos de Google, "
            "p. ej. mar-jun 2026) se excluyen automáticamente."
        )
        st.markdown(brand.pill("Más fuertes por estación y fecha especial vs el año anterior"), unsafe_allow_html=True)
        stable = seasons.season_table({k: collect.load(k) for k in keywords}, today, glitch)
        if stable.empty:
            st.info("Hace falta más historia de Google Trends para comparar estaciones.")
        else:
            comp_sum = competition.summary_table()
            extra = comp_sum[["keyword", "precio_mediana", "vendidos_mes_top10"]] if not comp_sum.empty else None
            c1, c2 = st.columns(2)
            view = c1.segmented_control("Ver", ["Fechas especiales", "Estaciones"], default="Fechas especiales",
                                        key="season_view") or "Fechas especiales"
            order = c2.segmented_control("Ordenar por", ["Cuánto sube en la fecha", "Crecimiento vs año anterior"],
                                         default="Cuánto sube en la fecha", key="season_order")                 or "Cuánto sube en la fecha"
            holidays = view == "Fechas especiales"
            periods = seasons.HOLIDAYS if holidays else seasons.SEASONS
            min_weight = 1.2 if holidays else 1.1
            metric = "crec_vs_mercado_pct" if order.startswith("Crec") else "peso_temporada"
            tops = seasons.top_by_season(stable, min_weight=min_weight, periods=periods, by=metric)
            tabs = st.tabs(list(periods))
            for tab, (season, top) in zip(tabs, tops.items()):
                with tab:
                    if top.empty:
                        st.info("Ningún producto escaneado se concentra en esta fecha todavía.")
                        continue
                    st.caption(f"{top.loc[0, 'periodo']} comparado con {top.loc[0, 'comparado_con']}")
                    top = top.merge(pt[["keyword", "patron"]], on="keyword", how="left")
                    if extra is not None:
                        top = top.merge(extra, on="keyword", how="left")
                    top = top.sort_values(metric, ascending=False).reset_index(drop=True)
                    if metric == "peso_temporada":
                        bars = top.assign(peso_pct=(top["peso_temporada"] - 1) * 100)
                        st.plotly_chart(charts.growth_bars(bars, "peso_pct", f"{season}: % sobre sus semanas normales"),
                                        width="stretch")
                    else:
                        st.plotly_chart(charts.growth_bars(top, metric, f"{season}: crecimiento vs año anterior"),
                                        width="stretch")
                    st.dataframe(brand.pretty(top.drop(columns=["estacion", "grupo", "periodo", "comparado_con"])),
                                 hide_index=True, width="stretch")
            st.caption(
                "Son BÚSQUEDAS en Google, no ventas: no hay ventas históricas sin Keepa. Fechas especiales = las semanas "
                "de compra antes de cada fecha (Navidad 1-24 dic, San Valentín 24 ene-14 feb, Día de la Madre las 3 "
                "semanas previas...). 'Cuánto sube' compara esas semanas con las 6 semanas antes y después (estaciones: "
                "con los 12 meses alrededor), así un producto que creció todo el año no sale en todas las fechas. Cada "
                "producto aparece solo en la fecha donde más sube. Crecimiento = misma ventana del año anterior, "
                "descontando el mercado. Las fechas tapadas por el error de Google de 2026 usan el año anterior. "
                "Términos como 'mothers day gifts' miden la demanda de la fecha, no un producto concreto. Precio y "
                "vendidos/mes son el top 10 de Amazon de hoy."
            )

        pick = st.multiselect("Graficar", keywords, default=list(keywords[:3]))
        if pick:
            df = pd.concat({k: collect.load(k) for k in pick}, axis=1)
            st.plotly_chart(px.line(df, labels={"value": "Interés", "fecha": "", "variable": ""}), width="stretch")

PATTERN_HELP = """
- **Estacional**: sube cada año en la misma época (se indica temporada y fecha comercial del pico).
- **Todo el año**: demanda pareja, sin picos ni temporada. Inventario predecible.
- **Viral**: subió durante semanas (redes sociales, cultura pop) y después cayó a menos de la mitad.
- **Shock de mercado**: saltó de golpe en 1-2 semanas por un evento externo (pánico, huelga, clima,
  estreno) y volvió a la normalidad. Riesgoso: si llegas tarde, te quedas con el inventario.
- **Creciente**: crece más de 30% al año de forma sostenida, sin pico y caída.
- **Subiendo rápido**: los últimos 3 meses duplican el semestre anterior y siguen arriba. Todavía no se
  sabe si se queda (creciente) o se apaga (viral).

Reglas heurísticas, no validadas con ventas. Las semanas con error de datos de Google (feb-jul 2026)
se excluyen; aparecen sombreadas en las mini gráficas.
"""

# ---------------------------------------------------------------- shared: patterns, trends, sectors
today = date.today()
pt, glitch = pattern_table(tuple(collect.cached_keywords()))
_kw_meta = pd.read_csv(DATA_DIR / "keywords.csv")
SECTOR_OF = {r.keyword: str(r.categoria).replace("descubierto: ", "") for r in _kw_meta.itertuples()}
_tt = trend_table(tuple(collect.cached_keywords()))
PRODUCTS = pt.merge(_tt[["keyword", "clasificacion", "crec_vs_mercado_pct"]], on="keyword", how="left")
SECTORS = alerts.sector_table(PRODUCTS, SECTOR_OF)
SECTORS = SECTORS[SECTORS["sector"] != "control"]

# ---------------------------------------------------------------- Lo que viene
def page_next():
    page_title("Lo que viene", "Fechas de venta, temporadas y tendencias en alza")
    st.markdown(brand.pill("Próximas fechas de venta en EE.UU."), unsafe_allow_html=True)
    moments = cal.upcoming_moments(cfg, today)
    st.dataframe(brand.pretty(moments), hide_index=True, width="stretch")
    st.caption(
        f"'Vender desde' = cuándo el producto ya debe estar disponible en Amazon. 'Pedir antes de' resta "
        f"{lead_days(cfg)} días (producción + flete marítimo + recepción en Amazon + rampa). Si ya pasó, esa fecha "
        "solo se alcanza con envío aéreo (mucho más caro) o queda para el año siguiente."
    )

    st.markdown(brand.pill("Tus productos estacionales: cuándo pedir"), unsafe_allow_html=True)
    windows = cal.seasonal_windows(pt, cfg, today)
    if windows.empty:
        st.info("No hay productos estacionales escaneados todavía.")
    else:
        st.plotly_chart(charts.season_timeline(windows, today), width="stretch")
        st.dataframe(brand.pretty(windows), hide_index=True, width="stretch")

    st.markdown(brand.pill("Tendencias crecientes"), unsafe_allow_html=True)
    tt = trend_table(tuple(collect.cached_keywords()))
    rising = tt.merge(pt[["keyword", "patron"]], on="keyword", how="left")
    rising = rising[(rising["crec_vs_mercado_pct"] > 15)
                    & (rising["patron"].isin(["Subiendo rápido", "Creciente", "Estacional", "Todo el año"])
                       | rising["clasificacion"].isin(["Emergente", "Estacional en crecimiento"]))]
    rising = rising.nlargest(15, "crec_vs_mercado_pct")
    if rising.empty:
        st.info("Ninguna keyword crece más de 15% por encima del mercado.")
    else:
        st.plotly_chart(charts.growth_bars(rising, "crec_vs_mercado_pct", "Crecimiento anual vs mercado"),
                        width="stretch")
        top = rising.head(6)["keyword"].tolist()
        st.plotly_chart(charts.small_multiples({k: collect.load(k).iloc[-104:] for k in top}, glitch),
                        width="stretch")
        st.caption(
            "Crecimiento de los últimos 12 meses contra los 12 anteriores, descontando el crecimiento de las "
            "keywords de control. Las modas de cultura pop (series, TikTok) aparecen como 'Subiendo rápido' en "
            "Patrones y las encuentra la pestaña Descubrimientos."
        )

    st.markdown(brand.pill("Sectores que crecen más que el mercado"), unsafe_allow_html=True)
    if SECTORS.empty:
        st.info("Sin datos de sectores todavía.")
    else:
        st.plotly_chart(charts.sector_treemap(PRODUCTS, SECTORS, SECTOR_OF), width="stretch")
        st.caption(
            "Cada bloque es un sector (tamaño = productos analizados, color = crecimiento mediano vs mercado: "
            "cian crece, magenta cae). Haz clic en un sector para ver sus productos; los ganadores aparecen "
            "más claros. Los sectores con 1-2 productos son poco representativos: la pestaña Descubrimientos "
            "los va llenando."
        )
        st.dataframe(brand.pretty(SECTORS), hide_index=True, width="stretch")


# ---------------------------------------------------------------- shared: funnel evaluation
UNIVERSE = pd.read_csv(criteria.UNIVERSE_PATH) if criteria.UNIVERSE_PATH.exists() else pd.DataFrame()
UCOUNTS = pd.read_csv(criteria.COUNTS_PATH) if criteria.COUNTS_PATH.exists() else pd.DataFrame()
COMP_SUM = competition.summary_table()
EV = None
if not UNIVERSE.empty:
    _types = criteria.product_types(UNIVERSE)
    # Candidates that came from the Google side (e.g. dog cooling mat) join the funnel too
    _extra = []
    for _kw in pd.read_csv(CANDIDATES_PATH)["keyword"].dropna().unique():
        if _kw not in set(_types["tipo"]):
            _price = COMP_SUM.set_index("keyword").loc[_kw, "precio_mediana"] if (
                not COMP_SUM.empty and _kw in set(COMP_SUM["keyword"])) else float("nan")
            _extra.append({"tipo": _kw, "sector": SECTOR_OF.get(_kw, "otros"), "listados": 0, "lanzamientos_nuevos": 0,
                           "precio_mediana": _price, "resenas_min": None, "mejor_puesto": None,
                           "ejemplo": "candidato (Google Trends)", "senal": ""})
    _types = pd.concat([_types, pd.DataFrame(_extra)], ignore_index=True).dropna(subset=["precio_mediana"])
    EV = criteria.with_manual(criteria.evaluate(_types, cfg, _tt, pt, COMP_SUM), criteria.load_pipeline(), cfg)

def run_decision(budget: float, max_products: int, mult: float = 1.0, prioridad: str | None = None):
    """Shortlist -> economics -> recommendation (used by Decisión and Inicio)."""
    best = criteria.shortlist(EV)
    cands = pd.read_csv(CANDIDATES_PATH)
    supplier = {}  # keyword -> real quote: landed cost, MOQ, lead time (days, door to Amazon)
    for _, r in cands.iterrows():
        f, fl = pd.to_numeric(r.get("costo_fabrica"), errors="coerce"), pd.to_numeric(r.get("flete_unidad"), errors="coerce")
        moq, lead = pd.to_numeric(r.get("moq"), errors="coerce"), pd.to_numeric(r.get("dias_entrega"), errors="coerce")
        if str(r.get("nombre", "")).startswith("EJEMPLO"):
            continue
        supplier[r["keyword"]] = {
            "real_cost": float(f) + (0.0 if pd.isna(fl) else float(fl)) if pd.notna(f) else None,
            "moq": float(moq) if pd.notna(moq) else None, "lead_days": float(lead) if pd.notna(lead) else None,
        }
    comp_rows = competition.load()
    econ = pd.DataFrame([decision.economics(r, comp_rows[comp_rows["keyword"] == r["tipo"]], cfg, mult,
                                            **supplier.get(r["tipo"], {}))
                         for _, r in best.iterrows()])
    win = cal.seasonal_windows(pt, cfg, today)
    timing = {} if win.empty else {r["keyword"]: (int(r["dias_para_pedir"]), str(r["buscar_proveedor_desde"]))
                                   for _, r in win.iterrows()}
    if econ.empty:
        return {"veredicto": ("ninguno", "No compren nada este mes", "Todavía no hay candidatos que pasen el embudo."),
                "preliminar": True, "opciones": pd.DataFrame(), "asignacion": pd.DataFrame(), "esperar": [],
                "descartados": []}, econ
    return decision.recommend(econ, budget, cfg, max_products, timing, prioridad), econ


def verdict_card(rec: dict) -> None:
    kind, title, text = rec["veredicto"]
    badge = ('<span class="wv-badge">Preliminar · costos estimados (sin cotización)</span>'
             if rec["preliminar"] else '<span class="wv-badge ok">Con costos reales</span>')
    st.markdown(f'<div class="wv-verdict {kind}"><div class="wv-v-label">Recomendación {badge}</div>'
                f'<div class="wv-v-title">{title}</div><div class="wv-v-text">{text}</div></div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------- Decisión
def page_decision():
    page_title("Decisión", "Qué comprar este mes y cómo dividir el presupuesto")
    if EV is None:
        st.info("Primero hace falta el universo de Amazon (pestaña Embudo).")
    else:
        d1, d2, d3, d4 = st.columns(4)
        dec_budget = d1.number_input("Presupuesto total (USD)", min_value=1000, max_value=50_000, value=int(SETTINGS["presupuesto_usd"]),
                                     step=250, key="dec_budget")
        dec_max = d2.slider("Máximo de productos a considerar", 1, 5, 3, key="dec_max")
        dec_esc = d3.select_slider("Escenario de ventas", ["Pesimista", "Base", "Optimista"], value="Base",
                                   key="dec_esc")
        mult = {"Pesimista": 0.5, "Base": 1.0, "Optimista": 1.5}[dec_esc]
        prio_modes = {"GMROI": "gmroi", "Rotación": "rotacion", "Ganancia": "ganancia"}
        default_mode = cfg["decision"].get("prioridad", {}).get("valor", "gmroi")
        default_prio = next(k for k, v in prio_modes.items() if v == default_mode)
        prio = d4.segmented_control(
            "Priorizar por", list(prio_modes), default=default_prio, key="dec_prio",
            help="GMROI = dólares de margen al año por cada dólar en inventario (margen × rotación), recomendado. "
                 "Rotación = unidades/mes de un vendedor nuevo. Ganancia = filtro de margen y mayor ganancia mensual.",
        ) or default_prio
        mode = prio_modes[prio]
        by_units = mode == "rotacion"

        rec, econ = run_decision(float(dec_budget), dec_max, mult, mode)

        verdict_card(rec)

        alloc = rec["asignacion"]
        if not alloc.empty:
            invested = float((alloc["inversion_inventario"] + alloc["costo_lanzamiento"]).sum())
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Invertido", f"${invested:,.0f}")
            k2.metric("Reserva", f"${dec_budget - invested:,.0f}")
            horizon = cfg['decision']['horizonte_meses']['valor']
            if by_units:
                k3.metric(f"Unidades vendidas en {horizon} meses", f"{alloc['unidades_horizonte'].sum():,.0f}")
            else:
                k3.metric(f"Ganancia esperada {horizon} meses", f"${alloc['ganancia_horizonte'].sum():,.0f}")
            k4.metric("Ganancia mensual proyectada", f"${alloc['ganancia_mes_proy'].sum():,.0f}")
            for r in alloc.itertuples():
                if r.condicion:
                    st.warning(f"**{r.producto}**: su margen queda bajo el mínimo con el costo supuesto. "
                               f"{r.condicion} (fábrica + flete por unidad) para ganar "
                               f"{cfg['supuestos']['margen_neto_minimo']['valor']:.0%}. Pide esa cotización primero.",
                               icon=":material/request_quote:")
            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown(brand.pill("Cómo dividir el presupuesto"), unsafe_allow_html=True)
                st.plotly_chart(charts.allocation_bar(alloc, dec_budget - invested), width="stretch")
            with c2:
                st.markdown(brand.pill("Opciones comparadas"), unsafe_allow_html=True)
                chosen = len(alloc)
                st.plotly_chart(charts.options_bar(rec["opciones"], chosen), width="stretch")
            st.markdown(brand.pill("Plan de compra"), unsafe_allow_html=True)
            st.dataframe(brand.pretty(alloc[["producto", "precio_sugerido", "unidades", "inversion_inventario",
                                             "costo_lanzamiento", "ventas_mes_proy", "unidades_horizonte",
                                             "condicion", "meses_de_stock_est",
                                             "ganancia_mes_proy", "ganancia_horizonte", "ganancia_esperada_si_vende_todo",
                                             "recupera_inversion_meses", "confianza"]]),
                         hide_index=True, width="stretch")

        if rec["esperar"]:
            st.markdown(brand.pill("Todavía no (estacionales)"), unsafe_allow_html=True)
            st.dataframe(brand.pretty(pd.DataFrame(rec["esperar"], columns=["producto", "motivo"])),
                         hide_index=True, width="stretch")

        ranking = rec.get("ranking", pd.DataFrame())
        if not ranking.empty:
            st.markdown(brand.pill(f"Plan de operación · {ranking.loc[0, 'tipo']}"), unsafe_allow_html=True)
            top = ranking.iloc[0]
            o1, o2, o3, o4 = st.columns(4)
            o1.metric("Primer pedido", f"{top['pedido_unidades']:,} u.",
                      help="Max(pedido mínimo, 2 meses de venta) + stock de seguridad.")
            o2.metric("Reponer cuando queden", f"{top['punto_reorden']:,} u.",
                      help="Punto de reorden = venta diaria × días de entrega + stock de seguridad.")
            o3.metric("Stock de seguridad", f"{top['stock_seguridad']:,} u.",
                      help=f"Z × variabilidad × √días de entrega, para {cfg['inventario']['nivel_servicio']['valor']:.0%} "
                           "de probabilidad de no quedarse sin stock.")
            o4.metric("GMROI", f"{top['gmroi']:.1f}", help="Dólares de margen al año por cada dólar en inventario.")
            inv = cfg["inventario"]
            cov = top["cobertura_inicial_dias"]
            band = (f"El primer pedido cubre ~{cov} días: " +
                    ("dentro de la zona sana de FBA." if inv["cobertura_min_dias"]["valor"] <= cov <= inv["cobertura_max_dias"]["valor"]
                     else f"fuera de la zona sana de FBA ({inv['cobertura_min_dias']['valor']}–{inv['cobertura_max_dias']['valor']} "
                          "días): manda a Amazon solo una parte y guarda el resto con el forwarder."))
            steps = [
                band,
                f"Precio {top['precio_sugerido']:.2f} (terminado en 9, bajo el umbral del dólar siguiente).",
                "Meta: 5 reseñas lo antes posible (Amazon Vine + solicitar reseña en Seller Central). Es la palanca de "
                "conversión más fuerte.",
                "Publicidad al lanzar para ganar velocidad; el costo de publicidad sobre la venta total (TACoS) debe "
                "bajar mes a mes.",
                f"Nunca quedarse sin stock: al llegar a {top['punto_reorden']:,} unidades, pedir de nuevo "
                f"(entrega de {top['dias_entrega']:.0f} días).",
            ]
            if top["oportunidades"]:
                steps.append(f"Oportunidad: {top['oportunidades']}.")
            if top["riesgos"]:
                steps.append(f"Riesgo: {top['riesgos']}.")
            st.markdown("\n".join(f"{i}. {t}" for i, t in enumerate(steps, 1)))
            if top["proveedor_estimado"]:
                st.caption(f"Pedido mínimo ({top['moq']:.0f} u.) y entrega ({top['dias_entrega']:.0f} días) son supuestos: "
                           "cárgalos con la cotización en Productos y rentabilidad (columnas moq y dias_entrega).")

            label = {"gmroi": " por GMROI", "rotacion": " por rotación", "ganancia": " por ganancia"}[mode]
            st.markdown(brand.pill("Ranking de candidatos" + label), unsafe_allow_html=True)
            nicho = COMP_SUM.set_index("keyword")["vendidos_mes_top10"] if not COMP_SUM.empty else pd.Series(dtype=float)
            ranking = ranking.assign(vendidos_mes_top10=ranking["tipo"].map(nicho))
            cols = ["tipo", "gmroi", "rotacion_anual", "ventas_mes_proy", "vendidos_mes_top10", "precio_sugerido",
                    "costo_puesto", "costo_objetivo", "margen_pct", "ganancia_mes_proy", "pedido_unidades", "punto_reorden",
                    "condicion", "riesgos", "oportunidades", "confianza", "empate_con_el_1", "falta_verificar"]
            ranking.insert(0, "puesto", range(1, len(ranking) + 1))
            st.dataframe(brand.pretty(ranking[["puesto", *cols]]), hide_index=True, width="stretch")
            ties = int(ranking["empate_con_el_1"].sum())
            if ties > 1:
                st.caption(f"{ties} candidatos están a menos de 20% del primero: es un empate técnico con los datos "
                           "actuales. La cotización real (costo, pedido mínimo y entrega) decide.")
        elif not econ.empty:
            st.dataframe(brand.pretty(econ), hide_index=True, width="stretch")
        if rec["descartados"]:
            with st.expander(f"Descartados por el cerebro ({len(rec['descartados'])})"):
                st.dataframe(brand.pretty(pd.DataFrame(rec["descartados"], columns=["producto", "motivo"])),
                             hide_index=True, width="stretch")
        d = cfg["decision"]
        st.caption(
            f"Cómo decide: precio sugerido = mediana del top 10 de Amazon (terminado en .99). Costo = cotización real si "
            f"la cargaste en Productos y rentabilidad; si no, {d['costo_pct_precio']['valor']:.0%} del precio (estimado). "
            + {"gmroi": "Prioridad GMROI: margen anual ÷ inventario promedio a costo (pedido/2 + stock de seguridad), o sea "
                         "margen × rotación; descarta bajo el GMROI mínimo. ",
               "rotacion": "Prioridad ROTACIÓN: ordena por unidades/mes que vendería un vendedor nuevo. ",
               "ganancia": "Prioridad GANANCIA: descarta lo que no llega al margen mínimo y ordena por ganancia mensual. "}[mode]
            + "Siempre descarta: lo que pierde dinero, un pedido mínimo de más de "
            f"{cfg['inventario']['cobertura_max_dias']['valor']} días de venta y una cotización por encima del costo objetivo. "
            + f"Ventas/mes = lo que venden hoy los listados nuevos (<500 reseñas) del top 10 × "
            f"{d['captura_nuevo_vendedor']['valor']:.0%} × escenario. Confianza baja por cada dato sin verificar "
            f"(tendencia, peso, costo). Prueba 1 a {dec_max} productos con las reglas del presupuesto (reserva, "
            f"lanzamiento, MOQ {d['moq_por_defecto']['valor']} u., máximo de meses de stock) y elige la opción que más vende (o más gana) "
            f"ajustada por confianza; solo suma productos si mejora al menos {d['mejora_minima_para_diversificar']['valor']:.0%}. "
            "Es una guía para decidir, no una garantía: valida con cotizaciones y muestras."
        )

# ---------------------------------------------------------------- Embudo
def page_funnel():
    page_title("Embudo", "De miles de productos de Amazon a tus mejores candidatos")
    universe, ucounts, comp_sum, ev = UNIVERSE, UCOUNTS, COMP_SUM, EV
    if ev is None:
        st.info("Todavía no hay universo de Amazon capturado.")
    else:

        e = ev["estado"].value_counts()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Listados revisados", f"{int(ucounts['total'].sum()):,}" if not ucounts.empty else "-")
        m2.metric("Tipos de producto", len(ev))
        m3.metric("Aptos", int(e.get("Apto", 0)))
        m4.metric("Falta dato", int(e.get("Falta dato", 0)))
        m5.metric("No aptos", int(e.get("No apto", 0)))

        st.markdown(brand.pill("Mejores candidatos"), unsafe_allow_html=True)
        best = criteria.shortlist(ev)
        if best.empty:
            st.info("Ningún tipo pasa todavía precio, competencia y demanda.")
        else:
            st.dataframe(brand.pretty(best[["tipo", "sector", "estado", "precio_ref", "precio", "competencia",
                                            "demanda", "tendencia", "peso", "peso_kg", "competencia_detalle",
                                            "tendencia_detalle", "notas"]]),
                         hide_index=True, width="stretch")
            st.caption("Pasan precio ($20-50), competencia (3+ del top 10 con <500 reseñas) y demanda (1,000+ "
                       "vendidos/mes). Primero los que ya tienen tendencia y peso verificados. "
                       "Peso: se carga en 'Tu pipeline' (kg).")

        specials = criteria.special_opportunities(comp_sum, competition.load(), cfg)
        if not specials.empty:
            st.markdown(brand.pill("Oportunidades especiales"), unsafe_allow_html=True)
            st.dataframe(brand.pretty(specials), hide_index=True, width="stretch")
            st.caption("Casos que las reglas normales no muestran: un líder con clientes insatisfechos, o una ola "
                       "fuerte donde solo una versión premium cumple el precio mínimo.")

        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown(brand.pill("Embudo"), unsafe_allow_html=True)
            st.plotly_chart(charts.funnel_chart(criteria.funnel_counts(ev, ucounts, universe)), width="stretch")
        with c2:
            st.markdown(brand.pill("Por qué se descartan"), unsafe_allow_html=True)
            if not ucounts.empty:
                st.plotly_chart(charts.rejection_bars(ucounts), width="stretch")
                st.caption("Best Sellers + New Releases de las subcategorías elegidas (top 30 de cada lista). "
                           "El precio es el filtro más duro: la mayoría de lo que más se vende cuesta menos de $20.")

        st.markdown(brand.pill("Tipos de producto"), unsafe_allow_html=True)
        order = {"Apto": 0, "Falta dato": 1, "No apto": 2}
        view = ev.assign(_o=ev["estado"].map(order)).sort_values(
            ["_o", "lanzamientos_nuevos", "listados"], ascending=[True, False, False])
        cols = ["tipo", "sector", "estado", "etapa", "senal", "listados", "lanzamientos_nuevos", "precio_ref",
                "precio", "tendencia", "competencia", "demanda", "peso", "tendencia_detalle", "competencia_detalle",
                "ejemplo"]
        st.dataframe(brand.pretty(view[cols]), hide_index=True, width="stretch", height=420)
        st.caption(
            "✓ pasa · ✗ no pasa · ? falta dato. Tendencia: se completa sola con el escaneo diario de Google Trends "
            "(~10 tipos por día). Competencia y demanda: se completan con la captura del top 10 de Amazon "
            "(pestaña Competencia). Peso: siempre manual, con la ficha del proveedor. Criterios en config.yaml."
        )

        st.markdown(brand.pill("Tu pipeline"), unsafe_allow_html=True)
        st.caption("Marca a mano cuando un producto pasa a cotización, muestra o pedido (o lo descartas).")
        editable = ev[["tipo", "etapa_auto", "etapa_manual", "peso_kg", "notas"]].sort_values("etapa_auto", key=lambda s: s.map(
            {x: i for i, x in enumerate(criteria.STAGES)}), ascending=False)
        edited_pipe = st.data_editor(
            editable, hide_index=True, width="stretch", key="pipe_editor",
            disabled=["tipo", "etapa_auto"],
            column_config={
                "tipo": st.column_config.Column("Producto"),
                "etapa_auto": st.column_config.Column("Etapa automática"),
                "etapa_manual": st.column_config.SelectboxColumn("Etapa manual", options=criteria.MANUAL_STAGES),
                "peso_kg": st.column_config.TextColumn("Peso (kg)"),
                "notas": st.column_config.TextColumn("Notas"),
            },
        )
        if st.button("Guardar pipeline"):
            filled = edited_pipe[["etapa_manual", "notas", "peso_kg"]].fillna("").astype(str).ne("").any(axis=1)
            edited_pipe[filled][criteria.PIPELINE_COLUMNS].to_csv(criteria.PIPELINE_PATH, index=False)
            st.success("Guardado.")

# ---------------------------------------------------------------- Alertas
def page_alerts():
    page_title("Alertas", "Plazos, oportunidades y lo que conviene descartar")
    _disc = discovery.load()
    _rank_path = DATA_DIR / "ranking.csv"
    if not _disc.empty and _rank_path.exists():
        _disc = _disc.merge(pd.read_csv(_rank_path)[["keyword", "finalista"]], left_on="termino",
                            right_on="keyword", how="left")
    ALERTS = alerts.build(PRODUCTS, cal.seasonal_windows(pt, cfg, today), cal.upcoming_moments(cfg, today),
                          SECTORS, _disc, today)
    by_type = ALERTS["tipo"].value_counts() if not ALERTS.empty else pd.Series(dtype=int)
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("Prioridad alta", int((ALERTS["prioridad"] == "Alta").sum()) if not ALERTS.empty else 0)
    a2.metric("Plazos", int(by_type.get("Plazo", 0)))
    a3.metric("Oportunidades", int(by_type.get("Oportunidad", 0)))
    a4.metric("Descartar", int(by_type.get("Descartar", 0)))
    a5.metric("Sectores", int(by_type.get("Sector", 0)))
    sections = [
        ("Plazo", "Plazos que se acercan",
         "Fechas límite para buscar proveedor o pedir a fábrica (próximos 6 meses)."),
        ("Oportunidad", "Oportunidades con momentum",
         "Productos subiendo rápido, crecimiento sostenido, estacionales en alza y descubrimientos nuevos."),
        ("Descartar", "Descartar",
         "Bajando, ya pasaron su pico, sin volumen o temporada perdida este año."),
        ("Sector", "Sectores", "Sectores que crecen o caen frente al mercado, con sus productos ganadores."),
    ]
    for tipo, title, desc in sections:
        st.markdown(brand.pill(title), unsafe_allow_html=True)
        st.caption(desc)
        part = ALERTS[ALERTS["tipo"] == tipo].drop(columns="tipo") if not ALERTS.empty else pd.DataFrame()
        if part.empty:
            st.caption("Nada por ahora.")
        else:
            st.dataframe(brand.pretty(part), hide_index=True, width="stretch")
    st.caption("Reglas heurísticas, no validadas con ventas. Se recalculan con cada actualización de datos "
               "(el descubrimiento diario corre a las 10:00).")

# ---------------------------------------------------------------- Patrones
def page_pat():
    page_title("Patrones", "Estacional, todo el año, viral o shock de mercado")
    pt_ok = pt[pt["patron"] != "Volumen insuficiente"]
    counts = pt_ok["patron"].value_counts()
    cols = st.columns(6)
    for col, name in zip(cols, ["Estacional", "Todo el año", "Viral", "Shock de mercado", "Creciente",
                                "Subiendo rápido"]):
        col.metric("Shock" if name == "Shock de mercado" else name, int(counts.get(name, 0)))
    with st.expander("Cómo se define cada patrón"):
        st.markdown(PATTERN_HELP)

    st.markdown(brand.pill("Calendario estacional"), unsafe_allow_html=True)
    seasonal = pt_ok[pt_ok["patron"] == "Estacional"]
    if not seasonal.empty:
        heat = pd.DataFrame({k: patterns.month_heat(collect.load(k), glitch) for k in seasonal["keyword"]}).T
        heat = heat.iloc[heat.values.argmax(axis=1).argsort(kind="stable")]
        labels = seasonal.set_index("keyword")["festividad"].fillna("").to_dict()
        heat.index = [f"{k} · {labels[k]}" if labels.get(k) else k for k in heat.index]
        st.plotly_chart(charts.season_heatmap(heat), width="stretch")
        st.caption("Cada fila es un producto; cada celda, cuánto se busca ese mes comparado con un mes promedio "
                   "(más claro = temporada alta). Ordenado por mes pico.")

    st.markdown(brand.pill("Mapa de patrones"), unsafe_allow_html=True)
    st.plotly_chart(charts.pattern_map(pt_ok), width="stretch")
    st.caption("Derecha = se repite cada año. Arriba = picos y caídas fuertes. Abajo a la izquierda = demanda pareja.")

    st.markdown(brand.pill("Ejemplos por patrón"), unsafe_allow_html=True)
    available = [p for p in patterns.PATTERNS if p in set(pt_ok["patron"])]
    sel = st.segmented_control("Patrón", available, default=available[0] if available else None,
                               label_visibility="collapsed")
    if sel:
        ks = pt_ok[pt_ok["patron"] == sel].sort_values("crec_anual_pct", ascending=False)["keyword"].head(9).tolist()
        st.plotly_chart(charts.small_multiples({k: collect.load(k) for k in ks}, glitch), width="stretch")
        longs = {k: s for k in ks if (s := collect.load(k, long=True)) is not None}
        if longs:
            st.caption("Historial largo (mensual desde 2004):")
            st.plotly_chart(charts.small_multiples(longs, pd.DatetimeIndex([])), width="stretch")
        st.caption("Zona sombreada = semanas con error de datos de Google, excluidas del análisis.")

    st.markdown(brand.pill("Todos los productos"), unsafe_allow_html=True)
    st.dataframe(brand.pretty(pt.sort_values(["patron", "keyword"])), hide_index=True, width="stretch")

# ---------------------------------------------------------------- Descubrimientos
def page_disc():
    page_title("Descubrimientos", "Búsquedas en aumento detectadas cada día")
    disc = discovery.load()
    seeds = pd.read_csv(discovery.SEEDS_PATH)
    state_path = DATA_DIR / "discovery_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"seed_log": {}, "runs": []}
    counts = disc["estado"].value_counts() if not disc.empty else pd.Series(dtype=int)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Semillas exploradas", f"{len(state['seed_log'])} / {len(seeds)}")
    m2.metric("Términos útiles", int(counts.get("pendiente", 0) + counts.get("escaneado", 0)))
    m3.metric("Escaneados", int(counts.get("escaneado", 0)))
    m4.metric("Pendientes", int(counts.get("pendiente", 0)))
    if state["runs"]:
        last = state["runs"][-1]
        st.caption(
            f"Última corrida: {last['fecha']} · {last['semillas']} semillas · {last['nuevos']} términos nuevos · "
            f"{last['escaneados']} escaneados" + (" · Google bloqueó, sigue mañana" if last["bloqueado"] else "")
        )
    st.caption(
        "Cada día se consultan las búsquedas 'en aumento' (últimos 12 meses, EE.UU.) de unas pocas categorías semilla "
        "y se escanean los términos nuevos con el mismo análisis de Tendencias. Google limita las consultas, por eso "
        "avanza de a poco. Semillas en data/seeds.csv. Corrida manual: .venv/Scripts/python -m scripts.discover"
    )
    if disc.empty:
        st.info("Todavía no hay descubrimientos. Se llenará con la primera corrida.")
    else:
        ranking_path = DATA_DIR / "ranking.csv"
        if ranking_path.exists():
            rk = pd.read_csv(ranking_path)[["keyword", "clasificacion", "trend_score", "crec_vs_mercado_pct",
                                            "volumen_vs_yoga_mat_pct", "finalista"]]
            disc = disc.merge(rk, left_on="termino", right_on="keyword", how="left").drop(columns="keyword")
        useful = disc[disc["estado"] != "filtrado"].sort_values(
            ["finalista", "trend_score", "subida_pct"], ascending=False, na_position="last")
        st.markdown(brand.pill("Términos descubiertos"), unsafe_allow_html=True)
        st.dataframe(brand.pretty(useful), hide_index=True, width="stretch")
        with st.expander(f"Filtrados automáticamente ({int(counts.get('filtrado', 0))})"):
            st.dataframe(brand.pretty(disc[disc["estado"] == "filtrado"][["termino", "seed", "motivo"]]),
                         hide_index=True, width="stretch")

# ---------------------------------------------------------------- Competencia
def page_comp():
    page_title("Competencia", "Top 10 de Amazon por producto")
    with st.expander("Qué revisar en los primeros 10 resultados de Amazon", expanded=False):
        st.markdown("""
Busca la keyword en amazon.com y mira los **10 primeros resultados orgánicos** (sin 'Sponsored'):

1. **Reseñas**: tu listado empieza en 0. Si casi todos tienen miles, es muy difícil entrar.
   Que haya **3 o más con menos de 500** significa que los nuevos sí llegan a la primera página.
2. **'X+ bought in past month'**: es el dato de ventas de Amazon (un mínimo). Súmalo para ver el tamaño del nicho.
3. **Concentración**: si el top 3 se lleva más del 70% de esas ventas, o una marca ocupa varios puestos,
   el nicho está dominado.
4. **Precio**: la mediana es el precio de mercado. Si es muy bajo (<$12), las tarifas de FBA se comen el margen.
5. **Rating**: un promedio bajo (<4.2) es una **oportunidad**: lee las reseñas de 1-3 estrellas,
   ahí está lo que tu producto debe mejorar.
6. **Anuncios**: muchos 'Sponsored' en la página = el PPC va a ser caro.

El veredicto (Accesible / Media / Difícil) es una regla heurística, no validada.
La 'marca' se toma de la primera palabra del título y puede fallar en productos genéricos.
""")
    comp = competition.load()
    if comp.empty:
        st.info("Todavía no hay datos de competencia. Agrégalos abajo o con `scripts/ingest_search.py`.")
    else:
        st.markdown(brand.pill("Resumen por keyword"), unsafe_allow_html=True)
        st.dataframe(brand.pretty(competition.summary_table(comp)), hide_index=True, width="stretch")
        st.caption("Vendidos/mes top 10 suma los 'X+ bought in past month' (mínimos); los listados sin ese dato cuentan 0.")
    st.markdown(brand.pill("Top 10 orgánico (editable)"), unsafe_allow_html=True)
    edited_comp = st.data_editor(
        comp if not comp.empty else pd.DataFrame(columns=competition.COLUMNS),
        num_rows="dynamic", width="stretch", key="comp_editor",
        column_config=editor_labels(competition.COLUMNS),
    )
    if st.button("Guardar competencia"):
        edited_comp.to_csv(competition.COMPETITION_PATH, index=False)
        st.success("Guardado.")

# ---------------------------------------------------------------- Navidad
def page_xmas():
    page_title("Navidad", "Qué productos de regalo pasan los criterios y cuándo hay que pedirlos")
    summary = competition.summary_table()
    pl = criteria.load_pipeline()
    weights = dict(zip(pl["tipo"], pd.to_numeric(pl["peso_kg"], errors="coerce"))) if "peso_kg" in pl else {}
    weights = {k: v for k, v in weights.items() if v == v}
    rt = navidad.routes(cfg, today)
    ev = navidad.evaluate(summary, cfg, weights)

    st.markdown(brand.pill("Las dos rutas"), unsafe_allow_html=True)
    st.dataframe(brand.pretty(rt), hide_index=True, width="stretch")
    air = cfg["navidad"]["aereo"]
    st.caption(
        f"Aire = compra de stock listo {air['compra_y_preparacion']} d + flete {air['flete_aereo']} d + recepción de "
        f"Amazon en Q4 {air['recepcion_amazon_q4']} d, a ~${air['costo_usd_kg']['valor']:.0f}/kg (todo estimado, ver "
        "config.yaml `navidad`). Sin cuenta de vendedor activa la ruta aérea no es posible."
    )
    if ev.empty:
        st.info("No hay búsquedas navideñas capturadas todavía.")
        return

    passing = ev[ev["pasa"]]
    c1, c2, c3 = st.columns(3)
    c1.metric("Productos evaluados", len(ev))
    c2.metric("Pasan los criterios", len(passing))
    c3.metric("Viables por aire este año", int((passing["costo_max_aire"] >= 3).sum()),
               help="Pasan los criterios y aún dejan al menos $3 por unidad para fábrica después del flete aéreo.")

    heat = {}
    for k in ev["keyword"]:
        s = collect.load(k)
        if s is not None:
            heat[k] = round(float(patterns.month_heat(s, glitch)["dic"]), 2)
    ev["diciembre_vs_mes_medio"] = ev["keyword"].map(heat)

    st.markdown(brand.pill("Candidatos de Navidad"), unsafe_allow_html=True)
    show = ev.drop(columns=["pasa"])
    st.dataframe(brand.pretty(show), hide_index=True, width="stretch")
    st.caption(
        "Costo máx. = lo máximo que puedes pagar por unidad (fábrica + flete) y aún ganar "
        f"{cfg['supuestos']['margen_neto_minimo']['valor']:.0%} neto al precio mediano. 'Aire' ya le resta el flete aéreo "
        "(0.5 kg si no hay peso cargado en el Embudo → peso supuesto). Diciembre vs mes medio sale de Google Trends "
        "(1.0 = un mes normal), solo para keywords escaneadas. Ventas = suma de 'bought in past month' del top 10 "
        "en octubre; en diciembre suelen ser varias veces más."
    )
    with st.expander("Cómo leer esto"):
        st.markdown("""
- **Los productos navideños puros** (adornos, kits, mascotas) se venden casi todos a **$10-16**: después de tarifas
  de Amazon no queda margen, y menos con flete aéreo.
- **Los regalos que pasan los criterios** tienen precio de $20-50 y venden todo el año con pico en diciembre:
  es mejor apuesta que un producto que solo vende 6 semanas (el sobrante no se queda en el almacén pagando Q1).
- **Para este año**, solo tiene sentido si tu cuenta ya está activa y encuentras stock listo a un costo por
  debajo de la columna 'costo máx. aire'. Si no, la Navidad del año que viene por mar es la ruta.
""")

# ---------------------------------------------------------------- Keepa
def page_keepa():
    page_title("Amazon · Keepa", "Historial de ventas y precio (requiere clave de Keepa)")
    if keepa.api_key():
        st.success("Clave de Keepa configurada.")
    else:
        st.warning(
            "Falta la clave de Keepa. Copia `.env.example` como `.env` en la carpeta del proyecto, "
            "pon `KEEPA_API_KEY=tu_clave` y reinicia el panel. Clave en keepa.com → API (suscripción de pago)."
        )
    st.write(
        "Pega ASINs (los 10 primeros resultados de Amazon para tu keyword) o búscalos por término. "
        "Cada ASIN consume tokens de Keepa; los datos se guardan y solo se vuelven a pedir pasadas 24 h."
    )
    term = st.text_input("Buscar top 10 en Amazon US por término (consume tokens extra)")
    if st.button("Buscar ASINs") and term.strip():
        try:
            st.session_state["asin_text"] = " ".join(keepa.search_asins(term.strip()))
        except keepa.KeepaError as e:
            st.error(str(e))
    asin_text = st.text_area("ASINs", key="asin_text", placeholder="B0XXXXXXXX B0YYYYYYYY ...")
    if st.button("Traer historial de Keepa", type="primary") and split_asins(asin_text):
        with st.spinner("Consultando Keepa..."):
            try:
                res = keepa.fetch_products(split_asins(asin_text))
                left = res["tokens_left"]
                st.success(f"{len(res['products'])} productos ({res['consultados']} consultados a la API)"
                           + (f" · tokens restantes: {left}" if left is not None else ""))
            except keepa.KeepaError as e:
                st.error(str(e))

    asins = keepa.cached_asins()
    if asins:
        st.markdown(brand.pill("Productos consultados"), unsafe_allow_html=True)
        st.dataframe(brand.pretty(pd.DataFrame([keepa.metrics(keepa.load_cached(a)) for a in asins])),
                     hide_index=True, width="stretch")
        st.caption(
            "BSR: menor = vende más. Cambio BSR % negativo = está vendiendo MÁS que en los 60 días previos. "
            "Vendidos/mes es el dato de Amazon 'comprado el mes pasado'; muchos productos no lo tienen."
        )
        pick = st.selectbox("Ver historial", asins)
        hist = keepa.product_history(keepa.load_cached(pick))
        c1, c2 = st.columns(2)
        if hist["bsr"].notna().any():
            fig = px.line(hist["bsr"].dropna(), title="BSR (más abajo en la gráfica = mejor)",
                          labels={"value": "BSR", "index": ""})
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(showlegend=False)
            c1.plotly_chart(fig, width="stretch")
        prices = pd.concat([hist["precio_nuevo"], hist["precio_amazon"]], axis=1).dropna(how="all")
        if not prices.empty:
            c2.plotly_chart(px.line(prices, title="Precio (USD)", labels={"value": "USD", "index": "", "variable": ""}),
                            width="stretch")

def product_results(edited: pd.DataFrame):
    """Unit economics + score for every candidate row (Productos and Presupuesto pages)."""
    trends_by_kw = trend_table(tuple(collect.cached_keywords())).set_index("keyword") if collect.cached_keywords() else None
    comp_by_kw = competition.summary_table()
    comp_by_kw = comp_by_kw.set_index("keyword") if not comp_by_kw.empty else None
    rows, pending = [], []
    for _, r in edited.iterrows():
        price, cost = num(r.get("precio_venta")), num(r.get("costo_fabrica"))
        if not r.get("nombre"):
            continue
        if price is None or cost is None:
            if price is not None:
                cap = max_landed_cost(Product(sale_price=price, unit_cost=0, freight_per_unit=0,
                                              fba_fee=num(r.get("fba_fee")),
                                              size_tier=r.get("size_tier") or "large_standard_1lb",
                                              cuft_per_unit=num(r.get("cuft_unidad"), 0.1)), cfg)
                pending.append({"producto": r["nombre"], "precio_venta": price,
                                "costo_max_puesto_en_amazon": cap})
            else:
                pending.append({"producto": r["nombre"], "precio_venta": None, "costo_max_puesto_en_amazon": None})
            continue
        econ = compute(
            Product(
                sale_price=price,
                unit_cost=cost,
                freight_per_unit=num(r.get("flete_unidad"), 0.0),
                fba_fee=num(r.get("fba_fee")),
                size_tier=r.get("size_tier") or "large_standard_1lb",
                cuft_per_unit=num(r.get("cuft_unidad"), 0.1),
            ),
            cfg,
        )
        kw = r.get("keyword") if isinstance(r.get("keyword"), str) else None
        trend = trends_by_kw.loc[kw] if trends_by_kw is not None and kw in trends_by_kw.index else None
        t_score = num(trend["trend_score"]) if trend is not None else None
        reviews, reviews_src = num(r.get("resenas_top10")), "manual"
        market = keepa.market_summary(split_asins(r.get("asins_competidores")))
        comp_row = comp_by_kw.loc[kw] if comp_by_kw is not None and kw in comp_by_kw.index else None
        if reviews is None and market and market["resenas_prom"] is not None:
            reviews, reviews_src = market["resenas_prom"], f"Keepa ({market['n']} ASINs)"
        if reviews is None and comp_row is not None and pd.notna(comp_row["resenas_mediana"]):
            reviews, reviews_src = comp_row["resenas_mediana"], "Competencia (mediana top 10)"
        sc = overall(t_score, econ["margen_pct"], reviews)
        rows.append({
            "nombre": r["nombre"],
            "score": sc["score"],
            "tendencia": trend["clasificacion"] if trend is not None else "sin datos",
            "resenas_competencia": None if reviews is None else round(reviews),
            "fuente_resenas": reviews_src if reviews is not None else "",
            "precio_mediana_mercado": market["precio_mediana"] if market
            else (comp_row["precio_mediana"] if comp_row is not None else None),
            "vendidos_mes_mercado": market["vendidos_mes_total"] if market
            else (comp_row["vendidos_mes_top10"] if comp_row is not None else None),
            "competencia": comp_row["veredicto"] if comp_row is not None else "sin datos",
            "bsr_cambio_mercado_pct": market["bsr_cambio_mediana_pct"] if market else None,
            **{k: v for k, v in econ.items() if k != "campos_estimados"},
            "datos_estimados": ", ".join(econ["campos_estimados"]),
            "datos_faltantes_score": ", ".join(sc["faltantes"]),
            "_moq": int(num(r.get("moq"), 1)),
            "_ventas_mes": num(r.get("ventas_mes_est"), 0.0),
        })
    results = pd.DataFrame(rows)
    return results, pending


# ---------------------------------------------------------------- Productos
def page_products():
    page_title("Productos y rentabilidad", "Costos, márgenes y costo máximo por producto")
    st.write(
        "Edita los candidatos. Deja la tarifa FBA vacía para usar la estimación por tamaño (se marcará como estimado). "
        "Reseñas top 10 = reseñas típicas de los 10 primeros resultados de Amazon; si lo dejas vacío se toma "
        "de la pestaña Competencia (por keyword) o de los ASINs competidores consultados en Keepa."
    )
    raw = pd.read_csv(CANDIDATES_PATH)
    edited = st.data_editor(
        raw,
        num_rows="dynamic",
        width="stretch",
        column_config=editor_labels(
            raw.columns,
            size_tier=st.column_config.SelectboxColumn(
                brand.LABELS["size_tier"], options=list(cfg["fees"]["fba_fee_por_tier"]["valores"].keys())
            ),
        ),
    )
    if st.button("Guardar candidatos"):
        edited.to_csv(CANDIDATES_PATH, index=False)
        st.success("Guardado.")

    results, pending = product_results(edited)
    if pending:
        st.markdown(brand.pill("Pendientes de cotización"), unsafe_allow_html=True)
        st.dataframe(brand.pretty(pd.DataFrame(pending)), hide_index=True, width="stretch")
        st.caption(
            f"Costo máximo (fábrica + flete + aranceles, por unidad) para llegar a "
            f"{int(cfg['supuestos']['margen_neto_minimo']['valor']*100)}% de margen neto con las tarifas estimadas. "
            "Úsalo como tope al pedir cotizaciones."
        )
    if not results.empty:
        st.markdown(brand.pill("Rentabilidad por unidad y score"), unsafe_allow_html=True)
        st.dataframe(
            brand.pretty(results.drop(columns=["_moq", "_ventas_mes"]).sort_values("score", ascending=False)),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            f"Score = {int(WEIGHTS['tendencia']*100)}% tendencia + {int(WEIGHTS['margen']*100)}% margen + "
            f"{int(WEIGHTS['competencia']*100)}% competencia. Pesos heurísticos, no validados. "
            "Si falta un componente se usa 50 (neutral) y aparece en `datos_faltantes_score`."
        )

# ---------------------------------------------------------------- Presupuesto
def page_budget():
    page_title("Presupuesto", "Reparto del capital con reglas de riesgo")
    budget = st.number_input("Presupuesto total (USD)", min_value=500, max_value=100_000,
                             value=int(SETTINGS["presupuesto_usd"]), step=250)
    results, _ = product_results(pd.read_csv(CANDIDATES_PATH))
    if results.empty:
        st.info("Agrega candidatos con costo en Productos y rentabilidad.")
    else:
        cands = [
            Candidate(
                name=r["nombre"],
                score=r["score"],
                landed_cost=r["costo_puesto"],
                net_profit=r["ganancia_neta"],
                moq=r["_moq"],
                est_monthly_units=r["_ventas_mes"],
            )
            for _, r in results.iterrows()
        ]
        plan = allocate(cands, float(budget), cfg)
        m1, m2, m3 = st.columns(3)
        m1.metric("Invertido (inventario + lanzamiento)", f"${plan['gastado']:,.0f}")
        m2.metric("Reserva (PPC, imprevistos, recompra)", f"${plan['reserva']:,.0f}")
        m3.metric("Productos seleccionados", len(plan["asignacion"]))
        if plan["asignacion"]:
            st.dataframe(brand.pretty(pd.DataFrame(plan["asignacion"])), hide_index=True, width="stretch")
        if plan["rechazados"]:
            st.markdown(brand.pill("No seleccionados"), unsafe_allow_html=True)
            st.dataframe(brand.pretty(pd.DataFrame(plan["rechazados"])), hide_index=True, width="stretch")
        b = cfg["presupuesto"]
        st.caption(
            f"Reglas: reserva {int(b['reserva_pct']['valor']*100)}%, máx. {b['max_productos']['valor']} productos, "
            f"máx. {b['meses_de_prueba']['valor']} meses de ventas estimadas en la primera orden, "
            f"${b['costo_lanzamiento_por_producto']['valor']} de lanzamiento por producto. Editable en config.yaml. "
            "'Ganancia esperada' asume que se vende todo al precio indicado."
        )

# ---------------------------------------------------------------- Supuestos
def page_assumptions():
    page_title("Supuestos", "Valores estimados que conviene verificar")
    st.write("Estos valores son **aproximaciones** y deben verificarse antes de comprar inventario:")
    st.dataframe(brand.pretty(pd.DataFrame(estimated_assumptions(cfg))), hide_index=True, width="stretch")
    st.write(
        "- Las filas de candidatos marcadas *EJEMPLO FICTICIO* no son datos reales.\n"
        "- La tarifa FBA exacta por producto sale del **FBA Revenue Calculator** de Amazon.\n"
        "- El costo de fábrica y el flete deben venir de cotizaciones reales (proveedor + forwarder)."
    )


# ---------------------------------------------------------------- Inicio
def page_home():
    name = SETTINGS.get("nombre_negocio") or ""
    page_title(f"Hola{', ' + name if name else ''}", f"Resumen de hoy · {today:%d/%m/%Y}")
    rec, _ = run_decision(float(SETTINGS["presupuesto_usd"]), int(cfg["presupuesto"]["max_productos"]["valor"]) + 1)
    verdict_card(rec)
    al = alerts.build(PRODUCTS, cal.seasonal_windows(pt, cfg, today), cal.upcoming_moments(cfg, today), SECTORS,
                      discovery.load(), today)
    best = criteria.shortlist(EV) if EV is not None else pd.DataFrame()
    moments = cal.upcoming_moments(cfg, today)
    nxt = moments[moments["dias_para_pedir"] >= 0].head(1)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analizados", f"{len(EV) if EV is not None else 0}")
    k2.metric("Candidatos", f"{len(best)}")
    k3.metric("Alertas altas", f"{int((al['prioridad'] == 'Alta').sum()) if not al.empty else 0}")
    k4.metric("Próximo pedido", nxt["pedir_antes_de"].iloc[0].strftime("%d/%m") if not nxt.empty else "-",
              nxt["momento"].iloc[0] if not nxt.empty else None, delta_color="off")

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown(brand.pill("Mejores candidatos"), unsafe_allow_html=True)
        if best.empty:
            st.info("Todavía no hay candidatos.")
        else:
            st.dataframe(brand.pretty(best.head(6)[["tipo", "sector", "precio_ref", "tendencia", "peso",
                                                     "competencia_detalle"]]), hide_index=True, width="stretch")
        st.page_link(PAGES["funnel"], label="Ver el embudo completo", icon=":material/arrow_forward:")
    with c2:
        st.markdown(brand.pill("Alertas"), unsafe_allow_html=True)
        if al.empty:
            st.caption("Nada por ahora.")
        else:
            top = al[al["prioridad"].isin(["Alta", "Media"])].head(6)
            for _, r in top.iterrows():
                st.markdown(brand.alert_row(r["prioridad"], r["tipo"], r["elemento"], r["accion"]),
                            unsafe_allow_html=True)
        st.page_link(PAGES["alerts"], label="Ver todas las alertas", icon=":material/arrow_forward:")


# ---------------------------------------------------------------- Ajustes
def page_settings():
    page_title("Ajustes", "Tu negocio, tu presupuesto y tus reglas para elegir productos")
    eff = settings_from_config(load_config(), load_settings())
    with st.form("settings"):
        st.markdown(brand.pill("Tu negocio"), unsafe_allow_html=True)
        a1, a2 = st.columns(2)
        nombre = a1.text_input("Nombre del negocio", eff.get("nombre_negocio", ""))
        budget = a2.number_input("Presupuesto para inventario (USD)", 500, 100_000, int(eff["presupuesto_usd"]), 250)
        all_sectors = sorted(set(SECTOR_OF.values()) - {"control", "otros"})
        sectores = st.multiselect("Sectores en los que te enfocas", all_sectors,
                                  [x for x in eff.get("sectores", []) if x in all_sectors])

        st.markdown(brand.pill("Criterios de producto"), unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        pmin = b1.number_input("Precio mínimo (USD)", 5, 200, int(eff["precio_min"]))
        pmax = b2.number_input("Precio máximo (USD)", 10, 500, int(eff["precio_max"]))
        peso = b3.number_input("Peso máximo (kg)", 0.1, 20.0, float(eff["peso_max_kg"]), 0.1)
        b4, b5, b6 = st.columns(3)
        low = b4.number_input("Mín. competidores con <500 reseñas (top 10)", 0, 10, int(eff["min_listados_bajo_500_resenas"]))
        dem = b5.number_input("Mín. ventas/mes del top 10", 0, 100_000, int(eff["min_vendidos_mes_top10"]), 100)
        marg = b6.number_input("Margen neto mínimo (%)", 0, 80, int(round(float(eff["margen_neto_minimo"]) * 100)))

        st.markdown(brand.pill("Reglas de presupuesto"), unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        res = c1.number_input("Reserva (%)", 0, 80, int(round(float(eff["reserva_pct"]) * 100)))
        maxp = c2.number_input("Máx. productos a la vez", 1, 10, int(eff["max_productos"]))
        months = c3.number_input("Meses de stock en la 1ª orden", 1, 12, int(eff["meses_de_prueba"]))
        launch = c4.number_input("Costo de lanzamiento por producto (USD)", 0, 5000, int(eff["costo_lanzamiento_por_producto"]), 50)

        st.markdown(brand.pill("Supuestos del cerebro"), unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        cost = d1.number_input("Costo estimado (% del precio) sin cotización", 5, 80, int(round(float(eff["costo_pct_precio"]) * 100)))
        cap = d2.number_input("Captura de un vendedor nuevo (%)", 5, 200, int(round(float(eff["captura_nuevo_vendedor"]) * 100)))
        moq = d3.number_input("MOQ típico del proveedor (unidades)", 1, 10_000, int(eff["moq_por_defecto"]), 10)

        if st.form_submit_button("Guardar ajustes", type="primary"):
            save_settings({
                "nombre_negocio": nombre, "presupuesto_usd": int(budget), "sectores": sectores,
                "precio_min": int(pmin), "precio_max": int(pmax), "peso_max_kg": float(peso),
                "min_listados_bajo_500_resenas": int(low), "min_vendidos_mes_top10": int(dem),
                "margen_neto_minimo": marg / 100, "reserva_pct": res / 100, "max_productos": int(maxp),
                "meses_de_prueba": int(months), "costo_lanzamiento_por_producto": int(launch),
                "costo_pct_precio": cost / 100, "captura_nuevo_vendedor": cap / 100, "moq_por_defecto": int(moq),
            })
            st.cache_data.clear()
            st.success("Ajustes guardados. Toda la plataforma ya usa tus reglas.")
            st.rerun()
    st.caption("Se guardan en data/settings.yaml y se aplican encima de la configuración base (config.yaml).")


# ---------------------------------------------------------------- Amazon Selling Partner API
def page_spapi():
    page_title("Amazon Seller Central", "Catálogo oficial SP-API · datos de tu cuenta autorizada")
    from fba_trends.sp_api import SPAPIClient, SPAPIError, configured
    if not configured():
        st.warning("Amazon SP-API todavía no está conectado. Configura las credenciales privadas del servidor.")
        st.caption("Consulta PRODUCTION.md para el alta de la aplicación privada en Seller Central.")
        return
    kw = st.text_input("Buscar en el catálogo Amazon US", placeholder="dog cooling mat")
    if st.button("Consultar catálogo oficial", type="primary") and kw.strip():
        with st.spinner("Consultando catálogo..."):
            try:
                items = SPAPIClient().search_catalog(kw).get("items", [])
                if items and __import__("os").getenv("DATABASE_URL"):
                    try:
                        from fba_trends.store import SnapshotStore
                        store = SnapshotStore()
                        store.initialize()
                        store.save(organization_id="default", actor_email=str(getattr(st.user, "email", "local-test")),
                                   source="amazon_spapi_catalog", query=kw,
                                   payload={"items": items})
                        st.caption("Consulta guardada en PostgreSQL para auditoría.")
                    except Exception:
                        st.warning("La búsqueda funcionó, pero no se pudo guardar el historial de auditoría.")
                if items:
                    st.dataframe(pd.DataFrame([{
                        "ASIN": item.get("asin"),
                        "Título": (item.get("summaries") or [{}])[0].get("itemName", ""),
                        "Marca": (item.get("summaries") or [{}])[0].get("brand", ""),
                    } for item in items]), hide_index=True, width="stretch")
                else:
                    st.info("No hay productos para esa búsqueda.")
            except (SPAPIError, ValueError) as e:
                st.error(str(e))
    st.caption("El catálogo no incluye automáticamente ventas de competidores. Para evaluar demanda "
               "se cruzan fuentes autorizadas y estimaciones etiquetadas con su nivel de confianza.")


# ---------------------------------------------------------------- navigation
PAGES = {
    "home": st.Page(page_home, url_path="inicio", title="Inicio", icon=":material/space_dashboard:", default=True),
    "decision": st.Page(page_decision, url_path="decision", title="Decisión", icon=":material/psychology:"),
    "funnel": st.Page(page_funnel, url_path="embudo", title="Embudo", icon=":material/filter_alt:"),
    "next": st.Page(page_next, url_path="lo-que-viene", title="Lo que viene", icon=":material/event_upcoming:"),
    "xmas": st.Page(page_xmas, url_path="navidad", title="Navidad", icon=":material/redeem:"),
    "alerts": st.Page(page_alerts, url_path="alertas", title="Alertas", icon=":material/notifications:"),
    "disc": st.Page(page_disc, url_path="descubrimientos", title="Descubrimientos", icon=":material/travel_explore:"),
    "pat": st.Page(page_pat, url_path="patrones", title="Patrones", icon=":material/insights:"),
    "trends": st.Page(page_trends, url_path="tendencias", title="Tendencias", icon=":material/trending_up:"),
    "comp": st.Page(page_comp, url_path="competencia", title="Competencia", icon=":material/storefront:"),
    "spapi": st.Page(page_spapi, url_path="amazon-seller", title="Amazon Seller Central", icon=":material/verified:"),
    "keepa": st.Page(page_keepa, url_path="keepa", title="Amazon · Keepa", icon=":material/query_stats:"),
    "products": st.Page(page_products, url_path="productos", title="Productos y rentabilidad", icon=":material/payments:"),
    "budget": st.Page(page_budget, url_path="presupuesto", title="Presupuesto", icon=":material/account_balance_wallet:"),
    "settings": st.Page(page_settings, url_path="ajustes", title="Ajustes", icon=":material/tune:"),
    "assumptions": st.Page(page_assumptions, url_path="supuestos", title="Supuestos", icon=":material/rule:"),
}
st.logo(str(brand.LOGO_PATH), size="large", icon_image=str(brand.ICON_PATH))
nav = st.navigation({
    "": [PAGES["home"], PAGES["decision"]],
    "Descubrir": [PAGES["funnel"], PAGES["next"], PAGES["xmas"], PAGES["alerts"], PAGES["disc"], PAGES["pat"], PAGES["trends"]],
    "Mercado": [PAGES["comp"], PAGES["keepa"], PAGES["spapi"]],
    "Plan": [PAGES["products"], PAGES["budget"]],
    "Configuración": [PAGES["settings"], PAGES["assumptions"]],
}, expanded=True)  # show every section; otherwise Streamlit folds them behind "View N more"


def last_data_update() -> str:
    """Newest modification time among the data files the dashboard reads."""
    files = [*(DATA_DIR / "trends").glob("*.csv"), DATA_DIR / "competition.csv", DATA_DIR / "discovery.csv",
             DATA_DIR / "ranking.csv", DATA_DIR / "candidates.csv", DATA_DIR / "pipeline.csv"]
    stamps = [f.stat().st_mtime for f in files if f.exists()]
    if not stamps:
        return "sin datos"
    from datetime import datetime
    return datetime.fromtimestamp(max(stamps)).strftime("%d/%m/%Y %H:%M")


with st.sidebar:
    st.markdown('<div class="wv-side-spacer"></div>', unsafe_allow_html=True)
    if st.button("Actualizar datos", icon=":material/refresh:", width="stretch", key="refresh_data",
                 help="Vuelve a leer todos los datos (escaneos, competencia, pipeline) sin reiniciar el servidor."):
        st.cache_data.clear()
        st.toast("Datos actualizados", icon=":material/check_circle:")
        st.rerun()
    st.caption(f"Datos al {last_data_update()}")

nav.run()
