"""Deterministic primitives — the whole reason this generator is byte-reproducible.

Every value in a data package is ultimately a function of a stable seed hashed into [0, 1]: no ``random``,
no clock, no ambient state. Two runs with the same knobs produce byte-identical output, on any machine.
``_unit`` is the hash→[0,1] map; ``_wiggle`` is a smooth deterministic signal over the time/frame axis
(used to shape the throughput series). Both are copied verbatim from the Prism sandbox they were grown in.
"""
from __future__ import annotations

import hashlib
import math


def _unit(*parts: object) -> float:
    """Stable float in [0,1] from a seed (sha256 → first 8 hex digits; ``ffffffff`` maps to 1.0)."""
    seed = "|".join(str(p) for p in parts)
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def _wiggle(frame: int, *seed: object) -> float:
    """A smooth, deterministic signal in ~[-1, 1] over the frame axis, mean ≈ 0.

    A slow trend (period ~11–33 frames) plus a small faster ripple, with hash-derived
    frequencies/phases per seed. No randomness, no clock — purely a function of ``frame`` and seed,
    so replay is byte-reproducible. Used to drift the throughput series around its baseline.
    """
    f1 = 0.03 + 0.09 * _unit(*seed, "wf1")  # slow trend
    p1 = _unit(*seed, "wp1")
    f2 = 0.13 + 0.17 * _unit(*seed, "wf2")  # faster ripple
    p2 = _unit(*seed, "wp2")
    main = math.sin(2 * math.pi * (f1 * frame + p1))
    ripple = 0.3 * math.sin(2 * math.pi * (f2 * frame + p2))
    return (main + ripple) / 1.3
