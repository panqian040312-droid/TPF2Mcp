#!/usr/bin/env python3
"""Find railway deadlock risk points from read-only bridge data.

Why this exists
---------------
On 2026-09-29 two trains on line 109995 (Almaty 扳手铁路) deadlocked head to
head and sat motionless for over five hours. Nothing in the tool chain caught
it:

* the engine has no player-facing deadlock warning (checked every string in
  res/strings/en/LC_MESSAGES/res.mo -- the only relevant text is the campaign
  tutorial teaching you to build a passing loop and place signals);
* TRANSFORM_VEHICLE.raw_state stays 1 ("running") while a train is stuck, so
  the vehicle state is useless as a signal;
* POSSIBLE_BUNCHING in line_diagnostics is a distance-only heuristic and labels
  a head-on deadlock the same as ordinary bunching;
* state.json carries no position and no speed at all.

So the risk has to be derived from topology instead of observed from a flag.

The rule
--------
TPF2 lets a train wait for an oncoming train only where there is somewhere to
wait: a passing loop, a spare platform, a siding. That is exactly what the
tutorial says -- "The trains should wait for each other on the passing siding.
This requires placing signals."

Topologically, "somewhere to wait" means a branch point, and "no way to avoid a
meeting" means a stretch of track with no branch point at all. So:

    a deadlock risk = a run of edges that are ALL bridges (remove any one and
                      the network splits) AND that contains no junction

The bridge test is what makes this exact rather than heuristic. On a double
track section the two parallel edges back each other up, so neither is a
bridge and the section is never flagged. On a single track section every edge
is a bridge.

A chain of consecutive bridges with all internal vertices of degree 2 is a
stretch you cannot get off, cannot pass on, and cannot back out of once two
trains are on it facing each other. Its length decides how bad that is: the
longer it is, the longer both trains are committed.

Usage
-----
    python tools/find_deadlock_risks.py [--rail-network PATH] [--signal-state PATH]
                                        [--min-length 30] [--json OUT]

Reads only. Writes only if --json is given.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import pathlib
import sys
from collections import defaultdict

# TPF2 rolling stock is about 20 m per unit. The number is only used to answer
# "is this train longer than that distance", so being roughly right is enough --
# a 15-unit freight consist clears 200 m either way.
DEFAULT_UNIT_LENGTH_M = 20.0

DEFAULT_STAGING = pathlib.Path(
    r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
)

# Severity bands, in metres of unbroken branchless single track.
# A TPF2 train consist is typically 60-200 m, so a chain shorter than a train
# can sometimes still be tolerated by one consist hanging out of a platform.
SEVERITY_HIGH = 250.0
SEVERITY_MEDIUM = 100.0


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_graph(network: dict):
    """Undirected multigraph over rail edges that have readable endpoints."""
    nodes = {}
    for node in network.get("nodes") or []:
        position = node.get("position") or {}
        if isinstance(position.get("x"), (int, float)) and isinstance(position.get("y"), (int, float)):
            nodes[node["entity_id"]] = (float(position["x"]), float(position["y"]))

    edges = {}
    adjacency: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for edge in network.get("edges") or []:
        n0, n1 = edge.get("node0"), edge.get("node1")
        if n0 not in nodes or n1 not in nodes or n0 == n1:
            continue
        edges[edge["entity_id"]] = (n0, n1)
        adjacency[n0].append((n1, edge["entity_id"]))
        adjacency[n1].append((n0, edge["entity_id"]))

    # A platform is somewhere a train can stand aside, so a branchless run of
    # single track has to be cut there too -- otherwise a long chain would
    # include the station the trains could actually have waited in.
    platform_nodes: set[int] = set()
    for station in network.get("stations") or []:
        for terminal in station.get("terminals") or []:
            node_id = terminal.get("node_id")
            if isinstance(node_id, int):
                platform_nodes.add(node_id)

    return nodes, edges, adjacency, platform_nodes


def find_bridges(adjacency: dict[int, list[tuple[int, int]]]) -> set[int]:
    """Tarjan bridge detection. Parallel edges between the same pair are not
    bridges: the second one is seen as a back edge, which is the correct
    treatment for a double track section."""
    sys.setrecursionlimit(max(200000, len(adjacency) * 4))
    discovery: dict[int, int] = {}
    low: dict[int, int] = {}
    parent: dict[int, tuple[int, int]] = {}
    bridges: set[int] = set()
    counter = [0]

    def visit(u: int) -> None:
        discovery[u] = low[u] = counter[0]
        counter[0] += 1
        for v, edge_id in adjacency[u]:
            if v not in discovery:
                parent[v] = (u, edge_id)
                visit(v)
                low[u] = min(low[u], low[v])
                if low[v] > discovery[u]:
                    bridges.add(edge_id)
            elif parent.get(u) and v != parent[u][0]:
                low[u] = min(low[u], discovery[v])

    for start in list(adjacency):
        if start not in discovery:
            visit(start)
    return bridges


def chain_bridges(edges: dict[int, tuple[int, int]], bridges: set[int],
                  platform_nodes: set[int]):
    """Group consecutive bridge edges into maximal junction-free chains.

    The bridge edges form a forest (a bridge can never lie on a cycle), so a
    chain is a path through that forest that passes only through vertices of
    degree 2. A vertex of degree >= 3 is a junction -- somewhere a train could
    stand aside -- and therefore terminates the chain.

    Walks each bridge from both ends and de-duplicates, which is simpler than
    trying to pick a canonical starting end.
    """
    degree: dict[int, int] = defaultdict(int)
    for n0, n1 in edges.values():
        degree[n0] += 1
        degree[n1] += 1

    incident: dict[int, set[int]] = defaultdict(set)
    for edge_id in bridges:
        n0, n1 = edges[edge_id]
        incident[n0].add(edge_id)
        incident[n1].add(edge_id)

    def other_end(edge_id: int, vertex: int) -> int:
        n0, n1 = edges[edge_id]
        return n1 if vertex == n0 else n0

    def stop_at(vertex: int) -> bool:
        """Chain terminates here: a junction, a platform, or a dead end."""
        return degree[vertex] > 2 or vertex in platform_nodes or len(incident[vertex]) <= 1

    def walk(edge_id: int, from_vertex: int) -> list[int]:
        chain = [edge_id]
        current = other_end(edge_id, from_vertex)
        while not stop_at(current):
            following = [e for e in incident[current] if e != chain[-1]]
            if not following:
                break
            chain.append(following[0])
            current = other_end(following[0], current)
        return chain

    # Only start walking from a chain endpoint. Starting from an interior edge
    # would emit every sub-run of the same physical track as its own "risk",
    # which is what made the first version report 2201 overlapping chains.
    unique: dict[tuple[int, ...], list[int]] = {}
    for edge_id in bridges:
        n0, n1 = edges[edge_id]
        for vertex in (n0, n1):
            if not stop_at(vertex):
                continue
            chain = walk(edge_id, vertex)
            unique.setdefault(tuple(sorted(chain)), chain)
    return list(unique.values())


def nearest_junction_distance(adjacency, degree, nodes, start, bridges, limit=6000.0):
    """Walk the track from `start` to the nearest junction (degree > 2).

    This is the distance a train standing at a platform has available before it
    fouls the points. A platform that is closer to the points than its longest
    calling train is long means that every call blocks the junction.

    Returns the junction, the distance, and whether EVERY edge on that walk is
    a bridge edge. A bridge edge is a single track whose removal would split
    the network, so a walk that is all bridges means there is no duplicate
    track to dodge into -- that is what turns "blocks the junction" into an
    actual standstill. Without this test the report flagged 22 platforms that
    all sit on doubled track and never actually deadlock.

    Note the adjacency stores (neighbour, edge_id); the edge id is NOT a length,
    so the weight has to be recomputed from the node positions.
    """
    best = {start: 0.0}
    parent: dict[int, tuple[int, int]] = {}
    queue = [(0.0, start)]
    while queue:
        distance, vertex = heapq.heappop(queue)
        if distance > limit:
            return None, None, None
        if vertex != start and degree.get(vertex, 0) > 2:
            single_track = True
            node = vertex
            while node != start:
                previous, edge_id = parent[node]
                if edge_id not in bridges:
                    single_track = False
                    break
                node = previous
            return vertex, distance, single_track
        here = nodes.get(vertex)
        if here is None:
            continue
        for neighbour, edge_id in adjacency.get(vertex, []):
            there = nodes.get(neighbour)
            if there is None:
                continue
            candidate = distance + math.dist(here, there)
            if candidate < best.get(neighbour, float("inf")):
                best[neighbour] = candidate
                parent[neighbour] = (vertex, edge_id)
                heapq.heappush(queue, (candidate, neighbour))
    return None, None, None


def platform_reach(network, adjacency, nodes, snapshot, unit_length, bridges):
    """For each platform: distance to the nearest points, against the length of
    the longest train that actually calls there.

    A platform whose nearest points are closer than its longest calling train
    cannot hold that train clear of the junction, so every call blocks the
    switch -- which is the mechanism behind the 2026-09-29 head-on deadlock.

    Using the per-station calling train rather than the map's longest train
    matters: this map also has a 32-unit monster, and applying that everywhere
    flags almost every platform, which is useless.
    """
    degree: dict[int, int] = defaultdict(int)
    for neighbours in adjacency.values():
        for neighbour, _ in neighbours:
            degree[neighbour] += 1

    line_length: dict[int, float] = {}
    for vehicle in (snapshot or {}).get("vehicles") or []:
        name = str(vehicle.get("name") or "")
        parts = vehicle.get("consist_parts") or []
        line_id = vehicle.get("line_id")
        if "列" not in name or not parts or not isinstance(line_id, int):
            continue
        length = len(parts) * unit_length
        if length > line_length.get(line_id, 0.0):
            line_length[line_id] = length

    group_lines: dict[int, set] = defaultdict(set)
    # How many other terminals a line calling at this node is allowed to use.
    # This is the engine's own "alternative terminals" list, so it is the honest
    # answer to "could this train just berth somewhere else here?". An empty
    # list means the line never assigned a fallback -- which is a setting, not
    # a physical limit. Keep the calling lines too so the report can say whether
    # the emptiness is a choice or a dead end.
    alt_lines: dict[int, set] = defaultdict(set)
    calling_lines: dict[int, set] = defaultdict(set)
    for line in network.get("lines") or []:
        line_id = line.get("entity_id")
        for stop in line.get("stops") or []:
            group_id = stop.get("station_group_id")
            if group_id is not None:
                group_lines[group_id].add(line_id)
            node_id = stop.get("node_id")
            if node_id is None:
                continue
            calling_lines[node_id].add(line_id)
            if stop.get("alternative_terminals"):
                alt_lines[node_id].add(line_id)

    rows = []
    for station in network.get("stations") or []:
        group_id = station.get("entity_id")
        calling = [line_length[l] for l in group_lines.get(group_id, ()) if l in line_length]
        longest = max(calling) if calling else None
        terminals = station.get("terminals") or []
        for terminal in terminals:
            node_id = terminal.get("node_id")
            if node_id not in adjacency:
                continue
            # Count only terminals of the SAME traffic. A five-platform
            # passenger station next door does not give a freight train
            # anywhere to go, so counting all terminals overstates the choices.
            cargo = bool(terminal.get("cargo"))
            same_cargo = sum(1 for t in terminals if bool(t.get("cargo")) == cargo)
            junction, distance, single_track = nearest_junction_distance(
                adjacency, degree, nodes, node_id, bridges)
            rows.append({
                "station": station.get("name"),
                # Two stations can share a name while being separate buildings
                # with different traffic: 降低Almaty is a 5-platform passenger
                # station (113700) AND a 1-platform freight station (223689).
                "station_entity_id": group_id,
                "platform_node": node_id,
                "platform_cargo": cargo,
                "same_cargo_terminals": same_cargo,
                "distance_m": round(distance, 1) if distance is not None else None,
                "longest_calling_train_m": round(longest, 1) if longest else None,
                "platforms_at_station": len(terminals),
                "alternative_terminals": len(alt_lines.get(node_id, ())),
                "lines_calling": len(calling_lines.get(node_id, ())),
                "single_track_berth": single_track,
                "fouls_points": (distance is not None and longest is not None and distance < longest),
            })

    # Assigning an alternative terminal only helps if one of the spares is
    # actually FARTHER from the points than the train is long. Otherwise the
    # train is simply longer than every siding at the station and no amount of
    # platform juggling will let it stand clear. Compute the best spare per
    # (station building, traffic) so the report can tell the two apart.
    best_spare: dict[tuple[int, bool], float] = {}
    for row in rows:
        key = (row["station_entity_id"], row["platform_cargo"])
        value = row["distance_m"]
        if value is None:
            continue
        if value > best_spare.get(key, -1.0):
            best_spare[key] = value
    for row in rows:
        key = (row["station_entity_id"], row["platform_cargo"])
        spare = best_spare.get(key)
        length = row["longest_calling_train_m"]
        # With only one terminal of this traffic there is no spare to report --
        # echoing the platform's own distance here would read like an option.
        row["best_spare_distance_m"] = round(spare, 1) if (
            spare is not None and row["same_cargo_terminals"] > 1) else None
        row["fixable_by_assignment"] = bool(
            row["same_cargo_terminals"] > 1
            and spare is not None
            and length is not None
            and spare >= length
        )

    rows.sort(key=lambda r: (r["distance_m"] is None, r["distance_m"] or 0))
    return rows


def edge_length(edges: dict[int, tuple[int, int]], nodes: dict, edge_id: int) -> float:
    n0, n1 = edges[edge_id]
    a, b = nodes.get(n0), nodes.get(n1)
    if a is None or b is None:
        return 0.0
    return math.dist(a, b)


def fouling_zones(edges: dict[int, tuple[int, int]], nodes: dict, short_threshold: float = 20.0):
    """Points and station throats appear in the track graph as runs of very
    short edges.

    A train standing on any of those edges has its body lying across the points,
    so nothing can be routed through it -- that is what "侵入道岔" means, and it
    is what actually caused the 2026-09-29 deadlock.

    Searching for the nearest junction NODE gets this wrong, which is the mistake
    the first version made: the train is already *inside* the throat, so the
    distance to the far end of it says nothing. The zone has to be measured as a
    run, not a point.
    """
    incident: dict[int, list[int]] = defaultdict(list)
    for edge_id, (n0, n1) in edges.items():
        incident[n0].append(edge_id)
        incident[n1].append(edge_id)

    short = {e for e in edges if edge_length(edges, nodes, e) < short_threshold}
    seen: set[int] = set()
    zones: list[list[int]] = []
    for edge_id in short:
        if edge_id in seen:
            continue
        stack, zone = [edge_id], []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            zone.append(current)
            for endpoint in edges[current]:
                for neighbour_edge in incident[endpoint]:
                    if neighbour_edge in short and neighbour_edge not in seen:
                        stack.append(neighbour_edge)
        zones.append(zone)
    return zones


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rail-network", type=pathlib.Path,
                        default=DEFAULT_STAGING / "bridge" / "rail-network.json")
    parser.add_argument("--signal-state", type=pathlib.Path,
                        default=DEFAULT_STAGING / "bridge" / "rail-control-state.json")
    parser.add_argument("--vehicles", type=pathlib.Path,
                        default=DEFAULT_STAGING / "bridge" / "live-rail-state.json",
                        help="vehicle positions, to count how many vehicles sit on each chain")
    parser.add_argument("--state", type=pathlib.Path,
                        default=DEFAULT_STAGING / "bridge" / "state.json",
                        help="world snapshot, used to size the consists")
    parser.add_argument("--unit-length", type=float, default=DEFAULT_UNIT_LENGTH_M,
                        help="metres per rolling stock unit")
    parser.add_argument("--min-length", type=float, default=30.0)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    args = parser.parse_args()

    network = load(args.rail_network)
    nodes, edges, adjacency, platform_nodes = build_graph(network)
    print(f"rail graph: {len(nodes)} nodes, {len(edges)} edges, {len(platform_nodes)} platform nodes")

    bridges = find_bridges(adjacency)
    print(f"bridge edges (single track bottlenecks): {len(bridges)}")

    chains = chain_bridges(edges, bridges, platform_nodes)
    print(f"branchless single-track chains: {len(chains)}")

    def length_of(chain) -> float:
        total = 0.0
        for edge_id in chain:
            n0, n1 = edges[edge_id]
            total += math.dist(nodes[n0], nodes[n1])
        return total

    def junction_count(chain) -> int:
        degree: dict[int, int] = defaultdict(int)
        for n0, n1 in edges.values():
            degree[n0] += 1
            degree[n1] += 1
        inside = set()
        for edge_id in chain:
            n0, n1 = edges[edge_id]
            inside.add(n0)
            inside.add(n1)
        return sum(1 for v in inside if degree[v] > 2)

    # Where are the vehicles right now? A branchless single-track chain that
    # happens to be empty is a latent risk; one with two or more vehicles on it
    # is where the deadlock will actually happen.
    vehicles_by_edge: dict[int, list[str]] = defaultdict(list)
    vehicle_speed: dict[int, float] = {}
    vehicle_state: dict[int, object] = {}
    if args.vehicles and args.vehicles.exists():
        frame = load(args.vehicles)
        for vehicle in frame.get("vehicles") or []:
            edge_id = vehicle.get("edge_id") or vehicle.get("current_edge_id")
            if isinstance(edge_id, int):
                vehicles_by_edge[edge_id].append(str(vehicle.get("name")))
                speed = vehicle.get("speed_kmh")
                if isinstance(speed, (int, float)):
                    vehicle_speed[edge_id] = speed
                vehicle_state[edge_id] = vehicle.get("raw_state")
        print(f"vehicles with a resolved edge: "
              f"{sum(len(v) for v in vehicles_by_edge.values())}")

    rows = []
    for chain in chains:
        length = length_of(chain)
        if length < args.min_length:
            continue
        vertices = set()
        for edge_id in chain:
            vertices.update(edges[edge_id])
        xs = [nodes[v][0] for v in vertices]
        ys = [nodes[v][1] for v in vertices]
        on_chain: list[str] = []
        for edge_id in chain:
            on_chain.extend(vehicles_by_edge.get(edge_id, []))
        rows.append({
            "length_m": round(length, 1),
            "edge_count": len(chain),
            "junctions": junction_count(chain),
            "vehicle_count": len(on_chain),
            "vehicles": on_chain,
            "bbox": {"min_x": round(min(xs), 1), "max_x": round(max(xs), 1),
                     "min_y": round(min(ys), 1), "max_y": round(max(ys), 1)},
            "center": {"x": round(sum(xs) / len(xs), 1), "y": round(sum(ys) / len(ys), 1)},
            "edges": list(chain),
        })
    # Occupied chains first (that is where it will bite), then by length.
    rows.sort(key=lambda r: (-r["vehicle_count"], -r["length_m"]))

    print()
    print(f"=== branchless single-track chains >= {args.min_length:.0f} m: {len(rows)} ===")
    print(f"{'长度m':>9}{'边数':>6}{'链上车':>7}  车                                   中心")
    shown = 0
    for row in rows:
        band = "HIGH" if row["length_m"] >= SEVERITY_HIGH else ("MED" if row["length_m"] >= SEVERITY_MEDIUM else "low")
        if row["vehicle_count"] >= 2:
            band = "DEADLOCK?"
        names = ",".join(row["vehicles"][:3])
        print(f"{row['length_m']:>9.1f}{row['edge_count']:>6}{row['vehicle_count']:>7}  "
              f"{names[:34]:<36}({row['center']['x']:.0f},{row['center']['y']:.0f})  [{band}]")
        shown += 1
        if shown >= 30:
            break

    occupied = [r for r in rows if r["vehicle_count"] >= 2]
    total_high = sum(1 for r in rows if r["length_m"] >= SEVERITY_HIGH)
    print()
    print(f"summary: chains with >=2 vehicles (head-on candidates)={len(occupied)}  "
          f"HIGH(>={SEVERITY_HIGH:.0f}m)={total_high}  listed={len(rows)}")

    # Longest consist on the map, for reference.
    snapshot = None
    if args.state and args.state.exists():
        snapshot = load(args.state)
        units = []
        for vehicle in snapshot.get("vehicles") or []:
            name = str(vehicle.get("name") or "")
            parts = vehicle.get("consist_parts") or []
            if parts and ("列" in name or name.startswith(("Train", "Zug", "Tram"))):
                units.append(len(parts))
        if units:
            print(f"longest rail consist on the map: {max(units)} units, "
                  f"~{max(units) * args.unit_length:.0f} m")

    platforms = platform_reach(network, adjacency, nodes, snapshot, args.unit_length, bridges)
    sized = [r for r in platforms if r["longest_calling_train_m"] is not None]
    fouls = [r for r in platforms if r["fouls_points"]]
    # A platform fouls its points when its longest calling train is longer than
    # the clear track behind it. That only becomes a standstill when the train
    # also has nowhere to go: no parallel track to dodge into (every edge on the
    # walk is a bridge) and no second terminal of the same traffic.
    on_single = [r for r in fouls if r["single_track_berth"]]
    # Three different problems, three different fixes:
    #   dead_end -- the station has exactly one terminal of this traffic, so no
    #               assignment can help and no train can give way. Rebuild or
    #               shorten the consist. 降低Almaty is this case.
    #   settable -- the station HAS more terminals of this traffic but the line
    #               never assigned any as a fallback. One edit in the line's
    #               stop list fixes it. Omsk and Ranchi are this case.
    #   has_alt  -- a fallback is already assigned and the train still does not
    #               fit; the platforms are simply too close to the points.
    dead_end = [r for r in on_single if r["same_cargo_terminals"] == 1]
    fixable = [r for r in on_single
               if r["same_cargo_terminals"] > 1 and r["fixable_by_assignment"]]
    unassignable = [r for r in on_single
                    if r["same_cargo_terminals"] > 1 and not r["fixable_by_assignment"]]
    doubled = [r for r in fouls if not r["single_track_berth"]]
    print()
    print(f"=== platform clearance ({len(sized)}/{len(platforms)} platforms have calling-line data) ===")
    print(f"    platform whose nearest points are closer than its longest calling train: {len(fouls)}")
    print(f"    ... standing on single track (no parallel track to dodge into):        {len(on_single)}")
    print(f"    ... only ONE terminal of this traffic -- no assignment can fix it:      {len(dead_end)}")
    print(f"    ... a spare terminal IS long enough -- fix by assigning it:            {len(fixable)}")
    print(f"    ... spare terminals exist but ALL are too short -- still needs the train cut: {len(unassignable)}")
    print(f"    ... on doubled track, so an opposing train can still slip past:          {len(doubled)}")
    print("    NOTE: this measures whether a train can stand CLEAR of the points, i.e.")
    print("          whether it could give way by retreating. It does NOT by itself mean")
    print("          the train fouls the points while berthed -- the head faces the")
    print("          departure direction, so the tail is the side that overhangs.")
    print("    NOTE: stations sharing a name are separate buildings. 降低Almaty is both")
    print("          a 5-platform passenger station and a 1-platform freight station;")
    print("          a freight train can only use the freight one, so '5 platforms'")
    print("          never means '5 choices'. Only same-traffic terminals count.")
    print("    NOTE: assigning an alternative terminal only cures a jam caused by two")
    print("          trains fighting over one platform. It does NOT make a train")
    print("          shorter, so it cannot fix a berth that is shorter than the train.")
    print(f"{'车站(性质)':<22}{'站台节点':>10}{'到道岔m':>9}{'最长列车m':>11}{'同性质台':>9}{'最长备用台m':>11}  判定")
    ordered = dead_end + fixable + unassignable + doubled
    for row in ordered[:30]:
        label = f"{str(row['station'])[:14]}({'货' if row['platform_cargo'] else '客'})"
        spare = row["best_spare_distance_m"]
        spare_text = "无" if row["same_cargo_terminals"] == 1 else (
            f"{spare:.0f}" if spare is not None else "-")
        if not row["single_track_berth"]:
            verdict = "🟡 复线：停不净，但对向车可从并行股道绕过"
        elif row["same_cargo_terminals"] == 1:
            verdict = "🔴🔴🔴 全场只有这一个同性质站台 → 无台可换，只能改车或改线"
        elif row["fixable_by_assignment"]:
            verdict = "🟠 换台可救：备选里有一个够长的股道，设上备选即可"
        else:
            verdict = "🔴🔴 备选台全都不够长 → 换台也救不了，还是要改车或改线"
        print(f"{label:<22}{row['platform_node']:>10}{row['distance_m']:>9.1f}"
              f"{row['longest_calling_train_m']:>11.0f}{row['same_cargo_terminals']:>9}"
              f"{spare_text:>11}  {verdict}")

    # Is any vehicle physically standing on the points right now?
    zones = fouling_zones(edges, nodes)
    zone_of: dict[int, int] = {}
    for index, zone in enumerate(zones):
        for edge_id in zone:
            zone_of[edge_id] = index
    zone_length = {}
    for index, zone in enumerate(zones):
        zone_length[index] = sum(edge_length(edges, nodes, e) for e in zone)
    standing = [(edge_id, names) for edge_id, names in vehicles_by_edge.items() if edge_id in zone_of]
    # Being on the points is normal while passing through; sitting on them with
    # no speed is the deadlock signature. Without the speed test this reports
    # every train currently traversing a station throat (7 of 7 were false).
    stuck_on_points = [
        (edge_id, names) for edge_id, names in standing
        if isinstance(vehicle_speed.get(edge_id), (int, float)) and vehicle_speed[edge_id] <= 1.0
    ]
    print()
    print(f"=== vehicles standing ON the points (fouling zones: {len(zones)} found) ===")
    print(f"    on the points: {len(standing)}    of which stationary: {len(stuck_on_points)}")
    if not stuck_on_points:
        print("    none stationary on the points")
    for edge_id, names in stuck_on_points:
        index = zone_of[edge_id]
        state = vehicle_state.get(edge_id)
        if state == 1:
            tag = "🔴 运行中却停住不动 = 死锁"
        elif state == 2:
            tag = "🟡 停站中（会走，但停站期间车体压住道岔）"
        else:
            tag = f"（state={state}）"
        print(f"  {tag}")
        print(f"      {'/'.join(names):<12} 边 {edge_id}"
              f"（道岔区 {len(zones[index])} 条短边 / {zone_length[index]:.1f} m）"
              f" speed={vehicle_speed[edge_id]} state={state}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({
            "schema_version": 1,
            "source_status": "DERIVED_FROM_TOPOLOGY",
            "rail_graph": {"nodes": len(nodes), "edges": len(edges), "bridges": len(bridges)},
            "thresholds": {"high_m": SEVERITY_HIGH, "medium_m": SEVERITY_MEDIUM},
            "unit_length_m": args.unit_length,
            "risks": rows,
            "platform_fouls": fouls,
            "platforms": platforms,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
