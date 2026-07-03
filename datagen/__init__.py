"""prism-datagen — a deterministic, clean-room cross-source data-package generator.

Generate a messy multi-store dataset (SQL + timeseries + news) whose cross-source causal link
(``news event → throughput anomaly → delayed shipments``) is PRE-EMBEDDED as ground-truth, with two knobs
(``dirtiness`` 0–1, ``link_explicitness`` 1–5) that corrupt/obscure ONLY the observations while the truth
is always recoverable. Byte-reproducible (sha256-seeded; no random, no clock).

    from datagen import generate, evaluate, preview
    pkg = generate("logistics_demo", dirtiness=0.6, link_explicitness=4, seed="ho-0")
    print(preview(pkg))
    print(evaluate(pkg))            # naive vs linked vs oracle F1
"""
from __future__ import annotations

from .generator import generate, list_sources, load_source, to_sqlite
from .materialize import preview, to_csv, to_json
from .oracle import (
    evaluate,
    linked_solve,
    naive_solve,
    observation_view,
    oracle_solve,
    score,
)

__version__ = "1.0.0"
__all__ = [
    "generate", "list_sources", "load_source",
    "evaluate", "observation_view", "oracle_solve", "naive_solve", "linked_solve", "score",
    "to_json", "to_csv", "to_sqlite", "preview",
    "__version__",
]
