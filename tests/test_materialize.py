"""Export modalities: JSON round-trips, per-store CSV row counts match, SQLite is real + queryable."""
import csv
import json
import sqlite3

from datagen import generate, to_csv, to_json, to_sqlite
from datagen.materialize import preview


def test_json_roundtrips(tmp_path):
    pkg = generate("logistics_demo", dirtiness=0.6, seed="ho-0")
    p = to_json(pkg, str(tmp_path / "pkg.json"))
    back = json.loads(open(p, encoding="utf-8").read())
    assert back["ground_truth"]["answers"] == pkg["ground_truth"]["answers"]
    assert back["manifest"]["counts"] == pkg["manifest"]["counts"]


def test_csv_row_counts(tmp_path):
    pkg = generate("logistics_demo", seed="ho-0")
    files = to_csv(pkg, str(tmp_path / "csv"))
    names = {p.split("\\")[-1].split("/")[-1] for p in files}
    assert {"warehouses.csv", "carriers.csv", "shipments.csv", "throughput.csv", "news.csv"} <= names
    ship_csv = next(p for p in files if p.endswith("shipments.csv"))
    with open(ship_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(pkg["stores"]["sql"]["shipments"])


def test_sqlite_is_queryable(tmp_path):
    pkg = generate("logistics_demo", seed="ho-0")
    db = to_sqlite(pkg, str(tmp_path / "pkg.db"))
    con = sqlite3.connect(db)
    try:
        n = con.execute("SELECT COUNT(*) FROM shipments WHERE status='delayed'").fetchone()[0]
    finally:
        con.close()
    delayed = sum(1 for s in pkg["stores"]["sql"]["shipments"] if s["status"] == "delayed")
    assert n == delayed  # the relational store answers a real query consistent with the package


def test_preview_is_deterministic_text():
    pkg = generate("logistics_demo", dirtiness=0.6, seed="ho-0")
    assert preview(pkg) == preview(pkg)
    assert "跨源真值" in preview(pkg) and "corruption_map" in preview(pkg)
