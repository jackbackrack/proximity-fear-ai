"""comp-00a ported models: pad counts, port counts, BOM value and key land positions.

Expected values come from the datasheets cited in each module docstring and in
``datasheets/<MPN>.spec.md``, not from the modules' own constants.
"""

from jitx.component import Component
from jitx.feature import Courtyard
from jitx.inspect import extract, visit
from jitx.landpattern import Pad, PadMapping, PadShape
from jitx.net import Port
from jitx.sample import SampleSubstrate
from jitx.test import TestCase

from proximity_fear.components.buttons.xkb_TS_1187A import TS_1187A_B_A_B
from proximity_fear.components.connectors.hroparts_TYPE_C_31_M_12 import TYPE_C_31_M_12
from proximity_fear.components.connectors.shouhan_PH2_2P import PH2_2P
from proximity_fear.components.diodes.kt_0603_red import KT_0603R
from proximity_fear.components.diodes.mdd_SS14 import SS14
from proximity_fear.components.power_linear_regulators.diodes_AP2112K_33TRG1 import AP2112K_33TRG1
from proximity_fear.components.power_linear_regulators.microchip_MCP73831T_2ACI_OT import MCP73831T_2ACI_OT
from proximity_fear.components.protection.nexperia_PESD5V0S1BL import PESD5V0S1BL
from proximity_fear.components.protection.st_USBLC6_2SC6 import USBLC6_2SC6
from proximity_fear.components.test_points.test_point import TestPoint
from proximity_fear.components.transistors.aos_AO3401A import AO3401A
from proximity_fear.components.transistors.diodes_BSS138 import BSS138


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


class PortedComponentsTest(TestCase):
    def setUp(self) -> None:
        SampleSubstrate()

    def _check(self, part: Component, pads: int, ports: int) -> None:
        self.assertEqual(sum(1 for _ in visit(part, Pad)), pads)
        self.assertEqual(len(list(extract(part, Port))), ports)
        self.assertIsNone(part.value)

    def test_counts(self) -> None:
        # Pin / pad counts per datasheet pin tables and drawings.
        self._check(MCP73831T_2ACI_OT(), 5, 5)  # DS20001984G Table 3-1, SOT-23-5
        self._check(AP2112K_33TRG1(), 5, 5)  # DS39724 Pin Descriptions, SOT25
        self._check(SS14(), 2, 2)
        self._check(KT_0603R(), 2, 2)
        self._check(TYPE_C_31_M_12(), 18, 18)  # 12 SMD lands + 4 shell slots + 2 holes
        self._check(PH2_2P(), 4, 4)  # 2 signal lands + 2 fitting nails
        self._check(TS_1187A_B_A_B(), 4, 4)
        self._check(USBLC6_2SC6(), 6, 6)  # DocID 11265 Figure 1
        self._check(PESD5V0S1BL(), 2, 2)
        self._check(AO3401A(), 3, 3)
        self._check(BSS138(), 3, 3)
        tp = TestPoint()
        self.assertEqual(sum(1 for _ in visit(tp.landpattern, Pad)), 1)

    def test_usb_c_land_positions(self) -> None:
        # HRO TYPE-C-31-M-12 recommended layout: GND at 6.40 span, VBUS at 4.80,
        # signal lands on 0.50 pitch across 3.50.
        part = TYPE_C_31_M_12()
        xs = {port: _xy(_pad_of(part, port))[0] for port in (*part.GND, *part.VBUS)}
        self.assertEqual(sorted(abs(x) for x in xs.values()), [2.4, 2.4, 3.2, 3.2])
        self.assertEqual(_xy(_pad_of(part, part.SBU2))[0], -1.75)  # B8 leftmost signal
        self.assertEqual(_xy(_pad_of(part, part.CC2))[0], 1.75)  # B5 rightmost signal
        self.assertEqual(_xy(_pad_of(part, part.DP1))[0], -0.25)  # A6
        self.assertEqual(_xy(_pad_of(part, part.DN1))[0], 0.25)  # A7

    def test_led_anode_is_pad_1(self) -> None:
        # KENTO drawing p.2: pin 1 (+) anode; LCSC footprint pad 1 at +0.75 mm.
        part = KT_0603R()
        self.assertEqual(_xy(_pad_of(part, part.A)), (0.75, 0.0))
        self.assertIs(_pad_of(part, part.A), part.landpattern.p[1])

    def test_switch_lands(self) -> None:
        # XKB PCB layout: lands centred at x +-3.0 (5.0 / 7.0 inner / outer).
        part = TS_1187A_B_A_B()
        for port in (part.A, part.B, part.C, part.D):
            self.assertEqual(abs(_xy(_pad_of(part, port))[0]), 3.0)

    def test_battery_connector_lands(self) -> None:
        # SHOU HAN layout: signal lands on 2.0 mm, nails 1.1 mm outside them, rows 5.7 apart.
        part = PH2_2P()
        p1, p2 = _xy(_pad_of(part, part.PIN1)), _xy(_pad_of(part, part.PIN2))
        m1 = _xy(_pad_of(part, part.MOUNT1))
        self.assertAlmostEqual(abs(p1[0] - p2[0]), 2.0)
        self.assertAlmostEqual(abs(m1[1] - p1[1]), 3.5 + 2.2)
        self.assertAlmostEqual(abs(m1[0]) - 0.75, 1.0 + 0.5 + 1.1)

    def _assert_pads_in_courtyard(self, part: SS14 | PH2_2P, body_half: tuple[float, float]) -> None:
        # Every pad's copper and the max body, plus the 0.25 mm IPC-7351B nominal
        # courtyard excess, must sit inside the courtyard.
        excess = 0.25
        courtyards = list(extract(part.landpattern, Courtyard))
        self.assertEqual(len(courtyards), 1)
        cx0, cy0, cx1, cy1 = courtyards[0].shape.to_shapely().bounds
        for pad in part.landpattern.p.values():
            px, py = _xy(pad)
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            x0, y0, x1, y1 = shape.to_shapely().bounds
            rot = pad.transform.rotation if pad.transform is not None else 0.0
            if round(rot) % 180 == 90:
                x0, y0, x1, y1 = y0, x0, y1, x1
            self.assertLessEqual(cx0, px + x0 - excess + 1e-6, f"pad at {(px, py)}")
            self.assertGreaterEqual(cx1, px + x1 + excess - 1e-6, f"pad at {(px, py)}")
            self.assertLessEqual(cy0, py + y0 - excess + 1e-6, f"pad at {(px, py)}")
            self.assertGreaterEqual(cy1, py + y1 + excess - 1e-6, f"pad at {(px, py)}")
        bx, by = body_half
        self.assertLessEqual(cx0, -bx - excess + 1e-6)
        self.assertGreaterEqual(cx1, bx + excess - 1e-6)
        self.assertLessEqual(cy0, -by - excess + 1e-6)
        self.assertGreaterEqual(cy1, by + excess - 1e-6)

    def test_ss14_courtyard_encloses_pads(self) -> None:
        # MDD p.1: body 4.50 x 2.80 max; p.3: 1.52 x 1.68 lands on 3.93 centres.
        self._assert_pads_in_courtyard(SS14(), (4.50 / 2, 2.80 / 2))

    def test_ph2_courtyard_encloses_pads(self) -> None:
        # SHOU HAN p.1: housing DIM.B 7.9 wide; lands 1.0 / 1.5 x 3.5, rows 5.7 apart.
        self._assert_pads_in_courtyard(PH2_2P(), (7.9 / 2, 0.0))
