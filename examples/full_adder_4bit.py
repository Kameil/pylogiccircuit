"""Hierarchical example: 1-bit Full Adder reused inside a 4-bit Ripple-Carry Adder."""

from pylogiccircuit import Gate, Project, Simulator


def build_4bit_adder() -> Project:
    proj = Project("4-bit Ripple-Carry Adder")

    # 1. Build reusable 1-bit Full Adder subcircuit
    fa = proj.add_circuit("FullAdder", notation="FA")
    a = fa.add_input("A", x=2, y=2)
    b = fa.add_input("B", x=2, y=7)
    cin = fa.add_input("Cin", x=2, y=12)

    xor1 = fa.add_gate(Gate.XOR2, x=10, y=2)
    xor2 = fa.add_gate(Gate.XOR2, x=18, y=5)
    and1 = fa.add_gate(Gate.AND2, x=10, y=11)
    and2 = fa.add_gate(Gate.AND2, x=18, y=12)
    or1 = fa.add_gate(Gate.OR2, x=25, y=11)

    s = fa.add_output("S", x=32, y=6)
    cout = fa.add_output("Cout", x=32, y=12)

    fa.connect(a, xor1.in_[0], and1.in_[0])
    fa.connect(b, xor1.in_[1], and1.in_[1])
    fa.connect(xor1.out, xor2.in_[0], and2.in_[0])
    fa.connect(cin, xor2.in_[1], and2.in_[1])
    fa.connect(and2.out, or1.in_[0])
    fa.connect(and1.out, or1.in_[1])
    fa.connect(xor2.out, s)
    fa.connect(or1.out, cout)
    fa.auto_route()

    # 2. Compose 4 FullAdder instances into a 4-bit adder
    top = proj.add_circuit("Adder4Bit", notation="ADD4", set_main=True)
    in_a = [top.add_input(f"A{i}", x=2, y=2 + i * 5) for i in range(4)]
    in_b = [top.add_input(f"B{i}", x=2, y=24 + i * 5) for i in range(4)]
    in_c0 = top.add_input("Cin", x=2, y=46)

    fas = [top.add_subcircuit(fa, x=16 + i * 8, y=10 + i * 8, label=f"FA{i}") for i in range(4)]

    out_s = [top.add_output(f"S{i}", x=52, y=10 + i * 8) for i in range(4)]
    out_c4 = top.add_output("Cout", x=52, y=42)

    for i in range(4):
        top.connect(in_a[i], fas[i]["A"])
        top.connect(in_b[i], fas[i]["B"])
        top.connect(fas[i]["S"], out_s[i])

    top.connect(in_c0, fas[0]["Cin"])
    for i in range(3):
        top.connect(fas[i]["Cout"], fas[i + 1]["Cin"])
    top.connect(fas[3]["Cout"], out_c4)

    top.auto_route(max_x=56, max_y=54)
    return proj


if __name__ == "__main__":
    project = build_4bit_adder()
    project.save("adder_4bit.CircuitProject")

    sim = Simulator.from_project(project)
    # Exhaustively verify all 512 combinations (A: 0..15, B: 0..15, Cin: 0..1)
    passed = 0
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
                passed += 1
    print(f"Verified 4-bit adder: {passed}/512 combinations PASSED!")
