"""Dirtiness corrupts ONLY observations, records every corruption as variant→canonical, and scales with d."""
from datagen import generate


def test_zero_dirtiness_is_clean():
    pkg = generate("logistics_demo", dirtiness=0.0, seed="ho-0")
    cmap = pkg["corruption_map"]
    assert not cmap["aliases"] and not cmap["weight_lb_ids"] and not cmap["status_nulled_ids"]
    assert not cmap["news_time_offset"] and not cmap["garbled_news"]
    # no shipment stored in lb, no nulled status
    assert all(s["unit"] == "kg" for s in pkg["stores"]["sql"]["shipments"])
    assert all(s["status"] is not None for s in pkg["stores"]["sql"]["shipments"])


def test_corruption_scales_with_dirtiness():
    def total(d):
        c = generate("logistics_demo", dirtiness=d, seed="ho-0")["corruption_map"]
        return (len(c["aliases"]) + len(c["weight_lb_ids"]) + len(c["status_nulled_ids"])
                + len(c["news_time_offset"]) + len(c["garbled_news"]))
    assert total(0.0) == 0
    assert total(0.9) > total(0.3) > 0  # more dirt ⇒ more corruption


def test_unit_drift_recorded_and_reversible():
    pkg = generate("logistics_demo", dirtiness=0.9, seed="ho-1")
    lb_ids = set(pkg["corruption_map"]["weight_lb_ids"])
    for s in pkg["stores"]["sql"]["shipments"]:
        # exactly the shipments in the corruption map are the ones stored in lb — a scorer can convert back
        assert (s["unit"] == "lb") == (s["id"] in lb_ids)


def test_garbled_news_flagged():
    pkg = generate("logistics_demo", dirtiness=0.9, seed="ho-0")
    garbled = set(pkg["corruption_map"]["garbled_news"])
    # every id the map flags as garbled exists in the news store (the map is a faithful index of corruption)
    news_ids = {n["id"] for n in pkg["stores"]["news"]}
    assert garbled.issubset(news_ids)


def test_dirtiness_never_touches_ground_truth():
    clean = generate("logistics_demo", dirtiness=0.0, seed="ho-4")
    dirty = generate("logistics_demo", dirtiness=0.9, seed="ho-4")
    assert clean["ground_truth"] == dirty["ground_truth"]
