"""cir-05 microphone circuit against LinkMems spec M196 v1.0 and ARCHITECTURE.md.

Expected values: p.6 "Measurement Circuit" (0.1 uF at VDD, L/R to GND for the
left channel, nothing else on CLK/DATA); p.7/p.8 port position; ARCHITECTURE.md
``Board``: mic port at (+4.5, 0) in the board-centre frame, centre zone r < 7.5 mm.
"""

import math
import unittest

import jitx
from jitx.component import Component
from jitx.feature import Courtyard
from jitx.inspect import visit
from jitx.test import TestCase
from jitx.units import nF
from jitxlib.landpatterns.pads import NPTHPad
from shapely.geometry.base import BaseGeometry

from proximity_fear.circuits.microphone import Microphone, TestDesign

# p.7 bottom view: port centre 1.04 mm from the body edge, body 3.50 mm long.
PORT_FROM_BODY_CENTRE_Y = 3.50 / 2 - 1.04
ASSEMBLY_X = 4.5  # ARCHITECTURE.md: mic (port) at (+4.5, 0)
CENTRE_ZONE_R = 7.5
CAP_0402_HALF_LENGTH = 0.5  # 1.0 x 0.5 mm body
COURTYARD_GAP_MIN = 0.10  # mm, user board review


def xy(placed: Component | NPTHPad) -> tuple[float, float]:
    """Translation of a placed object in its parent's frame."""
    placement = placed.transform
    if placement is None:
        raise AssertionError(f"{placed!r} has no placement")
    x, y = placement.translation
    return (x, y)


class MicrophoneTest(TestCase):
    def setUp(self) -> None:
        circuit = TestDesign().circuit
        assert isinstance(circuit, Microphone)
        self.c = circuit

    def test_supply_and_ground(self) -> None:
        c = self.c
        self.assertCountEqual(list(c.V3V3), [c.v3v3.Vp, c.mic.VDD])
        # GND: rail return, ring pad, L/R strap (left channel), decoupling return.
        self.assertCountEqual(list(c.GND), [c.v3v3.Vn, c.mic.GND, c.mic.LR, c.c_vdd.p2])
        self.assertNotIn(c.mic.LR, list(c.V3V3))

    def test_decoupling(self) -> None:
        c = self.c
        self.assertCountEqual(list(c.c_vdd_st), [c.c_vdd.p1, c.mic.VDD])
        self.assertAlmostEqual(c.c_vdd.capacitance, 100 * nF)
        self.assertEqual(c.c_vdd.temperature_coefficient_code, "X7R")

    def test_pdm_lines_direct(self) -> None:
        c = self.c
        self.assertCountEqual(list(c.PDM_CLK), [c.pdm_clk, c.mic.CLK])
        self.assertCountEqual(list(c.PDM_DIN), [c.pdm_din, c.mic.DATA])

    def test_port_hole_at_origin(self) -> None:
        c = self.c
        mic_xy = xy(c.mic)
        hole_xy = xy(c.mic.landpattern.port_hole)
        self.assertAlmostEqual(mic_xy[0] + hole_xy[0], 0.0, places=3)
        self.assertAlmostEqual(mic_xy[1] + hole_xy[1], 0.0, places=3)
        self.assertAlmostEqual(mic_xy[1], PORT_FROM_BODY_CENTRE_Y, places=3)

    def test_inside_centre_zone(self) -> None:
        c = self.c
        x, y = xy(c.c_vdd)
        far = math.hypot(ASSEMBLY_X + abs(x) + CAP_0402_HALF_LENGTH, abs(y) + CAP_0402_HALF_LENGTH)
        self.assertLess(far, CENTRE_ZONE_R)
        _, my = xy(c.mic)
        corner = math.hypot(ASSEMBLY_X + 2.65 / 2, my + 3.50 / 2)
        self.assertLess(corner, CENTRE_ZONE_R)


class MicrophoneCourtyardTest(unittest.TestCase):
    """Realized courtyards (the queried 0402 has one only in the runtime)."""

    def test_cap_courtyard_clear_of_mic(self) -> None:
        # User board review: courtyards never overlap and stay >= 0.10 mm apart.
        with jitx.runtime as runtime:
            rd = runtime.submit(TestDesign)
            circuit = rd.root.circuit
            assert isinstance(circuit, Microphone)
            shapes: list[BaseGeometry] = []
            for comp in (circuit.mic, circuit.c_vdd):
                placement = comp.transform
                assert placement is not None
                found = [
                    (placement * trace.transform * cy.shape).to_shapely().g
                    for trace, cy in visit(comp, Courtyard)
                    if trace.transform is not None
                ]
                self.assertEqual(len(found), 1)
                shapes.extend(found)
        mic, cap = shapes
        self.assertFalse(mic.intersects(cap))
        self.assertGreaterEqual(mic.distance(cap), COURTYARD_GAP_MIN)
