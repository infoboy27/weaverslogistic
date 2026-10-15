"""Snapshot of the first page of Amazon search results for a keyword (top 10 organic).

What each column tells you:
- resenas: the barrier to entry. A new listing starts at 0; a top 10 full of 10k+ review
  listings is very hard to break into. Listings with < 500 reviews on page 1 mean newcomers rank.
- vendidos_mes: Amazon's own "X+ bought in past month" (a lower bound, not an estimate).
- precio_usd: where to price. The median is the market price; the spread shows room for tiers.
- patrocinado: how many ads appear -> how expensive PPC will be.
- marca: if one brand holds several slots, the niche is dominated.

Verdict thresholds are heuristics, not validated against outcomes.
"""
import re
from datetime import date

import pandas as pd

from .config import DATA_DIR

COMPETITION_PATH = DATA_DIR / "competition.csv"
COLUMNS = ["keyword", "posicion", "asin", "titulo", "marca", "precio_usd", "rating", "resenas",
           "vendidos_mes", "patrocinados_pagina", "fecha"]


def parse_count(text) -> float | None:
    """'(28.6K)' -> 28600, '1,234' -> 1234, '6K+' -> 6000."""
    if text is None:
        return None
    m = re.search(r"([\d.,]+)\s*([KkMm]?)", str(text))
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return n * {"k": 1_000, "m": 1_000_000}.get(m.group(2).lower(), 1)


def parse_price(text, dop_per_usd: float | None = None) -> float | None:
    """'$13.99' -> 13.99; 'DOP 857.66' -> USD using the given rate."""
    if not text:
        return None
    n = parse_count(str(text).split()[-1].replace("$", ""))
    if n is None:
        return None
    if "DOP" in str(text):
        if not dop_per_usd:
            raise ValueError("Precio en DOP sin tasa de cambio.")
        return round(n / dop_per_usd, 2)
    return n


def parse_rating(text) -> float | None:
    m = re.search(r"([\d.]+) out of 5", str(text or ""))
    return float(m.group(1)) if m else None


def from_search_results(keyword: str, items: list[dict], dop_per_usd: float | None = None,
                        top: int = 10) -> tuple[pd.DataFrame, int]:
    """Raw search-result dicts (asin, sponsored, title, price, rating, reviews, bought) ->
    top-N organic rows, deduplicated by ASIN, plus the number of sponsored slots seen."""
    sponsored = sum(1 for it in items if it.get("sponsored"))
    rows, seen = [], set()
    for it in items:
        if it.get("sponsored") or not it.get("asin") or it["asin"] in seen:
            continue
        seen.add(it["asin"])
        title = it.get("title") or ""
        rows.append({
            "keyword": keyword,
            "posicion": len(rows) + 1,
            "asin": it["asin"],
            "titulo": title[:90],
            "marca": it.get("brand") or (title.split()[0] if title else None),  # first word ~ brand
            "precio_usd": parse_price(it.get("price"), dop_per_usd),
            "rating": parse_rating(it.get("rating")),
            "resenas": parse_count(it.get("reviews")),
            "vendidos_mes": parse_count(it.get("bought")),
            "fecha": date.today().isoformat(),
        })
        if len(rows) == top:
            break
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["patrocinados_pagina"] = sponsored
    return df, sponsored


def load() -> pd.DataFrame:
    if not COMPETITION_PATH.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(COMPETITION_PATH)


def save_keyword(df_kw: pd.DataFrame) -> None:
    """Replace the snapshot rows for the keyword(s) in df_kw."""
    current = load()
    current = current[~current["keyword"].isin(df_kw["keyword"].unique())]
    pd.concat([current, df_kw], ignore_index=True).to_csv(COMPETITION_PATH, index=False)


def summarize(df: pd.DataFrame) -> dict:
    reviews = df["resenas"].dropna()
    sold = df["vendidos_mes"].fillna(0)
    brands = df["marca"].dropna().str.lower().value_counts()
    low = int((reviews < 500).sum())
    median_reviews = float(reviews.median()) if not reviews.empty else None
    total_sold = float(sold.sum())

    if median_reviews is None:
        verdict = "Sin datos"
    elif median_reviews > 5000 and low <= 1:
        verdict = "Difícil"
    elif low >= 3 and total_sold >= 1000:
        verdict = "Accesible"
    else:
        verdict = "Media"

    return {
        "keyword": df["keyword"].iloc[0],
        "n": len(df),
        "precio_mediana": round(float(df["precio_usd"].median()), 2) if df["precio_usd"].notna().any() else None,
        "precio_min": df["precio_usd"].min(),
        "precio_max": df["precio_usd"].max(),
        "resenas_mediana": median_reviews,
        "resenas_prom": round(float(reviews.mean())) if not reviews.empty else None,
        "listados_bajo_500_resenas": low,
        "rating_prom": round(float(df["rating"].mean()), 2) if df["rating"].notna().any() else None,
        "vendidos_mes_top10": total_sold,
        "pct_ventas_top3": round(float(sold.nlargest(3).sum() / total_sold * 100), 1) if total_sold else None,
        "marca_dominante": brands.index[0] if not brands.empty else None,
        "puestos_marca_dominante": int(brands.iloc[0]) if not brands.empty else 0,
        "anuncios_en_pagina": int(df["patrocinados_pagina"].iloc[0]) if "patrocinados_pagina" in df
        and df["patrocinados_pagina"].notna().any() else None,
        "veredicto": verdict,
    }


def summary_table(df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = load() if df is None else df
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame([summarize(g) for _, g in df.groupby("keyword", sort=False)])
