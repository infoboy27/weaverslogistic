"""Daily SP-API catalog snapshot for the keywords we are researching.

Usage:  .venv/Scripts/python -m scripts.collect_catalog [--max 40] [--keyword "dog cooling mat"] [--no-offers]

Keyword order: those captured in Competencia (their organic top 10 ASINs are added, which is what
calibrates the sales estimate), then the ranking finalists. Keywords already collected today are
skipped, so a run that dies half way resumes where it stopped.
"""
import argparse
import sys
from datetime import date

import pandas as pd

from fba_trends import catalogo, competition
from fba_trends.config import DATA_DIR, load_config
from fba_trends.sp_api import SPAPIClient, SPAPIError, configured

RANKING_PATH = DATA_DIR / "ranking.csv"


def keyword_queue(comp: pd.DataFrame, ranking: pd.DataFrame) -> list[str]:
    kws = list(dict.fromkeys(comp["keyword"])) if not comp.empty else []
    if not ranking.empty and "finalista" in ranking:
        final = ranking[ranking["finalista"].astype(str).str.lower() == "true"]
        kws += [k for k in final["keyword"] if k not in kws]
    return kws


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int)
    ap.add_argument("--keyword", action="append", help="Solo estas keywords (se puede repetir)")
    ap.add_argument("--no-offers", action="store_true")
    ap.add_argument("--force", action="store_true", help="Repetir aunque ya se haya recolectado hoy")
    args = ap.parse_args(argv)

    if not configured():
        print("SP-API no configurada (SP_API_LWA_CLIENT_ID/SECRET, SP_API_REFRESH_TOKEN). Nada que hacer.")
        return 0
    cfg = load_config(with_settings=True).get("recolector", {})
    comp = competition.load()
    ranking = pd.read_csv(RANKING_PATH) if RANKING_PATH.exists() else pd.DataFrame()
    queue = args.keyword or keyword_queue(comp, ranking)
    today = date.today().isoformat()
    done = set() if args.force else catalogo.collected_on(today)
    queue = [k for k in queue if k not in done][: args.max or int(cfg.get("max_keywords", 40))]
    print(f"{len(queue)} keywords por recolectar ({len(done)} ya hechas hoy).")

    client = SPAPIClient()
    offers = bool(cfg.get("ofertas", True)) and not args.no_offers
    ok = 0
    for kw in queue:
        top10 = comp.loc[comp["keyword"] == kw, "asin"].dropna().tolist() if not comp.empty else []
        try:
            df, warnings = catalogo.collect_keyword(client, kw, top10, pages=int(cfg.get("paginas_busqueda", 1)),
                                                    offers=offers)
        except SPAPIError as e:
            print(f"  {kw}: ERROR {e}")
            if "HTTP 403" in str(e) or "HTTP 401" in str(e):
                print("Sin permiso: revisa el rol Product Listing de la app. Se detiene la corrida.")
                return 1
            continue
        catalogo.save(df)
        ok += 1
        priced = int(df["precio"].notna().sum()) if not df.empty else 0
        print(f"  {kw}: {len(df)} ASINs, {int(df['bsr_categoria'].notna().sum())} con BSR, {priced} con precio")
        for w in warnings:
            print(f"    aviso: {w}")
        if warnings and offers:  # pricing role missing or quota: don't keep paying 10 s per batch
            offers = False
            print("    (se sigue sin ofertas en esta corrida)")
    print(f"Listo: {ok}/{len(queue)} keywords.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
