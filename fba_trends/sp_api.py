"""Minimal read-only Amazon Selling Partner API client for US marketplace.

Server-side credentials only. This is NOT a substitute for approved SP-API
application roles or production authorization.
"""
import os
import time
import requests

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
NA_ENDPOINT = "https://sellingpartnerapi-na.amazon.com"
US_MARKETPLACE = "ATVPDKIKX0DER"


class SPAPIError(RuntimeError):
    pass


def configured(env=None):
    e = env if env is not None else os.environ
    return all(e.get(k) for k in ("SP_API_LWA_CLIENT_ID", "SP_API_LWA_CLIENT_SECRET", "SP_API_REFRESH_TOKEN"))


class SPAPIClient:
    def __init__(self, *, client_id=None, client_secret=None, refresh_token=None, session=None):
        self.client_id = client_id or os.getenv("SP_API_LWA_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SP_API_LWA_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.getenv("SP_API_REFRESH_TOKEN")
        self.session = session or requests.Session()
        self._token = None
        self._expires = 0
        if not all((self.client_id, self.client_secret, self.refresh_token)):
            raise SPAPIError("Faltan credenciales SP-API. Configura las variables de entorno en el servidor.")

    def access_token(self):
        if self._token and time.monotonic() < self._expires - 60:
            return self._token
        try:
            response = self.session.post(
                LWA_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": self.refresh_token,
                      "client_id": self.client_id, "client_secret": self.client_secret},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload["access_token"]
            ttl = int(payload.get("expires_in", 3600))
        except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
            raise SPAPIError("No se pudo renovar la autorización de Amazon.") from exc
        self._token, self._expires = token, time.monotonic() + ttl
        return token

    def search_catalog(self, keywords, *, page_size=10):
        """Search public catalog metadata; does not provide competitors' sales."""
        keywords = str(keywords).strip()
        if not keywords or len(keywords) > 250:
            raise ValueError("El término debe tener entre 1 y 250 caracteres.")
        if not 1 <= page_size <= 20:
            raise ValueError("page_size fuera del límite 1..20")
        try:
            response = self.session.get(
                f"{NA_ENDPOINT}/catalog/2022-04-01/items",
                params={"marketplaceIds": US_MARKETPLACE, "keywords": keywords,
                        "pageSize": page_size, "includedData": "summaries,images"},
                headers={"x-amz-access-token": self.access_token(), "accept": "application/json"},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SPAPIError("Amazon rechazó la consulta. Revisa roles, cuota y autorización SP-API.") from exc
