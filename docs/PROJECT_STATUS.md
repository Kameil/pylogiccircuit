# Project Status (`v0.1.0`)

This document captures the **current state** of **`pylogiccircuit`**, covering implemented modules, verified test and example results, LogicCircuit compatibility, known limitations, and the roadmap for upcoming releases.

---

## 1. Executive Summary

`pylogiccircuit` is a packaged Python library (`pyproject.toml`) with **zero required core dependencies** (100% Python 3.10+ standard library) that can:

1. **Construct digital circuits programmatically** using built-in LogicCircuit gates, input/output pins, clocks, LEDs, and nested hierarchical subcircuits.
2. **Auto-route orthogonal wires** on LogicCircuit's grid via A\* search with pin-stub protection, escape guards, and rip-up-and-reroute, guaranteeing zero shorts.
3. **Verify exact wire geometry and electrical connectivity** under LogicCircuit's true connection semantics (perpendicular crossings do not connect; T-junctions and overlapping collinear runs connect).
4. **Simulate combinational and sequential circuits** using a FIFO (*DirtyList*) evaluation engine matching LogicCircuit, generating full truth tables and detecting oscillations.
5. **Load and save `.CircuitProject` files** strictly adhering to LogicCircuit's XML schema order (`http://LogicCircuit.net/2.0.0.14/CircuitProject.xsd`).
6. **Render crisp PNG schematic previews** (optional `Pillow` dependency) complete with blueprint grid, inversion bubbles, T-junction dots, stats header, and legend.
7. **Run from the command line** via `pylogiccircuit list | verify | truth-table | render`.

---

## 2. Module Inventory

| Module | Lines | Responsibility | Dependencies | Status |
| --- | --: | --- | --- | :---: |
| [`src/pylogiccircuit/__init__.py`](../src/pylogiccircuit/__init__.py) | 46 | Public API exports and package version (`0.1.0`) | Stdlib | Ready |
| [`src/pylogiccircuit/gates.py`](../src/pylogiccircuit/gates.py) | 245 | Built-in LogicCircuit gate GUIDs, Boolean evaluation, and pin/subcircuit layout geometry | Stdlib | Ready |
| [`src/pylogiccircuit/project.py`](../src/pylogiccircuit/project.py) | 626 | Fluent builder API (`Project`, `Circuit`, handles) and `.CircuitProject` XML serializer/loader | Stdlib | Ready |
| [`src/pylogiccircuit/router.py`](../src/pylogiccircuit/router.py) | 383 | Orthogonal A\* router with stubs, escape guards, pin halo, and rip-up-and-reroute | Stdlib | Ready |
| [`src/pylogiccircuit/verifier.py`](../src/pylogiccircuit/verifier.py) | 154 | Exact connectivity graph and verification for shorts, split nets, and diagonal wires | Stdlib | Ready |
| [`src/pylogiccircuit/simulator.py`](../src/pylogiccircuit/simulator.py) | 385 | Hierarchical flattening (Union-Find), FIFO engine, truth-table sweep, and oscillation detection | Stdlib | Ready |
| [`src/pylogiccircuit/preview.py`](../src/pylogiccircuit/preview.py) | 292 | PNG schematic renderer (header, legend, inversion bubbles, junction dots, auto-fit labels) | Pillow *(optional)* | Ready |
| [`src/pylogiccircuit/cli.py`](../src/pylogiccircuit/cli.py) | 84 | CLI entry point (`list`, `verify`, `truth-table`, `render`) | Stdlib (+ Pillow for `render`) | Ready |

**Total core package (`src/pylogiccircuit/`):** `2,215` lines of typed Python.

---

## 3. Verification & Quality

### Unit Test Suite (`pytest`)

| Test File | Coverage | Status |
| --- | --- | :---: |
| [`tests/test_gates_and_xml.py`](../tests/test_gates_and_xml.py) | GUID decoding, gate truth evaluation, 4-sided subcircuit layout, XML round-trip, and XSD tag ordering | Passing |
| [`tests/test_router_and_verifier.py`](../tests/test_router_and_verifier.py) | Non-connecting perpendicular crossings, T-junction short detection, diagonal wire checks, crossed auto-routing | Passing |
| [`tests/test_simulator.py`](../tests/test_simulator.py) | Half Adder, hierarchical 2-bit adder, Ring Oscillator (oscillation detection), active-low NAND SR Latch | Passing |
| [`tests/test_preview_and_cli.py`](../tests/test_preview_and_cli.py) | PNG preview options (header/legend/custom title), junction detection, and CLI commands (`list`, `verify`, `truth-table`, `render`) | Passing |

### Verified Runnable Examples

| Example | Circuit | Exhaustive Verification | Rendered Preview |
| --- | --- | --- | --- |
| [`examples/half_adder.py`](../examples/half_adder.py) | 1-bit Half Adder | `4 / 4` truth-table rows | [`docs/images/half_adder.png`](images/half_adder.png) |
| [`examples/full_adder_4bit.py`](../examples/full_adder_4bit.py) | 1-bit Full Adder + Hierarchical 4-bit Adder | `512 / 512` input combinations | [`docs/images/full_adder_1bit.png`](images/full_adder_1bit.png), [`docs/images/adder_4bit.png`](images/adder_4bit.png) |
| [`examples/alu_4bit_74ls382.py`](../examples/alu_4bit_74ls382.py) | `BitMux` Selector + 4-bit `74LS382/74HC382` ALU | `4096 / 4096` combinations (`F3..F0`, `Cn+4`, `OVR`) | [`docs/images/bit_mux.png`](images/bit_mux.png), [`docs/images/alu_74ls382.png`](images/alu_74ls382.png) |

### Continuous Integration (CI)
- GitHub Actions workflow in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs `pytest -v` and executes all 3 examples across Python `3.10`, `3.11`, `3.12`, and `3.13` on every push and pull request to `main`.

---

## 4. LogicCircuit (`2.0.0.14`) Compatibility Matrix

| LogicCircuit Feature | Builder API | XML Load / Save | Auto-Router | FIFO Simulator | PNG Preview |
| --- | :---: | :---: | :---: | :---: | :---: |
| `Input` / `Output` pins (1-bit, 4 sides, inversion) | Yes | Yes | Yes | Yes | Yes |
| Built-in gates `NOT`, `AND`, `NAND`, `OR`, `NOR`, `XOR`, `XNOR` (1..8 inputs) | Yes | Yes | Yes | Yes | Yes |
| Hierarchical subcircuits (arbitrary nesting depth) | Yes | Yes | Yes | Yes | Yes |
| Internal `Clock` generator | Yes | Yes | Yes | Yes *(toggles per row)* | Yes |
| 1-bit `LED` | Yes | Yes | Yes | Ignored (observer) | Yes |
| `CircuitButton`, `TextNote`, `Constant`, `Sensor`, `Memory`, `CircuitProbe` | — | Preserved on `load`/`save` | — | Not yet simulated | Generic box |
| Multi-bit buses (`BitWidth > 1`) & `Splitter` | Not yet | Preserved via extra attrs | Not yet | 1-bit currently | Not yet |

---

## 5. Known Limitations

1. **Manual block placement (`x`, `y`)**: Users currently specify `(x, y)` coordinates for pins, gates, and subcircuits while `auto_route()` handles all wire routing. Automatic topological placement (*auto-placer*) is planned for a future release.
2. **1-bit bus width in simulation**: Multi-bit pins/gates (`BitWidth > 1`) and `Splitter` blocks are not yet natively simulated.
3. **Advanced LogicCircuit primitives**: `Constant`, `Memory` (ROM/RAM), `Sensor`, `Button`, and `LedMatrix` do not yet have dedicated builder methods or simulation models.
4. **Standard left-to-right orientation**: The router assumes LogicCircuit's default left-to-right gate orientation.

---

## 6. Roadmap

### `v0.2.0` — Expanded Components & Simulation Control
- [ ] Dedicated builders for `Constant` (0/1), `Button`, `Probe`, and `TextNote`.
- [ ] Multi-bit bus (`BitWidth`) and `Splitter` support across the builder and simulator.
- [ ] Interactive cycle-by-cycle sequential simulation (`sim.step()`, `sim.tick()`).

### `v0.3.0` — Automatic Placement & Vector Export
- [ ] Layered topological auto-placer (allowing optional `x, y` coordinates).
- [ ] Vector **SVG** schematic export alongside PNG.
- [ ] Standard building-block library (`pylogiccircuit.stdlib`: Mux, Decoder, FullAdder, RippleAdder, Flip-Flops).

### `v1.0.0` — PyPI Release
- [ ] Official PyPI package publication (`pip install pylogiccircuit`).
- [ ] Full `ROM`/`RAM` simulation support and hosted documentation (MkDocs / GitHub Pages).
