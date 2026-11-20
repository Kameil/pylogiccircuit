"""Tests for the orthogonal A* router and exact wire connectivity verifier."""

from pylogiccircuit import Gate, Project, Simulator, verify_connectivity


def test_perpendicular_crossing_does_not_short():
    # Horizontal wire (0,5)-(10,5) and vertical wire (5,0)-(5,10) cross at (5,5)
    # without an endpoint at (5,5) -> must remain two separate components.
    wires = [(0, 5, 10, 5), (5, 0, 5, 10)]
    pins = {(0, 5): "A", (10, 5): "B", (5, 0): "C", (5, 10): "D"}
    res = verify_connectivity(
        wires,
        pins,
        expected_nets=[("H", [(0, 5), (10, 5)]), ("V", [(5, 0), (5, 10)])],
    )
    assert res.ok


def test_t_junction_connects_and_detects_short():
    # Vertical wire stops ON (5,5) -> creates a LogicCircuit T-junction -> short!
    wires = [(0, 5, 10, 5), (5, 0, 5, 5)]
    pins = {(0, 5): "A", (10, 5): "B", (5, 0): "C"}
    res = verify_connectivity(
        wires,
        pins,
        expected_nets=[("H", [(0, 5), (10, 5)]), ("V", [(5, 0)])],
    )
    assert not res.ok
    assert any("Short circuit" in e for e in res.errors)


def test_diagonal_wire_flagged():
    res = verify_connectivity([(0, 0, 4, 4)], {(0, 0): "A", (4, 4): "B"})
    assert not res.ok
    assert any("diagonal" in e for e in res.errors)


def test_auto_route_crossing_inputs():
    # Intentionally cross inputs A (top) -> bottom gate and B (bottom) -> top gate
    proj = Project("Cross Test")
    c = proj.add_circuit("Cross", notation="X")
    a = c.add_input("A", x=2, y=2)
    b = c.add_input("B", x=2, y=10)
    g_top = c.add_gate(Gate.NOT, x=14, y=2)
    g_bot = c.add_gate(Gate.NOT, x=14, y=10)
    y_top = c.add_output("Y_top", x=22, y=3)
    y_bot = c.add_output("Y_bot", x=22, y=11)

    c.connect(a, g_bot.in_[0])
    c.connect(b, g_top.in_[0])
    c.connect(g_top.out, y_top)
    c.connect(g_bot.out, y_bot)

    c.auto_route()
    assert c.verify().ok

    sim = Simulator.from_project(proj)
    assert sim.evaluate("Cross", {"A": 1, "B": 0}) == {"Y_top": 1, "Y_bot": 0}
    assert sim.evaluate("Cross", {"A": 0, "B": 1}) == {"Y_top": 0, "Y_bot": 1}
