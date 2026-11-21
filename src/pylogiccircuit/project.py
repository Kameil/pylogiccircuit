"""High-level Project & Circuit builder and LogicCircuit XML serializer/loader."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .gates import (
    Gate,
    GateSpec,
    SCHEMA_NS,
    compute_subcircuit_layout,
    parse_gate_guid,
)
from .router import BoxObstacle, auto_route_nets
from .verifier import Point, VerificationResult, WireSegment, verify_connectivity

ET.register_namespace("", SCHEMA_NS)

PinLike = Union[Point, "PinHandle"]


@dataclass
class PinDef:
    pin_id: str
    circuit_id: str
    name: str
    pin_type: str = "Input"  # "Input" or "Output"
    pin_side: str = "Left"   # "Left", "Right", "Top", "Bottom"
    inverted: bool = False
    x: int = 2
    y: int = 2
    symbol_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def jam(self) -> Point:
        return (self.x + 2, self.y + 1) if self.pin_type == "Input" else (self.x, self.y + 1)


@dataclass
class SymbolDef:
    symbol_id: str
    circuit_id: str          # Target gate GUID, PinId, or subcircuit LogicalCircuitId
    logical_circuit_id: str  # Owner circuit ID
    x: int
    y: int
    label: str = ""
    extra_attribs: Dict[str, str] = field(default_factory=dict)


@dataclass
class WireDef:
    wire_id: str
    logical_circuit_id: str
    x1: int
    y1: int
    x2: int
    y2: int


class PinHandle:
    """Reference to a connectable pin coordinate on a pin, gate, or subcircuit."""

    def __init__(self, point: Point, name: str = "") -> None:
        self.point = point
        self.name = name

    def __repr__(self) -> str:
        return f"PinHandle({self.name!r}, {self.point})"


class GateHandle:
    """Handle returned by :meth:`Circuit.add_gate` exposing ``in_`` and ``out`` pins."""

    def __init__(
        self,
        spec: GateSpec,
        symbol: SymbolDef,
        inputs: List[PinHandle],
        output: Optional[PinHandle],
    ) -> None:
        self.spec = spec
        self.symbol = symbol
        self.in_ = inputs
        self._out = output

    @property
    def out(self) -> PinHandle:
        """Output pin handle of this gate (raises ``AttributeError`` for sinks like ``LED``)."""
        if self._out is None:
            raise AttributeError(f"Component {self.spec.kind!r} has no output pin.")
        return self._out

    @property
    def inputs(self) -> List[PinHandle]:
        return self.in_


class SubcircuitHandle:
    """Handle returned by :meth:`Circuit.add_subcircuit` exposing named pin access."""

    def __init__(
        self,
        target: "Circuit",
        symbol: SymbolDef,
        pins: Dict[str, PinHandle],
        width: int,
        height: int,
    ) -> None:
        self.target = target
        self.symbol = symbol
        self.pins = pins
        self.width = width
        self.height = height

    def __getitem__(self, pin_name: str) -> PinHandle:
        return self.pins[pin_name]


def _resolve_point(ref: PinLike) -> Point:
    if isinstance(ref, PinHandle):
        return ref.point
    return (int(ref[0]), int(ref[1]))


class Circuit:
    """A single LogicCircuit ``LogicalCircuit`` sheet (pins, gates, subcircuits, wires)."""

    def __init__(
        self,
        project: "Project",
        name: str,
        notation: str = "",
        circuit_shape: Optional[str] = None,
        circuit_id: Optional[str] = None,
    ) -> None:
        self.project = project
        self.circuit_id = circuit_id or str(uuid.uuid4())
        self.name = name
        self.notation = notation or name
        self.circuit_shape = circuit_shape

        self.pins: List[PinDef] = []
        self.symbols: List[SymbolDef] = []
        self.wires: List[WireDef] = []
        self._nets: List[Tuple[str, List[Point]]] = []
        self._net_counter = 0

    # ------------------------------------------------------------------
    # Building API
    # ------------------------------------------------------------------
    def add_input(
        self,
        name: str,
        x: int,
        y: int,
        side: str = "Left",
        inverted: bool = False,
        pin_id: Optional[str] = None,
        symbol_id: Optional[str] = None,
    ) -> PinHandle:
        """Add an external Input pin to this circuit."""
        pid = pin_id or str(uuid.uuid4())
        sid = symbol_id or str(uuid.uuid4())
        pdef = PinDef(
            pin_id=pid,
            circuit_id=self.circuit_id,
            name=name,
            pin_type="Input",
            pin_side=side,
            inverted=inverted,
            x=x,
            y=y,
            symbol_id=sid,
        )
        self.pins.append(pdef)
        self.symbols.append(
            SymbolDef(
                symbol_id=sid,
                circuit_id=pid,
                logical_circuit_id=self.circuit_id,
                x=x,
                y=y,
                label=name,
            )
        )
        return PinHandle(pdef.jam, name=name)

    def add_output(
        self,
        name: str,
        x: int,
        y: int,
        side: str = "Right",
        inverted: bool = False,
        pin_id: Optional[str] = None,
        symbol_id: Optional[str] = None,
    ) -> PinHandle:
        """Add an external Output pin to this circuit."""
        pid = pin_id or str(uuid.uuid4())
        sid = symbol_id or str(uuid.uuid4())
        pdef = PinDef(
            pin_id=pid,
            circuit_id=self.circuit_id,
            name=name,
            pin_type="Output",
            pin_side=side,
            inverted=inverted,
            x=x,
            y=y,
            symbol_id=sid,
        )
        self.pins.append(pdef)
        self.symbols.append(
            SymbolDef(
                symbol_id=sid,
                circuit_id=pid,
                logical_circuit_id=self.circuit_id,
                x=x,
                y=y,
                label=name,
            )
        )
        return PinHandle(pdef.jam, name=name)

    def add_gate(
        self,
        gate: GateSpec,
        x: int,
        y: int,
        label: str = "",
        symbol_id: Optional[str] = None,
    ) -> GateHandle:
        """Place a built-in LogicCircuit gate (e.g., ``Gate.AND2``, ``Gate.XOR2``, ``Gate.NOT``)."""
        sid = symbol_id or str(uuid.uuid4())
        sym = SymbolDef(
            symbol_id=sid,
            circuit_id=gate.guid,
            logical_circuit_id=self.circuit_id,
            x=x,
            y=y,
            label=label or gate.kind,
        )
        self.symbols.append(sym)
        ins = [
            PinHandle((x + dx, y + dy), name=f"{sym.label}.in[{i}]")
            for i, (dx, dy) in enumerate(gate.input_offsets())
        ]
        out_off = gate.output_offset()
        out = (
            PinHandle((x + out_off[0], y + out_off[1]), name=f"{sym.label}.out")
            if out_off is not None
            else None
        )
        return GateHandle(spec=gate, symbol=sym, inputs=ins, output=out)

    def add_clock(self, x: int, y: int, label: str = "CLK") -> PinHandle:
        """Place a built-in LogicCircuit Clock generator and return its output handle."""
        gh = self.add_gate(Gate.CLOCK, x=x, y=y, label=label)
        assert gh.out is not None
        return gh.out

    def add_subcircuit(
        self,
        subcircuit: "Circuit",
        x: int,
        y: int,
        label: str = "",
        symbol_id: Optional[str] = None,
    ) -> SubcircuitHandle:
        """Instantiate another :class:`Circuit` inside this circuit."""
        width, height, offsets = subcircuit.symbol_layout()
        sid = symbol_id or str(uuid.uuid4())
        sym = SymbolDef(
            symbol_id=sid,
            circuit_id=subcircuit.circuit_id,
            logical_circuit_id=self.circuit_id,
            x=x,
            y=y,
            label=label or subcircuit.name,
        )
        self.symbols.append(sym)
        handles = {
            pname: PinHandle((x + dx, y + dy), name=f"{sym.label}.{pname}")
            for pname, (dx, dy) in offsets.items()
        }
        return SubcircuitHandle(
            target=subcircuit, symbol=sym, pins=handles, width=width, height=height
        )

    def add_wire(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Add an explicit wire segment between ``(x1, y1)`` and ``(x2, y2)``."""
        if (x1, y1) == (x2, y2):
            return
        self.wires.append(
            WireDef(
                wire_id=str(uuid.uuid4()),
                logical_circuit_id=self.circuit_id,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )
        )

    def connect(self, *pins: PinLike, name: Optional[str] = None) -> None:
        """Declare a logical net connecting two or more pins (routed by :meth:`auto_route`)."""
        if len(pins) < 2:
            raise ValueError("connect() requires at least 2 pins.")
        pts = [_resolve_point(p) for p in pins]
        if name is None:
            self._net_counter += 1
            first_name = pins[0].name if isinstance(pins[0], PinHandle) and pins[0].name else f"net_{self._net_counter}"
            name = f"{first_name}#{self._net_counter}"
        self._nets.append((name, pts))

    # ------------------------------------------------------------------
    # Geometry, Auto-Routing & Verification
    # ------------------------------------------------------------------
    def symbol_layout(self) -> Tuple[int, int, Dict[str, Tuple[int, int]]]:
        """Return ``(width, height, {pin_name: (dx, dy)})`` when used as a subcircuit."""
        pin_dicts = [
            {
                "name": p.name,
                "pin_side": p.pin_side,
                "pin_type": p.pin_type,
                "x": p.x,
                "y": p.y,
            }
            for p in self.pins
        ]
        return compute_subcircuit_layout(pin_dicts)

    def _collect_obstacles_and_pins(self) -> Tuple[List[BoxObstacle], Dict[Point, str]]:
        pin_by_id = {p.pin_id: p for p in self.pins}
        lc_by_id = {c.circuit_id: c for c in self.project.circuits}

        obstacles: List[BoxObstacle] = []
        all_pins: Dict[Point, str] = {}

        for sym in self.symbols:
            x, y = sym.x, sym.y
            if sym.circuit_id in pin_by_id:
                pdef = pin_by_id[sym.circuit_id]
                jam = pdef.jam
                stub = (jam[0] + 1, jam[1]) if pdef.pin_type == "Input" else (jam[0] - 1, jam[1])
                all_pins[jam] = f"PIN:{pdef.name}"
                obstacles.append(BoxObstacle(x, y, 2, 2, {jam}, {jam: stub}))
            elif sym.circuit_id in lc_by_id:
                sub = lc_by_id[sym.circuit_id]
                w, h, offs = sub.symbol_layout()
                jams = set()
                stubs: Dict[Point, Point] = {}
                for pname, (dx, dy) in offs.items():
                    pt = (x + dx, y + dy)
                    jams.add(pt)
                    all_pins[pt] = f"SUB:{sym.label or sub.name}.{pname}"
                    if dx == 0:
                        stubs[pt] = (pt[0] - 1, pt[1])
                    elif dx == w:
                        stubs[pt] = (pt[0] + 1, pt[1])
                    elif dy == 0:
                        stubs[pt] = (pt[0], pt[1] - 1)
                    elif dy == h:
                        stubs[pt] = (pt[0], pt[1] + 1)
                obstacles.append(BoxObstacle(x, y, w, h, jams, stubs))
            else:
                gspec = parse_gate_guid(sym.circuit_id)
                if gspec is not None:
                    jams = set()
                    stubs = {}
                    for i, (dx, dy) in enumerate(gspec.input_offsets()):
                        pt = (x + dx, y + dy)
                        jams.add(pt)
                        stubs[pt] = (pt[0] - 1, pt[1])
                        all_pins[pt] = f"GATE_IN:{sym.label or gspec.kind}[{i}]"
                    out_off = gspec.output_offset()
                    if out_off is not None:
                        pt = (x + out_off[0], y + out_off[1])
                        jams.add(pt)
                        stubs[pt] = (pt[0] + 1, pt[1])
                        all_pins[pt] = f"GATE_OUT:{sym.label or gspec.kind}"
                    obstacles.append(BoxObstacle(x, y, gspec.width, gspec.height, jams, stubs))
        return obstacles, all_pins

    def auto_route(
        self,
        max_x: Optional[int] = None,
        max_y: Optional[int] = None,
        max_attempts: int = 25,
        bend_cost: float = 5.0,
        cross_cost: float = 3.0,
        clear_existing: bool = True,
    ) -> List[WireSegment]:
        """Auto-route all nets registered via :meth:`connect` using the orthogonal A* router."""
        obstacles, all_pins = self._collect_obstacles_and_pins()
        routed = auto_route_nets(
            obstacles=obstacles,
            all_pins=all_pins,
            nets=self._nets,
            max_x=max_x,
            max_y=max_y,
            max_attempts=max_attempts,
            bend_cost=bend_cost,
            cross_cost=cross_cost,
        )
        if clear_existing:
            self.wires.clear()
        for x1, y1, x2, y2 in routed:
            self.add_wire(x1, y1, x2, y2)
        return routed

    def verify(self, allow_diagonal: bool = False) -> VerificationResult:
        """Verify wire geometry and (if nets were declared via ``connect``) exact connectivity."""
        _, all_pins = self._collect_obstacles_and_pins()
        wire_segs = [(w.x1, w.y1, w.x2, w.y2) for w in self.wires]
        expected = self._nets if self._nets else None
        return verify_connectivity(
            wire_segs, all_pins, expected_nets=expected, allow_diagonal=allow_diagonal
        )


class Project:
    """Represents a complete LogicCircuit ``.CircuitProject`` file."""

    def __init__(
        self,
        name: str = "Project",
        project_id: Optional[str] = None,
        zoom: float = 1.0,
        frequency: int = 10,
    ) -> None:
        self.project_id = project_id or str(uuid.uuid4())
        self.name = name
        self.zoom = zoom
        self.frequency = frequency
        self.main_circuit_id: Optional[str] = None
        self.circuits: List[Circuit] = []
        self._extra_elements: Dict[str, List[ET.Element]] = {}

    def add_circuit(
        self,
        name: str,
        notation: str = "",
        circuit_shape: Optional[str] = None,
        circuit_id: Optional[str] = None,
        set_main: bool = False,
    ) -> Circuit:
        """Create and register a new :class:`Circuit` in this project."""
        c = Circuit(
            project=self,
            name=name,
            notation=notation or name,
            circuit_shape=circuit_shape,
            circuit_id=circuit_id,
        )
        self.circuits.append(c)
        if self.main_circuit_id is None or set_main:
            self.main_circuit_id = c.circuit_id
        return c

    def add_component(self, component_cls: type, *, set_main: bool = False) -> Circuit:
        """Compile a :class:`~pylogiccircuit.component.Component` subclass into this project."""
        return component_cls.compile_into(self, set_main=set_main)

    def get_circuit(self, name_or_id: str) -> Circuit:
        """Look up a circuit by name or GUID."""
        for c in self.circuits:
            if c.name == name_or_id or c.circuit_id == name_or_id:
                return c
        raise KeyError(f"Circuit {name_or_id!r} not found in project.")

    # ------------------------------------------------------------------
    # XML Serialization & Deserialization
    # ------------------------------------------------------------------
    def to_xml_tree(self) -> ET.ElementTree:
        root = ET.Element(f"{{{SCHEMA_NS}}}CircuitProject")

        main_id = self.main_circuit_id or (self.circuits[0].circuit_id if self.circuits else str(uuid.uuid4()))
        proj_attrib = {
            "ProjectId": self.project_id,
            "Name": self.name,
            "Zoom": str(self.zoom),
            "Frequency": str(self.frequency),
            "LogicalCircuitId": main_id,
        }
        ET.SubElement(root, f"{{{SCHEMA_NS}}}Project", proj_attrib)

        # Exact LogicCircuit XSD element order:
        # Project -> LogicalCircuit -> Pin -> CircuitButton -> ... -> CircuitSymbol -> Wire
        for c in self.circuits:
            attrib = {"LogicalCircuitId": c.circuit_id, "Name": c.name, "Notation": c.notation}
            if c.circuit_shape:
                attrib["CircuitShape"] = c.circuit_shape
            ET.SubElement(root, f"{{{SCHEMA_NS}}}LogicalCircuit", attrib)

        for c in self.circuits:
            for p in c.pins:
                attrib = {"PinId": p.pin_id, "CircuitId": p.circuit_id}
                if p.pin_type != "Input":
                    attrib["PinType"] = p.pin_type
                if p.pin_side != "Left":
                    attrib["PinSide"] = p.pin_side
                if p.inverted:
                    attrib["Inverted"] = "True"
                attrib["Name"] = p.name
                ET.SubElement(root, f"{{{SCHEMA_NS}}}Pin", attrib)

        for tag_name in ("CircuitButton", "Constant", "CircuitProbe", "Sensor", "Memory", "TextNote"):
            for elem in self._extra_elements.get(tag_name, []):
                root.append(elem)

        for c in self.circuits:
            for s in c.symbols:
                attrib = {
                    "CircuitSymbolId": s.symbol_id,
                    "CircuitId": s.circuit_id,
                    "LogicalCircuitId": s.logical_circuit_id,
                    "X": str(s.x),
                    "Y": str(s.y),
                }
                attrib.update(s.extra_attribs)
                ET.SubElement(root, f"{{{SCHEMA_NS}}}CircuitSymbol", attrib)

        for c in self.circuits:
            for w in c.wires:
                ET.SubElement(
                    root,
                    f"{{{SCHEMA_NS}}}Wire",
                    {
                        "WireId": w.wire_id,
                        "LogicalCircuitId": w.logical_circuit_id,
                        "X1": str(w.x1),
                        "Y1": str(w.y1),
                        "X2": str(w.x2),
                        "Y2": str(w.y2),
                    },
                )

        tree = ET.ElementTree(root)
        ET.indent(tree, space="\t")
        return tree

    def save(self, path: Union[str, Path]) -> Path:
        """Write this project as a valid LogicCircuit ``.CircuitProject`` XML file."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tree = self.to_xml_tree()
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
        return out_path

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Project":
        """Load an existing LogicCircuit ``.CircuitProject`` XML file."""
        tree = ET.parse(path)
        root = tree.getroot()

        proj = cls()
        lc_map: Dict[str, Circuit] = {}
        pin_map: Dict[str, PinDef] = {}

        for elem in root:
            tag = elem.tag.split("}")[-1]
            a = elem.attrib
            if tag == "Project":
                proj.project_id = a.get("ProjectId", proj.project_id)
                proj.name = a.get("Name", proj.name)
                proj.zoom = float(a.get("Zoom", "1.0"))
                proj.frequency = int(a.get("Frequency", "10"))
                proj.main_circuit_id = a.get("LogicalCircuitId")
            elif tag == "LogicalCircuit":
                cid = a["LogicalCircuitId"]
                c = proj.add_circuit(
                    name=a.get("Name", a.get("Notation", cid[:8])),
                    notation=a.get("Notation", a.get("Name", "")),
                    circuit_shape=a.get("CircuitShape"),
                    circuit_id=cid,
                )
                lc_map[cid] = c
            elif tag == "Pin":
                cid = a["CircuitId"]
                pdef = PinDef(
                    pin_id=a["PinId"],
                    circuit_id=cid,
                    name=a.get("Name", ""),
                    pin_type=a.get("PinType", "Input"),
                    pin_side=a.get("PinSide", "Left"),
                    inverted=a.get("Inverted", "False").lower() == "true",
                )
                pin_map[pdef.pin_id] = pdef
                if cid in lc_map:
                    lc_map[cid].pins.append(pdef)
            elif tag == "CircuitSymbol":
                lcid = a["LogicalCircuitId"]
                if lcid not in lc_map:
                    continue
                extra = {
                    k: v
                    for k, v in a.items()
                    if k not in ("CircuitSymbolId", "CircuitId", "LogicalCircuitId", "X", "Y")
                }
                sym = SymbolDef(
                    symbol_id=a["CircuitSymbolId"],
                    circuit_id=a["CircuitId"],
                    logical_circuit_id=lcid,
                    x=int(a["X"]),
                    y=int(a["Y"]),
                    extra_attribs=extra,
                )
                lc_map[lcid].symbols.append(sym)
                if sym.circuit_id in pin_map:
                    pdef = pin_map[sym.circuit_id]
                    pdef.x = sym.x
                    pdef.y = sym.y
                    pdef.symbol_id = sym.symbol_id
                    sym.label = pdef.name
            elif tag == "Wire":
                lcid = a["LogicalCircuitId"]
                if lcid not in lc_map:
                    continue
                lc_map[lcid].wires.append(
                    WireDef(
                        wire_id=a["WireId"],
                        logical_circuit_id=lcid,
                        x1=int(a["X1"]),
                        y1=int(a["Y1"]),
                        x2=int(a["X2"]),
                        y2=int(a["Y2"]),
                    )
                )
            else:
                proj._extra_elements.setdefault(tag, []).append(elem)

        return proj
