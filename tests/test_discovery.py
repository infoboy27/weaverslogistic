from datetime import date

import pandas as pd

from fba_trends import discovery as d


def rising(*pairs):
    return pd.DataFrame(pairs, columns=["query", "value"])


def test_junk_filter_on_real_examples():
    # Actual rising queries Google returned for "dog accessories"
    assert d.junk_reason("satamatkaa.com dog accessories", "dog accessories") == "dominio web"
    assert d.junk_reason("dog accessories near me", "dog accessories") is not None
    assert d.junk_reason("cute dog accessories", "dog accessories") is None
    assert d.junk_reason("dog", "dog accessories") == "demasiado genérico"
    assert d.junk_reason("petsmart dog bed", "dog bed") is not None


def test_clean_drops_years_and_filler():
    assert d.clean("Best Dog Cooling Mat 2026") == "dog cooling mat"


def test_add_rising_dedupes_flags_breakout_and_skips_known():
    table = pd.DataFrame(columns=d.COLUMNS)
    r = rising(("cooling dog bed", 5000), ("Cooling Dog Bed 2026", 300), ("dog bed near me", 200),
               ("orthopedic dog bed", 250), ("dog cooling mat", 900))
    table, new = d.add_rising(table, "dog bed", "mascotas", r, known_keywords={"dog cooling mat"},
                              today=date(2026, 10, 15))
    assert new == 2  # cooling dog bed + orthopedic dog bed
    assert sorted(table["termino"]) == ["cooling dog bed", "dog bed near me", "orthopedic dog bed"]
    assert bool(table.loc[table["termino"] == "cooling dog bed", "breakout"].iloc[0])
    assert table.loc[table["termino"] == "dog bed near me", "estado"].iloc[0] == "filtrado"
    assert d.next_to_scan(table, 5)[0] == "cooling dog bed"  # breakout first


def test_seeds_due_oldest_first(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds.csv"
    seeds.write_text("seed,categoria\na,x\nb,x\nc,x\n", encoding="utf-8")
    monkeypatch.setattr(d, "SEEDS_PATH", seeds)
    log = {"a": "2026-10-10", "b": "2026-08-01"}
    due = d.seeds_due(log, every_days=30, today=date(2026, 10, 15))
    assert [s for s, _ in due] == ["c", "b"]  # never-run first, then the oldest; "a" is recent


def test_reviews_and_brands_are_filtered():
    assert d.junk_reason("baby stroller review", "baby essentials") is not None
    assert d.junk_reason("huggies skin essentials", "baby essentials") == "marca"
    assert d.junk_reason("bathroom wall organizer", "bathroom organizer") is None


def test_refilter_after_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "DISCOVERY_PATH", tmp_path / "disc.csv")
    table, _ = d.add_rising(pd.DataFrame(columns=d.COLUMNS), "baby essentials", "bebé",
                            rising(("huggies skin essentials", 70), ("baby bottle warmer", 80)), set())
    table.loc[table["termino"] == "huggies skin essentials", ["estado", "motivo"]] = ["pendiente", ""]
    d.save(table)
    out = d.refilter(d.load())  # empty "motivo" must not break re-filtering
    assert out.set_index("termino").loc["huggies skin essentials", "estado"] == "filtrado"


def test_refilter_keeps_scan_and_user_decisions():
    table = pd.DataFrame([
        {"termino": "squeaky dog toys bulk", "seed": "amazon: mascotas", "categoria": "mascotas", "subida_pct": 0.0,
         "breakout": False, "descubierto": "2026-10-15", "estado": "filtrado", "motivo": "sin volumen en Google"},
        {"termino": "moving bags", "seed": "amazon: hogar", "categoria": "hogar", "subida_pct": 0.0,
         "breakout": False, "descubierto": "2026-10-15", "estado": "filtrado", "motivo": "descartado en el pipeline"},
    ], columns=d.COLUMNS)
    out = d.refilter(table)
    assert (out["estado"] == "filtrado").all()


def test_daily_order_alternates():
    from scripts.discover import seeds_first
    assert seeds_first(date(2026, 10, 22)) != seeds_first(date(2026, 10, 23))
