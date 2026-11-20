"""Exact LogicCircuit FIFO-queue circuit simulator and truth-table generator."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .gates import Gate, GateSpec, parse_gate_guid
from .project import Circuit, PinDef, Project
from .verifier import Point, build_wire_graph


@dataclass
class _CompiledGate:
    spec: GateSpec
    in_nets: List[int]
    out_net: int


@dataclass
class _CompiledCircuit:
    input_pins: List[PinDef]
    output_pins: List[PinDef]
    in_net_map: Dict[str, int]
    out_net_map: Dict[str, int]
    gates: List[_CompiledGate]
    clock_nets: List[int]
    num_nets: int
    fanout: List[List[int]]


@dataclass
class TruthTableResult:
    """Result of running a LogicCircuit-compatible truth table sweep."""

    circuit_name: str
    input_names: List[str]
    output_names: List[str]
    rows: List[Tuple[List[int], List[int]]]
    oscillated: bool = False
    oscillation_row: Optional[int] = None
    has_internal_clocks: bool = False

    def format_markdown(self) -> str:
        """Render the truth table as a GitHub-flavored Markdown table."""
        cols = self.input_names + self.output_names
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join(":-:" for _ in cols) + " |",
        ]
        for iv, ov in self.rows:
            vals = [str(x) for x in iv] + [str(x) for x in ov]
            lines.append("| " + " | ".join(vals) + " |")
        if self.oscillated:
            lines.append(f"\nOscillation detected at row {self.oscillation_row}.")
        return "\n".join(lines)


class Simulator:
    """Flattens hierarchical LogicCircuit projects and simulates them with exact FIFO semantics."""

    def __init__(self, project: Project) -> None:
        self.project = project
        self._compiled_cache: Dict[str, _CompiledCircuit] = {}

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Simulator":
        return cls(Project.load(path))

    @classmethod
    def from_project(cls, project: Project) -> "Simulator":
        return cls(project)

    # ------------------------------------------------------------------
    # Compilation (hierarchical flattening)
    # ------------------------------------------------------------------
    def _compile(self, circuit: Circuit) -> _CompiledCircuit:
        if circuit.circuit_id in self._compiled_cache:
            return self._compiled_cache[circuit.circuit_id]

        next_net_id = 0
        gates: List[_CompiledGate] = []
        clock_nets: List[int] = []

        # Union-find across all flattened net IDs so subcircuit boundary pins merge cleanly
        parent: List[int] = []

        def new_net() -> int:
            nonlocal next_net_id
            nid = next_net_id
            next_net_id += 1
            parent.append(nid)
            return nid

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        def instantiate(c: Circuit) -> Tuple[Dict[str, int], Dict[str, int]]:
            pin_by_id = {p.pin_id: p for p in c.pins}
            lc_by_id = {lc.circuit_id: lc for lc in self.project.circuits}

            # Gather all pin coordinates inside `c`
            pin_points: List[Point] = []
            for s in c.symbols:
                if s.circuit_id in pin_by_id:
                    pin_points.append(pin_by_id[s.circuit_id].jam)
                elif s.circuit_id in lc_by_id:
                    _, _, offs = lc_by_id[s.circuit_id].symbol_layout()
                    for dx, dy in offs.values():
                        pin_points.append((s.x + dx, s.y + dy))
                else:
                    gspec = parse_gate_guid(s.circuit_id)
                    if gspec is not None:
                        for dx, dy in gspec.input_offsets():
                            pin_points.append((s.x + dx, s.y + dy))
                        out_off = gspec.output_offset()
                        if out_off is not None:
                            pin_points.append((s.x + out_off[0], s.y + out_off[1]))

            wire_segs = [(w.x1, w.y1, w.x2, w.y2) for w in c.wires]
            comp_map = build_wire_graph(wire_segs, pin_points)
            comp_to_net: Dict[int, int] = {}

            def net_at(pt: Point) -> int:
                cid = comp_map.get(pt)
                if cid is None:
                    return new_net()
                if cid not in comp_to_net:
                    comp_to_net[cid] = new_net()
                return comp_to_net[cid]

            in_map: Dict[str, int] = {}
            out_map: Dict[str, int] = {}

            for s in c.symbols:
                if s.circuit_id in pin_by_id:
                    pdef = pin_by_id[s.circuit_id]
                    nid = net_at(pdef.jam)
                    if pdef.pin_type == "Input":
                        in_map[pdef.name] = nid
                    else:
                        out_map[pdef.name] = nid
                elif s.circuit_id in lc_by_id:
                    sub = lc_by_id[s.circuit_id]
                    _, _, offs = sub.symbol_layout()
                    sub_in, sub_out = instantiate(sub)
                    sub_pins = {p.name: p for p in sub.pins}
                    for pname, (dx, dy) in offs.items():
                        ext_net = net_at((s.x + dx, s.y + dy))
                        pdef = sub_pins[pname]
                        if pdef.pin_type == "Input" and pname in sub_in:
                            if pdef.inverted:
                                gates.append(_CompiledGate(Gate.NOT, [ext_net], sub_in[pname]))
                            else:
                                union(ext_net, sub_in[pname])
                        elif pdef.pin_type == "Output" and pname in sub_out:
                            if pdef.inverted:
                                gates.append(_CompiledGate(Gate.NOT, [sub_out[pname]], ext_net))
                            else:
                                union(ext_net, sub_out[pname])
                else:
                    gspec = parse_gate_guid(s.circuit_id)
                    if gspec is None:
                        continue
                    if gspec.kind == "CLOCK":
                        out_off = gspec.output_offset()
                        assert out_off is not None
                        clock_nets.append(net_at((s.x + out_off[0], s.y + out_off[1])))
                    elif gspec.kind == "LED":
                        continue
                    else:
                        in_nets = [net_at((s.x + dx, s.y + dy)) for dx, dy in gspec.input_offsets()]
                        out_off = gspec.output_offset()
                        assert out_off is not None
                        out_net = net_at((s.x + out_off[0], s.y + out_off[1]))
                        gates.append(_CompiledGate(gspec, in_nets, out_net))

            return in_map, out_map

        raw_in, raw_out = instantiate(circuit)

        # Compact canonical net IDs after union-find
        canon_map: Dict[int, int] = {}

        def canon(nid: int) -> int:
            r = find(nid)
            if r not in canon_map:
                canon_map[r] = len(canon_map)
            return canon_map[r]

        final_in = {k: canon(v) for k, v in raw_in.items()}
        final_out = {k: canon(v) for k, v in raw_out.items()}
        final_clocks = [canon(v) for v in clock_nets]
        final_gates = [
            _CompiledGate(g.spec, [canon(n) for n in g.in_nets], canon(g.out_net))
            for g in gates
        ]
        num_nets = len(canon_map)
        fanout: List[List[int]] = [[] for _ in range(num_nets)]
        for gidx, g in enumerate(final_gates):
            for n in g.in_nets:
                fanout[n].append(gidx)

        # LogicCircuit PinComparer ordering for truth table columns:
        # Left pins top-to-bottom (Y then X), then Top/Bottom/Right
        side_rank = {"Left": 0, "Top": 1, "Bottom": 2, "Right": 3}

        def pin_sort_key(p: PinDef) -> Tuple[int, int, int, str]:
            if p.pin_side in ("Top", "Bottom"):
                return (side_rank.get(p.pin_side, 9), p.x, p.y, p.name)
            return (side_rank.get(p.pin_side, 9), p.y, p.x, p.name)

        input_pins = sorted([p for p in circuit.pins if p.pin_type == "Input"], key=pin_sort_key)
        output_pins = sorted([p for p in circuit.pins if p.pin_type == "Output"], key=pin_sort_key)

        compiled = _CompiledCircuit(
            input_pins=input_pins,
            output_pins=output_pins,
            in_net_map=final_in,
            out_net_map=final_out,
            gates=final_gates,
            clock_nets=final_clocks,
            num_nets=num_nets,
            fanout=fanout,
        )
        self._compiled_cache[circuit.circuit_id] = compiled
        return compiled

    # ------------------------------------------------------------------
    # FIFO Evaluation Engine (matching LogicCircuit's CircuitState.Evaluate)
    # ------------------------------------------------------------------
    @staticmethod
    def _eval_fifo(
        cc: _CompiledCircuit,
        net_state: List[int],
        initial_dirty: List[int],
        max_steps: int = 2000,
    ) -> bool:
        queue = deque(initial_dirty)
        in_queue = set(initial_dirty)
        steps = 0
        while queue:
            steps += 1
            if steps > max_steps:
                return False
            gidx = queue.popleft()
            in_queue.discard(gidx)
            g = cc.gates[gidx]
            new_val = g.spec.eval_bits([net_state[n] for n in g.in_nets])
            if new_val != net_state[g.out_net]:
                net_state[g.out_net] = new_val
                for dep in cc.fanout[g.out_net]:
                    if dep not in in_queue:
                        in_queue.add(dep)
                        queue.append(dep)
        return True

    def evaluate(
        self,
        circuit_name: str,
        inputs: Dict[str, int],
        max_steps: int = 2000,
    ) -> Dict[str, int]:
        """Evaluate a combinational circuit on one input assignment.

        Raises ``RuntimeError`` if the circuit oscillates.
        """
        circuit = self.project.get_circuit(circuit_name)
        cc = self._compile(circuit)
        net_state = [0] * cc.num_nets

        for p in cc.input_pins:
            val = int(inputs.get(p.name, 0)) & 1
            if p.inverted:
                val ^= 1
            net_state[cc.in_net_map[p.name]] = val

        ok = self._eval_fifo(cc, net_state, list(range(len(cc.gates))), max_steps=max_steps)
        if not ok:
            raise RuntimeError(f"Circuit {circuit_name!r} oscillated for inputs {inputs}.")

        result: Dict[str, int] = {}
        for p in cc.output_pins:
            val = net_state[cc.out_net_map[p.name]]
            if p.inverted:
                val ^= 1
            result[p.name] = val
        return result

    def truth_table(
        self,
        circuit_name: str,
        max_rows: Optional[int] = None,
        max_steps: int = 2000,
    ) -> TruthTableResult:
        """Run LogicCircuit's exact sequential truth-table sweep (0 .. 2^N - 1)."""
        circuit = self.project.get_circuit(circuit_name)
        cc = self._compile(circuit)
        n_in = len(cc.input_pins)
        total_rows = 1 << n_in
        if max_rows is not None:
            total_rows = min(total_rows, max_rows)

        net_state = [0] * cc.num_nets
        # Initial power-up stabilization
        if not self._eval_fifo(cc, net_state, list(range(len(cc.gates))), max_steps=max_steps):
            return TruthTableResult(
                circuit_name=circuit.name,
                input_names=[p.name for p in cc.input_pins],
                output_names=[p.name for p in cc.output_pins],
                rows=[],
                oscillated=True,
                oscillation_row=-1,
                has_internal_clocks=bool(cc.clock_nets),
            )

        rows: List[Tuple[List[int], List[int]]] = []
        clock_val = 0

        for row in range(total_rows):
            dirty: List[int] = []
            dirty_set = set()
            iv: List[int] = []

            for bit_idx, p in enumerate(cc.input_pins):
                bit = (row >> (n_in - 1 - bit_idx)) & 1
                iv.append(bit)
                eff = (bit ^ 1) if p.inverted else bit
                nid = cc.in_net_map[p.name]
                if net_state[nid] != eff:
                    net_state[nid] = eff
                    for dep in cc.fanout[nid]:
                        if dep not in dirty_set:
                            dirty_set.add(dep)
                            dirty.append(dep)

            # LogicCircuit toggles internal Clock symbols once per row during TruthTable evaluation
            if cc.clock_nets:
                clock_val ^= 1
                for cn in cc.clock_nets:
                    if net_state[cn] != clock_val:
                        net_state[cn] = clock_val
                        for dep in cc.fanout[cn]:
                            if dep not in dirty_set:
                                dirty_set.add(dep)
                                dirty.append(dep)

            if dirty and not self._eval_fifo(cc, net_state, dirty, max_steps=max_steps):
                return TruthTableResult(
                    circuit_name=circuit.name,
                    input_names=[p.name for p in cc.input_pins],
                    output_names=[p.name for p in cc.output_pins],
                    rows=rows,
                    oscillated=True,
                    oscillation_row=row,
                    has_internal_clocks=bool(cc.clock_nets),
                )

            ov: List[int] = []
            for p in cc.output_pins:
                val = net_state[cc.out_net_map[p.name]]
                if p.inverted:
                    val ^= 1
                ov.append(val)
            rows.append((iv, ov))

        return TruthTableResult(
            circuit_name=circuit.name,
            input_names=[p.name for p in cc.input_pins],
            output_names=[p.name for p in cc.output_pins],
            rows=rows,
            oscillated=False,
            oscillation_row=None,
            has_internal_clocks=bool(cc.clock_nets),
        )
