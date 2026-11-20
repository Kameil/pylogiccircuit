"""Tests for the FIFO simulator: combinational, hierarchical, sequential, and oscillation."""

import pytest

from pylogiccircuit import Gate, Project, Simulator


def test_half_adder_truth_table():
    proj = Project("HA")
    ha = proj.add_circuit("HalfAdder")
    a = ha.add_input("A", x=2, y=2)
    b = ha.add_input("B", x=2, y=8)
    xg = ha.add_gate(Gate.XOR2, x=10, y=2)
    ag = ha.add_gate(Gate.AND2, x=10, y=8)
    s = ha.add_output("S", x=18, y=3)
    c = ha.add_output("C", x=18, y=9)

    ha.connect(a, xg.in_[0], ag.in_[0])
    ha.connect(b, xg.in_[1], ag.in_[1])
    ha.connect(xg.out, s)
    ha.connect(ag.out, c)
    ha.auto_route()

    sim = Simulator.from_project(proj)
    tt = sim.truth_table("HalfAdder")
    assert not tt.oscillated
    assert tt.input_names == ["A", "B"]
    assert tt.output_names == ["S", "C"]
    assert tt.rows == [
        ([0, 0], [0, 0]),
        ([0, 1], [1, 0]),
        ([1, 0], [1, 0]),
        ([1, 1], [0, 1]),
    ]


def test_hierarchical_2bit_adder():
    proj = Project("Add2")
    fa = proj.add_circuit("FA")
    a = fa.add_input("A", x=2, y=2)
    b = fa.add_input("B", x=2, y=7)
    cin = fa.add_input("Cin", x=2, y=12)
    x1 = fa.add_gate(Gate.XOR2, x=10, y=2)
    x2 = fa.add_gate(Gate.XOR2, x=18, y=5)
    a1 = fa.add_gate(Gate.AND2, x=10, y=11)
    a2 = fa.add_gate(Gate.AND2, x=18, y=12)
    o1 = fa.add_gate(Gate.OR2, x=25, y=11)
    s = fa.add_output("S", x=32, y=6)
    cout = fa.add_output("Cout", x=32, y=12)
    fa.connect(a, x1.in_[0], a1.in_[0])
    fa.connect(b, x1.in_[1], a1.in_[1])
    fa.connect(x1.out, x2.in_[0], a2.in_[0])
    fa.connect(cin, x2.in_[1], a2.in_[1])
    fa.connect(a2.out, o1.in_[0])
    fa.connect(a1.out, o1.in_[1])
    fa.connect(x2.out, s)
    fa.connect(o1.out, cout)
    fa.auto_route()

    top = proj.add_circuit("Add2", set_main=True)
    a0 = top.add_input("A0", x=2, y=2)
    a1_p = top.add_input("A1", x=2, y=8)
    b0 = top.add_input("B0", x=2, y=14)
    b1 = top.add_input("B1", x=2, y=20)
    c0 = top.add_input("Cin", x=2, y=26)

    fa0 = top.add_subcircuit(fa, x=16, y=6)
    fa1 = top.add_subcircuit(fa, x=28, y=14)

    s0 = top.add_output("S0", x=40, y=6)
    s1 = top.add_output("S1", x=40, y=14)
    c2 = top.add_output("Cout", x=40, y=20)

    top.connect(a0, fa0["A"])
    top.connect(b0, fa0["B"])
    top.connect(c0, fa0["Cin"])
    top.connect(fa0["S"], s0)
    top.connect(fa0["Cout"], fa1["Cin"])
    top.connect(a1_p, fa1["A"])
    top.connect(b1, fa1["B"])
    top.connect(fa1["S"], s1)
    top.connect(fa1["Cout"], c2)
    top.auto_route()

    sim = Simulator.from_project(proj)
    for av in range(4):
        for bv in range(4):
            for cv in range(2):
                out = sim.evaluate(
                    "Add2",
                    {
                        "A0": av & 1,
                        "A1": (av >> 1) & 1,
                        "B0": bv & 1,
                        "B1": (bv >> 1) & 1,
                        "Cin": cv,
                    },
                )
                got = out["S0"] + (out["S1"] << 1) + (out["Cout"] << 2)
                assert got == av + bv + cv


def test_ring_oscillator_detection():
    proj = Project("Osc")
    c = proj.add_circuit("RingOsc")
    en = c.add_input("En", x=2, y=4)
    nand = c.add_gate(Gate.NAND2, x=10, y=4)
    out = c.add_output("Out", x=20, y=5)

    c.connect(en, nand.in_[0])
    c.connect(nand.out, nand.in_[1], out)
    c.auto_route()

    sim = Simulator.from_project(proj)
    # When En=0, NAND output is stable 1
    assert sim.evaluate("RingOsc", {"En": 0}) == {"Out": 1}
    # When En=1, NAND feeds back into itself -> oscillates!
    with pytest.raises(RuntimeError, match="oscillated"):
        sim.evaluate("RingOsc", {"En": 1})

    tt = sim.truth_table("RingOsc")
    assert tt.oscillated
    assert tt.oscillation_row == 1


def test_nand_sr_latch_truth_table():
    # Active-low SR latch (2 cross-coupled NAND2 gates)
    proj = Project("SR")
    sr = proj.add_circuit("SRLatch")
    s_bar = sr.add_input("S_n", x=2, y=3)
    r_bar = sr.add_input("R_n", x=2, y=13)
    n1 = sr.add_gate(Gate.NAND2, x=12, y=3)
    n2 = sr.add_gate(Gate.NAND2, x=12, y=12)
    q = sr.add_output("Q", x=24, y=4)
    qn = sr.add_output("Qn", x=24, y=13)

    sr.connect(s_bar, n1.in_[0])
    sr.connect(r_bar, n2.in_[1])
    sr.connect(n1.out, n2.in_[0], q)
    sr.connect(n2.out, n1.in_[1], qn)
    sr.auto_route()

    sim = Simulator.from_project(proj)
    tt = sim.truth_table("SRLatch")
    assert not tt.oscillated
    # Row 0: (0,0)->(1,1); Row 1: (0,1)->SET(1,0); Row 2: (1,0)->RESET(0,1); Row 3: (1,1)->HOLD(0,1)
    assert tt.rows == [
        ([0, 0], [1, 1]),
        ([0, 1], [1, 0]),
        ([1, 0], [0, 1]),
        ([1, 1], [0, 1]),
    ]
