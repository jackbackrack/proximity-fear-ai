"""cir-03 LED rings + LED power switch.

Expected values come from their sources, not from ``led_rings.py``:
- WS2812C-2020-V6/W (``datasheets/WS2812C-2020-V6_W.spec.md``): pins 1 DO,
  2 GND, 3 DI, 4 VDD; 100 nF per LED and 33 ohm on the first DIN (project rules).
- ARCHITECTURE.md Object-Hierarchy Decisions: rings of 10, 16 and 24 LEDs at
  9.5, 15.5 and 21.5 mm, one chain inner -> middle -> outer. Board: 50 mm
  circle, 1 mm rim keepout (parts within r 24 mm); centre zone r < 7.5 mm.
- AO3401A / BSS138 spec notes: high-side P-FET, source to the supply, drain
  to load; gate pull-up to source; N-FET gate pull-down.
- Supply is SYS (port ``vin``), not VBAT: AN1149 p.5 keeps the system load off
  the charger output (ARCHITECTURE Power Tree, A-01). SYS max on USB is
  VBUS - VF(SS14, light load ~0.3 V, SS14 p.2 Fig. 3): ~4.95 V at USB 2.0
  5.25 V, ~5.2 V at a 5.5 V Type-C source (re-audit N-03). WS2812C VDD max
  5.3 V (p.2); VIH = 0.55 VDD (p.3) <= nRF VOH min VDD - 0.4 V at 0.5 mA
  (PS p.156) with 3V3 at -1.5 % (AP2112K) at the USB 2.0 corner; AO3401A VGS
  within +-12 V.
- SYS reservoir at the switch input, 4.7-10 uF X5R (re-audit N-06).
- All-white load 50 x 3 x 5 mA = 750 mA (WS2812C p.1).
- Copper clearance floor 0.15 mm (cir-03 brief; above JLCPCB's 0.1 mm).
- Courtyards: no overlap and >= 0.10 mm between any two (user board review).

The geometry tests submit the design to the running JITX runtime, because the
queried passives only get land patterns there.
"""

import math
import unittest
from itertools import pairwise

import jitx
from jitx.feature import Courtyard
from jitx.inspect import Trace, visit
from jitx.landpattern import Pad, PadShape
from jitx.shapes import Shape
from jitx.test import TestCase
from jitx.transform import Transform
from jitx.units import V, nF, ohm, uF
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry

from proximity_fear.circuits.led_rings import LEDRings, TestDesign
from proximity_fear.components.leds.worldsemi_WS2812C_2020 import WS2812C_2020_V6

RING_RADII = (9.5, 15.5, 21.5)
RING_COUNTS = (10, 16, 24)
N_LEDS = 50
PART_RADIUS_MAX = 25.0 - 1.0
CENTRE_ZONE_R = 7.5
PAD_CLEARANCE_MIN = 0.15
COURTYARD_GAP_MIN = 0.10  # user requirement: same-side courtyards >= 0.10 mm apart
# WS2812C pad rows sit +-0.55 mm about the body centre (spec note "PCB Solder
# Pad"), so an inner-ring DO on its outer row and a middle-ring DI on its inner
# row on the same radius are (15.5 - 9.5) - 2 x 0.55 = 4.9 mm apart.
HOP_INNER_TO_MIDDLE = 15.5 - 9.5 - 2 * 0.55


def _pad_centre(led: WS2812C_2020_V6, number: int) -> tuple[float, float]:
    """Centre of the LED's land-pattern pad ``number``, in the rings' frame."""
    placement = led.transform
    pad = led.landpattern.p[number]
    for trace, candidate in visit(led, Pad):
        if candidate is pad:
            if placement is None or trace.transform is None or pad.transform is None:
                raise AssertionError("unresolved pad frame")
            x, y = (placement * trace.transform * pad.transform).translation
            return (x, y)
    raise AssertionError("pad not found in component")


class LEDRingsConnectivity(TestCase):
    def setUp(self) -> None:
        circuit = TestDesign().circuit
        assert isinstance(circuit, LEDRings)
        self.c = circuit
        self.leds = [led for ring in circuit.rings for led in ring]
        self.caps = [cap for ring in circuit.ring_caps for cap in ring]

    def test_ring_shape(self) -> None:
        self.assertEqual(tuple(len(r) for r in self.c.rings), RING_COUNTS)
        self.assertEqual(tuple(len(r) for r in self.c.ring_caps), RING_COUNTS)
        self.assertEqual(len(self.leds), N_LEDS)

    def test_pin_numbers(self) -> None:
        led = self.leds[0]
        mapping = led.pad_mapping
        self.assertIs(mapping[led.DO], led.landpattern.p[1])
        self.assertIs(mapping[led.GND], led.landpattern.p[2])
        self.assertIs(mapping[led.DI], led.landpattern.p[3])
        self.assertIs(mapping[led.VDD], led.landpattern.p[4])

    def test_vled_and_ground(self) -> None:
        c = self.c
        self.assertCountEqual(list(c.VLED), [c.switch.vled.Vp, *(led.VDD for led in self.leds)])
        self.assertCountEqual(
            list(c.GND),
            [c.vin.Vn, c.switch.vled.Vn, *(led.GND for led in self.leds), *(cap.p2 for cap in self.caps)],
        )
        self.assertNotIn(c.vin.Vp, list(c.VLED))

    def test_decoupling_per_led(self) -> None:
        for led, cap, st in zip(self.leds, self.caps, self.c.c_led_st, strict=True):
            self.assertCountEqual(list(st), [cap.p1, led.VDD])
            self.assertAlmostEqual(cap.capacitance, 100 * nF)
            self.assertEqual(cap.temperature_coefficient_code, "X7R")

    def test_chain_inner_middle_outer(self) -> None:
        c = self.c
        self.assertCountEqual(list(c.DIN), [c.din, c.r_din.p1])
        self.assertCountEqual(list(c.DIN_LED), [c.r_din.p2, c.rings[0][0].DI])
        self.assertAlmostEqual(c.r_din.resistance, 33 * ohm)
        self.assertEqual(len(c.DATA), N_LEDS - 1)
        for k, net in enumerate(c.DATA):
            self.assertCountEqual(list(net), [self.leds[k].DO, self.leds[k + 1].DI])
        # ring hops: last of inner -> first of middle, last of middle -> first of outer
        self.assertCountEqual(list(c.DATA[9]), [c.rings[0][9].DO, c.rings[1][0].DI])
        self.assertCountEqual(list(c.DATA[25]), [c.rings[1][15].DO, c.rings[2][0].DI])

    def test_switch(self) -> None:
        s = self.c.switch
        self.assertCountEqual(list(s.VIN), [s.vin.Vp, s.q_switch.S, s.r_gate_pu.p2])
        self.assertCountEqual(list(s.VLED), [s.vled.Vp, s.q_switch.D, s.c_soft.p2])
        self.assertCountEqual(list(s.GATE), [s.q_switch.G, s.r_gate_pu.p1, s.r_gate_on.p1, s.c_soft.p1])
        self.assertCountEqual(list(s.GATE_PULL), [s.r_gate_on.p2, s.q_drive.D])
        self.assertCountEqual(list(s.ENABLE), [s.enable, s.q_drive.G, s.r_enable_pd.p1])
        self.assertCountEqual(
            list(s.GND), [s.vin.Vn, s.vled.Vn, s.q_drive.S, s.r_enable_pd.p2, s.c_bulk.p2, s.c_sys.p2]
        )
        self.assertCountEqual(list(s.c_bulk_st), [s.c_bulk.p1, s.q_switch.D])
        self.assertAlmostEqual(s.c_bulk.capacitance, 10 * uF)
        # SYS reservoir on the FET source (N-06): 4.7-10 uF X5R/X7R, rated >= 10 V.
        self.assertCountEqual(list(s.c_sys_st), [s.c_sys.p1, s.q_switch.S])
        self.assertGreaterEqual(s.c_sys.capacitance, 4.7 * uF)
        self.assertLessEqual(s.c_sys.capacitance, 10 * uF)
        self.assertIn(s.c_sys.temperature_coefficient_code, ("X5R", "X7R"))
        self.assertGreaterEqual(s.c_sys.rated_voltage_dc, 10 * V)
        self.assertAlmostEqual(s.r_gate_pu.resistance, 100e3 * ohm)
        self.assertAlmostEqual(s.r_enable_pd.resistance, 100e3 * ohm)
        # boundary: rings' vin is the switch's vin (SYS)
        self.assertCountEqual(list(self.c.ENABLE), [self.c.enable, s.enable])
        self.assertCountEqual(list(self.c.VIN), [self.c.vin, s.vin])

    def test_sys_range_limits(self) -> None:
        s = self.c.switch
        sys_min = 3.0  # VBAT floor, ARCHITECTURE Power Tree
        sys_usb2 = 5.25 - 0.3  # USB 2.0 max less light-load SS14 VF
        sys_max = 5.5 - 0.3  # 5.5 V Type-C source
        self.assertLessEqual(sys_max, 5.3)  # WS2812C VDD abs max (p.2)
        voh_min = 3.3 * (1 - 0.015) - 0.4  # AP2112K +-1.5 %, PS p.156 VOH,SD
        self.assertGreater(voh_min, 0.55 * sys_usb2)  # WS2812C VIH (p.3) at the USB 2.0 corner
        # Type-C 5.5 V corner: paper shortfall <= 0.02 V, accepted in the docstring.
        self.assertLess(0.55 * sys_max - voh_min, 0.02)
        ratio = s.r_gate_pu.resistance / (s.r_gate_pu.resistance + s.r_gate_on.resistance)
        self.assertLess(sys_max * ratio, 12.0)  # AO3401A VGS abs max (p.1)
        self.assertGreater(3.4 * ratio, 2.5)  # RDS(on) rated at VGS -2.5 V at the 3.4 V cut-off
        self.assertGreater(sys_min - 1.6, 0)  # gate plateau reachable: soft start works at 3.0 V
        all_white = 50 * 3 * 0.005
        self.assertAlmostEqual(all_white, 0.750)
        self.assertLess(all_white * 0.085, 0.07)  # drop at VGS -2.5 V rating (p.2)

    def test_leds_on_rings(self) -> None:
        for radius, ring in zip(RING_RADII, self.c.rings, strict=True):
            for led in ring:
                placement = led.transform
                assert placement is not None
                x, y = placement.translation
                self.assertAlmostEqual(math.hypot(x, y), radius, places=6)

    def test_do_faces_next_di(self) -> None:
        """Within a ring, DO of LED k is nearer LED k+1's DI than the LED centres are."""
        for ring in self.c.rings:
            for a, b in pairwise(ring):
                pa = a.transform
                pb = b.transform
                assert pa is not None and pb is not None
                centres = math.dist(pa.translation, pb.translation)
                link = math.dist(_pad_centre(a, 1), _pad_centre(b, 3))
                # facing pads are 2 x 0.92 mm closer along the tangent (one 1.1 mm
                # row step across); turned the wrong way they would be farther
                self.assertLess(link, centres - 1.0)

    def test_ring_hops_short(self) -> None:
        r = self.c.rings
        hop1 = math.dist(_pad_centre(r[0][-1], 1), _pad_centre(r[1][0], 3))
        self.assertAlmostEqual(hop1, HOP_INNER_TO_MIDDLE, delta=0.15)
        hop2 = math.dist(_pad_centre(r[1][-1], 1), _pad_centre(r[2][0], 3))
        self.assertLess(hop2, 7.0)


def _pad_geometry(component: jitx.Component, trace: Trace, pad: Pad) -> BaseGeometry:
    """Pad copper in the rings' frame."""
    shape = pad.shape
    if isinstance(shape, PadShape):
        shape = shape.shape
    return _geometry(component, trace, pad.transform, shape)


def _geometry(component: jitx.Component, trace: Trace, local: Transform | None, shape: Shape) -> BaseGeometry:
    placement = component.transform
    if placement is None or trace.transform is None:
        raise AssertionError("unresolved frame")
    frame = placement * trace.transform
    if local is not None:
        frame = frame * local
    return (frame * shape).to_shapely().g


class LEDRingsGeometry(unittest.TestCase):
    """Realized land patterns (queried 0402s included) from the running runtime."""

    courtyards: list[BaseGeometry]
    pads: list[tuple[int, BaseGeometry]]
    vdd_pairs: list[tuple[BaseGeometry, BaseGeometry]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.courtyards = []
        cls.pads = []
        cls.vdd_pairs = []
        with jitx.runtime as r:
            rd = r.submit(TestDesign)
            circ = rd.root.circuit
            assert isinstance(circ, LEDRings)
            owner = 0
            for leds, caps in zip(circ.rings, circ.ring_caps, strict=True):
                for led, cap in zip(leds, caps, strict=True):
                    by_part: list[list[BaseGeometry]] = []
                    vdd: list[BaseGeometry] = []
                    for comp in (led, cap):
                        owner += 1
                        for trace, cy in visit(comp, Courtyard):
                            cls.courtyards.append(_geometry(comp, trace, None, cy.shape))
                        geoms: list[BaseGeometry] = []
                        for trace, pad in visit(comp, Pad):
                            geom = _pad_geometry(comp, trace, pad)
                            geoms.append(geom)
                            cls.pads.append((owner, geom))
                            if pad is led.landpattern.p[4]:
                                vdd.append(geom)
                        by_part.append(geoms)
                    assert len(vdd) == 1
                    cls.vdd_pairs.append((vdd[0], min(by_part[1], key=vdd[0].distance)))

    def test_counts(self) -> None:
        self.assertEqual(len(self.courtyards), 2 * N_LEDS)
        self.assertEqual(len(self.pads), N_LEDS * 4 + N_LEDS * 2)

    def test_no_courtyard_overlap(self) -> None:
        # User requirement (board review): courtyards never overlap or abut; >= 0.10 mm apart.
        for i, a in enumerate(self.courtyards):
            for b in self.courtyards[i + 1 :]:
                self.assertFalse(a.intersects(b))
                self.assertGreaterEqual(a.distance(b), COURTYARD_GAP_MIN)

    def test_inside_rim_and_outside_centre_zone(self) -> None:
        for cy in self.courtyards:
            assert isinstance(cy, Polygon)
            for x, y in cy.exterior.coords:
                self.assertLessEqual(math.hypot(x, y), PART_RADIUS_MAX)
            # nearest courtyard point to the board centre
            self.assertGreater(cy.distance(Point(0.0, 0.0)), CENTRE_ZONE_R)

    def test_pad_clearance(self) -> None:
        for i, (oa, a) in enumerate(self.pads):
            for ob, b in self.pads[i + 1 :]:
                if oa != ob:
                    self.assertGreaterEqual(a.distance(b), PAD_CLEARANCE_MIN)

    def test_cap_beside_vdd(self) -> None:
        for vdd, p1 in self.vdd_pairs:
            self.assertLess(vdd.distance(p1), 0.6)
