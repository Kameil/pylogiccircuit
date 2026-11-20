"""Generate all documentation preview images using pylogiccircuit.render_circuit_png."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from pylogiccircuit import Gate, Project, Simulator, render_circuit_png
from half_adder import build_half_adder
from full_adder_4bit import build_4bit_adder
from alu_4bit_74ls382 import build_alu_74ls382


def build_sr_latch() -> Project:
    proj = Project("SR Latch Demo")
    sr = proj.add_circuit("SRLatch", notation="SR-NAND")
    s_n = sr.add_input("S_n", x=2, y=3)
    r_n = sr.add_input("R_n", x=2, y=13)
    n1 = sr.add_gate(Gate.NAND2, x=12, y=3)
    n2 = sr.add_gate(Gate.NAND2, x=12, y=12)
    q = sr.add_output("Q", x=24, y=4)
    qn = sr.add_output("Qn", x=24, y=13)

    sr.connect(s_n, n1.in_[0])
    sr.connect(r_n, n2.in_[1])
    sr.connect(n1.out, n2.in_[0], q)
    sr.connect(n2.out, n1.in_[1], qn)
    sr.auto_route()
    return proj


def main() -> None:
    out_dir = ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Half Adder
    ha_proj = build_half_adder()
    render_circuit_png(
        ha_proj.get_circuit("HalfAdder"),
        out_dir / "half_adder.png",
        scale=20,
        title="Half Adder (1-bit)",
    )

    # 2. Full Adder 1-bit + 4-bit Ripple-Carry Adder
    add4_proj = build_4bit_adder()
    render_circuit_png(
        add4_proj.get_circuit("FullAdder"),
        out_dir / "full_adder_1bit.png",
        scale=18,
        title="Full Adder (1-bit Subcircuit)",
    )
    render_circuit_png(
        add4_proj.get_circuit("Adder4Bit"),
        out_dir / "adder_4bit.png",
        scale=15,
        title="4-bit Ripple-Carry Adder (Hierarchical)",
    )

    # 3. 1-bit ALU Selector (BitMux) + Full 4-bit ALU 74LS382
    alu_proj = build_alu_74ls382()
    render_circuit_png(
        alu_proj.get_circuit("BitMux"),
        out_dir / "bit_mux.png",
        scale=16,
        title="BitMux (1-bit ALU Output Selector)",
    )
    render_circuit_png(
        alu_proj.get_circuit("ALU_74LS382"),
        out_dir / "alu_74ls382.png",
        scale=14,
        title="4-bit ALU 74LS382 / 74HC382 (4096/4096 Verified)",
    )

    # 4. Sequential SR Latch (NAND)
    sr_proj = build_sr_latch()
    tt = Simulator.from_project(sr_proj).truth_table("SRLatch")
    assert not tt.oscillated and len(tt.rows) == 4
    render_circuit_png(
        sr_proj.get_circuit("SRLatch"),
        out_dir / "sr_latch.png",
        scale=20,
        title="Active-Low SR Latch (Cross-Coupled NAND2)",
    )

    print(f"Generated 6 preview PNGs in {out_dir}")


if __name__ == "__main__":
    main()
