import random

from lake.generate import NEW_VARIANTS, WEEKS, make_lines


def test_lines_are_unique_per_invoice():
    lines = make_lines(random.Random(1), "medipro", new_variant=False)
    keys = [(l["invoice"], l["line_no"]) for l in lines]
    assert len(keys) == len(set(keys))
    assert {l["week"] for l in lines} == set(WEEKS)


def test_new_variant_only_hits_distrimed_from_week_33():
    lines = make_lines(random.Random(1), "distrimed", new_variant=True)
    hit = [l for l in lines if l["product"] in NEW_VARIANTS.values()]
    assert hit and all(l["week"] >= 33 for l in hit)
    assert not any(l["product"] in NEW_VARIANTS.values() for l in make_lines(random.Random(1), "medipro", True))
