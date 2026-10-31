"""UPC / EAN of the reference ASINs, so products can be found by barcode.

Sources, in order: Amazon SP-API catalog (identifiers) if configured, else Keepa (upcList/eanList).
Answers are cached in data/identifiers.csv and refreshed after max_age_days.
"""
import re
import time
from datetime import date

import pandas as pd

from . import keepa, safe_io
from .config import DATA_DIR

PATH = DATA_DIR / "identifiers.csv"
COLUMNS = ["asin", "upc", "ean", "titulo", "fecha", "fuente"]


class NoSource(RuntimeError):
    pass


def digits(code) -> str:
    return re.sub(r"\D", "", str(code or ""))


def same_code(a: str, b: str) -> bool:
    """UPC-A 036000291452 == EAN-13 0036000291452."""
    a, b = digits(a).lstrip("0"), digits(b).lstrip("0")
    return bool(a) and a == b


def looks_like_code(text: str) -> bool:
    t = str(text).strip().replace(" ", "")
    return t.isdigit() and len(t) in (8, 12, 13, 14)


def load() -> pd.DataFrame:
    if PATH.exists():
        return pd.read_csv(PATH, dtype=str).fillna("")
    return pd.DataFrame(columns=COLUMNS)


def save(rows: list[dict]) -> pd.DataFrame:
    current = load()
    if not rows:
        return current
    new = pd.DataFrame(rows).reindex(columns=COLUMNS).fillna("")
    merged = pd.concat([current[~current["asin"].isin(new["asin"])], new], ignore_index=True)
    safe_io.write_csv(merged, PATH)
    return merged


def from_keepa(product: dict) -> dict:
    return {"asin": str(product.get("asin", "")).upper(), "upc": " ".join(product.get("upcList") or []),
            "ean": " ".join(product.get("eanList") or []), "titulo": product.get("title") or "",
            "fecha": date.today().isoformat(), "fuente": "Keepa"}


def from_spapi(item: dict) -> dict:
    codes = {"UPC": [], "EAN": []}
    for group in item.get("identifiers") or []:
        for ident in group.get("identifiers") or []:
            kind = ident.get("identifierType")
            if kind in codes and ident.get("identifier") not in codes[kind]:
                codes[kind].append(ident["identifier"])
    summary = (item.get("summaries") or [{}])[0]
    return {"asin": str(item.get("asin", "")).upper(), "upc": " ".join(codes["UPC"]), "ean": " ".join(codes["EAN"]),
            "titulo": summary.get("itemName", ""), "fecha": date.today().isoformat(), "fuente": "SP-API"}


def source() -> str | None:
    from .sp_api import configured
    if configured():
        return "SP-API"
    return "Keepa" if keepa.api_key() else None


def fetch(asins: list[str], *, max_age_days: int = 60, progress=None, pause: float = 0.5) -> pd.DataFrame:
    """Fill identifiers for ASINs not looked up in the last max_age_days."""
    src = source()
    if not src:
        raise NoSource("Configura KEEPA_API_KEY o las credenciales SP-API en el servidor.")
    current = load()
    fresh = set()
    if not current.empty:
        age = (pd.Timestamp(date.today()) - pd.to_datetime(current["fecha"], errors="coerce")).dt.days
        fresh = set(current.loc[age <= max_age_days, "asin"])
    todo = [a for a in dict.fromkeys(x.strip().upper() for x in asins if x) if a not in fresh]
    rows = []
    if src == "SP-API":
        from .sp_api import SPAPIClient
        client = SPAPIClient()
        for i, asin in enumerate(todo):
            rows.append(from_spapi(client.get_item(asin)))
            if progress:
                progress(i + 1, len(todo))
            time.sleep(pause)  # getCatalogItem: 2 requests/second
    else:
        for i in range(0, len(todo), 100):
            products = keepa.fetch_products(todo[i:i + 100], max_age_hours=max_age_days * 24)["products"]
            rows += [from_keepa(p) for p in products.values()]
            if progress:
                progress(min(i + 100, len(todo)), len(todo))
    return save(rows)


def lookup(code: str) -> list[dict]:
    """Amazon listings under a barcode (and remember them)."""
    code = digits(code)
    src = source()
    if not src:
        raise NoSource("Configura KEEPA_API_KEY o las credenciales SP-API en el servidor.")
    if src == "SP-API":
        from .sp_api import SPAPIClient
        kind = "UPC" if len(code) == 12 else "EAN"
        rows = [from_spapi(it) for it in SPAPIClient().find_by_code(code, kind)]
    else:
        rows = [from_keepa(p) for p in keepa.find_by_code(code)]
    save(rows)
    return rows


def codes_for(asins: list[str], ids: pd.DataFrame) -> str:
    """UPCs (EAN when there is no UPC) of these ASINs, without repeats."""
    if ids is None or ids.empty or not asins:
        return ""
    by = ids.set_index("asin")
    out = []
    for a in asins:
        if a in by.index:
            row = by.loc[a]
            out += (row["upc"] or row["ean"]).split()
    return " ".join(dict.fromkeys(out))


def matches(query: str, *fields: str) -> bool:
    q = str(query).strip().lower()
    if not q:
        return True
    if q.replace(" ", "").isdigit() and len(digits(q)) >= 6:
        return any(same_code(q, c) or digits(q) in digits(c) for f in fields for c in str(f).split())
    return any(q in str(f).lower() for f in fields)
