"""Class-based Component example: 4-bit Shift Register built with stdlib.DFlipFlop."""

from pylogiccircuit import Component, Input, Output
from pylogiccircuit.stdlib import DFlipFlop


class ShiftRegister4Bit(Component):
    notation = "SHIFT4"
    route_max_x = 58
    route_max_y = 32

    D = Input(x=2, y=6)
    CLK = Input(x=2, y=14)
    Q0 = Output(x=52, y=4)
    Q1 = Output(x=52, y=10)
    Q2 = Output(x=52, y=16)
    Q3 = Output(x=52, y=22)

    def build(self) -> None:
        ff0 = self.use(DFlipFlop, x=12, y=6, label="FF0")
        ff1 = self.use(DFlipFlop, x=22, y=10, label="FF1")
        ff2 = self.use(DFlipFlop, x=32, y=14, label="FF2")
        ff3 = self.use(DFlipFlop, x=42, y=18, label="FF3")

        self.connect(self.D, ff0.D)
        self.connect(self.CLK, ff0.CLK, ff1.CLK, ff2.CLK, ff3.CLK)
        self.connect(ff0.Q, ff1.D, self.Q0)
        self.connect(ff1.Q, ff2.D, self.Q1)
        self.connect(ff2.Q, ff3.D, self.Q2)
        self.connect(ff3.Q, self.Q3)


if __name__ == "__main__":
    ShiftRegister4Bit.save("shift_register_4bit.CircuitProject")
    print(ShiftRegister4Bit.truth_table().format_markdown())
