"""Catalog collector, BSR sales estimator and brand share, with SP-API payloads in the documented shape."""
from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from fba_trends import catalogo, marcas, ventas_bsr
from fba_trends.config import load_config
from fba_trends.sp_api import SPAPIClient, SPAPIError


def item(asin, brand, rank, cat="Pet Supplies", sub_rank=None):
    return {
        "asin": asin,
        "summaries": [{"marketplaceId": "ATVPDKIKX0DER", "brand": brand, "itemName": f"{brand} cooling mat"}],
        "salesRanks": [{"marketplaceId": "ATVPDKIKX0DER",
                        "classificationRanks": [{"classificationId": "1", "title": "Dog Beds", "rank": sub_rank or rank // 50}],
                        "displayGroupRanks": [{"websiteDisplayGroup": "pet_products_display_on_website",
                                               "title": cat, "rank": rank}]}],
    }


def offers_resp(asin, price, sellers, amazon=False, status=200):
    offers = [{"SellerId": f"S{i}", "IsFulfilledByAmazon": i % 2 == 0} for i in range(sellers)]
    if amazon:
        offers.append({"SellerId": catalogo.AMAZON_SELLER_ID, "IsFulfilledByAmazon": True})
    return {"status": {"statusCode": status},
            "request": {"uri": f"/products/pricing/v0/items/{asin}/offers"},
            "body": {"payload": {"ASIN": asin, "Summary": {
                "TotalOfferCount": len(offers),
                "BuyBoxPrices": [{"condition": "New", "LandedPrice": {"Amount": price, "CurrencyCode": "USD"}}],
                "LowestPrices": [{"condition": "new", "fulfillmentChannel": "Amazon",
                                  "LandedPrice": {"Amount": price - 1}}]},
                "Offers": offers}}}


def test_parse_catalog_item_takes_main_category_bsr():
    r = catalogo.parse_catalog_item(item("B000000001", "Arf Pets", 1200))
    assert r == {"asin": "B000000001", "titulo": "Arf Pets cooling mat", "marca": "Arf Pets",
                 "categoria": "Pet Supplies", "bsr_categoria": 1200, "subcategoria": "Dog Beds", "bsr_subcategoria": 24}


def test_parse_catalog_item_without_ranks():
    r = catalogo.parse_catalog_item({"asin": "B000000009", "summaries": [{"brand": "X"}]})
    assert r["bsr_categoria"] is None and r["marca"] == "X"


def test_parse_offers_buybox_sellers_and_amazon():
    out = catalogo.parse_offers([offers_resp("B000000001", 29.99, 3, amazon=True),
                                 offers_resp("B000000002", 10, 1, status=400)])
    assert out == {"B000000001": {"precio": 29.99, "vendedores": 4, "vendedores_fba": 3, "amazon_vende": True}}


class FakeClient:
    def __init__(self):
        self.sleep = Mock()
        self.offer_calls = 0

    def catalog_page(self, keyword, page_size=20, page_token=None):
        return [item("B000000001", "Arf Pets", 1000), item("B000000002", "Pecute", 5000)], None

    def catalog_by_asins(self, asins):
        return [item(a, "Top Brand", 300) for a in asins]

    def item_offers_batch(self, asins):
        self.offer_calls += 1
        return [offers_resp(a, 30.0, 2) for a in asins]


def test_collect_keyword_merges_search_and_top10():
    client = FakeClient()
    df, warnings = catalogo.collect_keyword(client, "dog cooling mat", ["B000000002", "B000000003"],
                                            today=date(2026, 11, 4))
    assert warnings == []
    assert df["asin"].tolist() == ["B000000001", "B000000002", "B000000003"]
    assert df["origen"].tolist() == ["busqueda", "busqueda+top10", "top10"]
    assert (df["precio"] == 30.0).all() and (df["fecha"] == "2026-11-04").all()
    assert client.offer_calls == 1


def test_collect_keyword_keeps_catalog_when_pricing_fails():
    client = FakeClient()
    client.item_offers_batch = Mock(side_effect=SPAPIError("sin rol Pricing"))
    df, warnings = catalogo.collect_keyword(client, "dog cooling mat")
    assert len(df) == 2 and df["precio"].isna().all()
    assert warnings and "Pricing" in warnings[0]


def test_save_replaces_same_day_keyword(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "CATALOG_DIR", tmp_path)
    df, _ = catalogo.collect_keyword(FakeClient(), "a", today=date(2026, 11, 4))
    catalogo.save(df)
    catalogo.save(df)  # re-run same day: no duplicates
    other, _ = catalogo.collect_keyword(FakeClient(), "b", today=date(2026, 11, 4))
    catalogo.save(other)
    loaded = catalogo.load()
    assert len(loaded) == 4
    assert catalogo.collected_on("2026-11-04") == {"a", "b"}
    assert (tmp_path / "2026-11.csv").exists()


def test_latest_keeps_last_snapshot_per_keyword():
    df = pd.DataFrame({"keyword": ["a", "a", "b"], "fecha": ["2026-10-01", "2026-11-01", "2026-10-15"], "asin": [1, 2, 3]})
    assert catalogo.latest(df)["asin"].tolist() == [2, 3]


# ---------------------------------------------------------------- estimator
CFG = {"ventas_bsr": {"factor_sobre_minimo": 1.0, "min_puntos_calibracion": 8,
                      "por_defecto": {"a": 1_000_000, "b": 0.85},
                      "categorias": {"Pet Supplies": {"a": 650_000, "b": 0.85}}}}


def test_prior_curve_and_bad_bsr():
    c = ventas_bsr.prior(CFG, "Pet Supplies")
    assert c.units(1000) == pytest.approx(650_000 * 1000 ** -0.85)
    assert c.units(None) is None and c.units(0) is None and c.units("x") is None
    assert ventas_bsr.prior(CFG, "Desconocida").a == 1_000_000


def pairs_from(a, b, bsrs):
    return pd.DataFrame({"asin": [f"B{i:09d}" for i in range(len(bsrs))], "categoria": "Pet Supplies",
                         "bsr": bsrs, "unidades": [a * x ** -b for x in bsrs]})


def test_fit_recovers_curve_with_enough_points():
    base = ventas_bsr.prior(CFG, "Pet Supplies")
    c = ventas_bsr.fit(pairs_from(2_000_000, 0.9, [200, 500, 1000, 3000, 8000, 15000, 40000, 90000]), base, 8)
    assert c.fuente == "calibrado (n=8)"
    assert c.b == pytest.approx(0.9, abs=1e-6) and c.a == pytest.approx(2_000_000, rel=1e-6)


def test_fit_clamps_slope_and_rescales_with_few_points():
    base = ventas_bsr.prior(CFG, "Pet Supplies")
    steep = ventas_bsr.fit(pairs_from(1e9, 2.0, [100, 300, 1000, 3000, 9000, 20000, 50000, 80000]), base, 8)
    assert steep.b == ventas_bsr.B_RANGE[1]
    few = ventas_bsr.fit(pairs_from(1_300_000, 0.85, [1000, 5000, 20000]), base, 8)
    assert few.fuente == "ajustado (n=3)" and few.b == 0.85 and few.a == pytest.approx(1_300_000)
    assert ventas_bsr.fit(pairs_from(1, 1, [10]), base, 8) is base


def test_calibration_pairs_join_badge_with_latest_bsr():
    snaps = pd.DataFrame({"asin": ["A", "A", "B"], "fecha": ["2026-10-01", "2026-11-01", "2026-11-01"],
                          "categoria": "Pet Supplies", "bsr_categoria": [900, 1000, 5000]})
    comp = pd.DataFrame({"asin": ["A", "B", "C"], "fecha": "2026-10-15", "vendidos_mes": [1000, None, 50]})
    p = ventas_bsr.calibration_pairs(snaps, comp, 1.3)
    assert p.to_dict("records") == [{"asin": "A", "categoria": "Pet Supplies", "bsr": 1000, "unidades": 1300.0}]


def test_real_config_has_priors_flagged_estimated():
    cfg = load_config()
    assert cfg["ventas_bsr"]["estimado"] is True
    assert 500 < ventas_bsr.prior(cfg, "Home & Kitchen").units(1000) < 5000


# ---------------------------------------------------------------- brands
def snapshot():
    rows = [("Arf Pets", 500, 30.0, True), ("Arf Pets", 2000, 25.0, False), ("Pecute", 1000, 20.0, False),
            ("Visit the Pecute Store", 8000, 22.0, False), ("Tiny", 50000, 15.0, False), (None, 90000, 12.0, False)]
    return pd.DataFrame([{"fecha": "2026-11-04", "keyword": "dog cooling mat", "asin": f"B{i:09d}", "marca": m,
                          "categoria": "Pet Supplies", "bsr_categoria": bsr, "precio": p, "vendedores": 2,
                          "vendedores_fba": 1, "amazon_vende": amz} for i, (m, bsr, p, amz) in enumerate(rows)])


def estimator():
    return ventas_bsr.Estimator(CFG, pd.DataFrame(columns=catalogo.COLUMNS), pd.DataFrame())


def test_norm_brand():
    assert marcas.norm_brand("Visit the Pecute Store") == "pecute"
    assert marcas.norm_brand(None) == "(sin marca)"


def test_brands_in_niche_shares_add_up_and_merge_store_names():
    df = marcas.with_estimates(snapshot(), estimator())
    b = marcas.brands_in_niche(df)
    assert b["marca"].iloc[0] == "Arf Pets" and b["listados"].iloc[0] == 2
    assert set(b["marca"]) == {"Arf Pets", "Pecute", "Tiny", "(sin marca)"}
    assert b["cuota_pct"].sum() == pytest.approx(100, abs=0.5)
    assert b.loc[b["marca"] == "Arf Pets", "amazon_vende"].item() is True


def test_niche_metrics_concentration():
    m = marcas.niche_metrics(marcas.with_estimates(snapshot(), estimator()))
    assert m["marcas"] == 4 and m["listados"] == 6
    assert m["marca_lider"] == "Arf Pets" and m["cuota_lider_pct"] > 50
    assert m["hhi"] > 2500 and m["concentracion"] == "Concentrado"
    assert m["marcas_80pct"] == 2 and m["amazon_vende_listados"] == 1
    assert m["pct_ofertas_fba"] == 50.0


@pytest.mark.parametrize("hhi,label", [(None, "Sin datos"), (900, "Fragmentado"), (2000, "Moderado"), (4000, "Concentrado")])
def test_concentration_label(hhi, label):
    assert marcas.concentration_label(hhi) == label


def test_revenue_change_vs_month_before():
    old = snapshot().assign(fecha="2026-10-05")
    new = snapshot().assign(precio=snapshot()["precio"] * 1.1)
    history = pd.concat([old, new], ignore_index=True)
    est = estimator()
    s = marcas.niche_summary(marcas.with_estimates(new, est), history, est)
    assert s["cambio_ingresos_30d_pct"].iloc[0] == pytest.approx(10.0, abs=0.1)
    assert marcas.revenue_change(new, est, "dog cooling mat", "2026-11-04", 100) is None  # one date only


def test_brands_across_niches():
    a = snapshot()
    b = snapshot().assign(keyword="dog bed")
    cross = marcas.brands_across_niches(marcas.with_estimates(pd.concat([a, b]), estimator()))
    assert cross["nichos"].max() == 2 and "(sin marca)" not in set(cross["marca"])


# ---------------------------------------------------------------- client
def client_with(session):
    session.post.return_value.json.return_value = {"access_token": "t", "expires_in": 3600}
    c = SPAPIClient(client_id="id", client_secret="s", refresh_token="r", session=session)
    c.sleep = Mock()
    return c


def test_catalog_by_asins_params_and_validation():
    session = Mock()
    session.request.return_value.status_code = 200
    session.request.return_value.json.return_value = {"items": [{"asin": "B000000001"}]}
    c = client_with(session)
    assert c.catalog_by_asins(["b000000001"])[0]["asin"] == "B000000001"
    params = session.request.call_args.kwargs["params"]
    assert params["identifiersType"] == "ASIN" and params["identifiers"] == "B000000001"
    assert "salesRanks" in params["includedData"]
    with pytest.raises(ValueError):
        c.catalog_by_asins(["B0"] * 21)


def test_offers_batch_body():
    session = Mock()
    session.request.return_value.status_code = 200
    session.request.return_value.json.return_value = {"responses": []}
    client_with(session).item_offers_batch(["B000000001", "B000000002"])
    args, kwargs = session.request.call_args
    assert args[0] == "POST" and args[1].endswith("batches/products/pricing/v0/itemOffers")
    reqs = kwargs["json"]["requests"]
    assert len(reqs) == 2 and reqs[0]["uri"] == "/products/pricing/v0/items/B000000001/offers"


def test_retries_on_429_then_succeeds():
    session = Mock()
    throttled, ok = Mock(status_code=429), Mock(status_code=200)
    ok.json.return_value = {"items": [], "pagination": {"nextToken": "n2"}}
    session.request.side_effect = [throttled, ok]
    c = client_with(session)
    items, token = c.catalog_page("dog bed")
    assert items == [] and token == "n2"
    assert c.sleep.call_count == 1
