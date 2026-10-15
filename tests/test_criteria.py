import pandas as pd

from fba_trends import criteria as cr
from fba_trends.config import load_config

CFG = load_config()

UNIVERSE = pd.DataFrame([
    {"asin": "A", "sector": "mascotas", "lista": "New Releases", "rank": 5, "titulo": "Hammock 1", "precio_usd": 40, "resenas": 3, "tipo": "dog grooming hammock"},
    {"asin": "B", "sector": "mascotas", "lista": "New Releases", "rank": 9, "titulo": "Hammock 2", "precio_usd": 44, "resenas": 12, "tipo": "dog grooming hammock"},
    {"asin": "C", "sector": "mascotas", "lista": "New Releases", "rank": 3, "titulo": "Hammock 3", "precio_usd": 30, "resenas": 98, "tipo": "dog grooming hammock"},
    {"asin": "D", "sector": "hogar", "lista": "Best Sellers", "rank": 1, "titulo": "Caddy", "precio_usd": 26, "resenas": 49537, "tipo": "adhesive shower caddy"},
    {"asin": "E", "sector": "hobby", "lista": "Best Sellers", "rank": 2, "titulo": "Yarn", "precio_usd": 25, "resenas": 3000, "tipo": "chunky chenille yarn"},
])


def test_product_types_flags_launch_clusters():
    t = cr.product_types(UNIVERSE).set_index("tipo")
    assert t.loc["dog grooming hammock", "lanzamientos_nuevos"] == 3
    assert t.loc["dog grooming hammock", "senal"] == "Varios lanzamientos nuevos"
    assert t.loc["adhesive shower caddy", "senal"] == ""


def test_evaluate_states_and_stages():
    types = cr.product_types(UNIVERSE)
    trends = pd.DataFrame([{"keyword": "dog grooming hammock", "clasificacion": "Emergente"},
                           {"keyword": "chunky chenille yarn", "clasificacion": "En declive"}])
    comp = pd.DataFrame([{"keyword": "dog grooming hammock", "precio_mediana": 38.0, "listados_bajo_500_resenas": 6,
                          "vendidos_mes_top10": 2500, "veredicto": "Accesible"}])
    ev = cr.evaluate(types, CFG, trends, None, comp).set_index("tipo")
    assert ev.loc["dog grooming hammock", "estado"] == "Apto"
    assert ev.loc["dog grooming hammock", "etapa_auto"] == "Competencia OK"
    assert ev.loc["chunky chenille yarn", "estado"] == "No apto"            # declining trend
    assert ev.loc["adhesive shower caddy", "estado"] == "Falta dato"        # not scanned yet
    assert ev.loc["adhesive shower caddy", "etapa_auto"] == "Pasa reglas"
    assert ev.loc["dog grooming hammock", "peso"] == "?"                     # always manual


def test_manual_stage_overrides_and_funnel():
    ev = cr.evaluate(cr.product_types(UNIVERSE), CFG)
    pipe = pd.DataFrame([{"tipo": "adhesive shower caddy", "etapa_manual": "Cotizando", "notas": "3 proveedores"}])
    df = cr.with_manual(ev, pipe).set_index("tipo")
    assert df.loc["adhesive shower caddy", "etapa"] == "Cotizando"
    f = cr.funnel_counts(df.reset_index(), None, UNIVERSE).set_index("etapa")["cantidad"]
    assert f["Tipos de producto"] == 3 and f["Cotizando"] == 1 and f["Pasa reglas"] == 3


def test_weight_over_limit_makes_type_not_apt_and_shortlist_order():
    types = cr.product_types(UNIVERSE)
    trends = pd.DataFrame([{"keyword": "dog grooming hammock", "clasificacion": "Emergente"}])
    comp = pd.DataFrame([
        {"keyword": k, "precio_mediana": 30.0, "listados_bajo_500_resenas": 5, "vendidos_mes_top10": 2000,
         "veredicto": "Accesible"} for k in ["dog grooming hammock", "adhesive shower caddy", "chunky chenille yarn"]])
    ev = cr.evaluate(types, CFG, trends, None, comp)
    pipe = pd.DataFrame([{"tipo": "dog grooming hammock", "etapa_manual": "", "notas": "", "peso_kg": "0.49"},
                         {"tipo": "chunky chenille yarn", "etapa_manual": "", "notas": "", "peso_kg": "1.6"}])
    df = cr.with_manual(ev, pipe, CFG).set_index("tipo")
    assert df.loc["dog grooming hammock", "peso"] == "✓"
    assert df.loc["chunky chenille yarn", "estado"] == "No apto"
    best = cr.shortlist(df.reset_index())["tipo"].tolist()
    assert best == ["dog grooming hammock", "adhesive shower caddy"]  # verified trend+weight first; heavy one out


def test_special_opportunities():
    summary = pd.DataFrame([
        {"keyword": "dog toe grips", "vendidos_mes_top10": 10400, "precio_mediana": 39.99},
        {"keyword": "rhinestone kit", "vendidos_mes_top10": 127000, "precio_mediana": 11.99},
        {"keyword": "cat wrestling glove", "vendidos_mes_top10": 3900, "precio_mediana": 28.99},
    ])
    rows = pd.DataFrame([
        {"keyword": "dog toe grips", "marca": "Dr", "rating": 3.1, "vendidos_mes": 2000, "precio_usd": 39.99},
        {"keyword": "dog toe grips", "marca": "DOK", "rating": 4.2, "vendidos_mes": 4000, "precio_usd": 17.99},
        {"keyword": "rhinestone kit", "marca": "TINKRSTUFF", "rating": 4.7, "vendidos_mes": 50000, "precio_usd": 9.99},
        {"keyword": "cat wrestling glove", "marca": "Cat", "rating": 4.3, "vendidos_mes": 1000, "precio_usd": 27.99},
    ])
    out = cr.special_opportunities(summary, rows, CFG).set_index("tipo")
    assert out.loc["dog toe grips", "oportunidad"] == "Clientes insatisfechos"
    assert out.loc["rhinestone kit", "oportunidad"] == "Ola fuerte pero barata"
    assert "cat wrestling glove" not in out.index


def test_no_google_volume_is_unknown_when_amazon_proves_demand():
    types = cr.product_types(UNIVERSE)
    trends = pd.DataFrame([{"keyword": "dog grooming hammock", "clasificacion": "Volumen insuficiente"},
                           {"keyword": "adhesive shower caddy", "clasificacion": "Volumen insuficiente"}])
    comp = pd.DataFrame([{"keyword": "dog grooming hammock", "precio_mediana": 36.0, "listados_bajo_500_resenas": 7,
                          "vendidos_mes_top10": 2600, "veredicto": "Accesible"}])
    ev = cr.evaluate(types, CFG, trends, None, comp).set_index("tipo")
    assert ev.loc["dog grooming hammock", "tendencia"] == "?"           # Amazon demand proven -> unknown
    assert ev.loc["dog grooming hammock", "estado"] == "Falta dato"
    assert ev.loc["adhesive shower caddy", "tendencia"] == "✗"          # no Amazon evidence -> still fails
