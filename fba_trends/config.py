from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"
SETTINGS_PATH = DATA_DIR / "settings.yaml"

# User-editable settings (Ajustes page) -> where they live in config.yaml.
# Entries ending in "valor" are the {valor, estimado, nota} blocks.
SETTINGS_MAP = {
    "presupuesto_usd": None,  # only used by the UI as the default budget
    "nombre_negocio": None,
    "sectores": None,
    "precio_min": ("criterios", "precio_min"),
    "precio_max": ("criterios", "precio_max"),
    "peso_max_kg": ("criterios", "peso_max_kg"),
    "min_listados_bajo_500_resenas": ("criterios", "min_listados_bajo_500_resenas"),
    "min_vendidos_mes_top10": ("criterios", "min_vendidos_mes_top10"),
    "reserva_pct": ("presupuesto", "reserva_pct", "valor"),
    "max_productos": ("presupuesto", "max_productos", "valor"),
    "meses_de_prueba": ("presupuesto", "meses_de_prueba", "valor"),
    "costo_lanzamiento_por_producto": ("presupuesto", "costo_lanzamiento_por_producto", "valor"),
    "costo_pct_precio": ("decision", "costo_pct_precio", "valor"),
    "captura_nuevo_vendedor": ("decision", "captura_nuevo_vendedor", "valor"),
    "moq_por_defecto": ("decision", "moq_por_defecto", "valor"),
    "margen_neto_minimo": ("supuestos", "margen_neto_minimo", "valor"),
}
DEFAULT_SETTINGS = {"presupuesto_usd": 3500, "nombre_negocio": "", "sectores": ["mascotas", "hobby", "hogar"]}


def load_settings(path: Path = SETTINGS_PATH) -> dict:
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    with open(path, encoding="utf-8") as f:
        return {**DEFAULT_SETTINGS, **(yaml.safe_load(f) or {})}


def save_settings(settings: dict, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, allow_unicode=True, sort_keys=False)


def _get(cfg: dict, keys: tuple):
    node = cfg
    for k in keys:
        node = node[k]
    return node


def _set(cfg: dict, keys: tuple, value) -> None:
    node = cfg
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value


def apply_settings(cfg: dict, settings: dict) -> dict:
    for name, keys in SETTINGS_MAP.items():
        if keys and name in settings and settings[name] is not None:
            _set(cfg, keys, settings[name])
    return cfg


def settings_from_config(cfg: dict, settings: dict) -> dict:
    """Current effective value of every setting (config value unless the user overrode it)."""
    out = dict(settings)
    for name, keys in SETTINGS_MAP.items():
        if keys and name not in out:
            out[name] = _get(cfg, keys)
    return out


def load_config(path: Path = CONFIG_PATH, with_settings: bool = False) -> dict:
    """Base config.yaml; with_settings=True also applies the user's Ajustes (data/settings.yaml)."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return apply_settings(cfg, load_settings()) if with_settings else cfg


def estimated_assumptions(cfg: dict) -> list[dict]:
    """Flatten every config entry flagged `estimado: true` so the UI can list them."""
    out = []

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("estimado"):
                out.append({"supuesto": ".".join(path), "nota": node.get("nota", "")})
            for k, v in node.items():
                walk(v, path + [k])

    walk(cfg, [])
    return out
