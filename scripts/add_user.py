"""Add or update a dashboard user in the users file (password mode).

    python -m scripts.add_user secrets/users.txt usuario            # asks for the password
    python -m scripts.add_user secrets/users.txt usuario --generate  # prints a random one

The file keeps one ``usuario hash`` per line; never commit it.
"""
import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

from fba_trends.auth import hash_password


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("user")
    ap.add_argument("--generate", action="store_true", help="genera una contraseña aleatoria y la imprime")
    a = ap.parse_args()
    user = a.user.strip().casefold()
    if not user or any(c.isspace() for c in user):
        sys.exit("Usuario inválido.")
    if a.generate:
        pwd = secrets.token_urlsafe(15)
    else:
        pwd = getpass.getpass("Contraseña: ")
        if pwd != getpass.getpass("Repite: "):
            sys.exit("No coinciden.")
    if len(pwd) < 12:
        sys.exit("Mínimo 12 caracteres.")

    path = Path(a.file)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [ln for ln in lines if ln.split()[:1] != [user]]
    lines.append(f"{user} {hash_password(pwd)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o640)
    print(f"Usuario '{user}' guardado en {path}.")
    if a.generate:
        print(f"Contraseña: {pwd}")


if __name__ == "__main__":
    main()
