"""Declarative class-based circuit components with typed pin autocomplete."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Type, TypeVar, Union, overload

from .gates import GateSpec
from .preview import render_circuit_png
from .project import Circuit, GateHandle, PinHandle, PinLike, Project, SubcircuitHandle
from .simulator import Simulator, TruthTableResult

T = TypeVar("T", bound="Component")


class _PinDescriptor:
    """Descriptor declaring a typed Input or Output pin on a :class:`Component` subclass."""

    pin_type: str = "Input"
    default_side: str = "Left"

    def __init__(
        self,
        x: int,
        y: int,
        *,
        side: Optional[str] = None,
        name: Optional[str] = None,
        inverted: bool = False,
    ) -> None:
        self.x = x
        self.y = y
        self.side = side or self.default_side
        self.explicit_name = name
        self.inverted = inverted
        self.attr_name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.attr_name = name

    @property
    def pin_name(self) -> str:
        return self.explicit_name or self.attr_name

    @overload
    def __get__(self, obj: None, objtype: Optional[type] = None) -> "_PinDescriptor": ...

    @overload
    def __get__(self, obj: "Component", objtype: Optional[type] = None) -> PinHandle: ...

    def __get__(
        self, obj: Optional["Component"], objtype: Optional[type] = None
    ) -> Union["_PinDescriptor", PinHandle]:
        if obj is None:
            return self
        return obj._pin_handles[self.attr_name]


class Input(_PinDescriptor):
    """Declare a typed Input pin on a :class:`Component` subclass."""

    pin_type = "Input"
    default_side = "Left"


class Output(_PinDescriptor):
    """Declare a typed Output pin on a :class:`Component` subclass."""

    pin_type = "Output"
    default_side = "Right"


class Component:
    """Base class for reusable, typed, declarative LogicCircuit subcircuits."""

    circuit_name: Optional[str] = None
    notation: Optional[str] = None
    circuit_shape: Optional[str] = None
    route_max_x: Optional[int] = None
    route_max_y: Optional[int] = None
    route_max_attempts: int = 25

    def __init__(self) -> None:
        self._project: Optional[Project] = None
        self._circuit: Optional[Circuit] = None
        self._pin_handles: Dict[str, PinHandle] = {}
        self._sub_handle: Optional[SubcircuitHandle] = None

    @classmethod
    def _pin_descriptors(cls) -> Dict[str, _PinDescriptor]:
        descs: Dict[str, _PinDescriptor] = {}
        for base in reversed(cls.__mro__):
            for attr, val in base.__dict__.items():
                if isinstance(val, _PinDescriptor):
                    descs[attr] = val
        return descs

    @classmethod
    def get_circuit_name(cls) -> str:
        return cls.circuit_name or cls.__name__

    @classmethod
    def get_notation(cls) -> str:
        return cls.notation or cls.get_circuit_name()

    @classmethod
    def compile_into(cls, project: Project, *, set_main: bool = False) -> Circuit:
        """Build (or reuse cached) :class:`Circuit` definition for this component inside ``project``."""
        cache: Dict[type, Circuit] = getattr(project, "_component_cache", None)
        if cache is None:
            cache = {}
            setattr(project, "_component_cache", cache)

        if cls in cache:
            circuit = cache[cls]
            if set_main:
                project.main_circuit_id = circuit.circuit_id
            return circuit

        inst = cls()
        circuit = project.add_circuit(
            name=cls.get_circuit_name(),
            notation=cls.get_notation(),
            circuit_shape=cls.circuit_shape,
            set_main=set_main,
        )
        cache[cls] = circuit
        inst._project = project
        inst._circuit = circuit

        for attr, desc in cls._pin_descriptors().items():
            if desc.pin_type == "Input":
                handle = circuit.add_input(
                    desc.pin_name,
                    x=desc.x,
                    y=desc.y,
                    side=desc.side,
                    inverted=desc.inverted,
                )
            else:
                handle = circuit.add_output(
                    desc.pin_name,
                    x=desc.x,
                    y=desc.y,
                    side=desc.side,
                    inverted=desc.inverted,
                )
            inst._pin_handles[attr] = handle

        inst.build()

        if circuit._nets and not circuit.wires:
            circuit.auto_route(
                max_x=cls.route_max_x,
                max_y=cls.route_max_y,
                max_attempts=cls.route_max_attempts,
            )

        return circuit

    def build(self) -> None:
        """Override in subclasses to place gates/subcircuits and connect nets."""
        raise NotImplementedError(f"{type(self).__name__}.build() must be implemented.")

    @property
    def circuit(self) -> Circuit:
        assert self._circuit is not None, "Component is not attached to a Circuit."
        return self._circuit

    @property
    def project(self) -> Project:
        assert self._project is not None, "Component is not attached to a Project."
        return self._project

    def gate(self, gate: GateSpec, x: int, y: int, label: str = "") -> GateHandle:
        return self.circuit.add_gate(gate, x=x, y=y, label=label)

    def clock(self, x: int, y: int, label: str = "CLK") -> PinHandle:
        return self.circuit.add_clock(x=x, y=y, label=label)

    def input(
        self,
        name: str,
        x: int,
        y: int,
        *,
        side: str = "Left",
        inverted: bool = False,
    ) -> PinHandle:
        return self.circuit.add_input(name, x=x, y=y, side=side, inverted=inverted)

    def output(
        self,
        name: str,
        x: int,
        y: int,
        *,
        side: str = "Right",
        inverted: bool = False,
    ) -> PinHandle:
        return self.circuit.add_output(name, x=x, y=y, side=side, inverted=inverted)

    def use(self, component_cls: Type[T], x: int, y: int, label: str = "") -> T:
        """Instantiate another :class:`Component` as a typed subcircuit with pin autocomplete."""
        sub_circuit = component_cls.compile_into(self.project, set_main=False)
        sub_handle = self.circuit.add_subcircuit(
            sub_circuit, x=x, y=y, label=label or component_cls.get_notation()
        )
        proxy = component_cls()
        proxy._project = self.project
        proxy._circuit = sub_circuit
        proxy._sub_handle = sub_handle
        for attr, desc in component_cls._pin_descriptors().items():
            proxy._pin_handles[attr] = sub_handle[desc.pin_name]
        return proxy

    def connect(self, *pins: PinLike, name: Optional[str] = None) -> None:
        self.circuit.connect(*pins, name=name)

    def wire(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.circuit.add_wire(x1, y1, x2, y2)

    def __getitem__(self, pin_name: str) -> PinHandle:
        if self._sub_handle is not None:
            return self._sub_handle[pin_name]
        for attr, desc in type(self)._pin_descriptors().items():
            if desc.pin_name == pin_name or attr == pin_name:
                return self._pin_handles[attr]
        raise KeyError(f"Pin {pin_name!r} not found on {type(self).__name__}.")

    @classmethod
    def to_project(cls, project_name: Optional[str] = None) -> Project:
        """Compile this component (and all nested dependencies) into a standalone :class:`Project`."""
        proj = Project(project_name or cls.get_circuit_name())
        cls.compile_into(proj, set_main=True)
        return proj

    @classmethod
    def save(cls, path: Union[str, Path], project_name: Optional[str] = None) -> Path:
        """Compile and save directly to a ``.CircuitProject`` file."""
        return cls.to_project(project_name).save(path)

    @classmethod
    def render(
        cls,
        output_path: Union[str, Path],
        scale: int = 16,
        *,
        title: Optional[str] = None,
    ) -> Path:
        """Compile and render directly to a PNG schematic preview."""
        proj = cls.to_project()
        return render_circuit_png(
            proj.get_circuit(cls.get_circuit_name()), output_path, scale=scale, title=title
        )

    @classmethod
    def simulate(cls) -> Simulator:
        """Compile and return a :class:`Simulator` ready to evaluate this component."""
        return Simulator.from_project(cls.to_project())

    @classmethod
    def truth_table(cls, max_rows: Optional[int] = None) -> TruthTableResult:
        """Compile and run the LogicCircuit truth table for this component."""
        return cls.simulate().truth_table(cls.get_circuit_name(), max_rows=max_rows)
