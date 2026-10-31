"""Which products can be sold on Amazon US without asking for approval ("ungated").

Two levels of evidence:
- "Verificado SP-API": Listings Restrictions API answered for this seller account on the
  product's reference ASINs (top organic results / Best Sellers). Authoritative, per account.
- "Estimado por categoría": rules below, from Amazon's public lists of categories and products
  that need approval, plus licensed brands. A product with no rule hit is "No requiere aprobación"
  but should be confirmed with SP-API (or "Add a product" in Seller Central) before buying stock.

Hazmat (batteries, aerosols...) is not an approval but a dangerous-goods review that blocks FBA
until accepted, so it is reported as "Revisar".
"""
import re
import time
from datetime import date

import pandas as pd

from . import discovery, identifiers
from .config import DATA_DIR

RESTRICTIONS_PATH = DATA_DIR / "restrictions.csv"
RESTRICTION_COLUMNS = ["asin", "estado", "motivos", "fecha"]

LIBRE, APROBACION, REVISAR = "No requiere aprobación", "Requiere aprobación", "Revisar"
VERIFICADO, ESTIMADO = "Verificado SP-API", "Estimado por categoría"

# Word-bounded; "stitch" (Disney) but not cross-stitch / stitch book kits.
LICENSED = re.compile(r"\b(" + discovery.LICENSED.pattern.replace("|stitch|", "|") + r")\b"
                      r"|(?<!cross )\bstitch\b(?! (book|kit|markers?|counter))|tech sticker collection")
PET = re.compile(r"\b(dog|dogs|cat|cats|pet|pets|puppy|kitten|bird|hummingbird)\b")

# (status, reason, pattern). First match wins, so stricter rules go first.
RULES = [
    (APROBACION, "Marca con licencia o protegida (brand gating)", LICENSED),
    (APROBACION, "Marca registrada de terceros (brand gating)",
     re.compile(r"\b(" + "|".join(sorted(discovery.BRANDS)) + r")\b|" + discovery.BRAND_PHRASES.pattern)),
    (APROBACION, "Coleccionables (cartas, monedas, autógrafos)",
     re.compile(r"trading cards?|sticker (album|book|packs?)|collectible|autograph|memorabilia|\bcoins?\b")),
    (APROBACION, "Alimentos y bebidas (Grocery & Gourmet)",
     re.compile(r"\b(food|snacks?|candy|chocolate|coffee beans|ground coffee|tea bags|spices?|sauce|cookies?"
                r"|gummies|jerky|honey|protein powder|matcha powder)\b")),
    (APROBACION, "Suplementos / CBD",
     re.compile(r"\b(supplements?|vitamins?|probiotics?|collagen|melatonin|cbd|hemp oil|creatine)\b")),
    (APROBACION, "Pesticida regulado por EPA (pulgas, garrapatas, insectos)",
     re.compile(r"\b(flea|tick|pesticide|insecticide|bug spray|mosquito|repellent|weed killer|ant bait)\b")),
    (APROBACION, "Dispositivo médico",
     re.compile(r"\b(medical|thermometer|blood pressure|oximeter|hearing aid|contact lens|surgical|n95|cpap"
                r"|orthotics?|brace)\b")),
    (APROBACION, "Relojes (categoría Watches)", re.compile(r"\bwatch(es)?\b(?! band)")),
    (APROBACION, "Joyería fina (oro, plata, diamantes)",
     re.compile(r"\b(fine jewelry|gold|sterling silver|diamond|gemstone)\b")),
    (APROBACION, "Música / video físico", re.compile(r"\b(dvd|blu-?ray|vinyl record|cds?)\b")),
    (APROBACION, "Alcohol, tabaco o vapeo", re.compile(r"\b(wine|beer|liquor|vape|e-cig|tobacco|cigar)\b")),
    (REVISAR, "Hazmat: baterías, aerosoles o inflamables (revisión de mercancía peligrosa)",
     re.compile(r"\b(battery|batteries|lithium|rechargeable|aerosol|spray paint|flammable|lighter|propane|butane"
                r"|heated|perfume|nail polish|essential oils?|acrylic paint|paint)\b")),
    (REVISAR, "Cosmético tópico (algunas subcategorías de Beauty piden aprobación)",
     re.compile(r"\b(serum|lotion|cream|sunscreen|skincare|cosmetics?|makeup|shampoo|hair dye|wipes)\b")),
    (REVISAR, "Automotriz (algunas piezas piden aprobación)",
     re.compile(r"\b(car parts?|brake|engine|tires?|headlights?|motorcycle)\b")),
    (REVISAR, "Término genérico de regalo: depende del producto que elijas",
     re.compile(r"\b(gifts?|stuffers|essentials|supplies)\b")),
    (REVISAR, "Bebé: algunas subcategorías piden aprobación", re.compile(r"\b(baby formula|breast pump|car seat(?! gap| cover))\b")),
]
# Toys & Games (not pet toys): sellers without performance history cannot sell via FBA in Q4.
TOYS = re.compile(r"\b(toys?|squishy|slime|plush|puzzle|board game|doll|action figure)\b")
NOT_PRODUCT = {"vacío", "dominio web", "tienda/intención no-producto", "negocio local"}


def classify(text: str, today: date | None = None) -> tuple[str, str]:
    """Rule-based status and reason for a product description (keyword, category, titles)."""
    t = str(text).lower()
    for status, reason, rx in RULES:
        if rx.search(t):
            return status, reason
    if TOYS.search(t) and not PET.search(t):
        today = today or date.today()
        if today.month in (10, 11, 12, 1):
            return REVISAR, "Juguetes: restricciones de temporada navideña (nov–ene) para vendedores nuevos"
        return LIBRE, "Juguetes: libre fuera de la temporada navideña (ojo nov–ene)"
    return LIBRE, "Categoría abierta"


# ---------------------------------------------------------------- products
def products(ranking: pd.DataFrame, universe: pd.DataFrame, competition: pd.DataFrame) -> pd.DataFrame:
    """One row per product type with its reference ASINs and a little market context."""
    rows: dict[str, dict] = {}
    if universe is not None and not universe.empty:
        for tipo, g in universe.groupby("tipo"):
            rows[tipo] = {"producto": tipo, "sector": g["sector"].mode().iloc[0],
                          "subcategoria": g["subcategoria"].mode().iloc[0],
                          "precio_ref": round(float(g["precio_usd"].median()), 2),
                          "asins": list(g.sort_values("rank")["asin"].head(3)),
                          "titulos": " ".join(g["titulo"].astype(str).head(5))}
    if ranking is not None and not ranking.empty:
        for _, r in ranking.iterrows():
            k = str(r["keyword"])
            cat = str(r.get("categoria") or "").replace("descubierto: ", "")
            # control = market baseline; "ejemplo:" = real series kept only to illustrate patterns
            if (cat == "control" or str(r.get("notas") or "").startswith("ejemplo:")
                    or discovery.junk_reason(k, "") in NOT_PRODUCT):
                continue
            row = rows.setdefault(k, {"producto": k, "sector": cat, "subcategoria": "", "precio_ref": None,
                                      "asins": [], "titulos": ""})
            row.update(tendencia=r.get("clasificacion"), trend_score=r.get("trend_score"))
    if competition is not None and not competition.empty:
        for k, g in competition.groupby("keyword"):
            if k not in rows:
                continue
            row = rows[k]
            g = g.sort_values("posicion")
            row["asins"] = list(dict.fromkeys([*row["asins"], *g["asin"].dropna().head(3)]))[:3]
            row["titulos"] = (row["titulos"] + " " + " ".join(g["titulo"].astype(str).head(5))).strip()
            if row.get("precio_ref") is None and g["precio_usd"].notna().any():
                row["precio_ref"] = round(float(g["precio_usd"].median()), 2)
    return pd.DataFrame(list(rows.values()))


def load_restrictions() -> pd.DataFrame:
    if RESTRICTIONS_PATH.exists():
        return pd.read_csv(RESTRICTIONS_PATH, dtype=str).fillna("")
    return pd.DataFrame(columns=RESTRICTION_COLUMNS)


def report(prods: pd.DataFrame, restrictions: pd.DataFrame | None = None, today: date | None = None,
           ids: pd.DataFrame | None = None) -> pd.DataFrame:
    """Status per product; SP-API answers on its reference ASINs override the rules.

    ids (data/identifiers.csv) adds the UPC of the reference ASINs."""
    cols = ["producto", "estado", "upc", "motivo", "evidencia", "sector", "subcategoria", "precio_ref", "tendencia",
            "trend_score", "asins"]
    if prods is None or prods.empty:
        return pd.DataFrame(columns=cols)
    checked = {} if restrictions is None or restrictions.empty else restrictions.set_index("asin").to_dict("index")
    out = []
    for _, p in prods.iterrows():
        # Titles only add evidence for "needs approval"; a keyword alone decides "open".
        status, reason = classify(f"{p['producto']} {p.get('sector', '')} {p.get('subcategoria', '')}", today)
        if status == LIBRE:
            t_status, t_reason = classify(p.get("titulos", ""), today)
            if t_status == APROBACION:
                status, reason = REVISAR, f"Algunos listados de referencia: {t_reason.lower()}"
        evidence = ESTIMADO
        asins = list(p.get("asins") or [])
        answers = [checked[a] for a in asins if a in checked and checked[a]["estado"] in ("libre", "restringido")]
        if answers:
            evidence = f"{VERIFICADO} ({len(answers)} ASIN)"
            blocked = [a for a in answers if a["estado"] == "restringido"]
            if blocked:
                status, reason = APROBACION, blocked[0]["motivos"] or "Amazon pide aprobación"
            elif status != APROBACION or "brand" not in reason:
                status, reason = LIBRE, "Amazon no pide aprobación a tu cuenta para estos ASIN"
        out.append({**{c: p.get(c) for c in cols if c in p}, "producto": p["producto"], "estado": status,
                    "motivo": reason, "evidencia": evidence, "asins": " ".join(asins),
                    "upc": identifiers.codes_for(asins, ids)})
    order = {LIBRE: 0, REVISAR: 1, APROBACION: 2}
    df = pd.DataFrame(out).reindex(columns=cols)
    df["_o"] = df["estado"].map(order)
    df["_v"] = ~df["evidencia"].str.startswith(VERIFICADO)
    return (df.sort_values(["_o", "_v", "trend_score"], ascending=[True, True, False], na_position="last")
              .drop(columns=["_o", "_v"]).reset_index(drop=True))


# ---------------------------------------------------------------- SP-API verification
def summarize_restrictions(restrictions: list[dict]) -> tuple[str, str]:
    if not restrictions:
        return "libre", ""
    reasons = []
    for r in restrictions:
        for reason in r.get("reasons") or []:
            reasons.append(reason.get("message") or reason.get("reasonCode") or "")
    text = "; ".join(dict.fromkeys(x for x in reasons if x))[:300]
    codes = {reason.get("reasonCode") for r in restrictions for reason in r.get("reasons") or []}
    if codes and codes <= {"ASIN_NOT_FOUND"}:
        return "no_encontrado", text
    return "restringido", text or "Amazon pide aprobación"


def verify(asins: list[str], client, seller_id: str, *, pause: float = 0.25, max_age_days: int = 14,
           progress=None) -> pd.DataFrame:
    """Ask SP-API about each ASIN not checked in the last max_age_days and store the answers."""
    current = load_restrictions()
    fresh = set()
    if not current.empty:
        age = (pd.Timestamp(date.today()) - pd.to_datetime(current["fecha"], errors="coerce")).dt.days
        fresh = set(current.loc[age <= max_age_days, "asin"])
    todo = [a for a in dict.fromkeys(asins) if a and a not in fresh]
    new = []
    for i, asin in enumerate(todo):
        try:
            estado, motivos = summarize_restrictions(client.listing_restrictions(asin, seller_id))
        except ValueError:
            continue
        new.append({"asin": asin, "estado": estado, "motivos": motivos, "fecha": date.today().isoformat()})
        if progress:
            progress(i + 1, len(todo))
        time.sleep(pause)  # restrictions API: 5 requests/second
    if new:
        merged = pd.concat([current[~current["asin"].isin([n["asin"] for n in new])], pd.DataFrame(new)])
        merged[RESTRICTION_COLUMNS].to_csv(RESTRICTIONS_PATH, index=False)
        return merged
    return current
