"""Standard library of essential reusable digital logic components.

Every component is a :class:`~pylogiccircuit.component.Component` subclass that can be
instantiated inside your own circuits via ``self.use(...)`` with full pin autocomplete,
or exported/simulated standalone via ``.to_project()``, ``.save()``, ``.truth_table()``,
and ``.render()``.
"""

from __future__ import annotations

from .component import Component, Input, Output
from .gates import Gate


# ======================================================================
# Arithmetic Blocks
# ======================================================================
class HalfAdder(Component):
    """1-bit Half Adder (``S = A ^ B``, ``Cout = A & B``)."""

    notation = "HA"

    A = Input(x=2, y=2)
    B = Input(x=2, y=8)
    S = Output(x=18, y=3)
    Cout = Output(x=18, y=9)

    def build(self) -> None:
        xg = self.gate(Gate.XOR2, x=10, y=2)
        ag = self.gate(Gate.AND2, x=10, y=8)

        self.connect(self.A, xg.in_[0], ag.in_[0])
        self.connect(self.B, xg.in_[1], ag.in_[1])
        self.connect(xg.out, self.S)
        self.connect(ag.out, self.Cout)


class FullAdder(Component):
    """1-bit Full Adder (``S = A ^ B ^ Cin``, ``Cout = (A & B) | (Cin & (A ^ B))``)."""

    notation = "FA"

    A = Input(x=2, y=2)
    B = Input(x=2, y=7)
    Cin = Input(x=2, y=12)
    S = Output(x=32, y=6)
    Cout = Output(x=32, y=12)

    def build(self) -> None:
        x1 = self.gate(Gate.XOR2, x=10, y=2)
        x2 = self.gate(Gate.XOR2, x=18, y=5)
        a1 = self.gate(Gate.AND2, x=10, y=11)
        a2 = self.gate(Gate.AND2, x=18, y=12)
        o1 = self.gate(Gate.OR2, x=25, y=11)

        self.connect(self.A, x1.in_[0], a1.in_[0])
        self.connect(self.B, x1.in_[1], a1.in_[1])
        self.connect(x1.out, x2.in_[0], a2.in_[0])
        self.connect(self.Cin, x2.in_[1], a2.in_[1])
        self.connect(a2.out, o1.in_[0])
        self.connect(a1.out, o1.in_[1])
        self.connect(x2.out, self.S)
        self.connect(o1.out, self.Cout)


class Adder4Bit(Component):
    """4-bit Ripple-Carry Adder built from 4 :class:`FullAdder` subcircuits."""

    notation = "ADD4"
    route_max_x = 58
    route_max_y = 54

    A0 = Input(x=2, y=2)
    A1 = Input(x=2, y=7)
    A2 = Input(x=2, y=12)
    A3 = Input(x=2, y=17)
    B0 = Input(x=2, y=24)
    B1 = Input(x=2, y=29)
    B2 = Input(x=2, y=34)
    B3 = Input(x=2, y=39)
    Cin = Input(x=2, y=46)

    S0 = Output(x=52, y=10)
    S1 = Output(x=52, y=18)
    S2 = Output(x=52, y=26)
    S3 = Output(x=52, y=34)
    Cout = Output(x=52, y=42)

    def build(self) -> None:
        fa0 = self.use(FullAdder, x=16, y=10, label="FA0")
        fa1 = self.use(FullAdder, x=24, y=18, label="FA1")
        fa2 = self.use(FullAdder, x=32, y=26, label="FA2")
        fa3 = self.use(FullAdder, x=40, y=34, label="FA3")

        self.connect(self.A0, fa0.A)
        self.connect(self.B0, fa0.B)
        self.connect(self.Cin, fa0.Cin)
        self.connect(fa0.S, self.S0)

        self.connect(self.A1, fa1.A)
        self.connect(self.B1, fa1.B)
        self.connect(fa0.Cout, fa1.Cin)
        self.connect(fa1.S, self.S1)

        self.connect(self.A2, fa2.A)
        self.connect(self.B2, fa2.B)
        self.connect(fa1.Cout, fa2.Cin)
        self.connect(fa2.S, self.S2)

        self.connect(self.A3, fa3.A)
        self.connect(self.B3, fa3.B)
        self.connect(fa2.Cout, fa3.Cin)
        self.connect(fa3.S, self.S3)
        self.connect(fa3.Cout, self.Cout)


# ======================================================================
# Multiplexers & Decoders
# ======================================================================
class Mux2to1(Component):
    """2-to-1 Multiplexer (``Y = (~S & D0) | (S & D1)``)."""

    notation = "MUX2"

    D0 = Input(x=2, y=2)
    D1 = Input(x=2, y=8)
    S = Input(x=2, y=14)
    Y = Output(x=29, y=6)

    def build(self) -> None:
        ns = self.gate(Gate.NOT, x=8, y=13)
        a0 = self.gate(Gate.AND2, x=15, y=2)
        a1 = self.gate(Gate.AND2, x=15, y=9)
        o1 = self.gate(Gate.OR2, x=23, y=5)

        self.connect(self.D0, a0.in_[0])
        self.connect(self.D1, a1.in_[0])
        self.connect(self.S, ns.in_[0], a1.in_[1])
        self.connect(ns.out, a0.in_[1])
        self.connect(a0.out, o1.in_[0])
        self.connect(a1.out, o1.in_[1])
        self.connect(o1.out, self.Y)


class Mux4to1(Component):
    """4-to-1 Multiplexer (``S1, S0`` select among ``D0..D3``)."""

    notation = "MUX4"
    route_max_x = 38
    route_max_y = 34

    D0 = Input(x=2, y=2)
    D1 = Input(x=2, y=7)
    D2 = Input(x=2, y=12)
    D3 = Input(x=2, y=17)
    S1 = Input(x=2, y=23)
    S0 = Input(x=2, y=28)
    Y = Output(x=34, y=12)

    def build(self) -> None:
        ns1 = self.gate(Gate.NOT, x=9, y=22)
        ns0 = self.gate(Gate.NOT, x=9, y=27)

        m0 = self.gate(Gate.AND3, x=20, y=2)
        m1 = self.gate(Gate.AND3, x=20, y=9)
        m2 = self.gate(Gate.AND3, x=20, y=16)
        m3 = self.gate(Gate.AND3, x=20, y=23)

        or4 = self.gate(Gate.OR4, x=28, y=11)

        self.connect(self.D0, m0.in_[0])
        self.connect(self.D1, m1.in_[0])
        self.connect(self.D2, m2.in_[0])
        self.connect(self.D3, m3.in_[0])

        self.connect(self.S1, ns1.in_[0], m2.in_[1], m3.in_[1])
        self.connect(self.S0, ns0.in_[0], m1.in_[2], m3.in_[2])
        self.connect(ns1.out, m0.in_[1], m1.in_[1])
        self.connect(ns0.out, m0.in_[2], m2.in_[2])

        self.connect(m0.out, or4.in_[0])
        self.connect(m1.out, or4.in_[1])
        self.connect(m2.out, or4.in_[2])
        self.connect(m3.out, or4.in_[3])
        self.connect(or4.out, self.Y)


class Decoder2to4(Component):
    """2-to-4 Active-High Binary Decoder (``A1, A0 -> Y0..Y3``)."""

    notation = "DEC2x4"
    route_max_x = 30
    route_max_y = 28

    A1 = Input(x=2, y=5)
    A0 = Input(x=2, y=13)
    Y0 = Output(x=25, y=3)
    Y1 = Output(x=25, y=9)
    Y2 = Output(x=25, y=15)
    Y3 = Output(x=25, y=21)

    def build(self) -> None:
        na1 = self.gate(Gate.NOT, x=9, y=4)
        na0 = self.gate(Gate.NOT, x=9, y=12)

        y0 = self.gate(Gate.AND2, x=18, y=2)
        y1 = self.gate(Gate.AND2, x=18, y=8)
        y2 = self.gate(Gate.AND2, x=18, y=14)
        y3 = self.gate(Gate.AND2, x=18, y=20)

        self.connect(self.A1, na1.in_[0], y2.in_[0], y3.in_[0])
        self.connect(self.A0, na0.in_[0], y1.in_[1], y3.in_[1])
        self.connect(na1.out, y0.in_[0], y1.in_[0])
        self.connect(na0.out, y0.in_[1], y2.in_[1])

        self.connect(y0.out, self.Y0)
        self.connect(y1.out, self.Y1)
        self.connect(y2.out, self.Y2)
        self.connect(y3.out, self.Y3)


# ======================================================================
# Sequential Blocks (Latches & Edge-Triggered Flip-Flops)
# ======================================================================
class SRLatch(Component):
    """Active-low SR Latch (2 cross-coupled NAND2 gates)."""

    notation = "SR-L"
    circuit_shape = "FlipFlop"

    S_n = Input(x=2, y=3, name="~S")
    R_n = Input(x=2, y=13, name="~R")
    Q = Output(x=24, y=4)
    nQ = Output(x=24, y=13, name="~Q")

    def build(self) -> None:
        n1 = self.gate(Gate.NAND2, x=12, y=3)
        n2 = self.gate(Gate.NAND2, x=12, y=12)

        self.connect(self.S_n, n1.in_[0])
        self.connect(self.R_n, n2.in_[1])
        self.connect(n1.out, n2.in_[0], self.Q)
        self.connect(n2.out, n1.in_[1], self.nQ)


class SRFlipFlop(Component):
    """Clocked (gated) SR Flip-Flop built from 4 NAND2 gates."""

    notation = "SR-FF"
    circuit_shape = "FlipFlop"

    S = Input(x=2, y=2)
    CLK = Input(x=2, y=6)
    R = Input(x=2, y=10)
    Q = Output(x=28, y=3)
    nQ = Output(x=28, y=11, name="~Q")

    def build(self) -> None:
        n1 = self.gate(Gate.NAND2, x=10, y=2)
        n2 = self.gate(Gate.NAND2, x=10, y=10)
        n3 = self.gate(Gate.NAND2, x=18, y=2)
        n4 = self.gate(Gate.NAND2, x=18, y=10)

        self.connect(self.S, n1.in_[0])
        self.connect(self.CLK, n1.in_[1], n2.in_[0])
        self.connect(self.R, n2.in_[1])
        self.connect(n1.out, n3.in_[0])
        self.connect(n2.out, n4.in_[1])
        self.connect(n3.out, n4.in_[0], self.Q)
        self.connect(n4.out, n3.in_[1], self.nQ)


class DFlipFlop(Component):
    """Positive-edge-triggered D Flip-Flop (classic 6-NAND architecture)."""

    notation = "D-FF"
    circuit_shape = "FlipFlop"
    route_max_x = 34
    route_max_y = 30

    D = Input(x=2, y=10)
    CLK = Input(x=2, y=17)
    Q = Output(x=30, y=10)
    nQ = Output(x=30, y=18, name="~Q")

    def build(self) -> None:
        n1 = self.gate(Gate.NAND2, x=12, y=2)
        n2 = self.gate(Gate.NAND2, x=12, y=9)
        n3 = self.gate(Gate.NAND3, x=12, y=16)
        n4 = self.gate(Gate.NAND2, x=12, y=23)
        n5 = self.gate(Gate.NAND2, x=22, y=9)
        n6 = self.gate(Gate.NAND2, x=22, y=17)

        self.connect(self.D, n4.in_[1])
        self.connect(self.CLK, n2.in_[1], n3.in_[1])
        self.connect(n1.out, n2.in_[0])
        self.connect(n2.out, n1.in_[1], n3.in_[0], n5.in_[0])
        self.connect(n3.out, n4.in_[0], n6.in_[1])
        self.connect(n4.out, n1.in_[0], n3.in_[2])
        self.connect(n5.out, n6.in_[0], self.Q)
        self.connect(n6.out, n5.in_[1], self.nQ)


class DFlipFlopAsync(Component):
    """Positive-edge-triggered D Flip-Flop with active-low asynchronous Preset & Clear.

    Ideal building block for synchronous counters (74HC160/161/162/163) and registers:
    - ``PRE_n = 0, CLR_n = 1`` -> forces ``Q = 1, ~Q = 0`` immediately.
    - ``PRE_n = 1, CLR_n = 0`` -> forces ``Q = 0, ~Q = 1`` immediately.
    - ``PRE_n = 1, CLR_n = 1`` -> normal positive-edge D flip-flop operation.
    """

    notation = "D-FF+"
    circuit_shape = "FlipFlop"
    route_max_x = 38
    route_max_y = 36

    PRE_n = Input(x=18, y=1, side="Top", name="~PRE")
    D = Input(x=2, y=12)
    CLK = Input(x=2, y=19)
    CLR_n = Input(x=18, y=32, side="Bottom", name="~CLR")
    Q = Output(x=34, y=12)
    nQ = Output(x=34, y=20, name="~Q")

    def build(self) -> None:
        n1 = self.gate(Gate.NAND3, x=13, y=5)
        n2 = self.gate(Gate.NAND3, x=13, y=12)
        n3 = self.gate(Gate.NAND3, x=13, y=19)
        n4 = self.gate(Gate.NAND3, x=13, y=26)
        n5 = self.gate(Gate.NAND3, x=25, y=11)
        n6 = self.gate(Gate.NAND3, x=25, y=19)

        self.connect(self.PRE_n, n1.in_[0], n5.in_[0])
        self.connect(self.CLR_n, n2.in_[2], n4.in_[2], n6.in_[2])
        self.connect(self.D, n4.in_[1])
        self.connect(self.CLK, n2.in_[1], n3.in_[1])

        self.connect(n1.out, n2.in_[0])
        self.connect(n2.out, n1.in_[2], n3.in_[0], n5.in_[1])
        self.connect(n3.out, n4.in_[0], n6.in_[1])
        self.connect(n4.out, n1.in_[1], n3.in_[2])
        self.connect(n5.out, n6.in_[0], self.Q)
        self.connect(n6.out, n5.in_[2], self.nQ)


class JKFlipFlop(Component):
    """Positive-edge-triggered JK Flip-Flop (race-around free, built on :class:`DFlipFlop`).

    Next-state logic: ``D = (J & ~Q) | (~K & Q)``.
    """

    notation = "JK-FF"
    circuit_shape = "FlipFlop"
    route_max_x = 42
    route_max_y = 24

    J = Input(x=2, y=4)
    CLK = Input(x=2, y=10)
    K = Input(x=2, y=16)
    Q = Output(x=36, y=7)
    nQ = Output(x=36, y=13, name="~Q")

    def build(self) -> None:
        nk = self.gate(Gate.NOT, x=8, y=15)
        a_j = self.gate(Gate.AND2, x=15, y=3)
        a_k = self.gate(Gate.AND2, x=15, y=14)
        or_d = self.gate(Gate.OR2, x=22, y=7)
        dff = self.use(DFlipFlop, x=29, y=8, label="DFF")

        self.connect(self.J, a_j.in_[0])
        self.connect(self.K, nk.in_[0])
        self.connect(nk.out, a_k.in_[0])
        self.connect(a_j.out, or_d.in_[0])
        self.connect(a_k.out, or_d.in_[1])
        self.connect(or_d.out, dff.D)
        self.connect(self.CLK, dff.CLK)
        self.connect(dff.Q, a_k.in_[1], self.Q)
        self.connect(dff.nQ, a_j.in_[1], self.nQ)


class TFlipFlop(Component):
    """Positive-edge-triggered Toggle (T) Flip-Flop (built on :class:`DFlipFlop`).

    Next-state logic: ``D = T ^ Q``.
    """

    notation = "T-FF"
    circuit_shape = "FlipFlop"
    route_max_x = 32
    route_max_y = 20

    T = Input(x=2, y=5)
    CLK = Input(x=2, y=12)
    Q = Output(x=26, y=6)
    nQ = Output(x=26, y=12, name="~Q")

    def build(self) -> None:
        xg = self.gate(Gate.XOR2, x=10, y=5)
        dff = self.use(DFlipFlop, x=19, y=7, label="DFF")

        self.connect(self.T, xg.in_[0])
        self.connect(xg.out, dff.D)
        self.connect(self.CLK, dff.CLK)
        self.connect(dff.Q, xg.in_[1], self.Q)
        self.connect(dff.nQ, self.nQ)


__all__ = [
    "Adder4Bit",
    "Decoder2to4",
    "DFlipFlop",
    "DFlipFlopAsync",
    "FullAdder",
    "HalfAdder",
    "JKFlipFlop",
    "Mux2to1",
    "Mux4to1",
    "SRFlipFlop",
    "SRLatch",
    "TFlipFlop",
]
