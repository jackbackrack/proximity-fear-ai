"""cir-06 NFC front end against the nRF52 PS NFCT antenna recommendations.

Expected values: Nordic's example in the PS (L_ant = 2 uH -> "range of 130 pF
on each pin") and an independent hand calculation for 3 uH at 13.56 MHz.
Matching: the PS requires the total capacitance on NFC1 and NFC2 to be matched,
so each tuning cap is C0G at <= +/-2 % (M-8). Each leg also carries one DNP
0402 trim footprint (not in the BOM, not soldered), identical on both legs.
"""

import math

from jitx.test import TestCase
from jitx.units import pF

from proximity_fear.circuits.nfc import NFCFrontEnd, TestDesign, tuning_capacitance


def resonance_hz(inductance_h: float, c_per_pin_total_f: float) -> float:
    """Two legs to GND in series around the loop: C' = C_leg / 2."""
    return 1 / (2 * math.pi * math.sqrt(inductance_h * c_per_pin_total_f / 2))


class TuningFormulaTest(TestCase):
    def test_nordic_example(self) -> None:
        # PS: 2 uH gives "tuning capacitors in the range of 130 pF".
        c = tuning_capacitance(2e-6, 13.56e6, 4e-12, 4e-12)
        self.assertAlmostEqual(c * 1e12, 130, delta=5)

    def test_three_microhenry(self) -> None:
        # Hand calc: 2 / ((2 pi 13.56e6)^2 * 3e-6) = 91.84 pF, less 8 pF.
        c = tuning_capacitance(3e-6, 13.56e6, 4e-12, 4e-12)
        self.assertAlmostEqual(c * 1e12, 83.84, places=1)


class NFCFrontEndTest(TestCase):
    def setUp(self) -> None:
        circuit = TestDesign().circuit
        assert isinstance(circuit, NFCFrontEnd)
        self.c = circuit

    def test_nets(self) -> None:
        c = self.c
        t = c.trim
        self.assertCountEqual(list(c.NFC1), [c.nfc1, c.antenna.p1, c.c_tune[0].p1, t.nfc1])
        self.assertCountEqual(list(c.NFC2), [c.nfc2, c.antenna.p2, c.c_tune[1].p1, t.nfc2])
        self.assertCountEqual(list(c.GND), [c.gnd, c.c_tune[0].p2, c.c_tune[1].p2, t.gnd])
        # Trim footprint k is in parallel with tuning cap k.
        self.assertCountEqual(list(t.NFC1), [t.nfc1, t.c_trim[0].p1])
        self.assertCountEqual(list(t.NFC2), [t.nfc2, t.c_trim[1].p1])
        self.assertCountEqual(list(t.GND), [t.gnd, t.c_trim[0].p2, t.c_trim[1].p2])

    def test_trim_footprints_dnp(self) -> None:
        t = self.c.trim
        self.assertIs(t.in_bom, False)
        self.assertIs(t.soldered, False)
        self.assertEqual(len(t.c_trim), 2)
        for cap in t.c_trim:
            self.assertEqual(cap.case, "0402")
            self.assertEqual(cap.temperature_coefficient_code, "C0G")
            self.assertIsNone(cap.in_bom)  # defers to the DNP circuit
            self.assertIsNone(cap.soldered)
        # The populated tuning caps stay in the BOM.
        for cap in self.c.c_tune:
            self.assertIsNot(cap.in_bom, False)

    def test_caps_matched_c0g(self) -> None:
        caps = self.c.c_tune
        self.assertEqual(len(caps), 2)
        for cap in caps:
            self.assertEqual(cap.temperature_coefficient_code, "C0G")
            self.assertEqual(cap.case, "0402")
            self.assertAlmostEqual(cap.capacitance, caps[0].capacitance)
            self.assertLessEqual(cap.tolerance, 0.02)
            self.assertEqual(cap.mpn, caps[0].mpn)  # identical legs

    def test_starting_resonance_near_carrier(self) -> None:
        # 82 pF + C_int 4 pF + C_p 4 pF per leg with 3 uH: within 2 % of 13.56 MHz.
        f = resonance_hz(3e-6, self.c.c_tune[0].capacitance.m_as("F") + 8e-12)
        self.assertAlmostEqual(f / 13.56e6, 1.0, delta=0.02)
        self.assertAlmostEqual(self.c.c_tune[0].capacitance, 82 * pF)
