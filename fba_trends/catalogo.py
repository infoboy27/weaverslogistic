"""Daily catalog snapshots from Amazon SP-API: our own product database (BSR, brand, price, sellers).

For each keyword we keep the ASINs Amazon's catalog search returns plus the organic top 10 we
captured in Competencia, with their category BSR (Catalog Items API) and offers (Product Pricing
API: buy box price, number of sellers, FBA sellers, whether Amazon itself sells).

Snapshots are append-only, one file per month (data/catalog/YYYY-MM.csv), one row per
keyword × ASIN × day. Re-running the same day replaces that day's rows for the keyword.
History builds up from the first run: there is no back-fill (Keepa is the paid way to get that).
"""
from datetime import date

import pandas as pd

from . import safe_io
from .config import DATA_DIR

CATALOG_DIR = DATA_DIR / "catalog"
AMAZON_SELLER_ID = "ATVPDKIKX0DER"  # amazon.com sells as the US marketplace id
COLUMNS = ["fecha", "keyword", "origen", "posicion", "asin", "titulo", "marca", "categoria",
           "bsr_categoria", "subcategoria", "bsr_subcategoria", "precio", "vendedores",
           "vendedores_fba", "amazon_vende"]


def _first(items):
    return items[0] if items else {}


def parse_catalog_item(item: dict) -> dict:
    """Catalog Items 2022-04-01 item (summaries + salesRanks) -> flat row."""
    summary = _first(item.get("summaries") or [])
    ranks = _first(item.get("salesRanks") or [])
    display = sorted(ranks.get("displayGroupRanks") or [], key=lambda r: r.get("rank") or 1e12)
    classif = sorted(ranks.get("classificationRanks") or [], key=lambda r: r.get("rank") or 1e12)
    main, sub = _first(display), _first(classif)
    return {
        "asin": item.get("asin"),
        "titulo": (summary.get("itemName") or "")[:120],
        "marca": summary.get("brand") or summary.get("manufacturer"),
        "categoria": main.get("title") or summary.get("websiteDisplayGroupName"),
        "bsr_categoria": main.get("rank"),
        "subcategoria": sub.get("title"),
        "bsr_subcategoria": sub.get("rank"),
    }


def _amount(prices, condition="new"):
    for p in prices or []:
        if str(p.get("condition", "new")).lower() == condition:
            money = p.get("LandedPrice") or p.get("ListingPrice") or {}
            if money.get("Amount") is not None:
                return float(money["Amount"])
    return None


def _asin_of(resp: dict) -> str | None:
    payload = (resp.get("body") or {}).get("payload") or {}
    if payload.get("ASIN"):
        return payload["ASIN"]
    uri = (resp.get("request") or {}).get("uri") or ""
    parts = uri.strip("/").split("/")
    return parts[-2] if len(parts) >= 2 and parts[-1] == "offers" else None


def parse_offers(responses: list[dict]) -> dict[str, dict]:
    """getItemOffersBatch responses -> {asin: precio, vendedores, vendedores_fba, amazon_vende}.

    Price = buy box landed price, else the lowest new landed price. Seller counts come from the
    offers Amazon returns (top 20), so a listing with more sellers shows 20.
    """
    out = {}
    for resp in responses:
        if (resp.get("status") or {}).get("statusCode") != 200:
            continue
        asin = _asin_of(resp)
        payload = (resp.get("body") or {}).get("payload") or {}
        if not asin:
            continue
        summary = payload.get("Summary") or {}
        offers = payload.get("Offers") or []
        price = _amount(summary.get("BuyBoxPrices")) or _amount(summary.get("LowestPrices"))
        sellers = {o.get("SellerId") for o in offers if o.get("SellerId")}
        out[asin] = {
            "precio": price,
            "vendedores": summary.get("TotalOfferCount", len(offers)),
            "vendedores_fba": sum(1 for o in offers if o.get("IsFulfilledByAmazon")),
            "amazon_vende": AMAZON_SELLER_ID in sellers,
        }
    return out


def chunks(seq, n=20):
    seq = list(seq)
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def collect_keyword(client, keyword: str, extra_asins=(), *, pages: int = 1, offers: bool = True,
                    pause: float = 0.6, offers_pause: float = 10.0, today: date | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Snapshot one keyword. Returns (rows, warnings). Pricing failures don't lose the catalog data.

    Rate limits (SP-API defaults): catalog search ~2 req/s, item offers batch 0.1 req/s.
    """
    warnings = []
    rows, seen, token = [], set(), None
    for _ in range(max(1, pages)):
        items, token = client.catalog_page(keyword, page_size=20, page_token=token)
        for it in items:
            r = parse_catalog_item(it)
            if r["asin"] and r["asin"] not in seen:
                seen.add(r["asin"])
                rows.append({**r, "origen": "busqueda", "posicion": len(rows) + 1})
        client.sleep(pause)
        if not token:
            break
    missing = [a for a in dict.fromkeys(extra_asins) if a and a not in seen]
    for batch in chunks(missing):
        for it in client.catalog_by_asins(batch):
            r = parse_catalog_item(it)
            if r["asin"] and r["asin"] not in seen:
                seen.add(r["asin"])
                rows.append({**r, "origen": "top10", "posicion": None})
        client.sleep(pause)
    origin = {a: "top10" for a in extra_asins}
    for r in rows:  # ASINs in both: they are in the real organic top 10
        if r["origen"] == "busqueda" and r["asin"] in origin:
            r["origen"] = "busqueda+top10"
    prices = {}
    if offers and rows:
        try:
            for i, batch in enumerate(chunks([r["asin"] for r in rows])):
                if i:
                    client.sleep(offers_pause)
                prices.update(parse_offers(client.item_offers_batch(batch)))
        except Exception as exc:  # noqa: BLE001 - keep the catalog data, report the pricing failure
            warnings.append(f"Ofertas no disponibles: {exc}")
    day = (today or date.today()).isoformat()
    for r in rows:
        r.update(prices.get(r["asin"], {}))
        r["fecha"], r["keyword"] = day, keyword
    return pd.DataFrame(rows, columns=COLUMNS), warnings


def month_path(day: str):
    return CATALOG_DIR / f"{day[:7]}.csv"


def save(df: pd.DataFrame) -> None:
    """Replace the (fecha, keyword) rows present in df, month file by month file."""
    if df.empty:
        return
    for month, part in df.groupby(df["fecha"].str[:7]):
        path = CATALOG_DIR / f"{month}.csv"
        current = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=COLUMNS)
        keys = set(zip(part["fecha"], part["keyword"]))
        if not current.empty:
            current = current[[(f, k) not in keys for f, k in zip(current["fecha"], current["keyword"])]]
        out = part if current.empty else pd.concat([current, part], ignore_index=True)
        safe_io.write_csv(out[COLUMNS], path)


def load(months: int | None = None) -> pd.DataFrame:
    files = sorted(CATALOG_DIR.glob("*.csv")) if CATALOG_DIR.exists() else []
    if months:
        files = files[-months:]
    if not files:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def collected_on(day: str) -> set[str]:
    path = month_path(day)
    if not path.exists():
        return set()
    df = pd.read_csv(path, usecols=["fecha", "keyword"])
    return set(df.loc[df["fecha"] == day, "keyword"])


def latest(df: pd.DataFrame) -> pd.DataFrame:
    """Only each keyword's most recent snapshot."""
    if df.empty:
        return df
    last = df.groupby("keyword")["fecha"].transform("max")
    return df[df["fecha"] == last]
