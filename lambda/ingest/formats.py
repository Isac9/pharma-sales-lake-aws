"""Every wholesaler sends its weekly file in its own format.

This module turns any of them into the same canonical record, then matches
product and locality names against the alias tables. Pure functions only:
no AWS here, so everything is unit tested.
"""
import csv
import io
from collections import Counter
from datetime import datetime
from decimal import Decimal

FORMATS = {
    "medipro": {
        "encoding": "utf-8", "delimiter": ",", "decimal": ".", "date": "%Y-%m-%d", "price_is_line_total": False,
        "columns": {"invoice_no": "invoice_no", "line_no": "line_no", "date": "invoice_date", "product": "product",
                    "locality": "locality", "quantity": "qty", "price": "unit_price"},
    },
    "pharmalink": {
        "encoding": "utf-8", "delimiter": ";", "decimal": ",", "date": "%d/%m/%Y", "price_is_line_total": False,
        "columns": {"invoice_no": "N_FACTURE", "line_no": "LIGNE", "date": "DATE", "product": "DESIGNATION",
                    "locality": "VILLE", "quantity": "QTE", "price": "PU"},
    },
    "santeplus": {
        "encoding": "utf-8", "delimiter": ",", "decimal": ".", "date": "%Y%m%d", "price_is_line_total": True,
        "columns": {"invoice_no": "doc", "line_no": "item", "date": "date", "product": "article",
                    "locality": "zone", "quantity": "quantity", "price": "amount"},
    },
    "distrimed": {
        "encoding": "cp1252", "delimiter": ";", "decimal": ",", "date": "%d/%m/%Y", "price_is_line_total": False,
        "columns": {"invoice_no": "Facture", "line_no": "Ligne", "date": "Date", "product": "Produit",
                    "locality": "Localite", "quantity": "Quantite", "price": "Prix"},
    },
}


def parse_key(key):
    """landing/medipro/2026-W30.csv -> ("medipro", "2026-W30")"""
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "landing" or not parts[2].endswith(".csv"):
        raise ValueError(f"unexpected key: {key}")
    if parts[1] not in FORMATS:
        raise ValueError(f"unknown wholesaler: {parts[1]}")
    return parts[1], parts[2][:-4]


def normalize_text(value):
    """Upper case and single spaces. It does NOT guess abbreviations: SUS and SUSP stay different."""
    return " ".join((value or "").strip().upper().split())


def to_decimal(value, decimal_sep):
    value = value.strip().replace(" ", "")
    if decimal_sep == ",":
        value = value.replace(".", "").replace(",", ".")
    return Decimal(value)


def parse_file(body, wholesaler, source_file, file_week):
    fmt = FORMATS[wholesaler]
    col = fmt["columns"]
    reader = csv.DictReader(io.StringIO(body.decode(fmt["encoding"])), delimiter=fmt["delimiter"])
    rows = []
    for line in reader:
        quantity = int(line[col["quantity"]])
        price = to_decimal(line[col["price"]], fmt["decimal"])
        rows.append({
            "wholesaler": wholesaler,
            "invoice_no": line[col["invoice_no"]].strip(),
            "line_no": int(line[col["line_no"]]),
            "invoice_date": datetime.strptime(line[col["date"]].strip(), fmt["date"]).date().isoformat(),
            "product_source_name": line[col["product"]].strip(),
            "locality_source_name": line[col["locality"]].strip(),
            "quantity": quantity,
            "amount_xof": price if fmt["price_is_line_total"] else price * quantity,
            "source_file": source_file,
            "file_week": file_week,
        })
    return rows


def load_aliases(csv_text, per_wholesaler):
    """product_aliases.csv: wholesaler,source_name,product_code / locality_aliases.csv: source_name,locality_code"""
    aliases = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        scope = row["wholesaler"] if per_wholesaler else "*"
        code = row.get("product_code") or row.get("locality_code")
        aliases[(scope, normalize_text(row["source_name"]))] = code
    return aliases


def apply_aliases(rows, products, localities):
    """Returns (canonical rows, unknown values). Unknown values are counted, never dropped silently."""
    good, unknown = [], {"product": Counter(), "locality": Counter()}
    for row in rows:
        product = products.get((row["wholesaler"], normalize_text(row["product_source_name"])))
        locality = localities.get(("*", normalize_text(row["locality_source_name"])))
        if product is None:
            unknown["product"][row["product_source_name"]] += 1
        if locality is None:
            unknown["locality"][row["locality_source_name"]] += 1
        if product and locality:
            good.append({**row, "product_code": product, "locality_code": locality})
    return good, {kind: dict(counts) for kind, counts in unknown.items() if counts}
