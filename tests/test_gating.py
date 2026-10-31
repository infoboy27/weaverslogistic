from datetime import date
from unittest.mock import Mock

import pandas as pd

from fba_trends import gating
from fba_trends.sp_api import SPAPIClient

SUMMER, Q4 = date(2026, 6, 1), date(2026, 11, 15)


def test_open_categories_are_free():
    for k in ["dog cooling mat", "adhesive shower caddy", "crochet kit", "cat window perch", "dog toy storage",
              "squeaky dog toys bulk", "cable organizer", "bird bath", "sticker"]:
        assert gating.classify(k, SUMMER)[0] == gating.LIBRE, k


def test_gated_rules():
    assert gating.classify("toy story 5", SUMMER)[0] == gating.APROBACION
    assert gating.classify("fifa world cup sticker book", SUMMER)[0] == gating.APROBACION
    assert gating.classify("dog flea collar", SUMMER)[0] == gating.APROBACION
    assert gating.classify("collagen supplement", SUMMER)[0] == gating.APROBACION
    assert gating.classify("diy watch kit", SUMMER)[0] == gating.APROBACION
    assert gating.classify("stanley cup", SUMMER)[0] == gating.APROBACION
    assert gating.classify("pet wipes", SUMMER)[0] == gating.REVISAR


def test_toys_depend_on_season_but_pet_toys_do_not():
    assert gating.classify("diy squishy kit", SUMMER)[0] == gating.LIBRE
    assert gating.classify("diy squishy kit", Q4)[0] == gating.REVISAR
    assert gating.classify("cat toy", Q4)[0] == gating.LIBRE


def _inputs():
    ranking = pd.DataFrame({"keyword": ["dog cooling mat", "yoga mat", "pet parlor pet grooming llc", "toy story 5"],
                            "categoria": ["mascotas", "control", "descubierto: mascotas", "descubierto: mascotas"],
                            "clasificacion": ["Estacional", "Estable", "Emergente", "Emergente"],
                            "trend_score": [70, 50, 60, 90]})
    universe = pd.DataFrame({"asin": ["B000000001"], "sector": ["hogar"], "subcategoria": ["Bathroom Storage"],
                             "lista": ["Best Sellers"], "rank": [3], "titulo": ["Suction Shower Caddy"],
                             "precio_usd": [19.99], "resenas": [100], "tipo": ["suction shower caddy"]})
    comp = pd.DataFrame({"keyword": ["dog cooling mat"] * 2, "posicion": [1, 2], "asin": ["B000000002", "B000000003"],
                         "titulo": ["Cooling Mat", "Pet Cooling Pad"], "marca": ["x", "y"],
                         "precio_usd": [25.0, 35.0]})
    return gating.products(ranking, universe, comp)


def test_products_merge_sources_and_skip_noise():
    p = _inputs().set_index("producto")
    assert set(p.index) == {"dog cooling mat", "toy story 5", "suction shower caddy"}
    assert p.loc["dog cooling mat", "asins"] == ["B000000002", "B000000003"]
    assert p.loc["dog cooling mat", "precio_ref"] == 30.0


def test_report_estimated_then_verified():
    rep = gating.report(_inputs(), None, SUMMER).set_index("producto")
    assert rep.loc["dog cooling mat", "estado"] == gating.LIBRE
    assert rep.loc["dog cooling mat", "evidencia"] == gating.ESTIMADO
    assert rep.loc["toy story 5", "estado"] == gating.APROBACION

    checked = pd.DataFrame({"asin": ["B000000002", "B000000001"], "estado": ["libre", "restringido"],
                            "motivos": ["", "You need approval"], "fecha": ["2026-10-31"] * 2})
    rep = gating.report(_inputs(), checked, SUMMER).set_index("producto")
    assert rep.loc["dog cooling mat", "evidencia"].startswith(gating.VERIFICADO)
    assert rep.loc["suction shower caddy", "estado"] == gating.APROBACION
    assert rep.loc["suction shower caddy", "motivo"] == "You need approval"


def test_summarize_restrictions():
    assert gating.summarize_restrictions([]) == ("libre", "")
    r = [{"conditionType": "new_new", "reasons": [{"reasonCode": "APPROVAL_REQUIRED", "message": "Need approval"}]}]
    assert gating.summarize_restrictions(r) == ("restringido", "Need approval")
    nf = [{"reasons": [{"reasonCode": "ASIN_NOT_FOUND", "message": "nope"}]}]
    assert gating.summarize_restrictions(nf)[0] == "no_encontrado"


def test_verify_stores_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(gating, "RESTRICTIONS_PATH", tmp_path / "r.csv")
    client = Mock()
    client.listing_restrictions.side_effect = [[], [{"reasons": [{"reasonCode": "APPROVAL_REQUIRED"}]}]]
    df = gating.verify(["B000000002", "B000000001", "B000000002"], client, "SELLER", pause=0)
    assert client.listing_restrictions.call_count == 2
    assert dict(zip(df["asin"], df["estado"])) == {"B000000002": "libre", "B000000001": "restringido"}
    gating.verify(["B000000002"], client, "SELLER", pause=0)  # fresh: not asked again
    assert client.listing_restrictions.call_count == 2


def test_spapi_restrictions_call():
    session = Mock()
    session.post.return_value.json.return_value = {"access_token": "tok", "expires_in": 3600}
    session.get.return_value.json.return_value = {"restrictions": []}
    client = SPAPIClient(client_id="id", client_secret="s", refresh_token="r", session=session)
    assert client.listing_restrictions("b000000001", "SELLER") == []
    params = session.get.call_args.kwargs["params"]
    assert params["asin"] == "B000000001" and params["sellerId"] == "SELLER"
    assert "/listings/2021-08-01/restrictions" in session.get.call_args.args[0]
