from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
