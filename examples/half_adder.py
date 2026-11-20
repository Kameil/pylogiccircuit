"""Minimal example: build, auto-route, simulate, and save a 1-bit Half Adder."""

from pylogiccircuit import Gate, Project, Simulator


def build_half_adder() -> Project:
    proj = Project("Half Adder Demo")
    ha = proj.add_circuit("HalfAdder", notation="HA")

    a = ha.add_input("A", x=2, y=2)
    b = ha.add_input("B", x=2, y=8)

    xor_gate = ha.add_gate(Gate.XOR2, x=10, y=2)
    and_gate = ha.add_gate(Gate.AND2, x=10, y=8)

    s = ha.add_output("S", x=18, y=3)
    c = ha.add_output("C", x=18, y=9)

    ha.connect(a, xor_gate.in_[0], and_gate.in_[0])
    ha.connect(b, xor_gate.in_[1], and_gate.in_[1])
    ha.connect(xor_gate.out, s)
    ha.connect(and_gate.out, c)

    ha.auto_route()
    return proj


if __name__ == "__main__":
    project = build_half_adder()
    project.save("half_adder.CircuitProject")

    sim = Simulator.from_project(project)
    print(sim.truth_table("HalfAdder").format_markdown())
