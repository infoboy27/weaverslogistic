"""Google Trends data in, cached as CSV under data/trends/.

Two ways in:
- `fetch_google_trends`: live via pytrends (unofficial; Google rate-limits it often).
- `parse_trends_csv`: the CSV you download from trends.google.com ("Descargar"),
  which always works and is the fallback when the live fetch is blocked.
"""
import io
import re
import time

import pandas as pd

from . import safe_io
from .config import DATA_DIR

TRENDS_DIR = DATA_DIR / "trends"
LONG_DIR = DATA_DIR / "trends_long"  # monthly since 2004: catches old shocks (e.g. 2020 toilet paper)
DATE_HEADERS = {"week", "month", "day", "time", "semana", "mes", "día", "dia", "tiempo"}


class TrendsFetchError(RuntimeError):
    pass


class NoTrendsData(TrendsFetchError):
    """Google answered but has no data for the term (volume too low). Not a rate-limit block."""


def slug(keyword: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")


def save(keyword: str, s: pd.Series, long: bool = False) -> None:
    folder = LONG_DIR if long else TRENDS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    safe_io.write_csv(s.rename(keyword).to_frame(), folder / f"{slug(keyword)}.csv", index=True, index_label="fecha")


def load(keyword: str, long: bool = False) -> pd.Series | None:
    path = (LONG_DIR if long else TRENDS_DIR) / f"{slug(keyword)}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col="fecha", parse_dates=True)
    return df.iloc[:, 0]


def cached_keywords() -> list[str]:
    if not TRENDS_DIR.exists():
        return []
    return [pd.read_csv(p, nrows=0).columns[1] for p in sorted(TRENDS_DIR.glob("*.csv"))]


def fetch_long(keyword: str, geo: str = "US") -> pd.Series:
    """Monthly interest since 2004, stored apart from the 5-year weekly series."""
    return fetch_google_trends(keyword, geo=geo, timeframe="all", long=True)


def fetch_google_trends(keyword: str, geo: str = "US", timeframe: str = "today 5-y",
                        long: bool = False) -> pd.Series:
    from pytrends.request import TrendReq

    for attempt in range(3):  # Google often answers 429 on the first try
        try:
            client = TrendReq(hl="en-US", tz=300)
            client.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = client.interest_over_time()
            break
        except Exception as e:  # pytrends raises a variety of HTTP/parse errors
            if attempt == 2:
                raise TrendsFetchError(
                    f"Google Trends bloqueó o falló la consulta ({type(e).__name__}). "
                    "Descarga el CSV desde trends.google.com y súbelo."
                ) from e
            time.sleep(4 * (attempt + 1))
    if df.empty:
        raise NoTrendsData(f"Sin datos para '{keyword}'.")
    s = df[keyword].astype(float)
    save(keyword, s, long=long)
    return s


# A full year before the Mar-Jun 2026 Google data glitch, so the anchor isn't distorted.
CLEAN_YEAR = "2024-10-01 2025-09-30"


def relative_volume(keywords: list[str], anchor: str = "yoga mat", geo: str = "US",
                    timeframe: str = CLEAN_YEAR) -> dict[str, float]:
    """Average interest over `timeframe` as % of an anchor keyword, queried together
    so they share one scale. Google Trends only compares within a single request (max 5 terms)."""
    from pytrends.request import TrendReq

    out = {}
    for i in range(0, len(keywords), 4):
        batch = keywords[i:i + 4]
        for attempt in range(3):
            try:
                client = TrendReq(hl="en-US", tz=300)
                client.build_payload([anchor, *batch], timeframe=timeframe, geo=geo)
                df = client.interest_over_time()
                break
            except Exception as e:
                if attempt == 2:
                    raise TrendsFetchError(f"Fallo comparando volumen ({type(e).__name__}).") from e
                time.sleep(30 * (attempt + 1))
        base = df[anchor].mean()
        for kw in batch:
            out[kw] = round(float(df[kw].mean() / base * 100), 1) if base else None
        time.sleep(10)
    return out


def _to_number(v) -> float:
    v = str(v).strip()
    return 0.5 if v == "<1" else float(v)


def parse_trends_csv(text: str) -> dict[str, pd.Series]:
    """Parse a trends.google.com export. Handles the 'Category: ...' preamble and '<1' values."""
    lines = text.lstrip("﻿").splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.split(",")[0].strip().strip('"').lower() in DATE_HEADERS),
        None,
    )
    if start is None:
        raise ValueError("No encontré la columna de fechas (Week/Semana/Month...) en el CSV.")
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str)
    df.index = pd.to_datetime(df.iloc[:, 0])
    out = {}
    for col in df.columns[1:]:
        keyword = col.split(":")[0].strip()  # "yoga mat: (United States)" -> "yoga mat"
        out[keyword] = df[col].map(_to_number)
    return out
