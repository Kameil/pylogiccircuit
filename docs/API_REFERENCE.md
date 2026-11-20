# API Reference (`pylogiccircuit`)

All public classes and functions are exported from the top-level package:

```python
from pylogiccircuit import (
    Project,
    Circuit,
    Gate,
    GateSpec,
    Simulator,
    TruthTableResult,
    VerificationResult,
    RoutingError,
    render_circuit_png,
    verify_connectivity,
    build_wire_graph,
    auto_route_nets,
    compute_subcircuit_layout,
    parse_gate_guid,
)
```

---

## 1. `Project` (`pylogiccircuit.project`)

Represents a complete LogicCircuit `.CircuitProject` file.

### Constructor

```python
Project(
    name: str = "Project",
    project_id: Optional[str] = None,
    zoom: float = 1.0,
    frequency: int = 10,
)
```

### Methods

| Method | Signature / Return | Description |
| --- | --- | --- |
| `add_circuit` | `(name, notation="", circuit_shape=None, circuit_id=None, set_main=False) -> Circuit` | Create and register a new `Circuit`. The first circuit (or one with `set_main=True`) becomes the startup sheet in LogicCircuit. |
| `get_circuit` | `(name_or_id: str) -> Circuit` | Look up a circuit by name or GUID (`circuit_id`). Raises `KeyError` if not found. |
| `to_xml_tree` | `() -> ET.ElementTree` | Build an XML `ElementTree` conforming to LogicCircuit's `2.0.0.14` XSD ordering. |
| `save` | `(path: str \| Path) -> Path` | Write the `.CircuitProject` XML file in UTF-8 (creating parent directories automatically). |
| `Project.load` | `classmethod (path: str \| Path) -> Project` | Load an existing `.CircuitProject` file while preserving extra XML tags (`CircuitButton`, `TextNote`, etc.). |

---

## 2. `Circuit` (`pylogiccircuit.project`)

Represents a single `LogicalCircuit` sheet containing pins, gates, subcircuits, and wires.

### Adding Components

- **`add_input(name, x, y, side="Left", inverted=False, pin_id=None, symbol_id=None) -> PinHandle`**
  Add an external Input pin at `(x, y)` (`2×2` footprint, wire jam at `(x+2, y+1)`).
  - `side`: side on which this pin appears when the circuit is used as a subcircuit (`"Left"`, `"Right"`, `"Top"`, `"Bottom"`).
  - `inverted`: if `True`, sets `Inverted="True"` on the pin.

- **`add_output(name, x, y, side="Right", inverted=False, pin_id=None, symbol_id=None) -> PinHandle`**
  Add an external Output pin at `(x, y)` (wire jam at `(x, y+1)`).

- **`add_gate(gate: GateSpec, x, y, label="", symbol_id=None) -> GateHandle`**
  Place a built-in LogicCircuit gate at `(x, y)`.
  - Returns a `GateHandle` exposing `handle.in_[i]` (or `handle.inputs[i]`) and `handle.out`.

- **`add_clock(x, y, label="CLK") -> PinHandle`**
  Place a built-in LogicCircuit `Clock` generator at `(x, y)` and return its output `PinHandle`.

- **`add_subcircuit(subcircuit: Circuit, x, y, label="", symbol_id=None) -> SubcircuitHandle`**
  Instantiate another `Circuit` at `(x, y)`.
  - Access pins by name via indexing: `sub["A"]`, `sub["Cout"]`, etc.
  - `sub.width` and `sub.height` are computed automatically using LogicCircuit's exact pin-layout rules.

### Connections, Auto-Routing & Verification

- **`connect(*pins: PinHandle | tuple[int, int], name: Optional[str] = None) -> None`**
  Declare an electrical net connecting 2 or more pins to be routed by `auto_route()`.

- **`add_wire(x1, y1, x2, y2) -> None`**
  Add an explicit straight wire segment from `(x1, y1)` to `(x2, y2)`.

- **`auto_route(max_x=None, max_y=None, max_attempts=25, bend_cost=5.0, cross_cost=3.0, clear_existing=True) -> List[WireSegment]`**
  Automatically route all nets declared with `connect()`, run post-routing short verification, and populate `circuit.wires`.
  - Raises `RoutingError` if all nets cannot be routed within the grid bounds after `max_attempts`.

- **`verify(allow_diagonal: bool = False) -> VerificationResult`**
  Audit the circuit's wires and return `VerificationResult(ok, errors, net_components)`.

- **`symbol_layout() -> Tuple[int, int, Dict[str, Tuple[int, int]]]`**
  Return `(width, height, {pin_name: (dx, dy)})` when this circuit is placed as a subcircuit.

---

## 3. `Gate` & `GateSpec` (`pylogiccircuit.gates`)

Catalogue of built-in LogicCircuit gates:

| Category | Constants | Dynamic Factories (`n` inputs) |
| --- | --- | --- |
| Inverter | `Gate.NOT` | — |
| AND / NAND | `Gate.AND2` .. `Gate.AND8`, `Gate.NAND2` .. `Gate.NAND4` | `Gate.and_(n)`, `Gate.nand(n)` |
| OR / NOR | `Gate.OR2` .. `Gate.OR8`, `Gate.NOR2` .. `Gate.NOR4` | `Gate.or_(n)`, `Gate.nor(n)` |
| XOR / XNOR | `Gate.XOR2` .. `Gate.XOR4`, `Gate.XNOR2` .. `Gate.XNOR4` | `Gate.xor(n)`, `Gate.xnor(n)` |
| Special | `Gate.CLOCK`, `Gate.LED` | — |

### Helper Functions in `gates.py`
- **`parse_gate_guid(guid: str) -> Optional[GateSpec]`**: Decode any built-in LogicCircuit gate GUID.
- **`compute_subcircuit_layout(pins) -> Tuple[int, int, Dict[str, Tuple[int, int]]]`**: Compute exact subcircuit dimensions and pin offsets.

---

## 4. `Simulator` & `TruthTableResult` (`pylogiccircuit.simulator`)

FIFO-queue circuit simulator matching LogicCircuit's evaluation engine.

### Instantiation

```python
sim = Simulator.from_project(project)
# or directly from a .CircuitProject file:
sim = Simulator.from_file("my_circuit.CircuitProject")
```

### Methods on `Simulator`

- **`evaluate(circuit_name: str, inputs: Dict[str, int], max_steps: int = 2000) -> Dict[str, int]`**
  Evaluate a combinational circuit on one input vector and return `{output_name: 0 | 1}`.
  - Raises `RuntimeError` if the circuit oscillates (`steps > max_steps`).

- **`truth_table(circuit_name: str, max_rows: Optional[int] = None, max_steps: int = 2000) -> TruthTableResult`**
  Run LogicCircuit's sequential truth-table sweep (`0 .. 2^N - 1`), retaining latch/flip-flop state across rows and toggling internal `Clock` generators once per row.

### `TruthTableResult` Fields & Methods

| Member | Type | Description |
| --- | --- | --- |
| `circuit_name` | `str` | Name of the evaluated circuit |
| `input_names` | `List[str]` | Input column names ordered by `PinComparer` |
| `output_names` | `List[str]` | Output column names |
| `rows` | `List[Tuple[List[int], List[int]]]` | List of `(input_vector, output_vector)` rows |
| `oscillated` | `bool` | `True` if oscillation occurred during initialization or evaluation |
| `oscillation_row` | `Optional[int]` | Row index where oscillation occurred (`-1` for power-up initialization) |
| `has_internal_clocks` | `bool` | `True` if the flattened circuit contains internal `Clock` blocks |
| `format_markdown()` | `str` | Format the truth table as GitHub-flavored Markdown |

---

## 5. `render_circuit_png` (`pylogiccircuit.preview`)

Render any `Circuit` to a PNG image (requires `Pillow`):

```python
render_circuit_png(
    circuit: Circuit,
    output_path: str | Path,
    scale: int = 16,
    padding: int = 3,
    *,
    title: Optional[str] = None,
    show_header: bool = True,
    show_legend: bool = True,
) -> Path
```

- `scale`: Pixels per LogicCircuit grid unit (e.g., `20` for small circuits, `14` for large ALUs).
- `padding`: Margin in grid units around the schematic bounds.
- `title`: Custom header bar title (defaults to `"{name} ({notation})"`).
- `show_header` / `show_legend`: Toggle the dark top stats bar and bottom color legend.

---

## 6. Low-Level Utilities (`verifier.py` & `router.py`)

- **`build_wire_graph(wires, pins) -> Dict[Point, int]`**: Compute connected components under LogicCircuit's exact wire-crossing rules.
- **`verify_connectivity(wires, all_pins, expected_nets=None, allow_diagonal=False) -> VerificationResult`**: Audit shorts, split nets, unassigned pin touches, and diagonal wires.
- **`auto_route_nets(obstacles, all_pins, nets, max_x=None, max_y=None, max_attempts=25, bend_cost=5.0, cross_cost=3.0) -> List[WireSegment]`**: Direct entry point to the orthogonal A\* router.

---

## 7. Recipe: Load, Audit, Simulate & Render an Existing Project

```python
from pylogiccircuit import Project, Simulator, render_circuit_png

proj = Project.load("my_assignment.CircuitProject")

# Inspect every circuit sheet
for c in proj.circuits:
    res = c.verify(allow_diagonal=True)
    print(f"{c.name}: ok={res.ok}, symbols={len(c.symbols)}, wires={len(c.wires)}")

# Run a truth table
sim = Simulator.from_project(proj)
tt = sim.truth_table("FullAdder")
print(tt.format_markdown())

# Export a high-resolution PNG schematic
render_circuit_png(proj.get_circuit("FullAdder"), "full_adder_preview.png", scale=18)
```
