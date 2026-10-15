from fba_trends import config as c


def test_settings_override_config(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "SETTINGS_PATH", tmp_path / "settings.yaml")
    c.save_settings({"precio_min": 25, "reserva_pct": 0.2, "costo_pct_precio": 0.3, "sectores": ["mascotas"]},
                    tmp_path / "settings.yaml")
    s = c.load_settings(tmp_path / "settings.yaml")
    cfg = c.apply_settings(c.load_config(), s)
    assert cfg["criterios"]["precio_min"] == 25
    assert cfg["presupuesto"]["reserva_pct"]["valor"] == 0.2
    assert cfg["decision"]["costo_pct_precio"]["valor"] == 0.3
    assert cfg["decision"]["costo_pct_precio"]["estimado"] is True  # metadata kept
    eff = c.settings_from_config(c.load_config(), {})
    assert eff["precio_max"] == 50 and eff["sectores"] if "sectores" in eff else True


def test_base_config_unaffected_by_user_settings():
    assert c.load_config()["criterios"]["precio_min"] == 20
