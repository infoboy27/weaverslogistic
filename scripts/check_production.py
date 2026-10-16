"""Validate deployment prerequisites without printing credentials."""
import os
import sys
from pathlib import Path

REQUIRED = ("APP_DOMAIN", "WEAVERS_ALLOWED_EMAILS", "POSTGRES_PASSWORD")
def check():
    missing = [key for key in REQUIRED if not os.getenv(key)]
    secrets = Path(".streamlit/secrets.toml")
    if not secrets.is_file():
        missing.append(".streamlit/secrets.toml")
    if os.getenv("WEAVERS_AUTH_MODE", "required") != "required":
        missing.append("WEAVERS_AUTH_MODE=required")
    if missing:
        print("NOT READY: ", ", ".join(missing))
        return 1
    print("Static configuration checks passed; verify live OIDC, backups, TLS and SP-API separately.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
