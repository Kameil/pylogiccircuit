"""Command-line interface for pylogiccircuit."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .preview import render_circuit_png
from .project import Project
from .simulator import Simulator
from .watch import watch_file


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pylogiccircuit",
        description="Inspect, verify, simulate, render, and live-preview LogicCircuit files.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List all circuits inside a .CircuitProject file.")
    p_list.add_argument("project", help="Path to .CircuitProject file")

    # verify
    p_ver = sub.add_parser("verify", help="Verify wire geometry on all circuits.")
    p_ver.add_argument("project", help="Path to .CircuitProject file")
    p_ver.add_argument("--allow-diagonal", action="store_true", help="Allow diagonal wires")

    # truth-table
    p_tt = sub.add_parser("truth-table", help="Evaluate the LogicCircuit truth table of a circuit.")
    p_tt.add_argument("project", help="Path to .CircuitProject file")
    p_tt.add_argument("-c", "--circuit", required=True, help="Circuit name or GUID")
    p_tt.add_argument("--max-rows", type=int, default=None, help="Limit number of rows")

    # render
    p_ren = sub.add_parser("render", help="Render a circuit schematic to PNG (requires Pillow).")
    p_ren.add_argument("project", help="Path to .CircuitProject file")
    p_ren.add_argument("-c", "--circuit", required=True, help="Circuit name or GUID")
    p_ren.add_argument("-o", "--output", required=True, help="Output PNG path")
    p_ren.add_argument("--scale", type=int, default=16, help="Pixels per grid cell (default: 16)")

    # watch (live preview for Zed / editors / browser)
    p_watch = sub.add_parser(
        "watch",
        help="Watch a .py script or .CircuitProject file and live-update PNG/Markdown previews on save.",
    )
    p_watch.add_argument("source", help="Path to a .py script or .CircuitProject file")
    p_watch.add_argument(
        "-o",
        "--output",
        default=".pylogiccircuit_preview.png",
        help="Output PNG preview path (default: .pylogiccircuit_preview.png)",
    )
    p_watch.add_argument(
        "--md",
        "--markdown",
        dest="markdown",
        default=None,
        help="Optional Markdown report path (image + verification + truth table) for Zed Markdown Preview",
    )
    p_watch.add_argument(
        "-c",
        "--circuit",
        default=None,
        help="Circuit name or GUID to render (defaults to the project's main circuit)",
    )
    p_watch.add_argument("--scale", type=int, default=16, help="Pixels per grid cell (default: 16)")
    p_watch.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="File poll interval in seconds (default: 0.25)",
    )
    p_watch.add_argument(
        "--serve",
        nargs="?",
        const=8765,
        type=int,
        default=None,
        metavar="PORT",
        help="Also start a local live-reloading web viewer (default port: 8765)",
    )
    p_watch.add_argument(
        "--once",
        action="store_true",
        help="Render once and exit (useful for testing or one-shot tasks)",
    )

    args = parser.parse_args(argv)

    if args.command == "watch":
        return watch_file(
            args.source,
            args.output,
            circuit_name=args.circuit,
            md_path=args.markdown,
            scale=args.scale,
            interval=args.interval,
            serve_port=args.serve,
            once=args.once,
        )

    proj = Project.load(args.project)

    if args.command == "list":
        for c in proj.circuits:
            n_in = sum(1 for p in c.pins if p.pin_type == "Input")
            n_out = sum(1 for p in c.pins if p.pin_type == "Output")
            print(
                f"{c.name} ({c.notation}) — inputs={n_in}, outputs={n_out}, "
                f"symbols={len(c.symbols)}, wires={len(c.wires)}"
            )
        return 0

    if args.command == "verify":
        all_ok = True
        for c in proj.circuits:
            res = c.verify(allow_diagonal=args.allow_diagonal)
            status = "OK" if res.ok else "FAIL"
            print(f"[{status}] {c.name} ({c.notation})")
            for err in res.errors:
                print(f"  - {err}")
            if not res.ok:
                all_ok = False
        return 0 if all_ok else 1

    if args.command == "truth-table":
        sim = Simulator.from_project(proj)
        tt = sim.truth_table(args.circuit, max_rows=args.max_rows)
        print(tt.format_markdown())
        return 1 if tt.oscillated else 0

    if args.command == "render":
        c = proj.get_circuit(args.circuit)
        out = render_circuit_png(c, args.output, scale=args.scale)
        print(f"Rendered {c.name!r} to {out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
