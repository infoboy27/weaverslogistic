"""Add or update a dashboard user in the users file (password mode).

    python -m scripts.add_user secrets/users.txt usuario            # asks for the password
    python -m scripts.add_user secrets/users.txt usuario --generate  # prints a random one
    python -m scripts.add_user secrets/users.txt usuario --totp      # also turns on 2FA

The file keeps one ``usuario hash [totp:secreto]`` per line; never commit it.
"""
import argparse
import base64
import getpass
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

from fba_trends.auth import hash_password


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("user")
    ap.add_argument("--generate", action="store_true", help="genera una contraseña aleatoria y la imprime")
    ap.add_argument("--totp", action="store_true", help="activa 2FA: imprime el secreto para la app autenticadora")
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
    totp = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=") if a.totp else None
    lines.append(f"{user} {hash_password(pwd)}" + (f" totp:{totp}" if totp else ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o640)
    print(f"Usuario '{user}' guardado en {path}.")
    if a.generate:
        print(f"Contraseña: {pwd}")
    if totp:
        print(f"2FA: agrega en Google Authenticator / 1Password este enlace o el secreto {totp}")
        print(f"otpauth://totp/Weavers%20FBA:{quote(user)}?secret={totp}&issuer=Weavers%20FBA")


if __name__ == "__main__":
    main()
