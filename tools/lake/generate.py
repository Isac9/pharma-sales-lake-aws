"""Generate 12 weeks of sales files from 4 fictional wholesalers, plus the alias tables.

Like real wholesaler exports, each weekly file is CUMULATIVE: week 30 contains
weeks 27 to 30 again. Summing every file would count the same sale many times.

    python -m lake.generate                 # clean data
    python -m lake.generate --new-variant   # from week 33, distrimed writes "SUSP" instead of "SUS"
"""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING_DIR = ROOT / "data" / "landing"
REFERENCE_DIR = ROOT / "reference"

WHOLESALERS = ["medipro", "pharmalink", "santeplus", "distrimed"]
WEEKS = list(range(27, 39))
YEAR = 2026

# product code -> (base price in XOF, name used by medipro, pharmalink, santeplus, distrimed)
PRODUCTS = {
    "P001": (600, "PARACETAMOL 500MG CP B/20", "Paracétamol 500 mg cp bte 20", "PARA 500 CPR X20", "PARACETAMOL 500 CP"),
    "P002": (1500, "AMOXICILLINE 500MG GEL B/12", "Amoxicilline 500 mg gél bte 12", "AMOX 500 GEL X12", "AMOXICILLINE 500 GELULE"),
    "P003": (1800, "AMOXICILLINE 250MG/5ML SUSP BUV", "Amoxicilline 250 mg/5 ml susp", "AMOX 250 SUSP 60ML", "AMOXICILLINE 250 SUS"),
    "P004": (900, "IBUPROFENE 400MG CP B/30", "Ibuprofène 400 mg cp bte 30", "IBU 400 CPR X30", "IBUPROFENE 400 CP"),
    "P005": (1200, "METRONIDAZOLE 125MG/5ML SUSP", "Métronidazole 125 mg/5 ml susp", "METRO 125 SUSP 120ML", "METRONIDAZOLE 125 SUS"),
    "P006": (2500, "ARTEMETHER/LUMEFANTRINE 20/120 B/24", "Artéméther-luméfantrine 20/120 bte 24", "AL 20/120 CPR X24", "ARTEMETHER LUMEF 20/120"),
    "P007": (1100, "COTRIMOXAZOLE 240MG/5ML SUSP", "Cotrimoxazole 240 mg/5 ml susp", "COTRI 240 SUSP 100ML", "COTRIMOXAZOLE 240 SUS"),
    "P008": (1400, "OMEPRAZOLE 20MG GEL B/14", "Oméprazole 20 mg gél bte 14", "OMEP 20 GEL X14", "OMEPRAZOLE 20 GELULE"),
    "P009": (150, "SRO SACHET B/50", "Sels de réhydratation orale sachet", "SRO SACH X50", "SRO SACHET"),
    "P010": (800, "PARACETAMOL 120MG/5ML SIROP", "Paracétamol 120 mg/5 ml sirop", "PARA 120 SIR 100ML", "PARACETAMOL 120 SIR"),
    "P011": (700, "ZINC 20MG CP DISP B/10", "Zinc 20 mg cp dispersible bte 10", "ZINC 20 CPR X10", "ZINC 20 CP DISP"),
    "P012": (300, "ALBENDAZOLE 400MG CP", "Albendazole 400 mg cp", "ALBEN 400 CPR X1", "ALBENDAZOLE 400 CP"),
}
# The second spelling distrimed starts using (the "SUS" / "SUSP" story)
NEW_VARIANTS = {"P003": "AMOXICILLINE 250 SUSP", "P005": "METRONIDAZOLE 125 SUSP",
                "P007": "COTRIMOXAZOLE 240 SUSP", "P010": "PARACETAMOL 120 SIROP"}

# locality code -> (medipro, pharmalink and distrimed, santeplus)
LOCALITIES = {
    "ABJ-YOP": ("ABIDJAN-YOPOUGON", "Yopougon", "YOP"),
    "ABJ-COC": ("ABIDJAN-COCODY", "Cocody", "COC"),
    "ABJ-ABO": ("ABIDJAN-ABOBO", "Abobo", "ABO"),
    "BKE": ("BOUAKE", "Bouaké", "BKE"),
    "YAM": ("YAMOUSSOUKRO", "Yamoussoukro", "YAKRO"),
    "SPD": ("SAN-PEDRO", "San-Pédro", "SPY"),
    "KOR": ("KORHOGO", "Korhogo", "KHG"),
    "DAL": ("DALOA", "Daloa", "DLA"),
}
LOCALITY_STYLE = {"medipro": 0, "pharmalink": 1, "santeplus": 2, "distrimed": 1}
INVOICE_FORMAT = {"medipro": "MP26-{:06d}", "pharmalink": "FAC{}", "santeplus": "SP/26/{}", "distrimed": "D-{}"}


def make_lines(rng, wholesaler, new_variant):
    index = WHOLESALERS.index(wholesaler)
    lines, invoice, n = [], 0, 0
    for week in WEEKS:
        monday = datetime.fromisocalendar(YEAR, week, 1)
        for _ in range(rng.randint(40, 60)):
            invoice += 1
            day = monday + timedelta(days=rng.randint(0, 5))
            locality = rng.choice(list(LOCALITIES))
            for line_no in range(1, rng.randint(1, 4) + 1):
                n += 1
                code = rng.choice(list(PRODUCTS))
                price, *names = PRODUCTS[code]
                name = names[index]
                if new_variant and wholesaler == "distrimed" and week >= 33 and code in NEW_VARIANTS and n % 2 == 0:
                    name = NEW_VARIANTS[code]
                lines.append({"week": week, "invoice": INVOICE_FORMAT[wholesaler].format(invoice), "line_no": line_no,
                              "date": day, "product": name, "locality": LOCALITIES[locality][LOCALITY_STYLE[wholesaler]],
                              "quantity": rng.randint(1, 50), "unit_price": round(price * rng.uniform(0.95, 1.10))})
    return lines


def fr_number(value):
    return f"{value:.2f}".replace(".", ",")


def to_row(wholesaler, line):
    q, p, d = line["quantity"], line["unit_price"], line["date"]
    if wholesaler == "medipro":
        return {"invoice_no": line["invoice"], "line_no": line["line_no"], "invoice_date": d.strftime("%Y-%m-%d"),
                "product": line["product"], "locality": line["locality"], "qty": q, "unit_price": f"{p:.2f}"}
    if wholesaler == "pharmalink":
        return {"N_FACTURE": line["invoice"], "LIGNE": line["line_no"], "DATE": d.strftime("%d/%m/%Y"),
                "DESIGNATION": line["product"], "VILLE": line["locality"], "QTE": q, "PU": fr_number(p)}
    if wholesaler == "santeplus":  # sends the line total, not the unit price
        return {"doc": line["invoice"], "item": line["line_no"], "date": d.strftime("%Y%m%d"),
                "article": line["product"], "zone": line["locality"], "quantity": q, "amount": f"{p * q:.2f}"}
    return {"Facture": line["invoice"], "Ligne": line["line_no"], "Date": d.strftime("%d/%m/%Y"),
            "Produit": line["product"], "Localite": line["locality"], "Quantite": q, "Prix": fr_number(p)}


def write_reference():
    REFERENCE_DIR.mkdir(exist_ok=True)
    with open(REFERENCE_DIR / "product_aliases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["wholesaler", "source_name", "product_code"])
        for code, (_, *names) in PRODUCTS.items():
            for wholesaler, name in zip(WHOLESALERS, names):
                w.writerow([wholesaler, name, code])
    with open(REFERENCE_DIR / "locality_aliases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_name", "locality_code"])
        for code, names in LOCALITIES.items():
            for name in names:
                w.writerow([name, code])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-variant", action="store_true")
    parser.add_argument("--write-reference", action="store_true", help="rewrite reference/*.csv from scratch")
    args = parser.parse_args(argv)
    if args.write_reference:
        write_reference()
    for i, wholesaler in enumerate(WHOLESALERS):
        lines = make_lines(random.Random(100 + i), wholesaler, args.new_variant)
        out = LANDING_DIR / wholesaler
        out.mkdir(parents=True, exist_ok=True)
        encoding = "cp1252" if wholesaler == "distrimed" else "utf-8"
        delimiter = ";" if wholesaler in ("pharmalink", "distrimed") else ","
        for week in WEEKS:
            rows = [to_row(wholesaler, l) for l in lines if l["week"] <= week]  # cumulative file
            with open(out / f"{YEAR}-W{week}.csv", "w", newline="", encoding=encoding) as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=delimiter)
                writer.writeheader()
                writer.writerows(rows)
        print(f"  {wholesaler}: {len(lines)} sale lines, {len(WEEKS)} cumulative weekly files")


if __name__ == "__main__":
    main()
