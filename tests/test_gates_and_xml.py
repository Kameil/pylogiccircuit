"""Tests for gate definitions, subcircuit geometry, and XML serialization."""

import xml.etree.ElementTree as ET

from pylogiccircuit import Gate, Project, compute_subcircuit_layout, parse_gate_guid


def test_parse_builtin_gates():
    for gate in (
        Gate.NOT,
        Gate.AND2,
        Gate.AND3,
        Gate.AND4,
        Gate.NAND2,
        Gate.NAND3,
        Gate.OR2,
        Gate.OR5,
        Gate.OR7,
        Gate.NOR2,
        Gate.XOR2,
        Gate.XOR4,
        Gate.XNOR2,
        Gate.CLOCK,
        Gate.LED,
    ):
        parsed = parse_gate_guid(gate.guid)
        assert parsed == gate


def test_gate_truth_evaluation():
    assert Gate.NOT.eval_bits([0]) == 1
    assert Gate.NOT.eval_bits([1]) == 0
    assert Gate.AND3.eval_bits([1, 1, 1]) == 1
    assert Gate.AND3.eval_bits([1, 0, 1]) == 0
    assert Gate.NAND2.eval_bits([1, 1]) == 0
    assert Gate.NAND2.eval_bits([1, 0]) == 1
    assert Gate.OR2.eval_bits([0, 0]) == 0
    assert Gate.OR2.eval_bits([0, 1]) == 1
    assert Gate.NOR2.eval_bits([0, 0]) == 1
    assert Gate.XOR4.eval_bits([1, 0, 1, 1]) == 1
    assert Gate.XNOR2.eval_bits([1, 1]) == 1
    assert Gate.XNOR2.eval_bits([1, 0]) == 0


def test_subcircuit_layout_all_sides():
    pins = [
        {"name": "L0", "pin_side": "Left", "x": 0, "y": 2},
        {"name": "L1", "pin_side": "Left", "x": 0, "y": 6},
        {"name": "R0", "pin_side": "Right", "x": 10, "y": 4},
        {"name": "T0", "pin_side": "Top", "x": 2, "y": 0},
        {"name": "T1", "pin_side": "Top", "x": 6, "y": 0},
        {"name": "B0", "pin_side": "Bottom", "x": 2, "y": 10},
        {"name": "B1", "pin_side": "Bottom", "x": 4, "y": 10},
        {"name": "B2", "pin_side": "Bottom", "x": 6, "y": 10},
    ]
    w, h, offs = compute_subcircuit_layout(pins)
    assert w == 4
    assert h == 4
    assert offs["L0"] == (0, 1)
    assert offs["L1"] == (0, 3)
    assert offs["R0"] == (4, 2)
    assert offs["T0"] == (1, 0)
    assert offs["T1"] == (3, 0)
    assert offs["B0"] == (1, 4)
    assert offs["B1"] == (2, 4)
    assert offs["B2"] == (3, 4)


def test_xml_roundtrip_and_schema_order(tmp_path):
    proj = Project("RoundTrip Test")
    c = proj.add_circuit("Inverter", notation="INV")
    inp = c.add_input("X", x=2, y=4)
    g = c.add_gate(Gate.NOT, x=8, y=3)
    out = c.add_output("Y", x=14, y=4, inverted=True)
    c.connect(inp, g.in_[0])
    c.connect(g.out, out)
    c.auto_route()

    path = tmp_path / "inv.CircuitProject"
    proj.save(path)

    # Verify strict LogicCircuit XSD tag ordering
    root = ET.parse(path).getroot()
    order = ["Project", "LogicalCircuit", "Pin", "CircuitSymbol", "Wire"]
    rank = {t: i for i, t in enumerate(order)}
    ranks = [rank[e.tag.split("}")[-1]] for e in root]
    assert ranks == sorted(ranks)

    # Reload and check integrity
    loaded = Project.load(path)
    assert loaded.name == "RoundTrip Test"
    lc = loaded.get_circuit("Inverter")
    assert len(lc.pins) == 2
    assert any(p.name == "Y" and p.inverted for p in lc.pins)
    assert len(lc.wires) >= 2
    assert lc.verify().ok
