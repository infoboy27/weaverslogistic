"""Discover new product keywords from Google Trends "rising" related queries.

Flow: seed (broad product type) -> rising related queries (last 12 months, US, web search)
-> junk filter -> data/discovery.csv (estado=pendiente) -> daily scan adds them to the regular
keyword pipeline (data/keywords.csv + data/trends/).

Google Shopping (gprop=froogle) was tested and returns no related queries, so web search is used.
Rising queries are noisy (cocktails named "salty dog", spam domains, "near me"); the filter below
removes the obvious junk and the rest is judged by the normal trend + Amazon checks.
"""
import re
import time
from datetime import date, timedelta

import pandas as pd

from .collect import TrendsFetchError
from . import safe_io
from .config import DATA_DIR

SEEDS_PATH = DATA_DIR / "seeds.csv"
DISCOVERY_PATH = DATA_DIR / "discovery.csv"
COLUMNS = ["termino", "seed", "categoria", "subida_pct", "breakout", "descubierto", "estado", "motivo"]

# Retailers, platforms and intent words that make a query useless as a product keyword.
JUNK_WORDS = {
    "near", "me", "how", "what", "why", "when", "where", "who", "meaning", "lyrics", "song", "movie",
    "reddit", "youtube", "tiktok", "walmart", "target", "costco", "amazon", "temu", "shein", "etsy",
    "ikea", "depot", "lowes", "petco", "petsmart", "chewy", "dollar", "michaels", "lobby", "aldi",
    "kohls", "macys", "nordstrom", "sams", "ebay", "coupon", "sale", "stock", "recall", "free",
    "login", "app", "jobs", "store", "stores", "open", "hours", "review", "reviews", "vs", "versus",
    "recipe", "recipes", "ideas", "list", "checklist", "registry", "ulta", "sephora",
    # local businesses and services (pet groomers, salons...), not products
    "llc", "inc", "co", "company", "salon", "spa", "mobile", "insurance", "tips", "school", "course", "class",
    "classes", "academy", "services", "service", "appointment", "prices", "cost", "projects", "corner",
    "nearby", "shop", "shops", "business", "rental", "rent",
    "nyt", "crossword", "clue", "fashioned",  # crossword clues ("kitchen gadget brand nyt")
    # learning / information intent ("python tutorial", "garden pest identification"), not products
    "tutorial", "tutorials", "learn", "learning", "programming", "python", "identification", "identify",
    "guide", "definition", "certification", "degree", "salary", "pdf", "online",
}
# US state abbreviations: "corner pet grooming greenville sc" is a local business search
US_STATES = {
    "al", "ak", "az", "ar", "ca", "ct", "de", "fl", "ga", "hi", "id", "il", "ia", "ks", "ky", "la", "md", "ma",
    "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
}
# Licensed franchises (excluded by the criteria) and electronics / battery-powered products.
LICENSED = re.compile(r"toy story|pokemon|marvel|star wars|harry potter|bluey|paw patrol|hello kitty|stitch|frozen"
                      r"|fifa|world cup|panini|topps|nfl|nba|mlb|ascended heroes")
ELECTRONIC = {"robot", "remote", "automatic", "electric", "heated", "vacuum", "battery", "rechargeable", "usb",
              "smart", "wireless", "bluetooth", "led", "camera", "gps", "printer"}
# Single words that are a whole category, not a product
TOO_BROAD = {"dog", "dogs", "cat", "cats", "pet", "pets", "puppy", "kitten", "baby", "toy", "toys", "gift", "gifts"}
# Big consumer brands: a branded query means people want THAT brand, not a private-label product.
BRANDS = {
    "huggies", "pampers", "nike", "adidas", "stanley", "owala", "yeti", "hydro", "apple", "samsung", "dyson",
    "lego", "disney", "barbie", "crocs", "lululemon", "kitchenaid", "ninja", "keurig", "nespresso", "cricut",
    "kong", "furbo", "graco", "chicco", "uppababy", "dove", "olaplex", "dyson", "shark", "bissell", "rubbermaid",
    "ruffwear", "k9", "frontline", "seresto", "maxpower", "froplay", "meowscles", "bark", "zuru", "canon", "liene",
    "gopro", "miu", "closetmaid", "theraband", "comcast", "verizon", "otterbox", "anker", "gucci", "prada", "coach",
}
BRAND_PHRASES = re.compile(r"craft smart|athletic works|royal change|dog friendly co|sticker therapy")
GENERIC = {"best", "top", "good", "new", "cheap", "for", "the", "and", "with", "a", "of", "to", "in", "on"}
YEAR = re.compile(r"\b20\d\d\b")


def clean(term: str) -> str:
    term = YEAR.sub("", term.lower())
    words = [w for w in re.split(r"\s+", term) if w and w not in {"best", "top", "cheap"}]
    return " ".join(words).strip()


def junk_reason(term: str, seed: str) -> str | None:
    words = term.split()
    if not words:
        return "vacío"
    if re.search(r"\.(com|net|org|io|co)\b|www|http", term):
        return "dominio web"
    if JUNK_WORDS & set(words):
        return "tienda/intención no-producto"
    if BRANDS & set(words) or BRAND_PHRASES.search(term):
        return "marca"
    if US_STATES & set(words[1:]):
        return "negocio local"
    if LICENSED.search(term):
        return "licencia de marca"
    if ELECTRONIC & set(words):
        return "electrónica"
    if len(words) == 1 and words[0] in TOO_BROAD:
        return "demasiado genérico"
    if "for kids" in term or "kids" in words:
        return "producto para niños"
    if len(words) > 5:
        return "demasiado largo"
    if term == clean(seed):
        return "igual a la semilla"
    seed_words = set(seed.lower().split()) - GENERIC
    if len(words) == 1 and words[0] in seed_words:
        return "demasiado genérico"
    return None


def rising_queries(seed: str, timeframe: str = "today 12-m", geo: str = "US") -> pd.DataFrame:
    """One Google Trends call. Raises TrendsFetchError when rate-limited."""
    from pytrends.request import TrendReq

    try:
        client = TrendReq(hl="en-US", tz=300)
        client.build_payload([seed], timeframe=timeframe, geo=geo)
        rising = client.related_queries()[seed]["rising"]
    except Exception as e:
        raise TrendsFetchError(f"Google bloqueó o falló ({type(e).__name__}).") from e
    return rising if rising is not None else pd.DataFrame(columns=["query", "value"])


def load() -> pd.DataFrame:
    if not DISCOVERY_PATH.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(DISCOVERY_PATH, dtype={"motivo": str, "estado": str, "termino": str})
    df["motivo"] = df["motivo"].fillna("")
    return df


def save(df: pd.DataFrame) -> None:
    safe_io.write_csv(df[COLUMNS], DISCOVERY_PATH)


def add_rising(df: pd.DataFrame, seed: str, categoria: str, rising: pd.DataFrame,
               known_keywords: set[str], today: date | None = None) -> tuple[pd.DataFrame, int]:
    """Merge one seed's rising queries into the discovery table. Returns (table, new rows)."""
    today = today or date.today()
    seen = set(df["termino"]) | {k.lower() for k in known_keywords}
    rows = []
    for _, r in rising.iterrows():
        term = clean(str(r["query"]))
        if not term or term in seen:
            continue
        seen.add(term)
        reason = junk_reason(term, seed)
        value = float(r["value"])
        rows.append({
            "termino": term, "seed": seed, "categoria": categoria,
            "subida_pct": value, "breakout": value >= 5000,  # Google labels >5000% as "Breakout"
            "descubierto": today.isoformat(),
            "estado": "filtrado" if reason else "pendiente", "motivo": reason or "",
        })
    if rows:
        df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    return df, sum(1 for r in rows if r["estado"] == "pendiente")


def seeds_due(seed_log: dict[str, str], every_days: int = 30, today: date | None = None) -> list[tuple[str, str]]:
    """Seeds never run or last run more than `every_days` ago, oldest first."""
    today = today or date.today()
    seeds = pd.read_csv(SEEDS_PATH)
    due = []
    for i, s in seeds.iterrows():
        last = seed_log.get(s["seed"])
        if last is None or date.fromisoformat(last) <= today - timedelta(days=every_days):
            due.append((last or "", i, s["seed"], s["categoria"]))  # never-run first, then file order
    return [(seed, cat) for _, _, seed, cat in sorted(due)]


def next_to_scan(df: pd.DataFrame, n: int, priority: list[str] | None = None, max_per_seed: int = 2) -> list[str]:
    """Pending terms: `priority` first (in its order), then Amazon types, then breakouts / biggest risers.
    At most `max_per_seed` non-priority terms per seed per run, so one seed's near-duplicates
    ('mini / long / booty resistance bands'...) don't eat the whole daily Google budget."""
    pending = df[df["estado"] == "pendiente"].copy()
    rank = {k: i for i, k in enumerate(priority or [])}
    pending["_prio"] = pending["termino"].map(lambda k: -rank.get(k, 10_000))
    pending["_amazon"] = pending["seed"].astype(str).str.startswith("amazon")  # product types already selling
    pending = pending.sort_values(["_prio", "_amazon", "breakout", "subida_pct"], ascending=False)
    is_prio = pending["termino"].isin(rank)
    nth = pending.groupby("seed").cumcount()
    pending = pending[is_prio | (nth < max_per_seed)]
    return pending["termino"].head(n).tolist()


def queue_amazon_types(df: pd.DataFrame, types: pd.DataFrame, known_keywords: set[str],
                       today: date | None = None) -> tuple[pd.DataFrame, int]:
    """Add Amazon product types to the scan queue (they skip the junk filter: they are real products)."""
    today = today or date.today()
    have = set(df["termino"]) | {k.lower() for k in known_keywords}
    rows = [{"termino": t["tipo"], "seed": f"amazon: {t['sector']}", "categoria": t["sector"], "subida_pct": 0.0,
             "breakout": False, "descubierto": today.isoformat(), "estado": "pendiente", "motivo": ""}
            for _, t in types.iterrows() if t["tipo"] not in have]
    if rows:
        df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    return df, len(rows)


def pause(seconds: float) -> None:
    time.sleep(seconds)


STICKY_REASONS = {"sin volumen en Google", "descartado en el pipeline"}


def refilter(df: pd.DataFrame) -> pd.DataFrame:
    """Re-apply the current junk filter to terms not scanned yet (after the filter changes)."""
    df = df.copy()
    for i, r in df[df["estado"].isin(["pendiente", "filtrado"])].iterrows():
        if r["motivo"] in STICKY_REASONS:
            continue  # decided by the scan or by the user, not by the junk filter: keep it
        reason = junk_reason(r["termino"], r["seed"])
        df.loc[i, "estado"] = "filtrado" if reason else "pendiente"
        df.loc[i, "motivo"] = reason or ""
    return df
