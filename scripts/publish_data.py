"""Commit and push the daily scan's data to GitHub (called by run_discover.cmd after the scan).

Only scan outputs are published; code and personal settings (data/settings.yaml) never are.
The commit carries [skip ci] so a data-only change doesn't rerun the CI/CD pipeline.
Any git failure is printed (it lands in data/discovery_log.txt) and the script exits non-zero
without touching anything else; the next day's run retries.
"""
import os
import subprocess
import sys
from datetime import date

from fba_trends.config import ROOT

# Scan outputs only (paths relative to the repo root).
PUBLISHED = [
    "data/trends", "data/trends_long", "data/discovery.csv", "data/discovery_state.json",
    "data/keywords.csv", "data/ranking.csv", "data/volume.csv",
]


def git(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # never hang waiting for a login prompt
    return subprocess.run(["git", "-c", "core.autocrlf=true", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=180)


def changed_paths() -> list[str]:
    existing = [p for p in PUBLISHED if (ROOT / p).exists()]
    out = git("status", "--porcelain", "--", *existing).stdout
    return [line[3:] for line in out.splitlines() if line.strip()]


def main() -> int:
    changes = changed_paths()
    if not changes:
        print("Publicar datos: sin cambios")
        return 0
    existing = [p for p in PUBLISHED if (ROOT / p).exists()]
    steps = [
        ("add", git("add", "--", *existing)),
        ("commit", git("commit", "-q", "-m", f"Datos del escaneo diario {date.today():%Y-%m-%d} [skip ci]",
                       "--", *existing)),
        ("pull", git("pull", "--rebase", "--autostash", "-q", "origin", "main")),
        ("push", git("push", "-q", "origin", "HEAD:main")),
    ]
    for name, res in steps:
        if res.returncode != 0:
            print(f"Publicar datos: FALLÓ en {name}: {(res.stderr or res.stdout).strip()[:300]}")
            return 1
    print(f"Publicar datos: {len(changes)} archivos subidos a GitHub")
    return 0


if __name__ == "__main__":
    sys.exit(main())
