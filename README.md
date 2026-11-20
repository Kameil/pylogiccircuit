# pylogiccircuit

**Programmatically build, auto-route, verify, simulate, and render [LogicCircuit](https://www.logiccircuit.org/) (`.CircuitProject`) digital circuits in Python.**

Zero required dependencies (100% Python standard library for core functionality; optional `Pillow` for PNG schematic previews).

---

## Features

- **Fluent Python Circuit Builder**: Create `Project` and `Circuit` sheets with inputs, outputs, built-in LogicCircuit gates (`NOT`, `AND`, `NAND`, `OR`, `NOR`, `XOR`, `XNOR`, `CLOCK`, `LED`), and reusable hierarchical subcircuits.
- **Orthogonal A\* Auto-Router**: Automatically routes nets on LogicCircuit's grid respecting exact crossing/T-junction semantics — no unintended shorts, no pin seal-offs, and clean human-readable layouts.
- **Exact Connectivity & Geometry Verifier**: Catches accidental shorts, disconnected nets, diagonal wires, and pin overlaps before you even open LogicCircuit.
- **LogicCircuit-Compatible FIFO Simulator**: Evaluates combinational and sequential circuits (including nested subcircuits and inverted pins), detects oscillations, and generates full truth tables.
- **Load & Edit Existing `.CircuitProject` Files**: Parse existing XML projects, inspect or modify circuits, and save back in valid LogicCircuit schema order.
- **Optional PNG Preview & CLI**: Render schematic previews with Pillow and run `pylogiccircuit list | verify | truth-table | render` from the terminal.

---

## Installation

```bash
pip install git+https://github.com/Kameil/pylogiccircuit.git
```

With optional PNG preview support (`Pillow`):

```bash
pip install "pylogiccircuit[preview] @ git+https://github.com/Kameil/pylogiccircuit.git"
```

For local development:

```bash
git clone https://github.com/Kameil/pylogiccircuit.git
cd pylogiccircuit
pip install -e ".[dev]"
pytest
```

---

## Quick Start

```python
from pylogiccircuit import Gate, Project, Simulator

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
proj.save("half_adder.CircuitProject")

sim = Simulator.from_project(proj)
print(sim.truth_table("HalfAdder").format_markdown())
```

Output:

| A | B | S | C |
| :-: | :-: | :-: | :-: |
| 0 | 0 | 0 | 0 |
| 0 | 1 | 1 | 0 |
| 1 | 0 | 1 | 0 |
| 1 | 1 | 0 | 1 |

---

## Hierarchical Subcircuits

Any `Circuit` can be instantiated inside another `Circuit` with `add_subcircuit()`. Pin positions along `Left`, `Right`, `Top`, and `Bottom` sides are calculated automatically to match LogicCircuit's exact symbol layout:

```python
fa_inst = top.add_subcircuit(full_adder, x=20, y=10, label="FA0")
top.connect(in_a0, fa_inst["A"])
top.connect(in_b0, fa_inst["B"])
top.connect(fa_inst["S"], out_s0)
```

See the complete runnable scripts in [`examples/`](examples/):

- [`examples/half_adder.py`](examples/half_adder.py) — minimal 1-bit Half Adder
- [`examples/full_adder_4bit.py`](examples/full_adder_4bit.py) — hierarchical 1-bit → 4-bit Ripple-Carry Adder (verified 512/512)
- [`examples/alu_4bit_74ls382.py`](examples/alu_4bit_74ls382.py) — full 4-bit 74LS382/74HC382 ALU (verified 4096/4096)

---

## CLI Usage

```bash
# List circuits in an existing .CircuitProject file
pylogiccircuit list my_project.CircuitProject

# Verify wire geometry across all circuits
pylogiccircuit verify my_project.CircuitProject

# Print the Markdown truth table for a circuit
pylogiccircuit truth-table my_project.CircuitProject --circuit HalfAdder

# Render a PNG schematic preview (requires Pillow)
pylogiccircuit render my_project.CircuitProject --circuit HalfAdder -o half_adder.png
```

---

## License

MIT License — see [LICENSE](LICENSE).
