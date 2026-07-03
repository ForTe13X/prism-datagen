"""Tiny local web UI for prism-datagen — sliders for the two knobs, live re-generate, and a visual of the
cross-source ground-truth chain + the corruptions. Pure read-only: it just calls the library and returns
JSON; the single-page UI (web/index.html) renders it. Run:

    pip install fastapi uvicorn
    python server.py                     # → http://127.0.0.1:8123

Everything the UI shows comes from the SAME deterministic generator the CLI uses — no separate code path.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from datagen import evaluate, generate, list_sources

_WEB = Path(__file__).resolve().parent / "web"
app = FastAPI(title="prism-datagen", description="确定性跨源数据包生成器 · 本地可视化")


@app.get("/api/specs")
def specs() -> list[dict]:
    return list_sources()


@app.get("/api/generate")
def api_generate(domain: str = "logistics_demo", dirtiness: float = 0.0,
                 link: int = 4, seed: str = "") -> JSONResponse:
    pkg = generate(domain, dirtiness=dirtiness, link_explicitness=link, seed=seed or None)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"unknown domain: {domain}")
    pkg["evaluation"] = evaluate(pkg)     # naive vs linked vs oracle, at these knobs
    return JSONResponse(pkg)


@app.get("/api/sweep")
def api_sweep(domain: str = "logistics_demo", over: str = "dirtiness", seed: str = "") -> JSONResponse:
    knobs = [0.0, 0.3, 0.6, 0.9] if over == "dirtiness" else [1, 2, 3, 4, 5]
    rows = []
    for k in knobs:
        kw = {"dirtiness": k} if over == "dirtiness" else {"link_explicitness": k}
        base = {"dirtiness": 0.0, "link_explicitness": 4, **kw}
        pkg = generate(domain, seed=seed or None, **base)  # type: ignore[arg-type]
        if pkg is None:
            raise HTTPException(status_code=404, detail=f"unknown domain: {domain}")
        ev = evaluate(pkg)
        rows.append({"knob": k, "naive_f1": ev["naive_f1"], "linked_f1": ev["linked_f1"], "gap": ev["gap"]})
    return JSONResponse({"over": over, "rows": rows})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_WEB / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8123)
