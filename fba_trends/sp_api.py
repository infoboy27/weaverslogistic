"""Minimal read-only Amazon Selling Partner API client for US marketplace.

Server-side credentials only. This is NOT a substitute for approved SP-API
application roles or production authorization.
"""
import os
import time
import requests

# Public OAuth endpoint URL (not a secret); bandit B105 flags the word "token".
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"  # nosec B105
NA_ENDPOINT = "https://sellingpartnerapi-na.amazon.com"
US_MARKETPLACE = "ATVPDKIKX0DER"


class SPAPIError(RuntimeError):
    pass


def validate_asin(asin):
    asin = str(asin).strip().upper()
    if len(asin) != 10 or not asin.isalnum():
        raise ValueError(f"ASIN inválido: {asin!r}")
    return asin


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
        self.sleep = time.sleep
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

    def _request(self, method, path, *, params=None, json_body=None, retries=3, error=None):
        """Signed call with backoff on 429 (quota) and 5xx. Raises SPAPIError otherwise."""
        error = error or "Amazon rechazó la consulta. Revisa roles, cuota y autorización SP-API."
        for attempt in range(retries + 1):
            try:
                response = self.session.request(
                    method, f"{NA_ENDPOINT}/{path}", params=params, json=json_body,
                    headers={"x-amz-access-token": self.access_token(), "accept": "application/json"},
                    timeout=30,
                )
                status = getattr(response, "status_code", 200)
                if isinstance(status, int) and (status == 429 or status >= 500) and attempt < retries:
                    self.sleep(2 ** attempt * 2)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                code = getattr(exc.response, "status_code", None)
                raise SPAPIError(f"{error} (HTTP {code})" if code else error) from exc
            except (requests.RequestException, ValueError) as exc:
                raise SPAPIError(error) from exc
        raise SPAPIError(error)

    def _catalog(self, path, params):
        return self._request("GET", f"catalog/2022-04-01/{path}",
                             params={"marketplaceIds": US_MARKETPLACE, **params})

    def catalog_page(self, keywords, *, page_size=20, page_token=None):
        """One page of a keyword search with sales ranks (BSR). Returns (items, next_token)."""
        keywords = str(keywords).strip()
        if not keywords or len(keywords) > 250:
            raise ValueError("El término debe tener entre 1 y 250 caracteres.")
        if not 1 <= page_size <= 20:
            raise ValueError("page_size fuera del límite 1..20")
        params = {"keywords": keywords, "pageSize": page_size, "includedData": "summaries,salesRanks"}
        if page_token:
            params["pageToken"] = page_token
        data = self._catalog("items", params)
        return data.get("items", []), (data.get("pagination") or {}).get("nextToken")

    def catalog_by_asins(self, asins):
        """Summaries and sales ranks for up to 20 ASINs in one call."""
        asins = [validate_asin(a) for a in asins]
        if not 1 <= len(asins) <= 20:
            raise ValueError("Entre 1 y 20 ASINs por consulta.")
        return self._catalog("items", {"identifiers": ",".join(asins), "identifiersType": "ASIN",
                                       "pageSize": 20, "includedData": "summaries,salesRanks"}).get("items", [])

    def item_offers_batch(self, asins):
        """New-condition offers for up to 20 ASINs (Product Pricing API, role Pricing).

        Returns the raw ``responses`` list; parse with ``catalogo.parse_offers``.
        """
        asins = [validate_asin(a) for a in asins]
        if not 1 <= len(asins) <= 20:
            raise ValueError("Entre 1 y 20 ASINs por consulta.")
        body = {"requests": [{"uri": f"/products/pricing/v0/items/{a}/offers", "method": "GET",
                              "MarketplaceId": US_MARKETPLACE, "ItemCondition": "New",
                              "CustomerType": "Consumer"} for a in asins]}
        return self._request("POST", "batches/products/pricing/v0/itemOffers", json_body=body,
                             error="Amazon rechazó la consulta de ofertas. Revisa el rol Pricing.").get("responses", [])

    def get_item(self, asin):
        """One ASIN with its identifiers (UPC/EAN) and summary."""
        asin = str(asin).strip().upper()
        if len(asin) != 10 or not asin.isalnum():
            raise ValueError(f"ASIN inválido: {asin!r}")
        return self._catalog(f"items/{asin}", {"includedData": "identifiers,summaries"})

    def find_by_code(self, code, code_type="UPC"):
        """ASINs listed under a UPC/EAN."""
        return self._catalog("items", {"identifiers": code, "identifiersType": code_type,
                                       "includedData": "identifiers,summaries"}).get("items", [])

    def listing_restrictions(self, asin, seller_id, *, condition="new_new"):
        """Whether *this seller* may list the ASIN (Listings Restrictions API, role Product Listing).

        Returns the ``restrictions`` list: empty means no approval needed; reasons carry
        codes such as APPROVAL_REQUIRED, ASIN_NOT_FOUND or NOT_ELIGIBLE.
        """
        asin = str(asin).strip().upper()
        if len(asin) != 10 or not asin.isalnum():
            raise ValueError(f"ASIN inválido: {asin!r}")
        if not seller_id:
            raise SPAPIError("Falta SP_API_SELLER_ID (Merchant Token de Seller Central).")
        try:
            response = self.session.get(
                f"{NA_ENDPOINT}/listings/2021-08-01/restrictions",
                params={"asin": asin, "sellerId": seller_id, "marketplaceIds": US_MARKETPLACE,
                        "conditionType": condition},
                headers={"x-amz-access-token": self.access_token(), "accept": "application/json"},
                timeout=20,
            )
            response.raise_for_status()
            return response.json().get("restrictions", [])
        except (requests.RequestException, ValueError) as exc:
            raise SPAPIError("Amazon rechazó la consulta de restricciones. Revisa el rol Product Listing "
                             "y SP_API_SELLER_ID.") from exc
