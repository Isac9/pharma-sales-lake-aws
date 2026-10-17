from decimal import Decimal

import pytest

from formats import apply_aliases, load_aliases, normalize_text, parse_file, parse_key, to_decimal

PRODUCTS = load_aliases("wholesaler,source_name,product_code\n"
                        "distrimed,AMOXICILLINE 250 SUS,P003\n"
                        "santeplus,PARA 500 CPR X20,P001\n", per_wholesaler=True)
LOCALITIES = load_aliases("source_name,locality_code\nYopougon,ABJ-YOP\nYOP,ABJ-YOP\n", per_wholesaler=False)


def test_parse_key():
    assert parse_key("landing/medipro/2026-W30.csv") == ("medipro", "2026-W30")


@pytest.mark.parametrize("key", ["landing/unknown/2026-W30.csv", "other/medipro/2026-W30.csv", "landing/medipro/x.txt"])
def test_parse_key_rejects_unexpected_files(key):
    with pytest.raises(ValueError):
        parse_key(key)


def test_french_decimals():
    assert to_decimal("1 250,50", ",") == Decimal("1250.50")
    assert to_decimal("1250.50", ".") == Decimal("1250.50")


def test_normalize_does_not_guess_abbreviations():
    assert normalize_text("  amoxicilline   250 sus ") == "AMOXICILLINE 250 SUS"
    assert normalize_text("AMOXICILLINE 250 SUSP") != normalize_text("AMOXICILLINE 250 SUS")


def test_distrimed_file_in_cp1252_with_unit_price():
    body = "Facture;Ligne;Date;Produit;Localite;Quantite;Prix\nD-1;1;03/07/2026;AMOXICILLINE 250 SUS;Yopougon;3;1800,00\n"
    [row] = parse_file(body.encode("cp1252"), "distrimed", "landing/distrimed/2026-W27.csv", "2026-W27")
    assert row["invoice_date"] == "2026-07-03"
    assert row["amount_xof"] == Decimal("5400.00")  # quantity x unit price


def test_santeplus_sends_the_line_total():
    body = "doc,item,date,article,zone,quantity,amount\nSP/26/1,1,20260703,PARA 500 CPR X20,YOP,10,6000.00\n"
    [row] = parse_file(body.encode(), "santeplus", "k", "2026-W27")
    assert row["amount_xof"] == Decimal("6000.00")


def test_new_spelling_is_reported_not_dropped():
    rows = [
        {"wholesaler": "distrimed", "product_source_name": "AMOXICILLINE 250 SUS", "locality_source_name": "Yopougon"},
        {"wholesaler": "distrimed", "product_source_name": "AMOXICILLINE 250 SUSP", "locality_source_name": "Yopougon"},
    ]
    good, unknown = apply_aliases(rows, PRODUCTS, LOCALITIES)
    assert [r["product_code"] for r in good] == ["P003"]
    assert unknown == {"product": {"AMOXICILLINE 250 SUSP": 1}}


def test_product_aliases_are_per_wholesaler():
    rows = [{"wholesaler": "medipro", "product_source_name": "PARA 500 CPR X20", "locality_source_name": "YOP"}]
    _, unknown = apply_aliases(rows, PRODUCTS, LOCALITIES)
    assert unknown == {"product": {"PARA 500 CPR X20": 1}}
