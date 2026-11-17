"""comp-00b front-side models: pad counts, port counts, BOM value and pad positions.

Expected values come from the datasheets cited in each module docstring and in
``datasheets/<MPN>.spec.md``, not from the modules' own constants.
"""

from jitx.component import Component
from jitx.inspect import extract, visit
from jitx.landpattern import Pad, PadMapping
from jitx.net import Port
from jitx.sample import SampleSubstrate
from jitx.test import TestCase

from proximity_fear.components.leds.everlight_IR11_21C import IR11_21C_TR8
from proximity_fear.components.leds.worldsemi_WS2812C_2020 import WS2812C_2020_V6
from proximity_fear.components.sensors.everlight_IRM_H638T import IRM_H638T_TR2
from proximity_fear.components.sensors.st_VL53L4CD import VL53L4CDV0DH_1
from proximity_fear.components.sensors.st_VL53L4CX import VL53L4CXV0DH_1


def _xy(pad: Pad) -> tuple[float, float]:
    placement = pad.transform
    if placement is None:
        raise AssertionError("pad has no placement")
    x, y = placement.translation
    return (round(x, 3), round(y, 3))


def _pad_of(part: Component, port: Port) -> Pad:
    mappings = list(extract(part, PadMapping))
    if len(mappings) != 1:
        raise AssertionError(f"expected one PadMapping, found {len(mappings)}")
    pad = mappings[0][port]
    if isinstance(pad, Pad):
        return pad
    pads = list(pad)
    if len(pads) != 1:
        raise AssertionError("port maps to several pads")
    return pads[0]


class FrontComponentsTest(TestCase):
    def setUp(self) -> None:
        SampleSubstrate()

    def _check(self, part: Component, pads: int, ports: int) -> None:
        self.assertEqual(sum(1 for _ in visit(part, Pad)), pads)
        self.assertEqual(len(list(extract(part, Port))), ports)
        self.assertIsNone(part.value)

    def test_counts(self) -> None:
        self._check(WS2812C_2020_V6(), 4, 4)  # p.2 pin table, 4 pins
        self._check(IR11_21C_TR8(), 2, 2)  # p.2, anode + cathode
        self._check(IRM_H638T_TR2(), 4, 4)  # p.1 pin configuration
        self._check(VL53L4CDV0DH_1(), 12, 12)  # DS13812 p.4 Table 2
        self._check(VL53L4CXV0DH_1(), 12, 12)  # DS13805 p.4 Table 2

    def test_ws2812c_rows(self) -> None:
        # p.2 PCB Solder Pad: 1.13 gap + 0.7 pad -> x centres +-0.915; 0.40 gap -> y +-0.55.
        # Top view turned 180 deg: DO top-left, VDD top-right, GND bottom-left, DI bottom-right.
        led = WS2812C_2020_V6()
        for port, (ex, ey) in (
            (led.DO, (-0.915, 0.55)),
            (led.VDD, (0.915, 0.55)),
            (led.GND, (-0.915, -0.55)),
            (led.DI, (0.915, -0.55)),
        ):
            x, y = _xy(_pad_of(led, port))
            self.assertAlmostEqual(x, ex, delta=0.01)
            self.assertAlmostEqual(y, ey, delta=0.001)

    def test_ir11_anode_is_pin1_on_plus_x(self) -> None:
        # p.2: pin 1 anode on the right (+x) of the top view; pin 2 cathode on the left.
        ir = IR11_21C_TR8()
        self.assertGreater(_xy(_pad_of(ir, ir.A))[0], 0)
        self.assertLess(_xy(_pad_of(ir, ir.C))[0], 0)

    def test_irm_pitch(self) -> None:
        # p.6: 2.54 mm lead pitch; pins 1 and 4 on the lens (+y) side, 1/2 on -x.
        irm = IRM_H638T_TR2()
        g0 = _xy(_pad_of(irm, irm.GND[0]))
        g1 = _xy(_pad_of(irm, irm.GND[1]))
        self.assertAlmostEqual(g0[1] - g1[1], 2.54, places=3)
        self.assertLess(g0[0], 0)
        self.assertGreater(_xy(_pad_of(irm, irm.VCC))[1], 0)
        self.assertGreater(_xy(_pad_of(irm, irm.OUT))[0], 0)

    def test_vl53_pin_positions(self) -> None:
        # DS13805 p.22 / DS13812 p.21 Figure 17: 0.8 pitch, 3.70 x 2.10 pattern of 0.5 pads
        # -> centres x +-1.6, y +-0.8; top view pin 1 bottom-right. Pin order from
        # Figure 2 (bottom view) mirrored to the top view.
        for tof in (VL53L4CDV0DH_1(), VL53L4CXV0DH_1()):
            expected = {
                tof.AVDDVCSEL: (1.6, -0.8),  # pin 1
                tof.XSHUT: (-1.6, -0.8),  # pin 5
                tof.GND3: (-1.6, 0.0),  # pin 6
                tof.GPIO1: (-1.6, 0.8),  # pin 7
                tof.AVDD: (1.6, 0.8),  # pin 11
                tof.GND4: (1.6, 0.0),  # pin 12
            }
            for port, xy in expected.items():
                self.assertEqual(_xy(_pad_of(tof, port)), xy)

    def test_vl53_identity(self) -> None:
        self.assertEqual(VL53L4CXV0DH_1.mpn, "VL53L4CXV0DH/1")  # DS13805 p.33 Table 19
        self.assertEqual(VL53L4CDV0DH_1.mpn, "VL53L4CDV0DH/1")  # DS13812 p.32 Table 19
