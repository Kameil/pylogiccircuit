"""Exact LogicCircuit wire connectivity and geometry verification."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

Point = Tuple[int, int]
WireSegment = Tuple[int, int, int, int]


@dataclass
class VerificationResult:
    """Result returned by :func:`verify_connectivity`."""

    ok: bool
    errors: List[str]
    net_components: Dict[Point, int]


def build_wire_graph(
    wires: Sequence[WireSegment],
    pins: Iterable[Point],
) -> Dict[Point, int]:
    """Compute exact LogicCircuit connected components over wire segments and pins.

    Matches LogicCircuit's wire-connection semantics:
    - Perpendicular crossing wires do **not** connect unless a wire endpoint or pin
      sits on the intersection point.
    - Any endpoint or pin lying along an orthogonal segment connects to that segment.
    - Overlapping collinear segments connect.
    """
    endpoints: Set[Point] = set()
    for x1, y1, x2, y2 in wires:
        endpoints.add((x1, y1))
        endpoints.add((x2, y2))

    all_nodes: Set[Point] = endpoints | set(pins)
    adj: Dict[Point, Set[Point]] = defaultdict(set)

    h_segs: Dict[int, List[Tuple[int, int, Point]]] = defaultdict(list)
    v_segs: Dict[int, List[Tuple[int, int, Point]]] = defaultdict(list)

    for x1, y1, x2, y2 in wires:
        p1, p2 = (x1, y1), (x2, y2)
        adj[p1].add(p2)
        adj[p2].add(p1)
        if x1 == x2:
            ylo, yhi = (y1, y2) if y1 <= y2 else (y2, y1)
            v_segs[x1].append((ylo, yhi, p1))
            for nd in all_nodes:
                if nd[0] == x1 and ylo <= nd[1] <= yhi:
                    adj[p1].add(nd)
                    adj[nd].add(p1)
        elif y1 == y2:
            xlo, xhi = (x1, x2) if x1 <= x2 else (x2, x1)
            h_segs[y1].append((xlo, xhi, p1))
            for nd in all_nodes:
                if nd[1] == y1 and xlo <= nd[0] <= xhi:
                    adj[p1].add(nd)
                    adj[nd].add(p1)

    for segs in h_segs.values():
        segs.sort()
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                if segs[j][0] <= segs[i][1]:
                    adj[segs[i][2]].add(segs[j][2])
                    adj[segs[j][2]].add(segs[i][2])
                else:
                    break

    for segs in v_segs.values():
        segs.sort()
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                if segs[j][0] <= segs[i][1]:
                    adj[segs[i][2]].add(segs[j][2])
                    adj[segs[j][2]].add(segs[i][2])
                else:
                    break

    comp_id: Dict[Point, int] = {}
    counter = 0
    for nd in all_nodes:
        if nd in comp_id:
            continue
        counter += 1
        stack = [nd]
        comp_id[nd] = counter
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in comp_id:
                    comp_id[v] = counter
                    stack.append(v)

    return comp_id


def verify_connectivity(
    wires: Sequence[WireSegment],
    all_pins: Dict[Point, str],
    expected_nets: Optional[Sequence[Tuple[str, Sequence[Point]]]] = None,
    allow_diagonal: bool = False,
) -> VerificationResult:
    """Verify wire geometry and optionally assert exact net connectivity.

    Checks:
    1. No diagonal wires (unless ``allow_diagonal=True``).
    2. If ``expected_nets`` is provided:
       - Every net's pins belong to a single connected component.
       - No two distinct nets are shorted together.
       - No unassigned pin is accidentally shorted to any expected net.
    """
    errors: List[str] = []
    if not allow_diagonal:
        for idx, (x1, y1, x2, y2) in enumerate(wires):
            if x1 != x2 and y1 != y2:
                errors.append(f"Wire #{idx} ({x1},{y1})->({x2},{y2}) is diagonal.")

    comp_id = build_wire_graph(wires, all_pins.keys())

    if expected_nets is not None:
        seen_comps: Dict[int, str] = {}
        expected_pins: Set[Point] = set()
        for net_name, pts in expected_nets:
            if not pts:
                continue
            expected_pins.update(pts)
            missing = [p for p in pts if p not in comp_id]
            if missing:
                errors.append(f"Net '{net_name}' references unknown pin(s): {missing}")
                continue
            cids = {comp_id[p] for p in pts}
            if len(cids) != 1:
                errors.append(
                    f"Net '{net_name}' is split across {len(cids)} disconnected components."
                )
                continue
            cid = next(iter(cids))
            if cid in seen_comps:
                errors.append(f"Short circuit between '{seen_comps[cid]}' and '{net_name}'.")
            else:
                seen_comps[cid] = net_name

        for pt, desc in all_pins.items():
            if pt not in expected_pins and pt in comp_id and comp_id[pt] in seen_comps:
                errors.append(
                    f"Unassigned pin {desc} at {pt} is shorted to net '{seen_comps[comp_id[pt]]}'."
                )

    return VerificationResult(ok=len(errors) == 0, errors=errors, net_components=comp_id)
