"""Command-line interface for pylogiccircuit."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .preview import render_circuit_png
from .project import Project
from .simulator import Simulator


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pylogiccircuit",
        description="Inspect, verify, simulate, and render LogicCircuit (.CircuitProject) files.",
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
    p_ren.add_argument("--scale", type=int, default=12, help="Pixels per grid cell (default: 12)")

    args = parser.parse_args(argv)
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
