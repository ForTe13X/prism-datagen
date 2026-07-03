"""Command-line interface for prism-datagen.

    python -m datagen list
    python -m datagen gen --dirtiness 0.6 --link 4 --seed ho-0 --eval
    python -m datagen gen -d 0.6 -o out --format all
    python -m datagen sweep --over dirtiness

Prints a human-readable preview to stdout and (with --out) writes json/csv/sqlite. Deterministic: the same
flags always produce byte-identical files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    __version__,
    evaluate,
    generate,
    list_sources,
    preview,
    to_csv,
    to_json,
    to_sqlite,
)


def _fix_console() -> None:
    # the preview/news text is CJK; a Windows GBK console would crash on it — force UTF-8 output.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def _cmd_list(_: argparse.Namespace) -> int:
    srcs = list_sources()
    if not srcs:
        print("(no specs found under datagen/specs/)")
        return 1
    print("可用数据域(specs):")
    for s in srcs:
        print(f"  {s['id']:20s} {s['scenario']:20s} {s['title']}")
    return 0


def _cmd_gen(a: argparse.Namespace) -> int:
    pkg = generate(a.domain, dirtiness=a.dirtiness, link_explicitness=a.link, seed=a.seed)
    if pkg is None:
        print(f"错误:未知数据域 '{a.domain}'(用 `list` 查看可用域)", file=sys.stderr)
        return 2
    print(preview(pkg))
    if a.eval:
        ev = evaluate(pkg)
        print("")
        print("── 判别力(naive vs linked vs oracle · F1)──")
        print(f"  naive={ev['naive_f1']:.3f}  linked={ev['linked_f1']:.3f}  oracle={ev['oracle_f1']:.3f}  "
              f"gap(linked−naive)={ev['gap']:+.3f}")
    if a.out:
        outdir = Path(a.out)
        outdir.mkdir(parents=True, exist_ok=True)
        stem = f"{a.domain}_d{a.dirtiness}_l{a.link}_{pkg['seed']}"
        fmts = {"json", "csv", "sqlite"} if a.format == "all" else {a.format}
        wrote = []
        if "json" in fmts:
            wrote.append(to_json(pkg, str(outdir / f"{stem}.json")))
        if "csv" in fmts:
            wrote += to_csv(pkg, str(outdir / f"{stem}_csv"))
        if "sqlite" in fmts:
            wrote.append(to_sqlite(pkg, str(outdir / f"{stem}.db")))
        if wrote:
            print("\n── 已写出 ──")
            for w in wrote:
                print(f"  {w}")
    return 0


def _cmd_sweep(a: argparse.Namespace) -> int:
    print(f"扫描 {a.over}(domain={a.domain}, seed={a.seed or '(spec default)'})")
    print(f"  {a.over:>10s} | naive_f1  linked_f1  gap")
    print("  " + "-" * 44)
    knobs = [0.0, 0.3, 0.6, 0.9] if a.over == "dirtiness" else [1, 2, 3, 4, 5]
    for k in knobs:
        kw = {"dirtiness": k} if a.over == "dirtiness" else {"link_explicitness": k}
        base = {"dirtiness": 0.0, "link_explicitness": 4}
        base.update(kw)
        pkg = generate(a.domain, seed=a.seed, **base)  # type: ignore[arg-type]
        if pkg is None:
            print(f"错误:未知数据域 '{a.domain}'", file=sys.stderr)
            return 2
        ev = evaluate(pkg)
        print(f"  {k!s:>10s} | {ev['naive_f1']:7.3f}  {ev['linked_f1']:8.3f}  {ev['gap']:+.3f}")
    print("\n  说明:link 越隐晦 / 脏度越高,naive 越崩,linked(跨源联结)越能显出价值 —— 判别区间。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="datagen", description="确定性跨源数据包生成器(clean-room)")
    p.add_argument("--version", action="version", version=f"prism-datagen {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出可用数据域").set_defaults(func=_cmd_list)

    g = sub.add_parser("gen", help="生成一个数据包(预览到 stdout,可选写文件)")
    g.add_argument("-D", "--domain", default="logistics_demo", help="数据域 spec id(默认 logistics_demo)")
    g.add_argument("-d", "--dirtiness", type=float, default=0.0, help="脏度 0..1(默认 0)")
    g.add_argument("-l", "--link", type=int, default=4, help="link 显眼度 1..5(默认 4)")
    g.add_argument("-s", "--seed", default=None, help="随机种子字符串(默认用 spec 的 seed)")
    g.add_argument("-o", "--out", default=None, help="输出目录(给出才写文件)")
    g.add_argument("-f", "--format", choices=["json", "csv", "sqlite", "all"], default="json", help="写文件格式(默认 json)")
    g.add_argument("--eval", action="store_true", help="同时打印 naive/linked/oracle 判别力 F1")
    g.set_defaults(func=_cmd_gen)

    s = sub.add_parser("sweep", help="扫描一个旋钮,打印判别力/鲁棒性曲线")
    s.add_argument("-D", "--domain", default="logistics_demo")
    s.add_argument("--over", choices=["dirtiness", "link"], default="dirtiness", help="扫描哪个旋钮")
    s.add_argument("-s", "--seed", default=None)
    s.set_defaults(func=_cmd_sweep)
    return p


def main(argv: list[str] | None = None) -> int:
    _fix_console()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
