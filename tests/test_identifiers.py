from unittest.mock import Mock

import pandas as pd

from fba_trends import gating, identifiers
from fba_trends.sp_api import SPAPIClient


def test_codes_and_matching():
    assert identifiers.same_code("036000291452", "0036000291452")  # UPC-A inside EAN-13
    assert not identifiers.same_code("036000291452", "036000291453")
    assert identifiers.looks_like_code("036000291452") and identifiers.looks_like_code("0036000291452")
    assert not identifiers.looks_like_code("B0GG6G94F2") and not identifiers.looks_like_code("dog bed")
    assert identifiers.matches("Dog Bed", "orthopedic dog bed", "", "")
    assert identifiers.matches("b0gg6g94", "x", "B0GG6G94F2 B000000001", "")
    assert identifiers.matches("0036000291452", "x", "", "123456789012 036000291452")
    assert identifiers.matches("291452", "x", "", "036000291452")  # partial barcode
    assert not identifiers.matches("999999999999", "x", "", "036000291452")


def test_parsers():
    k = identifiers.from_keepa({"asin": "b000000001", "upcList": ["036000291452"], "eanList": ["0036000291452"],
                                "title": "Mat"})
    assert (k["asin"], k["upc"], k["ean"], k["fuente"]) == ("B000000001", "036000291452", "0036000291452", "Keepa")
    item = {"asin": "B000000002", "summaries": [{"itemName": "Bed"}], "identifiers": [{
        "marketplaceId": "ATVPDKIKX0DER",
        "identifiers": [{"identifierType": "UPC", "identifier": "111111111111"},
                        {"identifierType": "EAN", "identifier": "0111111111111"},
                        {"identifierType": "UPC", "identifier": "111111111111"}]}]}
    s = identifiers.from_spapi(item)
    assert (s["upc"], s["ean"], s["titulo"]) == ("111111111111", "0111111111111", "Bed")


def test_fetch_with_keepa_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(identifiers, "PATH", tmp_path / "ids.csv")
    monkeypatch.setattr(identifiers, "source", lambda: "Keepa")
    calls = []

    def fake(asins, max_age_hours):
        calls.append(list(asins))
        return {"products": {a: {"asin": a, "upcList": [f"0000000000{i}"]} for i, a in enumerate(asins)}}
    monkeypatch.setattr(identifiers.keepa, "fetch_products", fake)
    df = identifiers.fetch(["B000000001", "B000000002", "B000000001"])
    assert len(df) == 2 and calls == [["B000000001", "B000000002"]]
    identifiers.fetch(["B000000001", "B000000003"])
    assert calls[-1] == ["B000000003"]  # fresh ones are not asked again
    # leading zeros survive the CSV; the same code twice is listed once
    assert identifiers.codes_for(["B000000001", "B000000003"], identifiers.load()) == "00000000000"
    assert identifiers.codes_for(["B000000002"], identifiers.load()) == "00000000001"


def test_fetch_without_source(monkeypatch):
    monkeypatch.setattr(identifiers, "source", lambda: None)
    try:
        identifiers.fetch(["B000000001"])
    except identifiers.NoSource:
        return
    raise AssertionError("expected NoSource")


def test_report_has_upc_column():
    prods = pd.DataFrame([{"producto": "dog cooling mat", "sector": "mascotas", "subcategoria": "",
                           "asins": ["B000000002", "B000000003"], "titulos": ""}])
    ids = pd.DataFrame([{"asin": "B000000002", "upc": "036000291452", "ean": "", "titulo": "", "fecha": "", "fuente": ""},
                        {"asin": "B000000003", "upc": "", "ean": "4006381333931", "titulo": "", "fecha": "", "fuente": ""}])
    rep = gating.report(prods, None, None, ids)
    assert rep.loc[0, "upc"] == "036000291452 4006381333931"
    assert gating.report(prods).loc[0, "upc"] == ""


def test_spapi_find_by_code():
    session = Mock()
    session.post.return_value.json.return_value = {"access_token": "tok", "expires_in": 3600}
    session.get.return_value.json.return_value = {"items": [{"asin": "B000000001"}]}
    client = SPAPIClient(client_id="id", client_secret="s", refresh_token="r", session=session)
    assert client.find_by_code("036000291452")[0]["asin"] == "B000000001"
    params = session.get.call_args.kwargs["params"]
    assert params["identifiers"] == "036000291452" and params["identifiersType"] == "UPC"
    client.get_item("b000000001")
    assert session.get.call_args.args[0].endswith("/catalog/2022-04-01/items/B000000001")
