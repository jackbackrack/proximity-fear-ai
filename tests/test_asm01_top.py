"""asm-01 top level against ARCHITECTURE.md (Power Tree, Interface Map, Board) and PLAN asm-01.

Expected connections come from the architecture, not from main.py:
- Power Tree (Phase 3b A-01): VBUS feeds the charger / power path and the nRF VBUS pad;
  SYS feeds the AP2112K and the LED switch; VBAT has no load outside the power block;
  3V3 feeds the nRF module, ToF, IR TX / RX and the mic; VLED is the switched
  LED rail.
- Interface Map: USB D+/D- from the USB-C block to the nRF; I2C nRF -> ToF; LED chain
  nRF -> ring DIN; PDM nRF -> mic; IR TX / RX; NFC1/NFC2 -> antenna front end.
- PLAN asm-01: FastGPIO x2 (LED data, IR TX), PDM x1, GPIO x6 (LED enable, IR RX, XSHUT,
  ToF INT, button, charge STAT) plus the IR receiver supply enable (A-04, so x7), ADC x1
  (VBAT sense), two 2.2 kOhm I2C pull-ups to 3V3.
- ARCHITECTURE Board: 50 mm circle, 1 mm rim keepout -> every Top part inside r <= 24 mm;
  only the rings and the centre sensors on Top; the bottom-port mic on Bottom with its
  port hole at (+4.5, 0) (A-03).
- ARCHITECTURE Board / asm-01 rework: the USB-C tab puts J1's through-board shell slots and
  locating holes outside every LED ring: >= 0.3 mm from all Top ring copper, clear of the
  ring parts' courtyards.
"""

import math
import unittest

import jitx
import shapely
from jitx.component import Component
from jitx.feature import Courtyard, Cutout
from jitx.inspect import visit
from jitx.issue import GeometricOverlap
from jitx.landpattern import Pad, PadShape
from jitx.layerindex import Side
from jitx.net import Net, Port
from jitx.run.runtime import RuntimeDesign
from jitx.shapes import Shape
from jitx.test import TestCase
from jitx.transform import Transform
from jitx.units import ohm
from jitxlib.landpatterns.pads import NPTHPad
from shapely import affinity
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from proximity_fear.components.mcus.ebyte_E73_2G4M08S1CX import E73_2G4M08S1CX
from proximity_fear.designs.badge import USB_AT, BadgeCircuit, board_outline
from proximity_fear.main import ProximityFearBadge

USABLE_RADIUS = 25.0 - 1.0  # ARCHITECTURE Board: 50 mm circle less the 1 mm case-lip band
I2C_PULL_UP_OHMS = 2200.0  # PLAN asm-01
TOP_OWNERS = ("rings.", "sensors.")
MIC_PORT = (4.5, 0.0)  # ARCHITECTURE Board centre zone  # ARCHITECTURE Board "Front (Top)"
J1_TO_RING_COPPER = 0.3  # mm, asm-01 rework requirement


def members(net: Net) -> list[object]:
    return [*net]


class TopLevelTest(TestCase):
    def setUp(self) -> None:
        circuit = ProximityFearBadge().circuit
        assert isinstance(circuit, BadgeCircuit)
        self.c = circuit

    def assert_members(self, net: Net, expected: list[Port]) -> None:
        got = members(net)
        for port in expected:
            self.assertIn(port, got)

    def test_power_rails(self) -> None:
        c = self.c
        self.assert_members(c.VBUS, [c.power.vbus.Vp, c.nrf.vbus.Vp])
        self.assert_members(c.VBAT, [c.power.vbat.Vp])
        self.assert_members(c.SYS, [c.power.sys.Vp, c.rings.vin.Vp])
        self.assertNotIn(c.rings.vin.Vp, members(c.VBAT))  # LED switch source is SYS, not VBAT
        self.assert_members(
            c.V3V3, [c.power.v3v3.Vp, c.nrf.v3v3.Vp, c.sensors.v3v3.Vp, c.mic.v3v3.Vp, c.r_sda.p2, c.r_scl.p2]
        )
        self.assert_members(c.VLED, [c.rings.vled.Vp])
        self.assert_members(
            c.GND,
            [
                c.power.vbus.Vn,
                c.power.vbat.Vn,
                c.power.sys.Vn,
                c.power.v3v3.Vn,
                c.nrf.v3v3.Vn,
                c.nrf.vbus.Vn,
                c.rings.vin.Vn,
                c.rings.vled.Vn,
                c.sensors.v3v3.Vn,
                c.mic.v3v3.Vn,
                c.nfc.gnd,
            ],
        )
        # No rail shorted onto another (each source port on one rail only).
        rails = [c.VBUS, c.VBAT, c.SYS, c.V3V3, c.VLED, c.GND]
        for port in [c.power.vbus.Vp, c.power.vbat.Vp, c.power.sys.Vp, c.power.v3v3.Vp, c.rings.vled.Vp]:
            self.assertEqual(sum(port in members(r) for r in rails), 1)

    def test_vled_reaches_the_leds(self) -> None:
        # LEDRings' new vled port joins the switch output, which feeds every LED VDD.
        c = self.c
        self.assert_members(c.rings.VLED_OUT, [c.rings.vled, c.rings.switch.vled])
        self.assertIn(c.rings.switch.vled.Vp, members(c.rings.VLED))

    def test_fixed_links(self) -> None:
        c = self.c
        self.assert_members(c.USB, [c.power.usb, c.nrf.usb])
        self.assertCountEqual(members(c.NFC1), [c.nrf.nfc1, c.nfc.nfc1])
        self.assertCountEqual(members(c.NFC2), [c.nrf.nfc2, c.nfc.nfc2])

    def test_pin_assigned_links(self) -> None:
        c = self.c
        # (net, the consumer ports it must carry); the remaining member is the E73 require() port.
        links: list[tuple[Net, list[Port]]] = [
            (c.I2C_SDA, [c.sensors.i2c.sda, c.r_sda.p1]),
            (c.I2C_SCL, [c.sensors.i2c.scl, c.r_scl.p1]),
            (c.LED_DATA, [c.rings.din]),
            (c.IR_TX, [c.sensors.ir_tx]),
            (c.PDM_CLK, [c.mic.pdm_clk]),
            (c.PDM_DIN, [c.mic.pdm_din]),
            (c.LED_EN, [c.rings.enable]),
            (c.IR_RX, [c.sensors.ir_rx]),
            (c.TOF_XSHUT, [c.sensors.xshut]),
            (c.TOF_INT, [c.sensors.tof_int]),
            (c.BUTTON, [c.nrf.button]),
            (c.CHG_STAT, [c.power.chg_stat]),
            (c.IR_RX_EN, [c.sensors.ir_rx_en]),
            (c.VBAT_SENSE, [c.power.vbat_sense]),
        ]
        provider_ports: list[object] = []
        for net, consumers in links:
            got = members(net)
            self.assertEqual(len(got), len(consumers) + 1, net)
            for port in consumers:
                self.assertIn(port, got)
            provider_ports.extend(p for p in got if not any(p is q for q in consumers))
        # 13 distinct required ports: no two signals share an nRF pin request.
        self.assertEqual(len({id(p) for p in provider_ports}), len(links))

    def test_i2c_pull_ups(self) -> None:
        c = self.c
        for r in (c.r_sda, c.r_scl):
            self.assertAlmostEqual(r.resistance / ohm, I2C_PULL_UP_OHMS)
            self.assertIn(r.p2, members(c.V3V3))

    def test_top_parts_inside_rim(self) -> None:
        top_parts = 0
        for trace, comp in visit(self.c, Component):
            # Bottom parts are placed with Circuit.place(), which the runtime resolves.
            placed = None if comp.transform is None or trace.transform is None else trace.transform * comp.transform
            if placed is not None and getattr(placed, "side", Side.Top) == Side.Top:
                top_parts += 1
                self.assertTrue(str(trace.path).startswith(TOP_OWNERS), trace.path)
        # 50 LEDs + 50 caps; ToF + 2 caps; IR LED; IR RX + filter R and C.
        self.assertEqual(top_parts, 50 + 50 + 3 + 1 + 3)
        for trace, pad in visit(self.c, Pad):
            if trace.transform is None or pad.transform is None:
                continue
            if getattr(trace.transform, "side", Side.Top) != Side.Top:
                continue
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            outline = (trace.transform * pad.transform * shape).to_shapely().g
            assert isinstance(outline, shapely.Polygon)
            far = max(math.hypot(x, y) for x, y in outline.exterior.coords)
            self.assertLessEqual(far, USABLE_RADIUS, f"{trace.path} pad at r {far:.2f}")

    def test_usb_slots_clear_the_rings(self) -> None:
        # J1 sits on Bottom at USB_AT, rotation 0: Bottom mirrors x about J1's origin.
        x0, y0 = USB_AT
        through: list[shapely.Polygon] = []
        for ptrace, pad in visit(self.c.power.usb_c.j1, Pad):
            if not list(visit(pad, Cutout)) or pad.transform is None:
                continue
            local = pad.transform if ptrace.transform is None else ptrace.transform * pad.transform
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            g = (local * shape).to_shapely().g
            assert isinstance(g, shapely.Polygon)
            through.append(affinity.translate(affinity.scale(g, -1.0, 1.0, origin=(0, 0)), x0, y0))
        self.assertEqual(len(through), 6)  # 4 shell slots + 2 locating holes (HRO drawing)
        ring_copper: list[shapely.Polygon] = []
        for trace, pad in visit(self.c.rings, Pad):
            if trace.transform is None or pad.transform is None:
                continue
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            g = (trace.transform * pad.transform * shape).to_shapely().g
            assert isinstance(g, shapely.Polygon)
            ring_copper.append(g)
        ring_courtyards: list[shapely.Polygon] = []
        for trace, courtyard in visit(self.c.rings, Courtyard):
            if trace.transform is None:
                continue
            g = (trace.transform * courtyard.shape).to_shapely().g
            assert isinstance(g, shapely.Polygon)
            ring_courtyards.append(g)
        slots = shapely.union_all(through)
        self.assertGreaterEqual(shapely.union_all(ring_copper).distance(slots), J1_TO_RING_COPPER)
        self.assertGreater(shapely.union_all(ring_courtyards).distance(slots), 0.0)

    def test_mic_on_bottom_port_at_spot(self) -> None:
        holes = []
        mic = self.c.mic.transform  # visit() from the mic excludes the mic's own placement
        for trace, pad in visit(self.c.mic, NPTHPad):
            assert mic is not None and trace.transform is not None and pad.transform is not None
            placed = mic * trace.transform * pad.transform
            holes.append(placed)
        self.assertEqual(len(holes), 1)  # the one acoustic port hole
        self.assertEqual(getattr(holes[0], "side", Side.Top), Side.Bottom)
        x, y = holes[0].translation
        self.assertAlmostEqual(x, MIC_PORT[0], places=6)
        self.assertAlmostEqual(y, MIC_PORT[1], places=6)


# Frozen GPIO map (asm-01 M-8 R-03; main.py docstring table): signal net -> E73 port.
FROZEN_PINS = {
    "P0_04": "PDM_CLK",
    "P0_12": "PDM_DIN",
    "P0_07": "I2C_SDA",
    "P0_15": "I2C_SCL",
    "P0_13": "LED_DATA",
    "P0_17": "IR_TX",
    "P0_20": "TOF_XSHUT",
    "P0_22": "TOF_INT",
    "P0_24": "IR_RX",
    "P1_02": "IR_RX_EN",
    "P1_04": "BUTTON",
    "P0_29": "LED_EN",
    "P0_31": "CHG_STAT",
    "P1_13": "CHG_EN",
    "P0_30": "VBAT_SENSE",
}
# PS p.609 / re-audit R-03: nothing on the pads routed between or beside XL1/XL2.
LFXO_NEIGHBOURS = ("P0_26", "P0_06", "P0_05", "P0_08")
OUTLINE_TOLERANCE = 1e-3  # mm, polygonised arcs
COURTYARD_GAP = 0.10  # mm, user requirement: same-side courtyards never overlap, >= 0.10 mm apart
COURTYARD_TOLERANCE = 1e-4  # mm, float noise only


def owner_of(path: str) -> str:
    """The component a land-pattern feature path belongs to."""
    return path.split(".landpattern", 1)[0]


def to_board(shape: Shape, transform: Transform) -> shapely.Polygon:
    """A courtyard in the board frame: every vertex through the placement (Bottom mirrors x)."""
    local = shape.to_shapely().g
    ox, oy = transform * (0.0, 0.0)
    ux, uy = transform * (1.0, 0.0)
    vx, vy = transform * (0.0, 1.0)
    g = affinity.affine_transform(local, [ux - ox, vx - ox, uy - oy, vy - oy, ox, oy])
    assert isinstance(g, shapely.Polygon), g.geom_type
    return g


class CapturedLayoutTest(unittest.TestCase):
    """Runtime capture: Circuit.place() positions and the solved pin assignment."""

    rd: RuntimeDesign[ProximityFearBadge]
    issues_complete: bool
    overlaps: list[GeometricOverlap]

    @classmethod
    def setUpClass(cls) -> None:
        with jitx.runtime as runtime:
            cls.rd = runtime.submit(ProximityFearBadge)
            cls.rd.capture()
            report = runtime.issues(cls.rd)
            cls.issues_complete = report.complete
            cls.overlaps = [issue for issue in report if isinstance(issue, GeometricOverlap)]

    def test_every_part_placed_on_the_board(self) -> None:
        # The runtime parks a part with no placement off the board, so "inside the
        # outline" is the placement check.
        outline = shapely.Polygon(board_outline()).buffer(OUTLINE_TOLERANCE)
        components = 0
        for trace, comp in visit(self.rd.root, Component):
            components += 1
            self.assertIsNotNone(comp.transform, trace.path)
            self.assertIsNotNone(trace.transform, trace.path)
        self.assertGreater(components, 150)
        pads = 0
        for trace, pad in visit(self.rd.root, Pad):
            assert trace.transform is not None and pad.transform is not None, trace.path
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            g = (trace.transform * pad.transform * shape).to_shapely().g
            pads += 1
            self.assertTrue(outline.contains(g), f"{trace.path} pad outside the board at {g.bounds}")
        self.assertGreater(pads, 400)

    def test_no_geometric_overlaps(self) -> None:
        # The runtime's physical-design report (as scripts/check_layout.py reads it): no copper
        # of any kind overlaps, e.g. the cir-04 100 nF GND pad that once touched the ToF
        # AVDDVCSEL (3V3) pad.
        self.assertTrue(self.issues_complete, "issue report incomplete (background tasks still running)")
        self.assertEqual([issue.text for issue in self.overlaps], [])

    def test_frozen_pin_map(self) -> None:
        circuit = self.rd.root.circuit
        assert isinstance(circuit, BadgeCircuit)
        module = circuit.nrf.module
        for port_name in dir(E73_2G4M08S1CX):
            if not port_name.startswith(("P0_", "P1_")) or port_name == "P1_00":
                continue
            net = self.rd.nets.find(getattr(module, port_name))
            expected = FROZEN_PINS.get(port_name)
            self.assertEqual(None if net is None else net.name, expected, port_name)
        for port_name in LFXO_NEIGHBOURS:
            self.assertNotIn(port_name, FROZEN_PINS)

    def test_courtyards_clear_on_each_side(self) -> None:
        # User requirement (board review): no two component courtyards on one side overlap,
        # and neighbours keep >= 0.10 mm between them (abutting at 0.0 fails). Every
        # courtyard of every component counts; a Bottom placement mirrors the courtyard and
        # its side (``trace.transform * side``, as scripts/check_layout.py maps pad layers).
        # Opposite-side courtyards (the TC2030's three pin-tip circles, local side Bottom)
        # land on the far side and are checked like any other courtyard there. One
        # exception: pairs within one component are not placement conflicts; the only ones
        # allowed are the E73's IPEX keep-clear against its own module body and the TC2030's
        # two right-hand pin-tip circles (0.041 mm apart, no overlap).
        courtyards: list[tuple[str, int, BaseGeometry]] = []
        opposite_side: list[str] = []
        for trace, courtyard in visit(self.rd.root, Courtyard):
            assert trace.transform is not None, trace.path
            path = str(trace.path)
            if courtyard.side == Side.Bottom:
                opposite_side.append(path)
            courtyards.append((path, int(trace.transform * courtyard.side), to_board(courtyard.shape, trace.transform)))
        self.assertGreater(len(courtyards), 150)
        self.assertEqual(
            sorted(opposite_side), [f"circuit.nrf.swd.landpattern.pin_tip_courtyards[{i}]" for i in range(3)]
        )
        tree = STRtree([g for _, _, g in courtyards])
        offending: list[str] = []
        own_overlaps: set[str] = set()
        for i, (path, side, g) in enumerate(courtyards):
            for j in tree.query(g, predicate="dwithin", distance=COURTYARD_GAP):
                other, other_side, h = courtyards[int(j)]
                if int(j) <= i or other_side != side:
                    continue
                gap = float(g.distance(h))
                if g.intersects(h) or gap < COURTYARD_GAP - COURTYARD_TOLERANCE:
                    if owner_of(path) == owner_of(other):
                        own_overlaps.add(f"{path} x {other}")
                        continue
                    overlap = float(g.intersection(h).area)
                    offending.append(f"{Side(side).name}: {path} x {other} gap={gap:.3f} overlap={overlap:.3f} mm2")
        if offending:
            print("\n".join(["courtyard violations:", *offending]))
        self.assertLessEqual(
            own_overlaps,
            {
                "circuit.nrf.module.landpattern.courtyard x circuit.nrf.module.landpattern.ipex_keep_clear",
                # Two pin-tip circles of the same plug, 2.032 mm apart (Ø1.991 each): they
                # do not overlap but sit 0.041 mm apart by the drawing's hole pitch.
                "circuit.nrf.swd.landpattern.pin_tip_courtyards[1] x circuit.nrf.swd.landpattern.pin_tip_courtyards[2]",
            },
        )
        self.assertEqual(offending, [])

    def test_nfc_legs_mirror_their_pads(self) -> None:
        # ov-nfc W3 / closure audit W-1: each leg's tuning cap sits on its own antenna pad's
        # side of the pads' centreline, and both legs are the same distance from their pad.
        antenna: dict[str, tuple[float, float]] = {}
        caps: dict[str, tuple[float, float]] = {}
        for trace, pad in visit(self.rd.root, Pad):
            path = str(trace.path)
            if not path.startswith(("circuit.nfc.antenna.", "circuit.nfc.c_tune")):
                continue
            net = self.rd.nets.find(pad)
            if net is None or net.name not in ("NFC1", "NFC2"):
                continue
            assert trace.transform is not None and pad.transform is not None
            x, y = (trace.transform * pad.transform).translation
            (antenna if path.startswith("circuit.nfc.antenna.") else caps)[net.name] = (x, y)
        self.assertEqual(sorted(antenna), ["NFC1", "NFC2"])
        self.assertEqual(sorted(caps), ["NFC1", "NFC2"])
        centre = (antenna["NFC1"][0] + antenna["NFC2"][0]) / 2
        for leg in ("NFC1", "NFC2"):
            self.assertGreater((caps[leg][0] - centre) * (antenna[leg][0] - centre), 0.0, leg)
        reach = [math.dist(caps[leg], antenna[leg]) for leg in ("NFC1", "NFC2")]
        self.assertAlmostEqual(reach[0], reach[1], delta=0.05)
