"""Export a generated package to concrete on-disk modalities — JSON (everything), per-store CSV, a real
queryable SQLite db (the relational store), and a human-readable text preview. All role-generic: they read
the package's own ``roles``/store keys, so any domain's package materializes, not just logistics.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .generator import to_sqlite  # re-exported so callers import one module

__all__ = ["to_json", "to_csv", "to_sqlite", "preview"]


def to_json(package: dict, path: str, *, indent: int = 2) -> str:
    """Dump the full package (stores + ground_truth + corruption_map + manifest) as UTF-8 JSON."""
    Path(path).write_text(json.dumps(package, ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


def to_csv(package: dict, outdir: str) -> list[str]:
    """One CSV per SQL store (columns = that store's own schema) + a long-form throughput.csv
    (hub_id, frame, value) + news.csv. Returns the paths written."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for table, rows in package["stores"]["sql"].items():
        if not rows:
            continue
        p = out / f"{table}.csv"
        cols = list(rows[0].keys())
        with p.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel reads CJK cleanly
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        written.append(str(p))

    ts = package["stores"]["timeseries"]
    metric_store = package["roles"]["metric_store"]
    series_map = ts.get(metric_store, {})
    if isinstance(series_map, dict) and series_map:
        p = out / f"{metric_store}.csv"
        with p.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["hub_id", "frame", "value"])
            for hid, series in series_map.items():
                for t, v in enumerate(series):
                    w.writerow([hid, t, v])
        written.append(str(p))

    news = package["stores"]["news"]
    if news:
        p = out / "news.csv"
        cols = [c for c in news[0].keys() if not c.startswith("_")]
        with p.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(news)
        written.append(str(p))
    return written


def _corruption_summary(cmap: dict) -> list[str]:
    lines = []
    if cmap.get("aliases"):
        lines.append(f"  别名改写(identity):{len(cmap['aliases'])} 处   {cmap['aliases']}")
    if cmap.get("weight_lb_ids"):
        lines.append(f"  单位漂移 kg→lb(unit):{len(cmap['weight_lb_ids'])} 条   {cmap['weight_lb_ids']}")
    if cmap.get("status_nulled_ids"):
        lines.append(f"  状态置空(missing):{len(cmap['status_nulled_ids'])} 条   {cmap['status_nulled_ids']}")
    if cmap.get("news_time_offset"):
        lines.append(f"  时间偏移(time):{len(cmap['news_time_offset'])} 条   {cmap['news_time_offset']}")
    if cmap.get("garbled_news"):
        lines.append(f"  编码乱码(encoding):{len(cmap['garbled_news'])} 条   {cmap['garbled_news']}")
    return lines or ["  (无 — dirtiness=0,观测未被污染)"]


def preview(package: dict, *, sample: int = 3) -> str:
    """A human-readable digest: manifest, ground-truth answers, corruption summary, a sample of each store.
    Deterministic (no clock) — the same package always yields the same preview text."""
    m = package["manifest"]
    roles = package["roles"]
    L: list[str] = []
    L.append(f"═══ {m['title']}  ({m['source_id']}) ═══")
    L.append(f"seed={m['seed']}  dirtiness={m['dirtiness']}  link_explicitness={m['link_explicitness']}")
    L.append(f"counts: {m['counts']}")
    L.append("")
    L.append("── 跨源真值(ground-truth · 始终保留,脏度不动它)──")
    for ev in package["ground_truth"]["events"]:
        L.append(f"  {ev['id']}  {ev['kind']} @ {ev[roles['record_hub_fk']]}/{ev['region']}/{ev['port']}  "
                 f"frame={ev['frame']}  → 延误 {ev[roles['record_ids_field']]}")
    L.append(f"  任务 explain_delays 答案(按新闻 id 键):{package['ground_truth']['answers']['explain_delays']}")
    L.append("")
    L.append(f"── 污染清单(corruption_map · variant→canonical,dirtiness={m['dirtiness']})──")
    L += _corruption_summary(package["corruption_map"])
    L.append("")
    L.append("── 观测样本(observation stores)──")
    sql = package["stores"]["sql"]
    for table, rows in sql.items():
        L.append(f"  [{table}] ({len(rows)} 行,示例 {min(sample, len(rows))} 行)")
        for r in rows[:sample]:
            L.append(f"    {r}")
    news = package["stores"]["news"]
    L.append(f"  [news] ({len(news)} 条,示例 {min(sample, len(news))} 条)")
    for n in news[:sample]:
        tag = "★真值" if n.get("_truth_event") else "干扰"
        L.append(f"    {n['id']} f{n['frame']} [{tag}] {n['body']}")
    return "\n".join(L)
