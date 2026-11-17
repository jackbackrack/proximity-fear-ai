#!/usr/bin/env python3
"""Check the realized (Warp-routed) copper of a design against its design rules (rte-01).

    python scripts/check_layout.py proximity_fear.main.ProximityFearBadge

Submits and captures the design. The design applies ``jitx_export.json`` itself when the
file is in the working directory (``ProximityFearBadge.__init__``), so run this from the
project root to check the imported layout. Then it measures, from the capture:

- Rule widths: every realized trace against the trace-width rule that wins for it (highest
  priority rule whose condition matches the trace's tags). Below the rule fails; wider is
  reported as a note (a Warp route can carry its own ``width``).
- Rule clearances: every pair of different-net copper on one layer where at least one side
  is routed copper (trace or via) against the clearance rule that wins for the pair. Pad to
  pad spacing is the footprints' and placement's, not routing's, and is not re-checked.
- Connectivity: every net's pads joined by realized traces, vias and pours.
- Routes: every authored ``Route`` (the layout file's) realized.
- Runtime issues: the runtime's own physical-design issue report. A geometric overlap whose
  copper is all on one net is a note (same-net contact); any other error is a finding.
- Routing intent (ARCHITECTURE.md Design Notes "Routing intent", the mechanically checkable
  part, for ``BadgeCircuit`` designs): no via in the crystal area, XL1/XL2 routed and short,
  PDM nets clear of XL copper, NFC1/NFC2 lengths matched with equal via counts.

The values come from the rule objects the design declares (``layout_checks.rule_width`` /
``rule_clearance``); only the routing-intent limits, which no rule carries, are constants
here, each labelled with its source.

Not verifiable from capture (named, never passed): trace-to-pour clearance, thermal relief,
pour sliver removal; "nothing fast between crystal and module", "slow nets on pads 8-10 leave
east of the crystal" and "TVS anode has its own GND via" stay visual checks.

Exit codes: 0 no findings (checks with no copper to witness them are listed as
unwitnessed); 1 findings; 2 could not run (bad target, no runtime, capture failure).
"""

from __future__ import annotations

import argparse
import importlib
import itertools
import logging
import math
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import jitx
import shapely
from jitx import Copper, Design, Pour
from jitx.circuit import Route
from jitx.component import Component
from jitx.constraints import (
    AndExpr,
    AtomExpr,
    BinaryDesignConstraint,
    BoolExpr,
    BuiltinTag,
    DesignConstraint,
    NotExpr,
    OnLayer,
    OrExpr,
    Tag,
    Tags,
    TrueExpr,
    UnaryDesignConstraint,
)
from jitx.inspect import visit
from jitx.issue import GeometricOverlap, Severity
from jitx.landpattern import Pad
from jitx.net import Net
from jitx.shapes import Shape
from jitx.shapes.primitive import Arc, ArcPolyline, Empty, PolygonSet, Polyline
from jitx.via import Via
from layout_checks import rule_clearance, rule_width
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from proximity_fear.circuits.nrf_support import LFXO_TRACE_LENGTHS_MM
from proximity_fear.designs.badge import BadgeCircuit
from proximity_fear.main import LAYOUT_FILE

# Measurement slack: float noise plus the chord error of polygonized round pads and vias,
# far below the 0.09 mm fab floor.
EPSILON_MM = 1e-3
ARC_STEP_DEG = 1.0  # trace arcs: sagitta at the 0.1875 mm corner radius seen in routing ~7e-6 mm
BUFFER_QUAD_SEGS = 32  # round trace ends / joins: 32 segments per quarter circle

# --- Routing-intent limits (no design rule carries these) --------------------------------
XL_MAX_ROUTED_LENGTH = 10.0  # rte-01 brief: XL1 / XL2 each < ~10 mm (ARCHITECTURE "XL1/XL2 short")
PDM_XL_MIN_SPACING = 1.0  # ARCHITECTURE Design Notes, Routing intent: PDM nets >= 1 mm from XL traces
NFC_LENGTH_MATCH = 0.10  # rte-01 brief: NFC1 vs NFC2 routed length within 10 % ("legs symmetric")


class Kind(Enum):
    TRACE = "trace"
    VIA = "via"
    PAD = "pad"
    POUR = "pour"


BUILTINS: dict[Kind, frozenset[BuiltinTag]] = {
    Kind.TRACE: frozenset({BuiltinTag.IsTrace, BuiltinTag.IsCopper}),
    Kind.VIA: frozenset({BuiltinTag.IsVia, BuiltinTag.IsCopper}),
    Kind.PAD: frozenset({BuiltinTag.IsPad, BuiltinTag.IsCopper}),
    Kind.POUR: frozenset({BuiltinTag.IsPour, BuiltinTag.IsCopper}),
}


@dataclass(eq=False)
class Item:
    """One piece of realized copper on one layer, in the board frame."""

    kind: Kind
    layer: int
    geometry: BaseGeometry
    net: Any  # RuntimeDesign.Net | None
    tags: frozenset[Tag]
    owner: object  # the Route, Via, Component (for a pad) or Pour it came from
    width: float | None = None  # traces: the polyline width
    length: float = 0.0  # traces: centreline length


class Status(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNWITNESSED = "UNWITNESSED"
    NOTE = "NOTE"


@dataclass(frozen=True)
class Line:
    status: Status
    name: str
    detail: str


@dataclass
class Report:
    lines: list[Line] = field(default_factory=list)

    def add(self, status: Status, name: str, detail: str) -> None:
        self.lines.append(Line(status, name, detail))

    def count(self, status: Status) -> int:
        return sum(1 for line in self.lines if line.status is status)


# --- Tag expressions ----------------------------------------------------------------------


def matches(expr: BoolExpr, item: Item, normalize: Any) -> bool:
    """Evaluate a rule condition against one copper item's tags, builtins and layer.

    Tag atoms match by class, so a rule on ``PowerTag`` matches a ``VLEDTag`` subclass, as
    the engine does (jitx-layout-constraints "Vocabulary").
    """
    if isinstance(expr, TrueExpr):
        return True
    if isinstance(expr, AtomExpr):
        atom = expr.atom
        if isinstance(atom, BuiltinTag):
            return atom in BUILTINS[item.kind]
        if isinstance(atom, OnLayer):
            return normalize(atom.index) == item.layer
        return any(isinstance(tag, atom.__class__) for tag in item.tags)
    if isinstance(expr, NotExpr):
        return not matches(expr.expr, item, normalize)
    if isinstance(expr, AndExpr):
        return matches(expr.left, item, normalize) and matches(expr.right, item, normalize)
    if isinstance(expr, OrExpr):
        return matches(expr.left, item, normalize) or matches(expr.right, item, normalize)
    raise TypeError(f"unhandled rule condition {expr!r}")


def winning_width_rule(rules: Sequence[UnaryDesignConstraint], item: Item, normalize: Any) -> Any:
    """The highest-priority trace-width rule matching ``item``; ties raise (undefined order)."""
    hits = [rule for rule in rules if matches(rule.condition, item, normalize)]
    if not hits:
        return None
    top = max(rule.priority for rule in hits)
    winners = [rule for rule in hits if rule.priority == top]
    if len(winners) > 1:
        raise ValueError(f"equal-priority width rules both match: {winners}")
    return winners[0]


def winning_clearance_rule(rules: Sequence[BinaryDesignConstraint], a: Item, b: Item, normalize: Any) -> Any:
    """The highest-priority clearance rule matching the pair in either order."""
    hits = [
        rule
        for rule in rules
        if (matches(rule.first, a, normalize) and matches(rule.second, b, normalize))
        or (matches(rule.first, b, normalize) and matches(rule.second, a, normalize))
    ]
    if not hits:
        return None
    return max(hits, key=lambda rule: (rule.priority, rule_clearance(rule)))


# --- Geometry -----------------------------------------------------------------------------


def to_geometry(shape: Shape, transform: Any) -> BaseGeometry:
    """Board-frame shapely geometry; computed pours keep their holes (PolygonSet)."""
    primitive = shape.geometry
    if isinstance(primitive, PolygonSet):
        local = shapely.MultiPolygon([shapely.Polygon(p.elements, p.holes) for p in primitive.polygons])
        local = shapely.affinity.affine_transform(local, affine(shape.transform))
    else:
        local = shape.to_shapely().g
    return local if transform is None else shapely.affinity.affine_transform(local, affine(transform))


def affine(transform: Any) -> list[float]:
    """shapely affine parameters [a, b, d, e, xoff, yoff] of a JITX transform."""
    ox, oy = transform * (0.0, 0.0)
    ux, uy = transform * (1.0, 0.0)
    vx, vy = transform * (0.0, 1.0)
    return [ux - ox, vx - ox, uy - oy, vy - oy, ox, oy]


def centreline(primitive: Polyline | ArcPolyline) -> list[tuple[float, float]]:
    """Centreline points of a trace; arcs are walked in ARC_STEP_DEG steps from start by sweep."""
    if isinstance(primitive, Polyline):
        return [(float(x), float(y)) for x, y in primitive.elements]
    points: list[tuple[float, float]] = []
    for element in primitive.elements:
        if isinstance(element, Arc):
            cx, cy = element.center
            steps = max(1, math.ceil(abs(element.arc) / ARC_STEP_DEG))
            for k in range(steps + 1):
                angle = math.radians(element.start + element.arc * k / steps)
                points.append((cx + element.radius * math.cos(angle), cy + element.radius * math.sin(angle)))
        else:
            points.append((float(element[0]), float(element[1])))
    return points


def trace_geometry(shape: Shape, primitive: Polyline | ArcPolyline) -> BaseGeometry:
    """The trace's copper: its centreline buffered by half its width (round ends and joins).

    Built here rather than with ``to_shapely()`` so arcs are fine enough for clearance: a
    coarse chord sits inside the true arc and reads a gap that is short by its sagitta.
    """
    points = centreline(primitive)
    line = shapely.LineString(points) if len(points) > 1 else shapely.Point(points[0])
    copper = line.buffer(primitive.width / 2, quad_segs=BUFFER_QUAD_SEGS)
    return copper if shape.transform is None else shapely.affinity.affine_transform(copper, affine(shape.transform))


# --- Capture ------------------------------------------------------------------------------


def collect(rd: Any) -> list[Item]:
    """Every realized trace, via, pad and computed pour as board-frame items."""
    root = rd.root
    nets = rd.nets
    normalize = rd.layers.normalize

    net_tags: dict[int, set[Tag]] = {}
    for _, net in visit(root, Net):
        tags = Tags.get(net)
        runtime_net = nets.find(net)
        if tags and runtime_net is not None:
            net_tags.setdefault(id(runtime_net), set()).update(tags.tags)

    pad_owner: dict[int, Component] = {}
    for _, component in visit(root, Component):
        for _, pad in visit(component, Pad):
            pad_owner[id(pad)] = component

    def own_tags(obj: object) -> set[Tag]:
        tags = Tags.get(obj)
        return set(tags.tags) if tags else set()

    items: list[Item] = []
    for trace, copper in rd.query(Copper):
        source = trace.path.access(root)
        runtime_net = nets.find(copper)
        tags = set(net_tags.get(id(runtime_net), ())) if runtime_net is not None else set()
        if isinstance(source, Route):
            layer = normalize(copper.layer)  # route copper is already on its board layer
        elif trace.transform is None:
            raise ValueError(f"unresolved frame for {trace.path}; its copper cannot be placed")
        else:
            # Pad and via copper carry the layer in their own frame: a Bottom placement (a
            # Placement with side=Bottom) maps it to the opposite side, as `transform * layer`.
            layer = normalize(trace.transform * copper.layer)
        if isinstance(copper, Pour):
            if isinstance(copper.shape.geometry, Empty):
                continue  # a removed pour (check_realization.py reports it)
            geometry = to_geometry(copper.shape, trace.transform)
            items.append(Item(Kind.POUR, layer, geometry, runtime_net, frozenset(tags | own_tags(copper)), copper))
        elif isinstance(source, Route):
            # Route copper is already board-global (geometry-verification.md, "Coordinate frames").
            primitive = copper.shape.geometry
            polyline = isinstance(primitive, Polyline | ArcPolyline)
            items.append(
                Item(
                    Kind.TRACE,
                    layer,
                    trace_geometry(copper.shape, primitive) if polyline else to_geometry(copper.shape, None),
                    runtime_net,
                    frozenset(tags | own_tags(source)),
                    source,
                    # A trace realized as a polygon has no width: check_widths fails it.
                    width=float(primitive.width) if polyline else None,
                    length=sum(math.dist(p, q) for p, q in itertools.pairwise(centreline(primitive)))
                    if polyline
                    else 0.0,
                )
            )
        elif isinstance(source, Via):
            geometry = to_geometry(copper.shape, trace.transform)
            items.append(Item(Kind.VIA, layer, geometry, runtime_net, frozenset(tags | own_tags(source)), source))
        elif isinstance(source, Pad):
            owner = pad_owner.get(id(source))
            extra = own_tags(source) | (own_tags(owner) if owner is not None else set())
            geometry = to_geometry(copper.shape, trace.transform)
            items.append(Item(Kind.PAD, layer, geometry, runtime_net, frozenset(tags | extra), owner or source))
    return items


# --- Checks -------------------------------------------------------------------------------


def check_widths(report: Report, rules: Sequence[UnaryDesignConstraint], items: Sequence[Item], normalize: Any) -> None:
    traces = [item for item in items if item.kind is Kind.TRACE]
    by_rule: dict[int, list[Item]] = {id(rule): [] for rule in rules}
    for item in traces:
        rule = winning_width_rule(rules, item, normalize)
        if rule is not None:
            by_rule[id(rule)].append(item)
    for rule in rules:
        expected = rule_width(rule)
        name = f"width {rule.condition} >= {expected:.3f} mm (priority {rule.priority})"
        hits = by_rule[id(rule)]
        if not hits:
            reason = "no routes" if not traces else "no trace matched this rule"
            report.add(Status.UNWITNESSED, name, f"({reason})")
            continue
        polygons = [item for item in hits if item.width is None]
        narrow = [item for item in hits if item.width is not None and item.width < expected - EPSILON_MM]
        wide = sorted({item.width for item in hits if item.width is not None and item.width > expected + EPSILON_MM})
        widths = sorted({round(item.width, 4) for item in hits if item.width is not None})
        detail = f"traces={len(hits)} widths={widths}"
        if polygons or narrow:
            nets = sorted({net_name(item.net) for item in (*polygons, *narrow)})
            report.add(
                Status.FAIL,
                name,
                f"{detail} below_rule={len(narrow)} without_width={len(polygons)} nets={nets}",
            )
        else:
            report.add(Status.PASS, name, detail)
        if wide:
            nets = sorted({net_name(item.net) for item in hits if item.width is not None and item.width in wide})
            report.add(Status.NOTE, name, f"wider than the rule: {wide} on {nets} (route width override?)")
    report.add(
        Status.NOTE,
        "rules not verifiable from capture",
        "thermal relief, trace-to-pour clearance, pour sliver removal (jitx-physical-layout)",
    )


def check_clearances(
    report: Report, rules: Sequence[BinaryDesignConstraint], items: Sequence[Item], normalize: Any
) -> None:
    copper = [item for item in items if item.kind is not Kind.POUR]
    routed = [item for item in copper if item.kind in (Kind.TRACE, Kind.VIA)]
    reach = max((rule_clearance(rule) for rule in rules), default=0.0)
    tree = STRtree([item.geometry for item in copper])
    worst: dict[int, tuple[float, str]] = {}
    failures: dict[int, list[str]] = {id(rule): [] for rule in rules}
    seen: set[tuple[int, int]] = set()
    for a in routed:
        for index in tree.query(a.geometry, predicate="dwithin", distance=reach):
            b = copper[int(index)]
            if b is a or b.layer != a.layer or not different_nets(a, b):
                continue
            key = (min(id(a), id(b)), max(id(a), id(b)))
            if key in seen:
                continue
            seen.add(key)
            rule = winning_clearance_rule(rules, a, b, normalize)
            if rule is None:
                continue
            gap = float(a.geometry.distance(b.geometry))
            where = f"{describe(a)} vs {describe(b)} L{a.layer} gap={gap:.4f}"
            if id(rule) not in worst or gap < worst[id(rule)][0]:
                worst[id(rule)] = (gap, where)
            if gap < rule_clearance(rule) - EPSILON_MM:
                failures[id(rule)].append(where)
    for rule in rules:
        minimum = rule_clearance(rule)
        name = f"clearance {rule.first} x {rule.second} >= {minimum:.3f} mm (priority {rule.priority})"
        if not routed:
            report.add(Status.UNWITNESSED, name, "(no routes or vias)")
        elif failures[id(rule)]:
            shown = "; ".join(failures[id(rule)][:8])
            report.add(Status.FAIL, name, f"violations={len(failures[id(rule)])}: {shown}")
        elif id(rule) in worst:
            report.add(Status.PASS, name, f"closest within {reach:.3f} mm: {worst[id(rule)][1]}")
        else:
            report.add(Status.PASS, name, f"no different-net copper within {minimum:.3f} mm of routed copper")
    has_traces = any(item.kind is Kind.TRACE for item in items)
    if not has_traces:
        report.add(Status.NOTE, "clearance scope", f"{len(routed)} vias checked; no traces yet")


def check_connectivity(report: Report, items: Sequence[Item]) -> None:
    traces = [item for item in items if item.kind is Kind.TRACE]
    by_net: dict[int, list[Item]] = {}
    for item in items:
        if item.net is not None:
            by_net.setdefault(id(item.net), []).append(item)
    split: list[str] = []
    multi_pad_nets = 0
    for members in by_net.values():
        if sum(1 for item in members if item.kind is Kind.PAD) < 2:
            continue
        multi_pad_nets += 1
        islands = islands_of(members)
        if islands > 1:
            split.append(f"{net_name(members[0].net)}({islands})")
    name = f"connectivity: every net's pads joined by realized copper ({multi_pad_nets} multi-pad nets)"
    if not traces:
        report.add(Status.UNWITNESSED, name, f"(no routes) {len(split)} nets currently open")
    elif split:
        report.add(Status.FAIL, name, f"open nets={len(split)}: {', '.join(sorted(split))}")
    else:
        report.add(Status.PASS, name, "all joined")


def islands_of(members: Sequence[Item]) -> int:
    """Connected groups of one net's copper: touching on a layer, or one via / pad across layers."""
    parent = list(range(len(members)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    first_of_owner: dict[tuple[Kind, int], int] = {}
    for i, item in enumerate(members):
        if item.kind in (Kind.VIA, Kind.PAD):
            # A via or a through-hole pad joins its layers. Pads of one component are distinct
            # (different Pad objects share the component owner), so key pads by geometry centre.
            key = (item.kind, id(item.owner) if item.kind is Kind.VIA else hash(item.geometry.centroid.wkb))
            if key in first_of_owner:
                union(i, first_of_owner[key])
            else:
                first_of_owner[key] = i
    tree = STRtree([item.geometry for item in members])
    for i, item in enumerate(members):
        for j in tree.query(item.geometry, predicate="dwithin", distance=EPSILON_MM):
            if members[int(j)].layer == item.layer:
                union(i, int(j))
    pad_roots = {find(i) for i, item in enumerate(members) if item.kind is Kind.PAD}
    return len(pad_roots)


def check_routes(report: Report, routes: Sequence[Route]) -> None:
    name = f"routes realized ({len(routes)} authored)"
    if not routes:
        report.add(Status.UNWITNESSED, name, "(no routes)")
        return
    missing = [route for route in routes if not route.traces]
    blocked = [route for route in routes if route.status is not None and route.status.blocked]
    if missing or blocked:
        report.add(Status.FAIL, name, f"unrealized={len(missing)} blocked={len(blocked)}")
    else:
        report.add(Status.PASS, name, "every route has traces")


def check_issues(report: Report, issues: Any, items: Sequence[Item]) -> None:
    if not issues.complete:
        report.add(Status.FAIL, "runtime issues", "report incomplete (background tasks still running)")
    for issue in issues:
        text = f"{issue.__class__.__name__}: {issue.text}"
        if issue.severity != Severity.ERROR:
            report.add(Status.NOTE, "runtime issue", text)
            continue
        if isinstance(issue, GeometricOverlap):
            pairs = different_net_overlaps(issue, items)
            if not pairs:
                report.add(Status.NOTE, "runtime issue", f"{text} (overlapping copper all on one net)")
                continue
            text += " -- different nets touch: " + "; ".join(f"{describe(a)} x {describe(b)}" for a, b in pairs)
        report.add(Status.FAIL, "runtime issue", text)
    if not any(issue.severity == Severity.ERROR for issue in issues):
        report.add(Status.PASS, "runtime issues", f"{len(issues)} issue(s), no errors")


def different_net_overlaps(issue: Any, items: Sequence[Item]) -> list[tuple[Item, Item]]:
    """Pairs of different-net copper that touch inside an overlap issue's regions.

    An issue whose regions hold no such pair is a same-net contact; one whose regions hold
    no copper at all is returned as unexplained (the copper itself is the pair).
    """
    found: list[Item] = []
    for shape in issue.shapes:
        region = to_geometry(shape.shape, None)
        for item in items:
            if item.kind is Kind.POUR or (shape.layers and item.layer not in shape.layers):
                continue
            if item not in found and item.geometry.intersects(region):
                found.append(item)
    if not found:
        raise ValueError(f"overlap issue {issue.text!r} matches no captured copper")
    return [
        (a, b)
        for n, a in enumerate(found)
        for b in found[n + 1 :]
        if a.layer == b.layer and different_nets(a, b) and a.geometry.intersects(b.geometry)
    ]


def check_intent(report: Report, rd: Any, items: Sequence[Item]) -> None:
    circuit = rd.root.circuit
    if not isinstance(circuit, BadgeCircuit):
        report.add(Status.NOTE, "routing intent", "skipped: not a BadgeCircuit design")
        return
    nets = rd.nets
    traces = [item for item in items if item.kind is Kind.TRACE]
    routed = bool(traces)

    def net_traces(net: Net) -> list[Item]:
        runtime_net = nets.find(net)
        return [item for item in traces if item.net is runtime_net]

    def net_vias(net: Net) -> int:
        runtime_net = nets.find(net)
        return len({id(item.owner) for item in items if item.kind is Kind.VIA and item.net is runtime_net})

    # No via in the crystal area: the hull of the crystal's and its load caps' pads.
    lfxo_parts = {id(circuit.nrf.xtal), *(id(cap) for cap in circuit.nrf.c_xl)}
    lfxo_pads = [item.geometry for item in items if item.kind is Kind.PAD and id(item.owner) in lfxo_parts]
    area = shapely.unary_union(lfxo_pads).convex_hull
    inside = {id(item.owner): item for item in items if item.kind is Kind.VIA and item.geometry.intersects(area)}
    name = "intent: no via in the crystal area (hull of crystal + load-cap pads)"
    if not lfxo_pads:
        report.add(Status.FAIL, name, "crystal / load-cap pads not found in the capture")
    elif inside:
        report.add(Status.FAIL, name, ", ".join(describe(item) for item in inside.values()))
    else:
        vias = len({id(item.owner) for item in items if item.kind is Kind.VIA})
        report.add(Status.PASS, name, f"{vias} vias checked, none inside {area.area:.1f} mm2")

    # XL1 / XL2 routed and short.
    xl1_budget, xl2_budget = LFXO_TRACE_LENGTHS_MM
    for label, net, budget in (("XL1", circuit.nrf.XL1, xl1_budget), ("XL2", circuit.nrf.XL2, xl2_budget)):
        name = f"intent: {label} routed, length < {XL_MAX_ROUTED_LENGTH:.1f} mm"
        if not routed:
            report.add(Status.UNWITNESSED, name, "(no routes)")
            continue
        length = sum(item.length for item in net_traces(net))
        if length == 0.0:
            report.add(Status.FAIL, name, "no trace on the net")
        elif length >= XL_MAX_ROUTED_LENGTH:
            report.add(Status.FAIL, name, f"length={length:.2f} mm")
        else:
            report.add(Status.PASS, name, f"length={length:.2f} mm")
            if length > budget:
                report.add(
                    Status.NOTE,
                    name,
                    f"longer than the {budget:.2f} mm in the LFXO load-cap budget "
                    "(nrf_support.LFXO_TRACE_LENGTHS_MM): re-check lfxo_effective_load",
                )

    # PDM nets clear of XL copper (same layer).
    name = f"intent: PDM_CLK / PDM_DIN >= {PDM_XL_MIN_SPACING:.1f} mm from XL1 / XL2 copper"
    xl = net_traces(circuit.nrf.XL1) + net_traces(circuit.nrf.XL2)
    pdm = net_traces(circuit.PDM_CLK) + net_traces(circuit.PDM_DIN)
    if not routed:
        report.add(Status.UNWITNESSED, name, "(no routes)")
    elif not xl or not pdm:
        report.add(Status.UNWITNESSED, name, f"xl_traces={len(xl)} pdm_traces={len(pdm)}")
    else:
        gaps = [float(a.geometry.distance(b.geometry)) for a in pdm for b in xl if a.layer == b.layer]
        if not gaps:
            report.add(Status.PASS, name, "no shared layer")
        elif min(gaps) < PDM_XL_MIN_SPACING - EPSILON_MM:
            report.add(Status.FAIL, name, f"min gap={min(gaps):.3f} mm")
        else:
            report.add(Status.PASS, name, f"min gap={min(gaps):.3f} mm")

    # NFC1 / NFC2 legs symmetric.
    name = f"intent: NFC1 / NFC2 routed length within {NFC_LENGTH_MATCH:.0%}, equal via counts"
    if not routed:
        report.add(Status.UNWITNESSED, name, "(no routes)")
    else:
        l1 = sum(item.length for item in net_traces(circuit.NFC1))
        l2 = sum(item.length for item in net_traces(circuit.NFC2))
        v1, v2 = net_vias(circuit.NFC1), net_vias(circuit.NFC2)
        detail = f"NFC1={l1:.2f} mm / {v1} vias, NFC2={l2:.2f} mm / {v2} vias"
        if l1 == 0.0 or l2 == 0.0:
            report.add(Status.FAIL, name, f"{detail}: a leg has no trace")
        elif abs(l1 - l2) > NFC_LENGTH_MATCH * max(l1, l2) or v1 != v2:
            report.add(Status.FAIL, name, detail)
        else:
            report.add(Status.PASS, name, detail)

    report.add(
        Status.NOTE,
        "intent not checked here",
        "nothing fast between crystal and module; pads 8-10 nets leave east of the crystal; "
        "TVS anode own GND via: inspect in Warp / the board viewer",
    )


# --- Helpers ------------------------------------------------------------------------------


def net_name(net: Any) -> str:
    return "<no net>" if net is None else str(net.name)


def different_nets(a: Item, b: Item) -> bool:
    return a.net is None or b.net is None or a.net is not b.net


def describe(item: Item) -> str:
    x, y = item.geometry.centroid.coords[0]
    return f"{item.kind.value}[{net_name(item.net)}]@({x:.2f},{y:.2f})"


def load_design(target: str) -> type[Design]:
    module_name, _, class_name = target.rpartition(".")
    if not module_name:
        raise ValueError(f"expected <module.path.DesignClass>, got {target!r}")
    module = importlib.import_module(module_name)
    cls = module.__dict__.get(class_name)
    if not (isinstance(cls, type) and issubclass(cls, Design)):
        raise TypeError(f"{target} is not a jitx Design class")
    return cls


def rules_of(rd: Any) -> tuple[list[UnaryDesignConstraint], list[BinaryDesignConstraint], int]:
    declared = [rule for _, rule in visit(rd.root, DesignConstraint)]
    widths = [r for r in declared if isinstance(r, UnaryDesignConstraint) and r.trace_width_constraint is not None]
    clearances = [r for r in declared if isinstance(r, BinaryDesignConstraint) and r.clearance_constraint is not None]
    return widths, clearances, len(declared)


def print_report(report: Report) -> int:
    for line in report.lines:
        print(f"{line.status.value:<11} {line.name}: {line.detail}")
    fails = report.count(Status.FAIL)
    print(
        f"summary: pass={report.count(Status.PASS)} fail={fails} "
        f"unwitnessed={report.count(Status.UNWITNESSED)} notes={report.count(Status.NOTE)}"
    )
    return 1 if fails else 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("design", help="module.path.DesignClass")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        design = load_design(args.design)
    except (ImportError, ValueError, TypeError) as exc:
        print(f"could not run: {exc}")
        return 2
    layout = Path(LAYOUT_FILE)
    print(f"design: {args.design}")
    print(f"layout: {layout.resolve() if layout.exists() else f'{LAYOUT_FILE} absent (code placements only)'}")
    try:
        with jitx.runtime as r:
            rd = r.submit(design)
            rd.capture()
            issues = r.issues(rd)
            items = collect(rd)
            widths, clearances, declared = rules_of(rd)
            routes = [route for _, route in visit(rd.root, Route)]
            normalize = rd.layers.normalize
            counts = {kind: sum(1 for item in items if item.kind is kind) for kind in Kind}
            print(
                f"copper: routes={len(routes)} trace_shapes={counts[Kind.TRACE]} "
                f"via_layers={counts[Kind.VIA]} pad_layers={counts[Kind.PAD]} pours={counts[Kind.POUR]}"
            )
            print(f"rules: declared={declared} width={len(widths)} clearance={len(clearances)}")
            report = Report()
            check_routes(report, routes)
            check_widths(report, widths, items, normalize)
            check_clearances(report, clearances, items, normalize)
            check_connectivity(report, items)
            check_issues(report, issues, items)
            check_intent(report, rd, items)
    except Exception:  # runtime, submit, capture or a check could not complete: nothing verified
        logging.getLogger(__name__).exception("could not run")
        return 2
    return print_report(report)


if __name__ == "__main__":
    sys.exit(main())
