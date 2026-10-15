import json

import pandas as pd
import pytest

from fba_trends import keepa

DAY = 24 * 60  # keepa minutes per day


def flat(start_min, values, step=DAY):
    out = []
    for i, v in enumerate(values):
        out += [start_min + i * step, v]
    return out


def fake_product(asin="B0TEST0001"):
    start = 7_000_000  # keepa minutes (~2024)
    csv = [None] * 18
    # BSR: 120 days around 5000, then last 30 days ~2500 (selling more)
    csv[keepa.SALES] = flat(start, [5000] * 120 + [2500] * 30)
    csv[keepa.NEW] = flat(start, [2999] * 100 + [-1] * 5 + [2799] * 45)  # cents, -1 = out of stock
    csv[keepa.COUNT_NEW] = flat(start, [3] * 120 + [6] * 30)
    csv[keepa.RATING] = flat(start, [45], step=DAY)
    csv[keepa.COUNT_REVIEWS] = flat(start, [100, 150, 210], step=50 * DAY)
    return {"asin": asin, "title": "Test product", "brand": "X", "monthlySold": 300, "csv": csv}


def test_keepa_time_matches_documented_example():
    # Keepa docs: 411180 -> 1318510800000 ms
    assert keepa.keepa_minutes_to_datetime([411180])[0] == pd.Timestamp(1318510800, unit="s")


def test_parse_series_scales_and_drops_missing():
    p = fake_product()
    h = keepa.product_history(p)
    assert h["precio_nuevo"].max() == pytest.approx(29.99)
    assert h["precio_nuevo"].isna().sum() == 5
    assert h["rating"].iloc[0] == 4.5
    assert h["precio_amazon"].empty  # index 0 missing -> empty series


def test_metrics_detects_improving_bsr_and_more_sellers():
    m = keepa.metrics(fake_product())
    assert m["bsr_actual"] == 2500
    assert m["bsr_cambio_30v60_pct"] == pytest.approx(-50.0, abs=2)
    assert m["vendedores_cambio_pct"] == pytest.approx(100.0, abs=5)
    assert m["resenas"] == 210
    assert m["precio_actual"] == pytest.approx(27.99)
    assert m["vendidos_mes"] == 300


def test_market_summary_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(keepa, "CACHE_DIR", tmp_path)
    for asin in ["B0A", "B0B"]:
        (tmp_path / f"{asin}.json").write_text(json.dumps(fake_product(asin)))
    s = keepa.market_summary(["B0A", "B0B", "B0MISSING"])
    assert s["n"] == 2
    assert s["resenas_prom"] == 210
    assert s["vendidos_mes_total"] == 600


def test_missing_key_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("KEEPA_API_KEY", raising=False)
    monkeypatch.setattr(keepa, "ROOT", tmp_path)
    monkeypatch.setattr(keepa, "CACHE_DIR", tmp_path / "cache")
    with pytest.raises(keepa.KeepaError, match="KEEPA_API_KEY"):
        keepa.fetch_products(["B0NOTCACHED"])
