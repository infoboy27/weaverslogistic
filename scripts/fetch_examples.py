"""One-off: example keywords for the pattern views (viral, shocks, holidays)."""
import random
import time

import pandas as pd

from fba_trends import collect
from fba_trends.config import DATA_DIR

EXAMPLES = [  # (keyword, categoria, notas, also fetch long history)
    ("the bear jacket", "ejemplo: viral", "serie The Bear", False),
    ("slime", "ejemplo: viral", "juguete niños", False),
    ("squishy", "ejemplo: viral", "juguete niños", False),
    ("dumpling squishy", "ejemplo: viral", "juguete niños", False),
    ("toilet paper", "ejemplo: shock", "pandemia 2020", True),
    ("graphics card", "ejemplo: shock", "minería cripto 2021", True),
    ("advent calendar", "ejemplo: navidad", "temporada navidad", False),
    ("ugly christmas sweater", "ejemplo: navidad", "temporada navidad", False),
]

kw = pd.read_csv(DATA_DIR / "keywords.csv")
for term, cat, note, long in EXAMPLES:
    if term not in set(kw["keyword"]):
        kw.loc[len(kw)] = [term, cat, note]
kw.to_csv(DATA_DIR / "keywords.csv", index=False)

jobs = [(t, False) for t, *_ in EXAMPLES if collect.load(t) is None]
jobs += [(t, True) for t, _, _, long in EXAMPLES if long and collect.load(t, long=True) is None]
for term, long in jobs:
    try:
        (collect.fetch_long if long else collect.fetch_google_trends)(term)
        print(f"ok {'largo ' if long else ''}{term}", flush=True)
    except collect.TrendsFetchError as e:
        print(f"BLOQUEADO {term}: {e}", flush=True)
        break
    time.sleep(random.uniform(30, 45))
print("Listo", flush=True)
