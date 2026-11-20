"""Tests for PNG preview rendering and CLI subcommands."""

import pytest

from pylogiccircuit import Gate, Project, render_circuit_png
from pylogiccircuit.cli import main as cli_main


def _make_sample_project(tmp_path):
    proj = Project("CLI Sample")
    c = proj.add_circuit("XorDemo", notation="XOR")
    a = c.add_input("A", x=2, y=2)
    b = c.add_input("B", x=2, y=8)
    g = c.add_gate(Gate.XOR2, x=10, y=4)
    y = c.add_output("Y", x=18, y=5)
    c.connect(a, g.in_[0])
    c.connect(b, g.in_[1])
    c.connect(g.out, y)
    c.auto_route()
    path = tmp_path / "xor_demo.CircuitProject"
    proj.save(path)
    return proj, path


def test_cli_list_verify_truth_table(tmp_path, capsys):
    _, path = _make_sample_project(tmp_path)

    assert cli_main(["list", str(path)]) == 0
    out = capsys.readouterr().out
    assert "XorDemo" in out

    assert cli_main(["verify", str(path)]) == 0
    out = capsys.readouterr().out
    assert "[OK] XorDemo" in out

    assert cli_main(["truth-table", str(path), "--circuit", "XorDemo"]) == 0
    out = capsys.readouterr().out
    assert "| A | B | Y |" in out
    assert "| 1 | 0 | 1 |" in out
    assert "| 1 | 1 | 0 |" in out


def test_preview_render_and_cli(tmp_path):
    pytest.importorskip("PIL")
    proj, path = _make_sample_project(tmp_path)

    png1 = tmp_path / "direct.png"
    render_circuit_png(proj.get_circuit("XorDemo"), png1)
    assert png1.exists() and png1.stat().st_size > 100

    png2 = tmp_path / "cli.png"
    assert cli_main(["render", str(path), "--circuit", "XorDemo", "-o", str(png2)]) == 0
    assert png2.exists() and png2.stat().st_size > 100
