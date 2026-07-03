# prism-datagen

[中文](README.md)

A deterministic cross-source data package generator. It creates messy datasets with embedded ground truth, so rule-based solvers and LLM pipelines can be scored exactly.

The core uses only the Python standard library. Generated packages can be exported as JSON, CSV, and SQLite, or inspected through the optional local web UI.

## How It Works

The generator starts from a known answer, then builds observations around it:

1. Define the ground truth, such as "storm event X caused shipments A and B to be delayed".
2. Split the evidence across multiple sources: shipment tables, warehouse throughput time series, and news items.
3. Add controlled noise: aliases, unit changes, missing values, shifted timestamps, numeric perturbations, and malformed text.

The answer remains unchanged while the surface data gets harder to read. This lets a benchmark separate real cross-source reasoning from simple string matching.

Two controls shape the difficulty:

| Control | Effect |
|---|---|
| `dirtiness` from 0 to 1 | Adds more aliases, missing fields, unit changes, timestamp shifts, numeric noise, and malformed text |
| `link_explicitness` from 1 to 5 | Moves from direct identifiers toward implicit semantic clues |

The same seed always produces the same package byte-for-byte, which makes runs comparable across time and machines.

## Demo

[3.5-minute walkthrough video, Chinese narration with bilingual subtitles](demo/prism-datagen-demo.mp4)

![Overview: score and ground-truth chain on the left, three data sources on the right](docs/screenshots/01_overview.png)

Hovering a ground-truth chain highlights the corresponding evidence across sources:

![Cross-source highlight on ground-truth hover](docs/screenshots/08_truthchain_hover.png)

## Quick Start

Python 3.10 or newer is required.

```bash
python -m datagen gen -d 0.6 -l 4 -s ho-0 --eval
python -m datagen gen -d 0.6 -s ho-0 -o out -f all
python -m datagen sweep --over dirtiness
```

Optional web UI:

```bash
pip install fastapi uvicorn
python server.py
```

Then open `http://127.0.0.1:8123`.

Python API:

```python
from datagen import evaluate, generate, preview

pkg = generate("logistics_demo", dirtiness=0.6, link_explicitness=4, seed="ho-0")
print(preview(pkg))
print(evaluate(pkg))
```

## Built-In Difficulty Checks

The project includes three reference solvers:

- `oracle`: reads the embedded answer and should always score 1.0.
- `naive`: uses literal matching and mostly single-source evidence.
- `linked`: uses deterministic cross-source alignment over entity, place, and time clues.

| Explicitness | naive F1 | linked F1 |
|---|---:|---:|
| L1, direct identifier | 1.000 | 0.800 |
| L2-L5, increasingly implicit | 0.000 | 0.800 |

Increasing dirtiness lowers linked performance in a smooth trend across seeds, which provides a simple robustness curve.

## Package Contents

A generated package contains:

- `stores`: observation sources, including relational tables, time series, and news text.
- `ground_truth`: event-to-record links used for exact scoring.
- `corruption_map`: reversible records of surface corruption when available.
- `manifest`: seed, controls, counts, and scope notes.

Exports include complete JSON, one CSV per table, and a queryable SQLite database. Example outputs live under [examples/](examples/).

## Layout

```text
datagen/          Generator core, standard library only
  specs/          Domain specs; add a spec to add a domain
server.py + web/  Local visual explorer
tests/            Determinism, recoverability, dirtiness, discriminability, export, and CLI tests
docs/             Technical docs, test docs, user manual, and PRD
demo/             Walkthrough video and reproduction scripts
examples/         Sample JSON, CSV, and SQLite outputs
```

```bash
python -m pytest tests/ -q
```

## Scope

- The data distribution is synthetic and manually configured. It is useful for controlled evaluation, not as evidence about real-world logistics data.
- The built-in `linked` solver is a deterministic reference baseline, not a semantic reasoning model.
- The robustness curve is a multi-seed trend; individual seeds may vary.
- Numeric freezing is not currently represented in `corruption_map`; other corruption types are tracked.
- The current discriminability checks focus on `explain_delays`.
- PDF and NoSQL modalities are not included. SQLite materializes only relational tables.
- The current domain is logistics with one causal pattern: event -> anomaly -> delay. New domains are added through specs.
- This project was extracted from Prism as a standalone generator and contains only its own code.
