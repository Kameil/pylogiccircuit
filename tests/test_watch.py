"""Tests for live preview watcher (pylogiccircuit watch)."""

import pytest

from pylogiccircuit import Gate, Project
from pylogiccircuit.cli import main as cli_main
from pylogiccircuit.watch import load_project_from_source, render_once


def test_watch_once_on_python_script_with_builder_function(tmp_path):
    pytest.importorskip("PIL")
    script = tmp_path / "my_circuit.py"
    script.write_text(
        """
from pylogiccircuit import Gate, Project

def build_demo():
    p = Project("WatchDemo")
    c = p.add_circuit("XorGate", notation="XOR")
    a = c.add_input("A", x=2, y=2)
    b = c.add_input("B", x=2, y=8)
    g = c.add_gate(Gate.XOR2, x=10, y=4)
    y = c.add_output("Y", x=18, y=5)
    c.connect(a, g.in_[0])
    c.connect(b, g.in_[1])
    c.connect(g.out, y)
    c.auto_route()
    return p
""",
        encoding="utf-8",
    )

    out_png = tmp_path / ".pylogiccircuit_preview.png"
    out_md = tmp_path / ".pylogiccircuit_preview.md"
    snap = render_once(script, out_png, md_path=out_md)

    assert snap.ok
    assert snap.circuit_name == "XorGate"
    assert snap.error is None
    assert out_png.exists() and out_png.stat().st_size > 100
    assert out_md.exists()
    md_text = out_md.read_text(encoding="utf-8")
    assert "## Truth Table" in md_text
    assert "| A | B | Y |" in md_text
    assert "| 1 | 0 | 1 |" in md_text


def test_watch_once_on_top_level_script_and_circuitproject(tmp_path):
    pytest.importorskip("PIL")
    script = tmp_path / "top_level.py"
    script.write_text(
        """
from pylogiccircuit import Gate, Project

proj = Project("TopLevel")
c = proj.add_circuit("Inv")
x = c.add_input("X", x=2, y=3)
n = c.add_gate(Gate.NOT, x=8, y=2)
y = c.add_output("Y", x=14, y=3)
c.connect(x, n.in_[0])
c.connect(n.out, y)
c.auto_route()
""",
        encoding="utf-8",
    )
    proj = load_project_from_source(script)
    cp_path = tmp_path / "saved.CircuitProject"
    proj.save(cp_path)

    out_png = tmp_path / "out.png"
    rc = cli_main(["watch", str(cp_path), "-o", str(out_png), "--once"])
    assert rc == 0
    assert out_png.exists() and out_png.stat().st_size > 100


def test_watch_renders_error_card_without_crashing(tmp_path):
    pytest.importorskip("PIL")
    broken = tmp_path / "broken.py"
    broken.write_text("def oops(:\n    pass\n", encoding="utf-8")

    out_png = tmp_path / "err.png"
    out_md = tmp_path / "err.md"
    snap = render_once(broken, out_png, md_path=out_md)

    assert not snap.ok
    assert snap.error is not None
    assert "SyntaxError" in snap.error
    assert out_png.exists() and out_png.stat().st_size > 100
    assert "SyntaxError" in out_md.read_text(encoding="utf-8")
