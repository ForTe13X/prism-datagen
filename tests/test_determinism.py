"""The load-bearing property: byte-reproducibility. Same knobs → byte-identical package, no clock/random."""
import json

from datagen import generate


def _canon(pkg):
    return json.dumps(pkg, ensure_ascii=False, sort_keys=True)


def test_same_knobs_byte_identical():
    a = generate("logistics_demo", dirtiness=0.6, link_explicitness=4, seed="ho-0")
    b = generate("logistics_demo", dirtiness=0.6, link_explicitness=4, seed="ho-0")
    assert _canon(a) == _canon(b)


def test_seed_changes_output_but_stays_reproducible():
    a0 = generate("logistics_demo", seed="ho-0")
    a0b = generate("logistics_demo", seed="ho-0")
    a1 = generate("logistics_demo", seed="ho-1")
    assert _canon(a0) == _canon(a0b)      # same seed reproduces
    assert _canon(a0) != _canon(a1)       # different seed differs


def test_truth_invariant_to_dirtiness_and_link():
    base = generate("logistics_demo", dirtiness=0.0, link_explicitness=1, seed="ho-2")
    for d in (0.0, 0.3, 0.6, 0.9):
        for l in (1, 2, 3, 4, 5):
            pkg = generate("logistics_demo", dirtiness=d, link_explicitness=l, seed="ho-2")
            # the two OBSERVATION-facing knobs must NEVER change the ground-truth answers
            assert pkg["ground_truth"]["answers"] == base["ground_truth"]["answers"]


def test_knobs_are_clamped():
    lo = generate("logistics_demo", dirtiness=-5, link_explicitness=-9, seed="ho-0")
    hi = generate("logistics_demo", dirtiness=99, link_explicitness=99, seed="ho-0")
    assert lo["dirtiness"] == 0.0 and lo["link_explicitness"] == 1
    assert hi["dirtiness"] == 1.0 and hi["link_explicitness"] == 5


def test_unknown_domain_returns_none():
    assert generate("does_not_exist") is None
