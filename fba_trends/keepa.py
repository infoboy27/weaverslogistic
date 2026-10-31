"""Keepa API: BSR, price, seller-count and review history for Amazon ASINs.

API key: set KEEPA_API_KEY in the environment or in a `.env` file at the project root
(never commit it). Each product with history costs Keepa tokens; responses are cached
under data/keepa/ and only re-fetched when older than `max_age_hours`.

Format reference (keepacom/api_backend, Product.java):
- `csv[i]` is a flat [keepa_minute, value, keepa_minute, value, ...] list per CsvType.
- Prices are in cents; -1 means no offer / no data at that time.
- RATING is 0-50 (45 = 4.5 stars); RATING and COUNT_REVIEWS need `rating=1`.
"""
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

from .config import DATA_DIR, ROOT

API_URL = "https://api.keepa.com"
CACHE_DIR = DATA_DIR / "keepa"
DOMAIN_US = 1

# CsvType indices used here (from Keepa's Product.CsvType enum)
AMAZON, NEW, SALES, COUNT_NEW, RATING, COUNT_REVIEWS = 0, 1, 3, 11, 16, 17
SERIES = {"precio_amazon": AMAZON, "precio_nuevo": NEW, "bsr": SALES,
          "vendedores": COUNT_NEW, "rating": RATING, "resenas": COUNT_REVIEWS}
PRICE_SERIES = {"precio_amazon", "precio_nuevo"}


class KeepaError(RuntimeError):
    pass


def api_key() -> str | None:
    key = os.environ.get("KEEPA_API_KEY")
    if key:
        return key.strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("KEEPA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"') or None
    return None


def keepa_minutes_to_datetime(minutes) -> pd.DatetimeIndex:
    return pd.to_datetime((pd.Series(minutes, dtype="int64") + 21_564_000) * 60, unit="s")


def parse_series(flat: list[int] | None, name: str) -> pd.Series:
    """[t, v, t, v, ...] -> Series indexed by datetime. -1 becomes NaN (no offer / no data)."""
    if not flat or len(flat) < 2:
        return pd.Series(dtype=float, name=name)
    times, values = flat[0::2], flat[1::2]
    s = pd.Series(values, index=keepa_minutes_to_datetime(times), dtype=float, name=name)
    s = s.where(s >= 0)
    if name in PRICE_SERIES:
        s = s / 100
    elif name == "rating":
        s = s / 10
    return s[~s.index.duplicated(keep="last")].sort_index()


def product_history(product: dict) -> dict[str, pd.Series]:
    csv = product.get("csv") or []
    return {name: parse_series(csv[i] if i < len(csv) else None, name) for name, i in SERIES.items()}


# ------------------------------------------------------------------ HTTP + cache
def _get(path: str, params: dict) -> dict:
    key = api_key()
    if not key:
        raise KeepaError("Falta KEEPA_API_KEY (ponla en el archivo .env del proyecto).")
    try:
        r = requests.get(f"{API_URL}/{path}", params={"key": key, **params}, timeout=60)
    except requests.RequestException as e:
        raise KeepaError(f"No se pudo conectar con Keepa: {type(e).__name__}") from e
    try:
        data = r.json()
    except ValueError:
        raise KeepaError(f"Respuesta inválida de Keepa (HTTP {r.status_code}).")
    if r.status_code != 200 or data.get("error"):
        err = data.get("error") or {}
        msg = err.get("message") if isinstance(err, dict) else err
        hint = " Sin tokens: espera a que se recarguen." if r.status_code == 429 else ""
        raise KeepaError(f"Keepa HTTP {r.status_code}: {msg or 'error'}.{hint}")
    return data


def _cache_path(asin: str) -> Path:
    return CACHE_DIR / f"{asin.upper()}.json"


def load_cached(asin: str) -> dict | None:
    p = _cache_path(asin)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cached_asins() -> list[str]:
    return sorted(p.stem for p in CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []


def fetch_products(asins: list[str], max_age_hours: float = 24, domain: int = DOMAIN_US) -> dict:
    """Return {asin: product}, hitting the API only for missing/stale ASINs (max 100 per call)."""
    asins = [a.strip().upper() for a in asins if a.strip()]
    out, stale = {}, []
    for a in asins:
        cached = load_cached(a)
        if cached and time.time() - cached.get("_fetched_at", 0) < max_age_hours * 3600:
            out[a] = cached
        else:
            stale.append(a)
    tokens_left = None
    for i in range(0, len(stale), 100):
        batch = stale[i:i + 100]
        data = _get("product", {"domain": domain, "asin": ",".join(batch),
                                "history": 1, "rating": 1, "stats": 90})
        tokens_left = data.get("tokensLeft")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for p in data.get("products") or []:
            p["_fetched_at"] = time.time()
            _cache_path(p["asin"]).write_text(json.dumps(p), encoding="utf-8")
            out[p["asin"].upper()] = p
    return {"products": out, "tokens_left": tokens_left, "consultados": len(stale)}


def find_by_code(code: str, domain: int = DOMAIN_US) -> list[dict]:
    """Products listed under a UPC/EAN (Keepa `code` lookup, no history: 1 token per product)."""
    return _get("product", {"domain": domain, "code": code}).get("products") or []


def search_asins(term: str, domain: int = DOMAIN_US) -> list[str]:
    """Top results for a search term (Keepa product search; costs extra tokens per page)."""
    data = _get("search", {"domain": domain, "type": "product", "term": term, "page": 0})
    return [p["asin"] for p in data.get("products") or [] if p.get("asin")][:10]


# ------------------------------------------------------------------ metrics
def _pct_change(s: pd.Series, recent_days: int, prior_days: int) -> float | None:
    if s.dropna().empty:
        return None
    daily = s.resample("D").last().ffill()
    end = daily.index[-1]
    recent = daily[daily.index > end - pd.Timedelta(days=recent_days)].mean()
    prior = daily[(daily.index <= end - pd.Timedelta(days=recent_days))
                  & (daily.index > end - pd.Timedelta(days=recent_days + prior_days))].mean()
    if pd.isna(recent) or pd.isna(prior) or prior == 0:
        return None
    return float(recent / prior - 1)


def _last(s: pd.Series):
    s = s.dropna()
    return None if s.empty else float(s.iloc[-1])


def _mean_since(s: pd.Series, days: int):
    s = s.dropna()
    if s.empty:
        return None
    daily = s.resample("D").last().ffill()
    return float(daily[daily.index > daily.index[-1] - pd.Timedelta(days=days)].mean())


def metrics(product: dict) -> dict:
    h = product_history(product)
    bsr_change = _pct_change(h["bsr"], 30, 60)
    price = h["precio_nuevo"] if h["precio_nuevo"].notna().any() else h["precio_amazon"]
    return {
        "asin": product.get("asin"),
        "titulo": (product.get("title") or "")[:80],
        "marca": product.get("brand"),
        "bsr_actual": _last(h["bsr"]),
        "bsr_prom_90d": _mean_since(h["bsr"], 90),
        # Lower BSR = more sales, so a negative change means the product is selling MORE.
        "bsr_cambio_30v60_pct": None if bsr_change is None else round(bsr_change * 100, 1),
        "precio_actual": _last(price),
        "precio_prom_90d": _mean_since(price, 90),
        "vendedores": _last(h["vendedores"]),
        "vendedores_cambio_pct": None if (c := _pct_change(h["vendedores"], 30, 60)) is None else round(c * 100, 1),
        "resenas": _last(h["resenas"]),
        "rating": _last(h["rating"]),
        "vendidos_mes": product.get("monthlySold") or None,  # Amazon's "bought in past month"; often missing
    }


def market_summary(asins: list[str]) -> dict | None:
    """Aggregate cached competitor ASINs (e.g. the top 10 for a keyword)."""
    rows = [metrics(p) for a in asins if (p := load_cached(a))]
    if not rows:
        return None
    df = pd.DataFrame(rows)
    return {
        "n": len(df),
        "resenas_prom": None if df["resenas"].dropna().empty else float(df["resenas"].mean()),
        "precio_mediana": None if df["precio_actual"].dropna().empty else float(df["precio_actual"].median()),
        "vendidos_mes_total": None if df["vendidos_mes"].dropna().empty else float(df["vendidos_mes"].sum()),
        "bsr_cambio_mediana_pct": None if df["bsr_cambio_30v60_pct"].dropna().empty
        else float(df["bsr_cambio_30v60_pct"].median()),
    }
