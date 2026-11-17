"""cir-04 centre sensors against the spec notes, the datasheets and ARCHITECTURE.md.

Expected values come from the sources, not from the circuit's constants:
- VL53L4CX DS13805: p.5 Figure 3 (supplies, grounds, 100 nF + 4.7 uF, 10 k on
  XSHUT / GPIO1, DNC open); p.24 Figure 19 (aperture positions, exclusion cones).
- IR11-21C p.3: IF 65 mA continuous, VF; BSS138 p.3 Fig.6: RDS(on) at 2.75 V.
- IRM-H638T p.2 application circuit: 47-220 ohm + >= 2.2 uF supply filter;
  p.3 Icc 0.4 typ / 0.7 max mA always on -> switched supply (A-04).
- AO3401A p.2: VGS(th) -0.5..-1.3 V, RDS(on) <= 85 mOhm at VGS -2.5 V; P-FET
  high-side, source to 3V3, gate pull-up so it is off with the GPIO undriven.
- ARCHITECTURE.md Board: ToF (0, 0), IR TX (0, +4.5), IR RX (-4.5, 0); centre
  zone r < 7.5 mm; mic at (+4.5, 0) belongs to cir-05.
"""

import math
from collections.abc import Sequence
from itertools import combinations

import jitx
import shapely
from jitx.component import Component
from jitx.feature import Courtyard
from jitx.inspect import visit
from jitx.landpattern import Pad, PadShape
from jitx.placement import Placement
from jitx.run.runtime import RuntimeDesign
from jitx.test import TestCase
from jitx.transform import Transform
from jitx.units import kohm, nF, ohm, uF

from proximity_fear.circuits.centre_sensors import CentreSensors, TestDesign

CENTRE_ZONE_R = 7.5
PAD_CLEARANCE = 0.15  # mm, Top pad copper to any other net's pad (cir-04 rework floor)
COURTYARD_GAP = 0.10  # mm, user board review: courtyards never overlap, >= 0.10 mm apart
# 0603 land-pattern half-extent (local x, local y), mm: resolved passives put their pads
# on the local y axis (p1 at +y), so the long half-extent is along y.
PASSIVE_HALF = (0.6, 1.3)
MIC_COURTYARD_LEFT = 4.5 - 3.65 / 2  # cir-05: mic at (+4.5, 0), courtyard 3.65 mm wide

# DS13805 p.24 Figure 19, in the component frame (pin 1 at +x, -y): the
# collector is 0.665 mm from the end opposite pin 1, and the emitter is 3 mm
# further on. Both are on the long axis. Datum A is the module top.
COLLECTOR_XY = (-2.2 + 0.665, 0.0)
EMITTER_XY = (-2.2 + 0.665 + 3.0, 0.0)
COLLECTOR_CONE = (0.22 / 2, 25.0 / 2)  # radius at datum A, half-angle
EMITTER_CONE = (0.38 / 2, 29.0 / 2)
DATUM_A_HEIGHT = 1.0  # spec note: 4.40 x 2.40 x 1.0 mm

# Body footprint (x, y) half-sizes in the component frame and height, mm.
IR_LED_BODY = (1.5, 0.75, 1.5)  # IR11-21C p.2: 3.0 x 1.5 x 1.5
IR_RX_BODY = (2.0, 2.5, 2.5)  # IRM-H638T p.6: 4.0 x 5.0 x 2.5 (model silkscreen axes)


def board_point(chain: Sequence[Placement | Transform | None], xy: tuple[float, float]) -> tuple[float, float]:
    """Map a point through the parent-to-child placement chain into the board frame."""
    x, y = xy
    for placement in reversed(chain):
        if placement is None:
            raise AssertionError("unplaced object in a fixed chain")
        (tx, ty), angle = placement.translation, math.radians(placement.rotation)
        x, y = tx + x * math.cos(angle) - y * math.sin(angle), ty + x * math.sin(angle) + y * math.cos(angle)
    return (round(x, 3), round(y, 3))


def body_gap(
    centre_chain: Sequence[Placement | Transform | None], half: tuple[float, float], p: tuple[float, float]
) -> float:
    """Horizontal distance from point ``p`` to a rectangular body (rotations are multiples of 90 deg)."""
    corners = [board_point(centre_chain, (sx * half[0], sy * half[1])) for sx in (-1, 1) for sy in (-1, 1)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    dx = max(min(xs) - p[0], 0.0, p[0] - max(xs))
    dy = max(min(ys) - p[1], 0.0, p[1] - max(ys))
    return math.hypot(dx, dy)


def cone_radius(cone: tuple[float, float], height: float) -> float:
    r0, half_angle = cone
    return r0 + max(height - DATUM_A_HEIGHT, 0.0) * math.tan(math.radians(half_angle))


class CentreSensorsTest(TestCase):
    def setUp(self) -> None:
        circuit = TestDesign().circuit
        assert isinstance(circuit, CentreSensors)
        self.c = circuit

    def test_tof_supply_and_grounds(self) -> None:
        t = self.c.tof
        u = t.u1
        self.assertCountEqual(list(t.V3V3), [t.v3v3.Vp, u.AVDD, u.AVDDVCSEL, t.r_xshut.p2, t.r_gpio1.p2])
        self.assertCountEqual(list(t.GND), [t.v3v3.Vn, u.AVSSVCSEL, u.GND, u.GND2, u.GND3, u.GND4, t.c_bulk.p2])
        self.assertCountEqual(list(t.c_hf_st), [t.c_hf.p1, u.AVDDVCSEL])
        self.assertCountEqual(list(t.c_hf_gnd_st), [t.c_hf.p2, u.AVSSVCSEL])
        self.assertCountEqual(list(t.c_bulk_st), [t.c_bulk.p1, u.AVDDVCSEL])
        self.assertAlmostEqual(t.c_hf.capacitance, 100 * nF)
        self.assertAlmostEqual(t.c_bulk.capacitance, 4.7 * uF)

    def test_tof_signals_and_pullups(self) -> None:
        t = self.c.tof
        u = t.u1
        self.assertCountEqual(list(t.SDA), [t.i2c.sda, u.SDA])
        self.assertCountEqual(list(t.SCL), [t.i2c.scl, u.SCL])
        self.assertCountEqual(list(t.XSHUT), [t.xshut, u.XSHUT, t.r_xshut.p1])
        self.assertCountEqual(list(t.TOF_INT), [t.tof_int, u.GPIO1, t.r_gpio1.p1])
        self.assertAlmostEqual(t.r_xshut.resistance, 10 * kohm)
        self.assertAlmostEqual(t.r_gpio1.resistance, 10 * kohm)
        # No I2C pull-ups in this circuit: the bus ones belong to the assembly.
        self.assertNotIn(u.SDA, list(t.V3V3))
        self.assertNotIn(u.SCL, list(t.V3V3))

    def test_ir_transmitter(self) -> None:
        x = self.c.ir_transmitter
        self.assertCountEqual(list(x.V3V3), [x.v3v3.Vp, x.r_led.p1])
        self.assertCountEqual(list(x.IR_LED_A), [x.r_led.p2, x.led.A])
        self.assertCountEqual(list(x.IR_LED_K), [x.led.C, x.q_drive.D])
        self.assertCountEqual(list(x.GND), [x.v3v3.Vn, x.q_drive.S, x.r_gate_pd.p2])
        self.assertCountEqual(list(x.IR_TX), [x.ir_tx, x.q_drive.G, x.r_gate_pd.p1])

    def test_ir_led_current_within_rating(self) -> None:
        r = self.c.ir_transmitter.r_led.resistance.to(ohm).magnitude
        # Highest case: 3V3 +2 % (3.37 V), VF 1.1 V, RDS(on) 2 ohm (cold) -> < 65 mA.
        self.assertLess((3.37 - 1.1) / (r + 2.0), 0.065)
        # Typical: VF 1.27 V at 40 mA (p.4 Fig.3), RDS(on) 3 ohm -> about 40 mA (Power Tree: 45 mA).
        self.assertTrue(0.035 < (3.3 - 1.27) / (r + 3.0) < 0.045)

    def test_ir_receiver(self) -> None:
        x = self.c.ir_receiver
        # 3V3 reaches the RC filter only through the switch's source-drain path.
        self.assertCountEqual(list(x.V3V3), [x.v3v3.Vp, x.q_en.S, x.r_gate_pu.p2])
        self.assertCountEqual(list(x.IR_RX_SW), [x.q_en.D, x.r_filter.p1])
        self.assertCountEqual(list(x.IR_RX_VCC), [x.r_filter.p2, x.u1.VCC])
        self.assertCountEqual(list(x.c_filter_st), [x.c_filter.p1, x.u1.VCC])
        self.assertCountEqual(list(x.GND), [x.v3v3.Vn, *x.u1.GND, x.c_filter.p2])
        self.assertCountEqual(list(x.IR_RX), [x.ir_rx, x.u1.OUT])
        self.assertTrue(47 <= x.r_filter.resistance.to(ohm).magnitude <= 220)
        self.assertGreaterEqual(x.c_filter.capacitance, 2.2 * uF)

    def test_ir_receiver_supply_switch(self) -> None:
        x = self.c.ir_receiver
        # Gate: enable port plus a pull-up to the source rail, so VGS = 0 (off)
        # while the nRF pin is an undriven reset-default input.
        self.assertCountEqual(list(x.IR_RX_EN), [x.ir_rx_en, x.q_en.G, x.r_gate_pu.p1])
        r_pu = x.r_gate_pu.resistance.to(ohm).magnitude
        self.assertTrue(10e3 <= r_pu <= 1e6)
        # Vcc with the switch on: 0.7 mA max Icc (IRM p.3) through 85 mOhm + R_filter
        # stays in Vs 2.7-5.5 V and VH >= Vcc - 0.4 clears nRF VIH 0.7 x 3.3.
        r = x.r_filter.resistance.to(ohm).magnitude
        vcc = 3.3 - 0.7e-3 * (r + 0.085)
        self.assertGreaterEqual(vcc, 2.7)
        self.assertGreaterEqual(vcc - 0.4, 0.7 * 3.3)
        # Inrush into the >= 2.2 uF filter cap is limited by R_filter, not by a GPIO.
        self.assertLessEqual(3.3 / r, 0.1)
        # The IRM is not on the 3V3 net directly, and OUT has no pull-up here.
        self.assertNotIn(x.u1.VCC, list(x.V3V3))
        self.assertCountEqual(list(x.IR_RX), [x.ir_rx, x.u1.OUT])

    def test_top_level_ports(self) -> None:
        c = self.c
        self.assertCountEqual(list(c.V3V3), [c.v3v3, c.tof.v3v3, c.ir_transmitter.v3v3, c.ir_receiver.v3v3])
        self.assertCountEqual(list(c.I2C), [c.i2c, c.tof.i2c])
        self.assertCountEqual(list(c.XSHUT), [c.xshut, c.tof.xshut])
        self.assertCountEqual(list(c.TOF_INT), [c.tof_int, c.tof.tof_int])
        self.assertCountEqual(list(c.IR_TX), [c.ir_tx, c.ir_transmitter.ir_tx])
        self.assertCountEqual(list(c.IR_RX), [c.ir_rx, c.ir_receiver.ir_rx])
        self.assertCountEqual(list(c.IR_RX_EN), [c.ir_rx_en, c.ir_receiver.ir_rx_en])

    def test_centre_zone_spots(self) -> None:
        c = self.c
        self.assertEqual(board_point([c.tof.transform, c.tof.u1.transform], (0, 0)), (0.0, 0.0))
        tx = [c.ir_transmitter.transform, c.ir_transmitter.led.transform]
        # ARCHITECTURE lists (0, +4.5); the LED moved 0.35 mm out along +y so its courtyard
        # clears the IR receiver's by >= 0.10 mm (user board review, reported for ARCHITECTURE).
        self.assertEqual(board_point(tx, (0, 0)), (0.0, 4.85))
        rx = [c.ir_receiver.transform, c.ir_receiver.u1.transform]
        self.assertEqual(board_point(rx, (0, 0)), (-4.5, 0.0))

    def test_front_parts_inside_centre_zone(self) -> None:
        c = self.c
        for sub, part in (
            (c.tof, c.tof.u1),
            (c.ir_transmitter, c.ir_transmitter.led),
            (c.ir_receiver, c.ir_receiver.u1),
        ):
            for pad in part.landpattern.p.values():
                x, y = board_point([sub.transform, part.transform, pad.transform], (0, 0))
                self.assertLess(math.hypot(x, y) + 0.8, CENTRE_ZONE_R, f"{part} pad at {(x, y)}")
        for sub, passive in (
            (c.tof, c.tof.c_hf),
            (c.tof, c.tof.c_bulk),
            (c.ir_receiver, c.ir_receiver.c_filter),
            (c.ir_receiver, c.ir_receiver.r_filter),
        ):
            chain = [sub.transform, passive.transform]
            corners = [
                board_point(chain, (sx * PASSIVE_HALF[0], sy * PASSIVE_HALF[1])) for sx in (-1, 1) for sy in (-1, 1)
            ]
            for x, y in corners:
                self.assertLess(math.hypot(x, y), CENTRE_ZONE_R, f"{passive} corner at {(x, y)}")
                self.assertLess(x, MIC_COURTYARD_LEFT, f"{passive} reaches the mic spot")

    def test_tall_parts_outside_exclusion_cones(self) -> None:
        c = self.c
        tof = [c.tof.transform, c.tof.u1.transform]
        for aperture, cone in ((COLLECTOR_XY, COLLECTOR_CONE), (EMITTER_XY, EMITTER_CONE)):
            p = board_point(tof, aperture)
            for chain, (hx, hy, h) in (
                ([c.ir_transmitter.transform, c.ir_transmitter.led.transform], IR_LED_BODY),
                ([c.ir_receiver.transform, c.ir_receiver.u1.transform], IR_RX_BODY),
            ):
                self.assertGreater(body_gap(chain, (hx, hy), p), cone_radius(cone, h) + 1.0)

    def test_collector_faces_away_from_ir_led(self) -> None:
        c = self.c
        tof = [c.tof.transform, c.tof.u1.transform]
        collector = board_point(tof, COLLECTOR_XY)
        emitter = board_point(tof, EMITTER_XY)
        self.assertLess(collector[1], 0.0)
        self.assertGreater(emitter[1], 0.0)


class CapturedPadClearanceTest(TestCase):
    """Runtime capture: every code-placed Top pad keeps PAD_CLEARANCE to other-net pads.

    Nets come from the runtime's net solve (``rd.nets.find``), not from the circuit
    code, so a pad overlapping another net's pad (the 3V3 / GND short that the
    100 nF once made with AVDDVCSEL) fails here.
    """

    rd: RuntimeDesign[TestDesign]
    fixed: frozenset[str]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        circuit = TestDesign().circuit
        # The front parts are the ones the circuit fixes with .at(); the rest go on the back.
        cls.fixed = frozenset(
            f"circuit.{trace.path}" for trace, comp in visit(circuit, Component) if comp.transform is not None
        )
        with jitx.runtime as runtime:
            cls.rd = runtime.submit(TestDesign)
            cls.rd.capture()

    def test_top_pads_clear_other_nets(self) -> None:
        pads: list[tuple[str, object, shapely.Polygon]] = []
        for trace, pad in visit(self.rd.root, Pad):
            path = str(trace.path)
            if not path.startswith(tuple(f"{part}." for part in self.fixed)):
                continue
            assert trace.transform is not None and pad.transform is not None, path
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            outline = (trace.transform * pad.transform * shape).to_shapely().g
            assert isinstance(outline, shapely.Polygon)
            net = self.rd.nets.find(pad)
            pads.append((path, pad if net is None else net, outline))  # an unconnected pad is its own net
        self.assertEqual(len({path.rsplit(".landpattern", 1)[0] for path, _, _ in pads}), 7)
        self.assertEqual(len(pads), 12 + 2 + 2 + 2 + 4 + 2 + 2)
        for (path_a, net_a, a), (path_b, net_b, b) in combinations(pads, 2):
            if net_a is net_b:
                continue
            gap = a.distance(b)
            self.assertGreaterEqual(gap, PAD_CLEARANCE, f"{path_a} x {path_b}: {gap:.3f} mm")

    def test_front_courtyards_apart(self) -> None:
        # User board review: no two courtyards overlap; >= 0.10 mm between any two.
        courtyards: list[tuple[str, shapely.Polygon]] = []
        for trace, courtyard in visit(self.rd.root, Courtyard):
            path = str(trace.path)
            if not path.startswith(tuple(f"{part}." for part in self.fixed)):
                continue
            assert trace.transform is not None, path
            outline = (trace.transform * courtyard.shape).to_shapely().g
            assert isinstance(outline, shapely.Polygon)
            courtyards.append((path, outline))
        self.assertEqual(len(courtyards), 7)
        for (path_a, a), (path_b, b) in combinations(courtyards, 2):
            self.assertFalse(a.intersects(b), f"{path_a} x {path_b} overlap")
            gap = a.distance(b)
            self.assertGreaterEqual(gap, COURTYARD_GAP, f"{path_a} x {path_b}: {gap:.3f} mm")
