"""Orthogonal A* schematic router tailored to LogicCircuit's grid rules."""

from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .verifier import Point, WireSegment, verify_connectivity


@dataclass
class BoxObstacle:
    """Grid bounding box ``[x, x+w] x [y, y+h]`` of a placed symbol and its pins."""

    x: int
    y: int
    w: int
    h: int
    pins: Set[Point]
    pin_stubs: Dict[Point, Point]


class RoutingError(RuntimeError):
    """Raised when the auto-router cannot route all nets within the grid bounds."""


class OrthogonalRouter:
    """Grid-based orthogonal schematic router for LogicCircuit.

    Key guarantees:
    - Never passes through symbol interiors or pins of another net.
    - Reserves 1-unit perpendicular exit stubs + escape guards on every pin so
      closely-packed multi-pin blocks (e.g., 4-bit adders or 8:1 MUXes) cannot be
      sealed off by earlier nets.
    - Allows clean perpendicular crossings between distinct nets (which do not
      connect in LogicCircuit) while preventing illegal corners/T-junctions on
      another net's wire.
    - Splits emitted collinear runs at same-net junctions so LogicCircuit always
      registers T-junctions and 4-way same-net intersections properly.
    """

    def __init__(
        self,
        obstacles: Sequence[BoxObstacle],
        max_x: int,
        max_y: int,
        bend_cost: float = 5.0,
        cross_cost: float = 3.0,
    ) -> None:
        self.max_x = max_x
        self.max_y = max_y
        self.bend_cost = bend_cost
        self.cross_cost = cross_cost

        self.blocked_body: Set[Point] = set()
        self.all_pins: Set[Point] = set()
        self.pin_stub_target: Dict[Point, Point] = {}
        self.pin_owner: Dict[Point, str] = {}
        self.pin_halo: Dict[Point, Set[str]] = defaultdict(set)
        self.escape_guard: Dict[Point, Tuple[str, int]] = {}

        for obs in obstacles:
            self.all_pins.update(obs.pins)
            self.pin_stub_target.update(obs.pin_stubs)
            for bx in range(obs.x, obs.x + obs.w + 1):
                for by in range(obs.y, obs.y + obs.h + 1):
                    if (bx, by) not in obs.pins:
                        self.blocked_body.add((bx, by))

        self.h_edge: Dict[Point, str] = {}
        self.v_edge: Dict[Point, str] = {}
        self.node_net: Dict[Point, str] = {}
        self.net_edges: Dict[str, Set[Tuple[str, int, int]]] = defaultdict(set)
        self.net_nodes: Dict[str, Set[Point]] = defaultdict(set)

    def register_nets(self, nets: Sequence[Tuple[str, Sequence[Point]]]) -> None:
        for name, pts in nets:
            for pt in pts:
                if pt in self.pin_owner and self.pin_owner[pt] != name:
                    raise RoutingError(
                        f"Pin {pt} assigned to multiple nets: {self.pin_owner[pt]!r} and {name!r}"
                    )
                self.pin_owner[pt] = name
                self.node_net[pt] = name
                self.net_nodes[name].add(pt)

                ex = self.pin_stub_target.get(pt)
                if ex is not None and ex not in self.blocked_body and ex not in self.all_pins:
                    if pt[0] == ex[0]:
                        ey = min(pt[1], ex[1])
                        self.v_edge[(pt[0], ey)] = name
                        self.net_edges[name].add(("V", pt[0], ey))
                    else:
                        ex0 = min(pt[0], ex[0])
                        self.h_edge[(ex0, pt[1])] = name
                        self.net_edges[name].add(("H", ex0, pt[1]))
                    self.node_net[ex] = name
                    self.net_nodes[name].add(ex)

                    gdx, gdy = ex[0] - pt[0], ex[1] - pt[1]
                    guard = (ex[0] + gdx, ex[1] + gdy)
                    axis = 0 if gdy == 0 else 1
                    if (
                        guard not in self.blocked_body
                        and guard not in self.all_pins
                        and guard not in self.escape_guard
                    ):
                        self.escape_guard[guard] = (name, axis)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        self.pin_halo[(ex[0] + dx, ex[1] + dy)].add(name)

                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    self.pin_halo[(pt[0] + dx, pt[1] + dy)].add(name)

    def _node_has_other_h(self, x: int, y: int, net: str) -> bool:
        e1 = self.h_edge.get((x - 1, y))
        e2 = self.h_edge.get((x, y))
        return (e1 is not None and e1 != net) or (e2 is not None and e2 != net)

    def _node_has_other_v(self, x: int, y: int, net: str) -> bool:
        e1 = self.v_edge.get((x, y - 1))
        e2 = self.v_edge.get((x, y))
        return (e1 is not None and e1 != net) or (e2 is not None and e2 != net)

    def _can_use_edge(self, x1: int, y1: int, x2: int, y2: int, net: str) -> bool:
        if x1 == x2:
            o = self.v_edge.get((x1, min(y1, y2)))
            return o is None or o == net
        o = self.h_edge.get((min(x1, x2), y1))
        return o is None or o == net

    def _can_be_terminal_or_corner(self, x: int, y: int, net: str) -> bool:
        if (x, y) in self.blocked_body:
            return False
        po = self.pin_owner.get((x, y))
        if po is not None and po != net:
            return False
        if (x, y) in self.all_pins and po != net:
            return False
        eg = self.escape_guard.get((x, y))
        if eg is not None and eg[0] != net:
            return False
        nn = self.node_net.get((x, y))
        if nn is not None and nn != net:
            return False
        if self._node_has_other_h(x, y, net) or self._node_has_other_v(x, y, net):
            return False
        return True

    def _can_pass_through(self, x: int, y: int, dir_idx: int, net: str) -> bool:
        if (x, y) in self.blocked_body:
            return False
        po = self.pin_owner.get((x, y))
        if po is not None and po != net:
            return False
        if (x, y) in self.all_pins and po != net:
            return False
        eg = self.escape_guard.get((x, y))
        if eg is not None and eg[0] != net and eg[1] == dir_idx:
            return False
        nn = self.node_net.get((x, y))
        if nn is not None and nn != net:
            return False
        if dir_idx == 0 and self._node_has_other_h(x, y, net):
            return False
        if dir_idx == 1 and self._node_has_other_v(x, y, net):
            return False
        return True

    def route_net(self, net: str, pts: Sequence[Point]) -> bool:
        if len(pts) < 2:
            return True
        tips = [
            self.pin_stub_target[p]
            if p in self.pin_stub_target and self.pin_stub_target[p] in self.net_nodes[net]
            else p
            for p in pts
        ]
        tree_nodes: Set[Point] = {tips[0]}
        remaining = list(tips[1:])
        while remaining:
            best_t = min(
                remaining,
                key=lambda t: min(abs(t[0] - s[0]) + abs(t[1] - s[1]) for s in tree_nodes),
            )
            remaining.remove(best_t)
            if best_t in tree_nodes:
                continue
            path = self._astar(net, tree_nodes, best_t)
            if path is None:
                return False
            self._commit_path(net, path)
            tree_nodes.update(path)
        return True

    def _astar(self, net: str, sources: Set[Point], target: Point) -> Optional[List[Point]]:
        tx, ty = target
        pq: List[Tuple[float, float, int, int, int]] = []
        dist: Dict[Tuple[int, int, int], float] = {}
        parent: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}

        for sx, sy in sources:
            if not self._can_be_terminal_or_corner(sx, sy, net):
                continue
            st = (sx, sy, 2)
            dist[st] = 0.0
            heapq.heappush(pq, (float(abs(sx - tx) + abs(sy - ty)), 0.0, sx, sy, 2))

        dirs = ((1, 0, 0), (-1, 0, 0), (0, 1, 1), (0, -1, 1))
        while pq:
            _, g, x, y, d = heapq.heappop(pq)
            if g > dist.get((x, y, d), 1e18):
                continue
            if (x, y) == target:
                path: List[Point] = []
                cur: Optional[Tuple[int, int, int]] = (x, y, d)
                while cur is not None:
                    path.append((cur[0], cur[1]))
                    cur = parent.get(cur)
                path.reverse()
                return path

            for dx, dy, nd in dirs:
                nx, ny = x + dx, y + dy
                if nx < 1 or nx > self.max_x or ny < 1 or ny > self.max_y:
                    continue
                if not self._can_use_edge(x, y, nx, ny, net):
                    continue
                if d != 2 and d != nd and not self._can_be_terminal_or_corner(x, y, net):
                    continue
                if (nx, ny) == target:
                    if not self._can_be_terminal_or_corner(nx, ny, net):
                        continue
                elif not self._can_pass_through(nx, ny, nd, net):
                    continue

                step = 1.0
                if nd == 0 and self.h_edge.get((min(x, nx), y)) == net:
                    step = 0.15
                elif nd == 1 and self.v_edge.get((x, min(y, ny))) == net:
                    step = 0.15
                else:
                    if d != 2 and d != nd:
                        step += self.bend_cost
                    if nd == 0 and self._node_has_other_v(nx, ny, net):
                        step += self.cross_cost
                    elif nd == 1 and self._node_has_other_h(nx, ny, net):
                        step += self.cross_cost
                    halo = self.pin_halo.get((nx, ny))
                    if halo and (len(halo) > 1 or net not in halo):
                        step += 4.0 if (d != 2 and d != nd) else 1.5

                ng = g + step
                nst = (nx, ny, nd)
                if ng < dist.get(nst, 1e18):
                    dist[nst] = ng
                    parent[nst] = (x, y, d)
                    heapq.heappush(pq, (ng + abs(nx - tx) + abs(ny - ty), ng, nx, ny, nd))
        return None

    def _commit_path(self, net: str, path: Sequence[Point]) -> None:
        self.node_net[path[0]] = net
        self.node_net[path[-1]] = net
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]
            if x1 == x2:
                ey = min(y1, y2)
                self.v_edge[(x1, ey)] = net
                self.net_edges[net].add(("V", x1, ey))
            else:
                ex = min(x1, x2)
                self.h_edge[(ex, y1)] = net
                self.net_edges[net].add(("H", ex, y1))
            if i > 0:
                px, py = path[i - 1]
                if (x1 - px) != (x2 - x1) or (y1 - py) != (y2 - y1):
                    self.node_net[(x1, y1)] = net
            self.net_nodes[net].add((x1, y1))
            self.net_nodes[net].add((x2, y2))

        for px, py in path:
            deg = (
                int(self.h_edge.get((px - 1, py)) == net)
                + int(self.h_edge.get((px, py)) == net)
                + int(self.v_edge.get((px, py - 1)) == net)
                + int(self.v_edge.get((px, py)) == net)
            )
            if deg != 2:
                self.node_net[(px, py)] = net

    def emit_wires(self) -> List[WireSegment]:
        """Merge adjacent unit edges into maximal straight segments, split at same-net junctions."""
        wires: List[WireSegment] = []
        for net, edges in self.net_edges.items():
            h_by_y: Dict[int, List[int]] = defaultdict(list)
            v_by_x: Dict[int, List[int]] = defaultdict(list)
            for kind, x, y in edges:
                if kind == "H":
                    h_by_y[y].append(x)
                else:
                    v_by_x[x].append(y)

            for y, xs in h_by_y.items():
                xs.sort()
                start = prev = xs[0]
                for x in xs[1:]:
                    has_v = (
                        self.v_edge.get((x, y - 1)) == net
                        or self.v_edge.get((x, y)) == net
                    )
                    if x == prev + 1 and not has_v:
                        prev = x
                    else:
                        wires.append((start, y, prev + 1, y))
                        start = prev = x
                wires.append((start, y, prev + 1, y))

            for x, ys in v_by_x.items():
                ys.sort()
                start = prev = ys[0]
                for y in ys[1:]:
                    has_h = (
                        self.h_edge.get((x - 1, y)) == net
                        or self.h_edge.get((x, y)) == net
                    )
                    if y == prev + 1 and not has_h:
                        prev = y
                    else:
                        wires.append((x, start, x, prev + 1))
                        start = prev = y
                wires.append((x, start, x, prev + 1))
        return wires


def auto_route_nets(
    obstacles: Sequence[BoxObstacle],
    all_pins: Dict[Point, str],
    nets: Sequence[Tuple[str, Sequence[Point]]],
    max_x: Optional[int] = None,
    max_y: Optional[int] = None,
    max_attempts: int = 25,
    bend_cost: float = 5.0,
    cross_cost: float = 3.0,
) -> List[WireSegment]:
    """Route all ``nets`` with automatic rip-up-and-reroute and exact verification."""
    if not nets:
        return []

    if max_x is None:
        max_x = max((o.x + o.w for o in obstacles), default=10) + 6
    if max_y is None:
        max_y = max((o.y + o.h for o in obstacles), default=10) + 6

    ordered = list(nets)
    last_failed = ""
    for _ in range(max_attempts):
        router = OrthogonalRouter(
            obstacles, max_x=max_x, max_y=max_y, bend_cost=bend_cost, cross_cost=cross_cost
        )
        router.register_nets(ordered)
        failed_idx: Optional[int] = None
        for idx, (name, pts) in enumerate(ordered):
            if not router.route_net(name, pts):
                failed_idx = idx
                last_failed = name
                break
        if failed_idx is None:
            wires = router.emit_wires()
            res = verify_connectivity(wires, all_pins, expected_nets=nets)
            if not res.ok:
                raise RoutingError("Post-routing verification failed: " + "; ".join(res.errors))
            return wires
        failed_item = ordered.pop(failed_idx)
        ordered.insert(0, failed_item)

    raise RoutingError(
        f"Failed to route all {len(nets)} nets after {max_attempts} attempts "
        f"(last blocked net: {last_failed!r}) in grid {max_x}x{max_y}. "
        f"Try increasing component spacing or passing larger max_x/max_y."
    )
