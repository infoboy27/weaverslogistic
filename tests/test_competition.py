import pandas as pd
import pytest

from fba_trends import competition as c


def item(asin, sponsored=False, price="DOP 612.90", reviews="(1.2K)", bought="1K+", title="Acme cooling towel"):
    return {"asin": asin, "sponsored": sponsored, "title": title, "price": price,
            "rating": "4.5 out of 5 stars", "reviews": reviews, "bought": bought}


def test_parsers():
    assert c.parse_count("(28.6K)") == pytest.approx(28_600)
    assert c.parse_count("6K+") == 6_000
    assert c.parse_count("(583)") == 583
    assert c.parse_count(None) is None
    assert c.parse_price("$13.99") == 13.99
    assert c.parse_price("DOP 857.66", 61.29) == pytest.approx(13.99, abs=0.01)
    assert c.parse_price("DOP 1,470.71", 61.29) == pytest.approx(24.0, abs=0.01)
    assert c.parse_rating("4.4 out of 5 stars") == 4.4
    with pytest.raises(ValueError):
        c.parse_price("DOP 100")


def test_top10_skips_sponsored_and_duplicates():
    items = [item("A", sponsored=True), item("A"), item("B"), item("B"), item("C", sponsored=True)]
    items += [item(f"X{i}") for i in range(12)]
    df, sponsored = c.from_search_results("cooling towel", items, dop_per_usd=61.29)
    assert sponsored == 2
    assert len(df) == 10
    assert df["asin"].tolist()[:2] == ["A", "B"]
    assert df["posicion"].tolist() == list(range(1, 11))


def frame(reviews, sold, brands=None):
    n = len(reviews)
    return pd.DataFrame({"keyword": ["k"] * n, "resenas": reviews, "vendidos_mes": sold,
                         "precio_usd": [10.0] * n, "rating": [4.5] * n,
                         "marca": brands or [f"b{i}" for i in range(n)]})


def test_verdicts():
    assert c.summarize(frame([20_000] * 10, [1000] * 10))["veredicto"] == "Difícil"
    assert c.summarize(frame([100, 200, 300] + [3000] * 7, [500] * 10))["veredicto"] == "Accesible"
    assert c.summarize(frame([2000] * 10, [100] * 10))["veredicto"] == "Media"


def test_summary_concentration_and_brand():
    s = c.summarize(frame([100] * 4, [6000, 1000, 1000, 2000], brands=["Sukeen", "sukeen", "Other", "X"]))
    assert s["vendidos_mes_top10"] == 10_000
    assert s["pct_ventas_top3"] == 90.0
    assert s["marca_dominante"] == "sukeen" and s["puestos_marca_dominante"] == 2


def test_save_replaces_keyword(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "COMPETITION_PATH", tmp_path / "comp.csv")
    df1, _ = c.from_search_results("a", [item("A1"), item("A2")], 61.29)
    df2, _ = c.from_search_results("b", [item("B1")], 61.29)
    c.save_keyword(df1)
    c.save_keyword(df2)
    df1b, _ = c.from_search_results("a", [item("A9")], 61.29)
    c.save_keyword(df1b)
    out = c.load()
    assert sorted(out["asin"]) == ["A9", "B1"]
