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
    from PIL import Image

    proj, path = _make_sample_project(tmp_path)
    circuit = proj.get_circuit("XorDemo")

    png1 = tmp_path / "direct.png"
    render_circuit_png(circuit, png1, title="Custom Title Demo", scale=18)
    assert png1.exists() and png1.stat().st_size > 100
    with Image.open(png1) as im1:
        w1, h1 = im1.size
        assert w1 >= 420 and h1 > 100

    png_minimal = tmp_path / "minimal.png"
    render_circuit_png(circuit, png_minimal, show_header=False, show_legend=False, scale=12)
    assert png_minimal.exists()
    with Image.open(png_minimal) as im2:
        assert im2.size[1] < h1

    png2 = tmp_path / "cli.png"
    assert cli_main(["render", str(path), "--circuit", "XorDemo", "-o", str(png2)]) == 0
    assert png2.exists() and png2.stat().st_size > 100


def test_preview_junction_detection():
    from pylogiccircuit.preview import _find_junction_points
    from pylogiccircuit.project import WireDef

    # T-junction at (5, 5): horizontal (0,5)-(10,5) touched by vertical (5,5)-(5,10)
    wires = [
        WireDef("w1", "c", 0, 5, 10, 5),
        WireDef("w2", "c", 5, 5, 5, 10),
        # Non-connecting perpendicular crossing at (8, 5)
        WireDef("w3", "c", 8, 0, 8, 10),
    ]
    junctions = _find_junction_points(wires)
    assert (5, 5) in junctions
    assert (8, 5) not in junctions
