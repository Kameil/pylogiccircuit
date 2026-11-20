"""Built-in LogicCircuit gate identifiers and exact pin geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


SCHEMA_NS = "http://LogicCircuit.net/2.0.0.14/CircuitProject.xsd"


@dataclass(frozen=True)
class GateSpec:
    """Metadata describing a built-in LogicCircuit primitive gate or component."""

    guid: str
    kind: str  # "NOT", "OR", "NOR", "AND", "NAND", "XOR", "XNOR", "CLOCK", "LED"
    n_inputs: int
    inverted: bool = False
    width: int = 3

    @property
    def height(self) -> int:
        if self.kind in ("CLOCK", "LED"):
            return 2
        return gate_height(self.n_inputs)

    def input_offsets(self) -> List[Tuple[int, int]]:
        if self.kind == "CLOCK":
            return []
        if self.kind == "LED":
            return [(0, 1)]
        return [(0, dy) for dy in gate_in_dys(self.n_inputs)]

    def output_offset(self) -> Optional[Tuple[int, int]]:
        if self.kind == "LED":
            return None
        if self.kind == "CLOCK":
            return (2, 1)
        return (self.width, gate_out_dy(self.n_inputs))

    def eval_bits(self, inputs: List[int]) -> int:
        """Evaluate this gate on a list of binary input values (0 or 1)."""
        if self.kind == "NOT":
            return 1 - (inputs[0] & 1)
        if self.kind in ("OR", "NOR"):
            val = 1 if any(inputs) else 0
            return (1 - val) if self.inverted else val
        if self.kind in ("AND", "NAND"):
            val = 1 if all(inputs) else 0
            return (1 - val) if self.inverted else val
        if self.kind in ("XOR", "XNOR"):
            val = 0
            for b in inputs:
                val ^= (b & 1)
            return (1 - val) if self.inverted else val
        raise ValueError(f"Gate kind {self.kind!r} cannot be evaluated as combinational logic.")


def gate_height(n_inputs: int) -> int:
    """Grid height of a standard LogicCircuit gate with ``n_inputs`` inputs."""
    return max(4, n_inputs + 1)


def gate_in_dys(n_inputs: int) -> List[int]:
    """Relative Y offsets of input pins along the left edge (dx = 0) of a gate."""
    if n_inputs <= 0:
        return []
    if n_inputs == 1:
        return [2]
    h = gate_height(n_inputs)
    step = (h - 2) // (n_inputs - 1)
    return [1 + i * step for i in range(n_inputs)]


def gate_out_dy(n_inputs: int) -> int:
    """Relative Y offset of the output pin along the right edge (dx = 3) of a gate."""
    if n_inputs == 1:
        return 2
    return gate_height(n_inputs) // 2


def make_gate_guid(family_code: int, n_inputs: int, inverted: bool) -> str:
    """Construct the canonical LogicCircuit built-in gate GUID.

    LogicCircuit encodes primitive gates as:
      ``00000000-0000-0000-0000-000000{family:02d}{inputs:02d}{inv:02d}``
    where family 02=NOT/BUF, 03=OR/NOR, 04=AND/NAND, 05=XOR/XNOR.
    """
    inv_code = 1 if inverted else 0
    return f"00000000-0000-0000-0000-000000{family_code:02d}{n_inputs:02d}{inv_code:02d}"


class Gate:
    """Catalogue of built-in LogicCircuit gates and primitive components."""

    # Clock & LED primitives
    CLOCK = GateSpec("00000000-0000-0000-0000-000000010000", "CLOCK", 0, False, width=2)
    LED   = GateSpec("00000000-0000-0000-0000-000000080100", "LED",   1, False, width=2)

    # Single-input inverter
    NOT   = GateSpec(make_gate_guid(2, 1, True), "NOT", 1, True)

    # OR / NOR (2..8 inputs)
    OR2   = GateSpec(make_gate_guid(3, 2, False), "OR", 2, False)
    OR3   = GateSpec(make_gate_guid(3, 3, False), "OR", 3, False)
    OR4   = GateSpec(make_gate_guid(3, 4, False), "OR", 4, False)
    OR5   = GateSpec(make_gate_guid(3, 5, False), "OR", 5, False)
    OR6   = GateSpec(make_gate_guid(3, 6, False), "OR", 6, False)
    OR7   = GateSpec(make_gate_guid(3, 7, False), "OR", 7, False)
    OR8   = GateSpec(make_gate_guid(3, 8, False), "OR", 8, False)

    NOR2  = GateSpec(make_gate_guid(3, 2, True), "NOR", 2, True)
    NOR3  = GateSpec(make_gate_guid(3, 3, True), "NOR", 3, True)
    NOR4  = GateSpec(make_gate_guid(3, 4, True), "NOR", 4, True)

    # AND / NAND (2..8 inputs)
    AND2  = GateSpec(make_gate_guid(4, 2, False), "AND", 2, False)
    AND3  = GateSpec(make_gate_guid(4, 3, False), "AND", 3, False)
    AND4  = GateSpec(make_gate_guid(4, 4, False), "AND", 4, False)
    AND5  = GateSpec(make_gate_guid(4, 5, False), "AND", 5, False)
    AND6  = GateSpec(make_gate_guid(4, 6, False), "AND", 6, False)
    AND7  = GateSpec(make_gate_guid(4, 7, False), "AND", 7, False)
    AND8  = GateSpec(make_gate_guid(4, 8, False), "AND", 8, False)

    NAND2 = GateSpec(make_gate_guid(4, 2, True), "NAND", 2, True)
    NAND3 = GateSpec(make_gate_guid(4, 3, True), "NAND", 3, True)
    NAND4 = GateSpec(make_gate_guid(4, 4, True), "NAND", 4, True)

    # XOR / XNOR (2..8 inputs)
    XOR2  = GateSpec(make_gate_guid(5, 2, False), "XOR", 2, False)
    XOR3  = GateSpec(make_gate_guid(5, 3, False), "XOR", 3, False)
    XOR4  = GateSpec(make_gate_guid(5, 4, False), "XOR", 4, False)

    XNOR2 = GateSpec(make_gate_guid(5, 2, True), "XNOR", 2, True)
    XNOR3 = GateSpec(make_gate_guid(5, 3, True), "XNOR", 3, True)
    XNOR4 = GateSpec(make_gate_guid(5, 4, True), "XNOR", 4, True)

    @staticmethod
    def or_(n: int) -> GateSpec:
        return GateSpec(make_gate_guid(3, n, False), "OR", n, False)

    @staticmethod
    def nor(n: int) -> GateSpec:
        return GateSpec(make_gate_guid(3, n, True), "NOR", n, True)

    @staticmethod
    def and_(n: int) -> GateSpec:
        return GateSpec(make_gate_guid(4, n, False), "AND", n, False)

    @staticmethod
    def nand(n: int) -> GateSpec:
        return GateSpec(make_gate_guid(4, n, True), "NAND", n, True)

    @staticmethod
    def xor(n: int) -> GateSpec:
        return GateSpec(make_gate_guid(5, n, False), "XOR", n, False)

    @staticmethod
    def xnor(n: int) -> GateSpec:
        return GateSpec(make_gate_guid(5, n, True), "XNOR", n, True)


def parse_gate_guid(guid: str) -> Optional[GateSpec]:
    """Decode any built-in LogicCircuit gate GUID into a :class:`GateSpec`."""
    g = guid.lower()
    if g == Gate.CLOCK.guid:
        return Gate.CLOCK
    if g == Gate.LED.guid:
        return Gate.LED
    prefix = "00000000-0000-0000-0000-000000"
    if not g.startswith(prefix) or len(g) != 36:
        return None
    tail = g[len(prefix):]
    if not tail.isdigit():
        return None
    family = int(tail[0:2])
    n_in = int(tail[2:4])
    inv = int(tail[4:6]) == 1
    if family == 2 and n_in == 1 and inv:
        return Gate.NOT
    if family == 3:
        return GateSpec(g, "NOR" if inv else "OR", n_in, inv)
    if family == 4:
        return GateSpec(g, "NAND" if inv else "AND", n_in, inv)
    if family == 5:
        return GateSpec(g, "XNOR" if inv else "XOR", n_in, inv)
    return None


def compute_subcircuit_layout(
    pins: List[Dict[str, object]],
) -> Tuple[int, int, Dict[str, Tuple[int, int]]]:
    """Compute LogicCircuit's exact symbol bounding box (W, H) and pin offsets.

    Follows LogicCircuit's ``LogicalCircuit.GlyphGrid`` layout:
    - Left/Right pins are ordered top-to-bottom (by their Y coordinate inside the subcircuit).
    - Top/Bottom pins are ordered left-to-right (by their X coordinate inside the subcircuit).
    - Width = max(3, max(len(top), len(bottom)) + 1)
    - Height = max(4, max(len(left), len(right)) + 1)
    """
    by_side: Dict[str, List[Dict[str, object]]] = {
        "Left": [],
        "Right": [],
        "Top": [],
        "Bottom": [],
    }
    for p in pins:
        side = str(p.get("pin_side", "Left"))
        by_side.setdefault(side, []).append(p)

    # LogicCircuit PinComparer sorts Left/Right by Y then X; Top/Bottom by X then Y
    by_side["Left"].sort(key=lambda p: (int(p.get("y", 0)), int(p.get("x", 0))))
    by_side["Right"].sort(key=lambda p: (int(p.get("y", 0)), int(p.get("x", 0))))
    by_side["Top"].sort(key=lambda p: (int(p.get("x", 0)), int(p.get("y", 0))))
    by_side["Bottom"].sort(key=lambda p: (int(p.get("x", 0)), int(p.get("y", 0))))

    n_tb = max(len(by_side["Top"]), len(by_side["Bottom"]))
    n_lr = max(len(by_side["Left"]), len(by_side["Right"]))

    width = max(3, n_tb + 1) if n_tb > 0 else 3
    height = max(4, n_lr + 1) if n_lr > 0 else 4

    offsets: Dict[str, Tuple[int, int]] = {}

    def _distribute(count: int, span: int) -> List[int]:
        if count == 0:
            return []
        if count == 1:
            return [span // 2]
        step = (span - 2) // (count - 1)
        if step < 1:
            step = 1
        return [1 + i * step for i in range(count)]

    for p, dy in zip(by_side["Left"], _distribute(len(by_side["Left"]), height)):
        offsets[str(p["name"])] = (0, dy)
    for p, dy in zip(by_side["Right"], _distribute(len(by_side["Right"]), height)):
        offsets[str(p["name"])] = (width, dy)
    for p, dx in zip(by_side["Top"], _distribute(len(by_side["Top"]), width)):
        offsets[str(p["name"])] = (dx, 0)
    for p, dx in zip(by_side["Bottom"], _distribute(len(by_side["Bottom"]), width)):
        offsets[str(p["name"])] = (dx, height)

    return width, height, offsets
