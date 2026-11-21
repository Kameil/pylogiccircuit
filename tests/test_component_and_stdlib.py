"""Comprehensive tests for class-based Component API and pylogiccircuit.stdlib."""

import pytest

from pylogiccircuit import Component, Gate, Input, Output, Project, Simulator
from pylogiccircuit.stdlib import (
    Adder4Bit,
    Decoder2to4,
    DFlipFlop,
    DFlipFlopAsync,
    FullAdder,
    HalfAdder,
    JKFlipFlop,
    Mux2to1,
    Mux4to1,
    SRFlipFlop,
    SRLatch,
    TFlipFlop,
)
from pylogiccircuit.watch import render_once


def test_half_adder_stdlib():
    tt = HalfAdder.truth_table()
    assert not tt.oscillated
    assert tt.rows == [
        ([0, 0], [0, 0]),
        ([0, 1], [1, 0]),
        ([1, 0], [1, 0]),
        ([1, 1], [0, 1]),
    ]


def test_full_adder_stdlib():
    tt = FullAdder.truth_table()
    assert not tt.oscillated
    for (a, b, cin), (s, cout) in tt.rows:
        assert s + 2 * cout == a + b + cin


def test_adder4bit_stdlib_exhaustive():
    proj = Adder4Bit.to_project()
    assert len(proj.circuits) == 2
    sim = Simulator.from_project(proj)
    for a in range(16):
        for b in range(16):
            for cin in range(2):
                inp = {
                    **{f"A{i}": (a >> i) & 1 for i in range(4)},
                    **{f"B{i}": (b >> i) & 1 for i in range(4)},
                    "Cin": cin,
                }
                out = sim.evaluate("Adder4Bit", inp)
                total = sum(out[f"S{i}"] << i for i in range(4)) + (out["Cout"] << 4)
                assert total == a + b + cin


def test_mux2to1_and_mux4to1_stdlib():
    sim2 = Mux2to1.simulate()
    for d0 in (0, 1):
        for d1 in (0, 1):
            for s in (0, 1):
                out = sim2.evaluate("Mux2to1", {"D0": d0, "D1": d1, "S": s})
                assert out["Y"] == (d1 if s else d0)

    sim4 = Mux4to1.simulate()
    for d in range(16):
        ds = [(d >> i) & 1 for i in range(4)]
        for s in range(4):
            inp = {f"D{i}": ds[i] for i in range(4)}
            inp["S1"] = (s >> 1) & 1
            inp["S0"] = s & 1
            assert sim4.evaluate("Mux4to1", inp)["Y"] == ds[s]


def test_decoder2to4_stdlib():
    tt = Decoder2to4.truth_table()
    assert not tt.oscillated
    assert tt.rows == [
        ([0, 0], [1, 0, 0, 0]),
        ([0, 1], [0, 1, 0, 0]),
        ([1, 0], [0, 0, 1, 0]),
        ([1, 1], [0, 0, 0, 1]),
    ]


def test_sr_latch_and_sr_ff_stdlib():
    tt_l = SRLatch.truth_table()
    assert not tt_l.oscillated
    assert tt_l.rows == [
        ([0, 0], [1, 1]),
        ([0, 1], [1, 0]),
        ([1, 0], [0, 1]),
        ([1, 1], [0, 1]),
    ]

    tt_ff = SRFlipFlop.truth_table()
    assert not tt_ff.oscillated
    assert len(tt_ff.rows) == 8


def test_dff_and_dff_async_stdlib():
    tt = DFlipFlop.truth_table()
    assert not tt.oscillated
    assert tt.rows == [
        ([0, 0], [1, 0]),
        ([0, 1], [0, 1]),
        ([1, 0], [0, 1]),
        ([1, 1], [1, 0]),
    ]

    tt_a = DFlipFlopAsync.truth_table()
    assert not tt_a.oscillated
    assert len(tt_a.rows) == 16
    idx_pre = tt_a.input_names.index("~PRE")
    idx_clr = tt_a.input_names.index("~CLR")
    for iv, (q, nq) in tt_a.rows:
        if iv[idx_pre] == 0 and iv[idx_clr] == 1:
            assert (q, nq) == (1, 0)
        elif iv[idx_pre] == 1 and iv[idx_clr] == 0:
            assert (q, nq) == (0, 1)


def test_jk_and_t_flipflop_stdlib_no_oscillation():
    tt_jk = JKFlipFlop.truth_table()
    assert not tt_jk.oscillated
    assert len(tt_jk.rows) == 8

    tt_t = TFlipFlop.truth_table()
    assert not tt_t.oscillated
    assert len(tt_t.rows) == 4


def test_custom_component_with_typed_subcircuit_pins():
    class TwoBitShiftReg(Component):
        notation = "SHIFT2"
        D = Input(x=2, y=6)
        CLK = Input(x=2, y=14)
        Q0 = Output(x=34, y=6)
        Q1 = Output(x=34, y=14)

        def build(self) -> None:
            ff0 = self.use(DFlipFlop, x=12, y=6, label="FF0")
            ff1 = self.use(DFlipFlop, x=24, y=10, label="FF1")
            self.connect(self.D, ff0.D)
            self.connect(self.CLK, ff0.CLK, ff1.CLK)
            self.connect(ff0.Q, ff1.D, self.Q0)
            self.connect(ff1.Q, self.Q1)

    proj = TwoBitShiftReg.to_project()
    assert len(proj.circuits) == 2
    assert proj.get_circuit("TwoBitShiftReg").verify().ok
    tt = TwoBitShiftReg.truth_table()
    assert not tt.oscillated


def test_watch_auto_discovers_component_class(tmp_path):
    pytest.importorskip("PIL")
    script = tmp_path / "my_comp.py"
    script.write_text(
        """
from pylogiccircuit import Component, Gate, Input, Output

class MyXor(Component):
    notation = "MYXOR"
    A = Input(x=2, y=2)
    B = Input(x=2, y=8)
    Y = Output(x=18, y=5)

    def build(self):
        g = self.gate(Gate.XOR2, x=10, y=4)
        self.connect(self.A, g.in_[0])
        self.connect(self.B, g.in_[1])
        self.connect(g.out, self.Y)
""",
        encoding="utf-8",
    )
    out_png = tmp_path / "preview.png"
    out_md = tmp_path / "preview.md"
    snap = render_once(script, out_png, md_path=out_md)
    assert snap.ok
    assert snap.circuit_name == "MyXor"
    assert out_png.exists() and out_png.stat().st_size > 100
    assert "| 1 | 0 | 1 |" in out_md.read_text(encoding="utf-8")
