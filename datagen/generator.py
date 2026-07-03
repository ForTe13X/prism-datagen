"""Spec-driven heterogeneous data-package generator (DP1) — deterministic, clean-room.

Emit a cross-source dataset (SQL shipments/carriers/warehouses + per-warehouse throughput timeseries +
port/weather news) whose link ``news event → throughput anomaly → delayed shipments`` is PRE-EMBEDDED as
ground-truth. The truth is built FIRST; every store is then materialized to be consistent with it. Two
knobs, BOTH preserving the truth (they only touch OBSERVATIONS):
  * ``link_explicitness`` 1–5 — how conspicuously the news exposes which warehouse/shipments it hits
    (1 = literal ids, 5 = pure semantic), so a benchmark can sit in the discriminative interval;
  * ``dirtiness`` 0–1 — identity/unit/time/missing/numeric/encoding corruption of observations, with a
    ``corruption_map`` recording variant→canonical so a scorer can still recover the truth.

Deterministic: reuses ``_unit``/``_wiggle`` (no clock, no random) → byte-reproducible. HONEST SCOPE:
distributions are hand-set synthetic, NOT calibrated to real data; there is no PDF/NoSQL modality and no
LLM benchmark here — this is the deterministic substrate those would build on.
"""
from __future__ import annotations

import json
from pathlib import Path

from .core import _unit, _wiggle

SOURCES_DIR = Path(__file__).resolve().parent / "specs"

# The cross-source CAUSAL PATTERN (source-event → metric anomaly → affected records) is the reusable
# engine; everything DOMAIN-specific — entity/field names, id prefixes, news wording, aliases, ranges —
# lives in the spec's ``vocab`` + ``roles`` blocks, so a new domain = a new spec (zero generator code).
# ``roles`` map the pattern's slots to a domain's store/field names so the downstream discriminability/
# solvers stay generic. Defaults below reproduce the logistics scenario verbatim.
_DEFAULT_VOCAB = {
    "hub": {"prefix": "WH", "id_width": 3, "name_suffix": "中心仓"},
    "agent": {"prefix": "CR", "id_width": 3, "names": ["远洋速运", "华联物流", "中际货运", "顺捷供应链", "通达运输", "鹏程冷链"]},
    "record": {"prefix": "SHP", "id_width": 4, "label": "运单", "measure_field": "weight_kg", "measure_range": [50, 1000], "unit": "kg"},
    "metric": {"name": "throughput", "range": [200, 900]},
    "status": {"initial": "in_transit", "affected": "delayed", "settle_high": "on_time", "settle_low": "in_transit", "settle_threshold": 0.3},
    "event": {"kinds": ["台风封港", "道路中断"]},
    "aliases": {"华东": ["华東", "华东区", "HD"], "华南": ["华南区", "HN", "华南"], "华北": ["华北区", "HB"]},
    "news": {
        "l1": "{kind}影响 {hub_id}({hub_name});受影响{record_label}:{ids}。",
        "l2": "{kind}波及『{region}{name_suffix}』一带,多批货受阻。",
        "l3": "{kind}袭{region},约第 {frame} 帧前后港区作业受限。",
        "l4": "第 {frame} 帧前后,某港口因{kind}临时停摆,吞吐骤降。",
        "l5": "{kind}逼近{port}所在沿海,航运预计中断数日。",
        "distractor": "{region}近日{kind},暂未见明显影响。",
        "headline": "{kind}快讯", "distractor_headline": "{region}{kind}提示",
    },
}
_DEFAULT_ROLES = {
    "hub_store": "warehouses", "agent_store": "carriers", "record_store": "shipments", "metric_store": "throughput",
    "record_hub_fk": "warehouse_id", "record_agent_fk": "carrier_id", "record_frame": "dispatch_frame",
    "record_status": "status", "record_ids_field": "shipment_ids", "affected_status": "delayed",
}


def _cfg(src: dict) -> dict:
    """Resolve the domain config from a spec (vocab/roles/regions/ports), defaulting to logistics."""
    v = {**_DEFAULT_VOCAB, **(src.get("vocab") or {})}
    return {
        "vocab": v,
        "roles": {**_DEFAULT_ROLES, **(src.get("roles") or {})},
        "regions": src.get("regions", ["华东", "华南", "华北"]),
        "ports": src.get("ports", ["宁波港", "盐田港", "天津港"]),
    }


def _u(seed: str, *parts: object) -> float:
    return _unit(seed, *parts)


def _ri(seed: str, lo: int, hi: int, *parts: object) -> int:
    if hi <= lo:
        return lo
    return lo + int(_u(seed, *parts) * (hi - lo + 1)) % (hi - lo + 1)


def load_source(source_id: str) -> dict | None:
    if not source_id or not source_id.replace("_", "").isalnum():
        return None
    path = SOURCES_DIR / f"{source_id}.json"
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if doc.get("id") == source_id else None


def list_sources() -> list[dict]:
    out = []
    if SOURCES_DIR.exists():
        for p in sorted(SOURCES_DIR.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if d.get("id"):
                out.append({"id": d["id"], "title": d.get("title", d["id"]), "scenario": d.get("scenario", "")})
    return out


def _build_truth(seed: str, p: dict, cfg: dict) -> tuple[list, list, list, dict]:
    """Build hub/agent/record rows and the ground-truth events. Truth is authored here; the observation
    stores are made consistent with it afterwards. Domain labels/field-names come from cfg (vocab/roles)."""
    # counts accept generic (hubs/agents/records) OR the logistics-named keys, so a domain spec reads cleanly
    nw = int(p.get("hubs", p.get("warehouses", 3)))
    nc = int(p.get("agents", p.get("carriers", 3)))
    ns = int(p.get("records", p.get("shipments", 10)))
    frames, n_gt, win = int(p["frames"]), int(p["ground_truth_events"]), int(p["delay_window"])
    v, roles, regions, ports = cfg["vocab"], cfg["roles"], cfg["regions"], cfg["ports"]
    hub, agent, rec, st = v["hub"], v["agent"], v["record"], v["status"]
    rhf, raf, rfr, rst, rids = (roles["record_hub_fk"], roles["record_agent_fk"], roles["record_frame"],
                                roles["record_status"], roles["record_ids_field"])
    mlo, mhi = rec["measure_range"]

    warehouses = [
        {"id": f"{hub['prefix']}-{i + 1:0{hub['id_width']}d}", "region": regions[i % len(regions)],
         "port": ports[i % len(ports)], "name": f"{regions[i % len(regions)]}{hub['name_suffix']}"}
        for i in range(nw)
    ]
    carriers = [{"id": f"{agent['prefix']}-{i + 1:0{agent['id_width']}d}", "name": agent["names"][i % len(agent["names"])]}
                for i in range(nc)]
    shipments = []
    for j in range(ns):
        wh = warehouses[_ri(seed, 0, nw - 1, "shipwh", j)]
        cr = carriers[_ri(seed, 0, nc - 1, "shipcr", j)]
        shipments.append({
            "id": f"{rec['prefix']}-{j + 1:0{rec['id_width']}d}", rhf: wh["id"], raf: cr["id"],
            rfr: _ri(seed, 4, frames - 4, "shipfr", j),
            rec["measure_field"]: round(mlo + (mhi - mlo) * _u(seed, "shipwt", j), 1),
            rst: st["initial"], "unit": rec["unit"],
        })

    # ground-truth events: each on a DISTINCT hub (capped at nw), each carves a metric anomaly + affects
    # its records. Distinct hubs is the keystone — one event per hub means the hub-keyed anomaly/answer
    # maps below never collapse two truths into one.
    events = []
    used_idx: set[int] = set()
    lo_b = max(2, min(14, frames // 4))            # anchor band, derived from frames (not hardcoded)
    hi_b = max(lo_b + 1, frames - 6)
    kinds = v["event"]["kinds"]
    for e in range(min(n_gt, nw)):
        start = _ri(seed, 0, nw - 1, "evtwh", e)
        idx = next(((start + k) % nw for k in range(nw) if (start + k) % nw not in used_idx), None)
        if idx is None:
            break
        used_idx.add(idx)
        wh = warehouses[idx]
        # anchor the event frame to a real record of this hub so it actually affects something
        band = [s for s in shipments if s[rhf] == wh["id"] and lo_b <= s[rfr] <= hi_b]
        if band:
            f_e = band[_ri(seed, 0, len(band) - 1, "evtpivot", e)][rfr]
        else:
            f_e = _ri(seed, lo_b, hi_b, "evtfr", e)
        f_e = max(2, min(frames - 3, f_e))          # keep the anomaly frame inside the series
        kind = kinds[e % len(kinds)]
        hit = sorted(s["id"] for s in shipments if s[rhf] == wh["id"] and abs(s[rfr] - f_e) <= win)
        for s in shipments:
            if s["id"] in hit:
                s[rst] = st["affected"]
        events.append({"id": f"EVT-{e + 1}", rhf: wh["id"], "region": wh["region"],
                       "port": wh["port"], "frame": f_e, "kind": kind, rids: hit})
    # the rest settle deterministically (harmless filler)
    for s in shipments:
        if s[rst] == st["initial"]:
            s[rst] = st["settle_high"] if _u(seed, "settle", s["id"]) > st["settle_threshold"] else st["settle_low"]
    return warehouses, carriers, shipments, {"events": events, "frames": frames, "window": win}


def _throughput(seed: str, warehouses: list, truth: dict, cfg: dict) -> dict:
    """Per-hub metric series; ground-truth events carve a dip (the anomaly) around their frame."""
    frames = truth["frames"]
    rhf = cfg["roles"]["record_hub_fk"]
    lo, hi = (cfg["vocab"]["metric"]["range"] + [0, 1])[:2]
    anomaly_frame = {ev[rhf]: ev["frame"] for ev in truth["events"]}
    out = {}
    for w in warehouses:
        base = lo + (hi - lo) * (0.45 + 0.25 * _u(seed, "twbase", w["id"]))
        amp = (hi - lo) * 0.12
        series = []
        af = anomaly_frame.get(w["id"])
        for t in range(frames):
            v = base + amp * _wiggle(t, seed, "tw", w["id"])
            if af is not None and af - 1 <= t <= af + 2:  # the injected anomaly dip
                v -= (hi - lo) * (0.45 - 0.1 * abs(t - af))
            series.append(round(max(0.0, v), 1))
        out[w["id"]] = series
    return out


def _news(seed: str, p: dict, warehouses: list, truth: dict, link: int, cfg: dict) -> list:
    """News feed: ground-truth events become news items whose link to the hub is exposed at the requested
    explicitness (templates from vocab.news); the rest are distractors. Clean truth unchanged — only wording."""
    frames = truth["frames"]
    v, roles = cfg["vocab"], cfg["roles"]
    rhf, rids = roles["record_hub_fk"], roles["record_ids_field"]
    nv, hub, rec, kinds = v["news"], v["hub"], v["record"], v["event"]["kinds"]
    by_wh = {w["id"]: w for w in warehouses}
    news = []
    for ev in truth["events"]:
        w = by_wh[ev[rhf]]
        f = ev["frame"]
        level = 1 if link <= 1 else (5 if link >= 5 else link)  # L1 literal … L5 prose stand-in
        body = nv[f"l{level}"].format(
            kind=ev["kind"], hub_id=w["id"], hub_name=w["name"], region=w["region"], port=w["port"],
            frame=f, ids=",".join(ev[rids]), record_label=rec.get("label", ""), name_suffix=hub.get("name_suffix", ""),
        )
        news.append({"id": f"NEWS-{len(news) + 1:03d}", "frame": f, "kind": ev["kind"],
                     "headline": nv["headline"].format(kind=ev["kind"]), "body": body, "_truth_event": ev["id"]})
    # distractors: unrelated events at other frames/regions (no ground-truth effect)
    nd = max(0, int(p["news_events"]) - len(news))
    for k in range(nd):
        reg = warehouses[_ri(seed, 0, len(warehouses) - 1, "ndreg", k)]["region"]
        kind = kinds[_ri(seed, 0, len(kinds) - 1, "ndkind", k)]
        f = _ri(seed, 2, frames - 2, "ndfr", k)
        news.append({"id": f"NEWS-{len(news) + 1:03d}", "frame": f, "kind": kind,
                     "headline": nv["distractor_headline"].format(region=reg, kind=kind),
                     "body": nv["distractor"].format(region=reg, kind=kind), "_truth_event": None})
    news.sort(key=lambda n: n["frame"])
    return news


def _apply_dirtiness(seed: str, d: float, warehouses: list, shipments: list, throughput: dict, news: list, cfg: dict) -> dict:
    """Corrupt OBSERVATIONS in place at intensity ``d`` (0..1); record variant→canonical so a scorer can
    still recover the truth. The ground-truth (event answers) is never touched here."""
    cmap: dict = {"aliases": {}, "weight_lb_ids": [], "status_nulled_ids": [], "news_time_offset": {}, "garbled_news": []}
    if d <= 0:
        return cmap
    aliases = cfg["vocab"]["aliases"]
    mf, rst = cfg["vocab"]["record"]["measure_field"], cfg["roles"]["record_status"]

    # identity: alias region tokens inside news bodies (entity-resolution pressure)
    for n in news:
        for region, variants in aliases.items():
            if region in n["body"] and _u(seed, "dirtyalias", n["id"]) < d:
                variant = variants[_ri(seed, 0, len(variants) - 1, "dav", n["id"])]
                n["body"] = n["body"].replace(region, variant)
                cmap["aliases"][variant] = region
    # unit drift: some record measures stored in lb (schema/unit dirtiness)
    for s in shipments:
        if _u(seed, "dirtylb", s["id"]) < d * 0.5:
            s[mf] = round(s[mf] * 2.20462, 1)
            s["unit"] = "lb"
            cmap["weight_lb_ids"].append(s["id"])
    # missing: null some statuses (hurts a solver that reads the affected status)
    for s in shipments:
        if _u(seed, "dirtynull", s["id"]) < d * 0.3:
            s[rst] = None
            cmap["status_nulled_ids"].append(s["id"])
    # time: shift some news timestamps ±1..2 frames (hurts spatiotemporal alignment)
    for n in news:
        if _u(seed, "dirtytime", n["id"]) < d * 0.4:
            off = (1 + _ri(seed, 0, 1, "dto", n["id"])) * (1 if _u(seed, "dts", n["id"]) > 0.5 else -1)
            n["frame"] = max(0, n["frame"] + off)
            cmap["news_time_offset"][n["id"]] = off
    # numeric: freeze a couple throughput points (sensor glitch)
    for wid, series in throughput.items():
        for t in range(1, len(series)):
            if _u(seed, "dirtyfreeze", wid, t) < d * 0.05:
                series[t] = series[t - 1]
    # encoding: garble a fraction of news bodies (GBK↔UTF mojibake stand-in)
    for n in news:
        if _u(seed, "dirtygarble", n["id"]) < d * 0.25:
            n["body"] = n["body"].encode("utf-8", "replace").decode("latin-1", "replace")
            cmap["garbled_news"].append(n["id"])
    return cmap


def generate(source_id: str, *, dirtiness: float = 0.0, link_explicitness: int = 4, seed: str | None = None) -> dict | None:
    src = load_source(source_id)
    if src is None:
        return None
    d = max(0.0, min(1.0, float(dirtiness)))
    link = max(1, min(5, int(link_explicitness)))
    sd = str(seed) if seed else str(src.get("seed", source_id))
    p = src["params"]
    cfg = _cfg(src)
    roles = cfg["roles"]
    rhf, rids = roles["record_hub_fk"], roles["record_ids_field"]

    warehouses, carriers, shipments, truth = _build_truth(sd, p, cfg)
    throughput = _throughput(sd, warehouses, truth, cfg)
    news = _news(sd, p, warehouses, truth, link, cfg)
    corruption_map = _apply_dirtiness(sd, d, warehouses, shipments, throughput, news, cfg)

    # task answers are keyed by OBSERVATION-visible ids (news id / hub id) so a solver that only sees the
    # stores can be scored against them — the ground-truth event ids stay internal.
    news_of_event = {n["_truth_event"]: n["id"] for n in news if n.get("_truth_event")}
    answers = {
        "explain_delays": {news_of_event[ev["id"]]: ev[rids]
                           for ev in truth["events"] if ev["id"] in news_of_event},
        "anomaly_cause": {ev[rhf]: {"frame": ev["frame"], "news": news_of_event.get(ev["id"])}
                          for ev in truth["events"]},
    }
    return {
        "source_id": source_id, "seed": sd, "dirtiness": d, "link_explicitness": link,
        "roles": roles,  # lets the generic discriminability/solvers find each domain's store/field names
        "stores": {
            "sql": {roles["hub_store"]: warehouses, roles["agent_store"]: carriers, roles["record_store"]: shipments},
            "timeseries": {roles["metric_store"]: throughput, "frames": truth["frames"]},
            "news": news,
        },
        "ground_truth": {"events": truth["events"], "answers": answers, "window": truth["window"]},
        "corruption_map": corruption_map,
        "tasks": src.get("tasks", []),
        "manifest": {
            "source_id": source_id, "title": src.get("title", source_id), "seed": sd,
            "dirtiness": d, "link_explicitness": link,
            "counts": {roles["hub_store"]: len(warehouses), roles["agent_store"]: len(carriers),
                       roles["record_store"]: len(shipments), "news": len(news),
                       "frames": truth["frames"], "ground_truth_events": len(truth["events"])},
            "scope": src.get("notes", {}).get("scope", ""), "honesty": src.get("notes", {}).get("honesty", ""),
        },
    }


def _sqlite_type(v: object) -> str:
    # bool is an int subclass — checked first only conceptually; here INTEGER covers it fine
    return "INTEGER" if isinstance(v, int) else "REAL" if isinstance(v, float) else "TEXT"


def to_sqlite(package: dict, path: str) -> str:
    """Materialize the SQL store as a real (queryable) SQLite db — the genuinely-relational modality.
    Role-generic: one table per store (named by its store key), columns inferred from each store's own
    record schema, so ANY domain's package materializes — not just logistics. ``id`` becomes the PK."""
    import sqlite3

    sql = package["stores"]["sql"]
    con = sqlite3.connect(path)
    try:
        cur = con.cursor()
        for table, rows in sql.items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            coldefs = ", ".join(
                f'"{c}" ' + ("TEXT PRIMARY KEY" if c == "id" else _sqlite_type(rows[0][c])) for c in cols
            )
            cur.execute(f'CREATE TABLE "{table}" ({coldefs})')
            placeholders = ",".join("?" for _ in cols)
            cur.executemany(
                f'INSERT INTO "{table}" VALUES ({placeholders})',
                [tuple(r.get(c) for c in cols) for r in rows],
            )
        con.commit()
    finally:
        con.close()
    return path
