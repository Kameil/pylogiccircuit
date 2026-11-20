"""Compact 4-bit ALU (74LS382 / 74HC382) built hierarchically and verified 4096/4096."""

from pylogiccircuit import Gate, Project, Simulator


def build_alu_74ls382() -> Project:
    proj = Project("ALU 74LS382")

    # 1. 1-bit Full Adder
    fa = proj.add_circuit("FullAdder", notation="FA")
    fa_a = fa.add_input("A", x=2, y=2)
    fa_b = fa.add_input("B", x=2, y=7)
    fa_c = fa.add_input("C", x=2, y=12)
    x1 = fa.add_gate(Gate.XOR2, x=10, y=2)
    x2 = fa.add_gate(Gate.XOR2, x=18, y=5)
    a1 = fa.add_gate(Gate.AND2, x=10, y=11)
    a2 = fa.add_gate(Gate.AND2, x=18, y=12)
    o1 = fa.add_gate(Gate.OR2, x=25, y=11)
    fa_s = fa.add_output("S", x=32, y=6)
    fa_co = fa.add_output("Cout", x=32, y=12)
    fa.connect(fa_a, x1.in_[0], a1.in_[0])
    fa.connect(fa_b, x1.in_[1], a1.in_[1])
    fa.connect(x1.out, x2.in_[0], a2.in_[0])
    fa.connect(fa_c, x2.in_[1], a2.in_[1])
    fa.connect(a2.out, o1.in_[0])
    fa.connect(a1.out, o1.in_[1])
    fa.connect(x2.out, fa_s)
    fa.connect(o1.out, fa_co)
    fa.auto_route()

    # 2. 4-bit Adder (74HC283 style)
    add4 = proj.add_circuit("Adder4", notation="74HC283")
    a_pins = [add4.add_input(f"A{i}", x=2, y=2 + i * 5) for i in range(4)]
    b_pins = [add4.add_input(f"B{i}", x=2, y=24 + i * 5) for i in range(4)]
    c0_pin = add4.add_input("C0", x=2, y=46)
    fas = [add4.add_subcircuit(fa, x=16 + i * 8, y=10 + i * 8) for i in range(4)]
    s_pins = [add4.add_output(f"S{i}", x=52, y=10 + i * 8) for i in range(4)]
    c4_pin = add4.add_output("C4", x=52, y=42)
    for i in range(4):
        add4.connect(a_pins[i], fas[i]["A"])
        add4.connect(b_pins[i], fas[i]["B"])
        add4.connect(fas[i]["S"], s_pins[i])
    add4.connect(c0_pin, fas[0]["C"])
    for i in range(3):
        add4.connect(fas[i]["Cout"], fas[i + 1]["C"])
    add4.connect(fas[3]["Cout"], c4_pin)
    add4.auto_route(max_x=56, max_y=54)

    # 3. 1-bit ALU Output Selector (000=0, 001/010/011=Sum, 100=XOR, 101=OR, 110=AND, 111=1)
    mux = proj.add_circuit("BitMux", notation="MUX")
    m_a = mux.add_input("A", x=2, y=2)
    m_b = mux.add_input("B", x=2, y=7)
    m_sum = mux.add_input("Sum", x=2, y=12)
    m_s2 = mux.add_input("S2", x=2, y=18)
    m_s1 = mux.add_input("S1", x=2, y=23)
    m_s0 = mux.add_input("S0", x=2, y=28)

    g_xor = mux.add_gate(Gate.XOR2, x=11, y=1)
    g_or = mux.add_gate(Gate.OR2, x=11, y=6)
    g_and = mux.add_gate(Gate.AND2, x=11, y=11)
    g_ns2 = mux.add_gate(Gate.NOT, x=11, y=17)
    g_ns1 = mux.add_gate(Gate.NOT, x=11, y=22)
    g_ns0 = mux.add_gate(Gate.NOT, x=11, y=27)
    g_s10 = mux.add_gate(Gate.OR2, x=11, y=32)

    ma = mux.add_gate(Gate.AND3, x=24, y=2)
    mx = mux.add_gate(Gate.AND4, x=24, y=8)
    mo = mux.add_gate(Gate.AND4, x=24, y=15)
    man = mux.add_gate(Gate.AND4, x=24, y=22)
    mp = mux.add_gate(Gate.AND3, x=24, y=29)

    g_orf = mux.add_gate(Gate.OR5, x=33, y=14)
    m_f = mux.add_output("F", x=38, y=16)

    mux.connect(m_a, g_xor.in_[0], g_or.in_[0], g_and.in_[0])
    mux.connect(m_b, g_xor.in_[1], g_or.in_[1], g_and.in_[1])
    mux.connect(m_sum, ma.in_[2])
    mux.connect(m_s2, g_ns2.in_[0], mx.in_[0], mo.in_[0], man.in_[0], mp.in_[0])
    mux.connect(m_s1, g_ns1.in_[0], g_s10.in_[0], man.in_[1], mp.in_[1])
    mux.connect(m_s0, g_ns0.in_[0], g_s10.in_[1], mo.in_[2], mp.in_[2])
    mux.connect(g_ns2.out, ma.in_[0])
    mux.connect(g_ns1.out, mx.in_[1], mo.in_[1])
    mux.connect(g_ns0.out, mx.in_[2], man.in_[2])
    mux.connect(g_s10.out, ma.in_[1])
    mux.connect(g_xor.out, mx.in_[3])
    mux.connect(g_or.out, mo.in_[3])
    mux.connect(g_and.out, man.in_[3])
    mux.connect(ma.out, g_orf.in_[0])
    mux.connect(mx.out, g_orf.in_[1])
    mux.connect(mo.out, g_orf.in_[2])
    mux.connect(man.out, g_orf.in_[3])
    mux.connect(mp.out, g_orf.in_[4])
    mux.connect(g_orf.out, m_f)
    mux.auto_route(max_x=41, max_y=39)

    # 4. Top-level 4-bit ALU (single 4-bit adder + programmable XOR inverters + OVR + 4x BitMux)
    alu = proj.add_circuit("ALU_74LS382", notation="74LS382", set_main=True)
    in_a = [alu.add_input(f"A{i}", x=2, y=3 + (3 - i) * 6) for i in range(4)]
    in_cn = alu.add_input("Cn", x=2, y=27)
    in_b = [alu.add_input(f"B{i}", x=2, y=32 + (3 - i) * 6) for i in range(4)]
    in_s2 = alu.add_input("S2", x=2, y=57)
    in_s1 = alu.add_input("S1", x=2, y=62)
    in_s0 = alu.add_input("S0", x=2, y=67)

    ns2 = alu.add_gate(Gate.NOT, x=9, y=56)
    ns1 = alu.add_gate(Gate.NOT, x=9, y=61)
    ns0 = alu.add_gate(Gate.NOT, x=9, y=66)
    inv_a = alu.add_gate(Gate.AND3, x=18, y=57)
    inv_b = alu.add_gate(Gate.AND3, x=18, y=63)

    x_a = [alu.add_gate(Gate.XOR2, x=14, y=3 + (3 - i) * 6) for i in range(4)]
    x_b = [alu.add_gate(Gate.XOR2, x=14, y=32 + (3 - i) * 6) for i in range(4)]

    adder = alu.add_subcircuit(add4, x=28, y=22, label="ADD4")

    ovr_xnor = alu.add_gate(Gate.XNOR2, x=39, y=18)
    ovr_xor = alu.add_gate(Gate.XOR2, x=39, y=24)
    ovr_and = alu.add_gate(Gate.AND2, x=45, y=21)

    muxes = [alu.add_subcircuit(mux, x=56, y=3 + (3 - i) * 10, label=f"MUX{i}") for i in range(4)]

    out_f = [alu.add_output(f"F{i}", x=62, y=5 + (3 - i) * 10) for i in range(4)]
    out_cn4 = alu.add_output("Cn+4", x=62, y=43)
    out_ovr = alu.add_output("OVR", x=62, y=47)

    for i in range(4):
        alu.connect(muxes[i]["F"], out_f[i])
        alu.connect(in_a[i], x_a[i].in_[0], muxes[i]["A"])
        alu.connect(in_b[i], x_b[i].in_[0], muxes[i]["B"])

    alu.connect(in_cn, adder["C0"])
    alu.connect(adder["C4"], out_cn4)
    alu.connect(ovr_and.out, out_ovr)
    alu.connect(ovr_xnor.out, ovr_and.in_[0])
    alu.connect(ovr_xor.out, ovr_and.in_[1])

    alu.connect(x_a[3].out, adder["A3"], ovr_xnor.in_[0], ovr_xor.in_[0])
    for i in range(3):
        alu.connect(x_a[i].out, adder[f"A{i}"])

    alu.connect(x_b[3].out, adder["B3"], ovr_xnor.in_[1])
    for i in range(3):
        alu.connect(x_b[i].out, adder[f"B{i}"])

    alu.connect(adder["S3"], muxes[3]["Sum"], ovr_xor.in_[1])
    for i in range(3):
        alu.connect(adder[f"S{i}"], muxes[i]["Sum"])

    alu.connect(ns2.out, inv_a.in_[0], inv_b.in_[0])
    alu.connect(ns1.out, inv_a.in_[1])
    alu.connect(ns0.out, inv_b.in_[2])
    alu.connect(inv_a.out, *(x_a[i].in_[1] for i in range(4)))
    alu.connect(inv_b.out, *(x_b[i].in_[1] for i in range(4)))

    alu.connect(in_s2, ns2.in_[0], *(muxes[i]["S2"] for i in range(4)))
    alu.connect(in_s1, ns1.in_[0], inv_b.in_[1], *(muxes[i]["S1"] for i in range(4)))
    alu.connect(in_s0, ns0.in_[0], inv_a.in_[2], *(muxes[i]["S0"] for i in range(4)))

    alu.auto_route(max_x=64, max_y=74)
    return proj


if __name__ == "__main__":
    project = build_alu_74ls382()
    project.save("alu_74ls382.CircuitProject")

    sim = Simulator.from_project(project)
    passed = 0
    for s in range(8):
        for cn in range(2):
            for a in range(16):
                for b in range(16):
                    inp = {
                        "S2": (s >> 2) & 1,
                        "S1": (s >> 1) & 1,
                        "S0": s & 1,
                        "Cn": cn,
                        **{f"A{i}": (a >> i) & 1 for i in range(4)},
                        **{f"B{i}": (b >> i) & 1 for i in range(4)},
                    }
                    out = sim.evaluate("ALU_74LS382", inp)
                    f_val = sum(out[f"F{i}"] << i for i in range(4))
                    if s == 0:
                        exp_f = 0
                    elif s == 1:
                        tot = (~a & 0xF) + b + cn
                        exp_f, exp_c = tot & 0xF, (tot >> 4) & 1
                        exp_v = ((~(a >> 3) & 1) == ((b >> 3) & 1)) and (((tot >> 3) & 1) != ((b >> 3) & 1))
                    elif s == 2:
                        tot = a + (~b & 0xF) + cn
                        exp_f, exp_c = tot & 0xF, (tot >> 4) & 1
                        exp_v = (((a >> 3) & 1) == (~(b >> 3) & 1)) and (((tot >> 3) & 1) != ((a >> 3) & 1))
                    elif s == 3:
                        tot = a + b + cn
                        exp_f, exp_c = tot & 0xF, (tot >> 4) & 1
                        exp_v = (((a >> 3) & 1) == ((b >> 3) & 1)) and (((tot >> 3) & 1) != ((a >> 3) & 1))
                    elif s == 4:
                        exp_f = a ^ b
                    elif s == 5:
                        exp_f = a | b
                    elif s == 6:
                        exp_f = a & b
                    else:
                        exp_f = 0xF
                    assert f_val == exp_f
                    if s in (1, 2, 3):
                        assert out["Cn+4"] == exp_c
                        assert out["OVR"] == int(exp_v)
                    passed += 1
    print(f"Verified 74LS382 ALU: {passed}/4096 combinations PASSED!")
