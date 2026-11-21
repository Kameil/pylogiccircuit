"""pylogiccircuit — Programmatically build, auto-route, verify, and simulate LogicCircuit files."""

from . import stdlib
from .component import Component, Input, Output
from .gates import Gate, GateSpec, SCHEMA_NS, compute_subcircuit_layout, parse_gate_guid
from .preview import render_circuit_png
from .project import (
    Circuit,
    GateHandle,
    PinDef,
    PinHandle,
    Project,
    SubcircuitHandle,
    SymbolDef,
    WireDef,
)
from .router import BoxObstacle, OrthogonalRouter, RoutingError, auto_route_nets
from .simulator import Simulator, TruthTableResult
from .verifier import VerificationResult, build_wire_graph, verify_connectivity
from .watch import RenderSnapshot, load_project_from_source, render_once, watch_file

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "BoxObstacle",
    "Circuit",
    "Component",
    "Gate",
    "GateHandle",
    "GateSpec",
    "Input",
    "OrthogonalRouter",
    "Output",
    "PinDef",
    "PinHandle",
    "Project",
    "RenderSnapshot",
    "RoutingError",
    "SCHEMA_NS",
    "Simulator",
    "SubcircuitHandle",
    "SymbolDef",
    "TruthTableResult",
    "VerificationResult",
    "WireDef",
    "auto_route_nets",
    "build_wire_graph",
    "compute_subcircuit_layout",
    "load_project_from_source",
    "parse_gate_guid",
    "render_circuit_png",
    "render_once",
    "stdlib",
    "verify_connectivity",
    "watch_file",
]
