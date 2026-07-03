"""The discriminative interval: naive (literal) collapses as the link is hidden; linked (cross-source join)
still recovers — so the task genuinely needs cross-source reasoning. Dirtiness then degrades linked."""
from datagen import evaluate, generate


def test_naive_perfect_when_link_is_literal():
    # L1 = the news literally names the shipment ids ⇒ even a literal solver nails it
    pkg = generate("logistics_demo", dirtiness=0.0, link_explicitness=1, seed="ho-0")
    ev = evaluate(pkg)
    assert ev["naive_f1"] == 1.0


def test_naive_collapses_when_link_hidden():
    # L4 = spatiotemporal prose, no literal id/hub ⇒ the literal solver has nothing to match
    pkg = generate("logistics_demo", dirtiness=0.0, link_explicitness=4, seed="ho-0")
    ev = evaluate(pkg)
    assert ev["naive_f1"] < ev["linked_f1"]   # linked wins where naive can't
    assert ev["gap"] > 0


def test_linked_beats_naive_in_discriminative_interval():
    # averaged over seeds at a hidden link, linked should out-recover naive
    gaps = [evaluate(generate("logistics_demo", dirtiness=0.0, link_explicitness=4, seed=f"ho-{i}"))["gap"]
            for i in range(8)]
    assert sum(gaps) / len(gaps) > 0            # positive mean gap = the cross-source task has teeth


def test_dirtiness_degrades_linked_on_the_mean():
    # HONEST claim: linked leans on region/port/time cues, so corrupting them degrades it — but only ON THE
    # MEAN across seeds, NOT strictly per-seed (on a single seed, corruption can occasionally flip a
    # borderline match the right way). Averaged over 8 seeds it is a monotone-ish robustness curve.
    def mean_linked(d):
        xs = [evaluate(generate("logistics_demo", dirtiness=d, link_explicitness=4, seed=f"ho-{i}"))["linked_f1"]
              for i in range(8)]
        return sum(xs) / len(xs)
    assert mean_linked(0.9) < mean_linked(0.0)          # heavy dirt clearly hurts on average
    assert mean_linked(0.0) >= mean_linked(0.3) >= mean_linked(0.6) >= mean_linked(0.9)  # monotone curve


def test_oracle_always_one():
    assert evaluate(generate("logistics_demo", seed="ho-2"))["oracle_f1"] == 1.0
