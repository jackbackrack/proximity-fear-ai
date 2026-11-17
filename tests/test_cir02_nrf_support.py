"""cir-02 nRF52840 support against the nRF52840 PS v1.1 config 3 (Figure 212, Table 153),
the PS LFXO equation (5.4.2.4) and the E73 / FC-135 / TC2030 / TS-1187A pinouts.

VBUS: PS p.583 recommends the series resistor on the USB supply for new designs; the
config-1 BOM (Table 149, p.586) gives R1 4R7 +-1 %.

VDD: the E73 already carries 4.7 uF on VDD and on VDDH (one net here; Ebyte p.11), at
the PS CVDD limit of 5.5 uF max (p.80), so no external capacitor may sit on VCC/VDDH. VBUS range 4.35-5.5 V (p.611), USB-active VBUS
current 2.4 mA (p.569).
"""

from jitx.inspect import extract
from jitx.net import ShortTrace
from jitx.test import TestCase
from jitx.units import ohm, pF, uF
from jitxlib.parts import Capacitor

from proximity_fear.circuits.nrf_support import (
    LFXO_LOAD_CAPACITOR,
    LFXO_TRACE_LENGTHS_MM,
    TestDesign,
    lfxo_effective_load,
    lfxo_load_capacitance,
    lfxo_pcb_capacitance,
)


class LfxoFormulaTest(TestCase):
    def test_nordic_reference(self) -> None:
        # PS Table 153: CL 9 pF crystal with 12 pF C17/C18; Cpin 4 pF (p.97); Cpcb 2 pF.
        self.assertAlmostEqual(lfxo_load_capacitance(9e-12, 4e-12, 2e-12) * 1e12, 12.0, places=6)

    def test_fc135(self) -> None:
        # PS p.97: Cpin 4 pF, CL_LFXO <= 12.5 pF. Closure audit W-2 strays for this board:
        # lands 1.9 pF per leg + 0.12 pF/mm over 5.65 (XL1) / 8.25 (XL2) mm of route.
        self.assertAlmostEqual(lfxo_pcb_capacitance(5.65) * 1e12, 1.9 + 0.678, places=6)
        self.assertAlmostEqual(lfxo_pcb_capacitance(8.25) * 1e12, 1.9 + 0.99, places=6)
        self.assertAlmostEqual(LFXO_LOAD_CAPACITOR, 16 * pF)
        cpcb1, cpcb2 = (lfxo_pcb_capacitance(mm) for mm in LFXO_TRACE_LENGTHS_MM)
        # Hand calc, PS 5.4.2.4 series combination:
        # nominal (16 + 4 + 2.578)(16 + 4 + 2.89) / (sum) = 11.37 pF.
        self.assertAlmostEqual(lfxo_effective_load(16e-12, 16e-12, 4e-12, cpcb1, cpcb2) * 1e12, 11.37, delta=0.01)
        # Worst case: +5 % caps and +0.5 pF inside the module per leg -> 12.02 pF <= 12.5 pF.
        worst = lfxo_effective_load(16.8e-12, 16.8e-12, 4e-12, cpcb1 + 0.5e-12, cpcb2 + 0.5e-12) * 1e12
        self.assertAlmostEqual(worst, 12.02, delta=0.01)
        self.assertLessEqual(worst, 12.5)
        # The previous 18 pF would exceed the PS maximum at the same corner (13.07 pF).
        too_big = lfxo_effective_load(18.9e-12, 18.9e-12, 4e-12, cpcb1 + 0.5e-12, cpcb2 + 0.5e-12) * 1e12
        self.assertGreater(too_big, 12.5)


class NRFSupportTest(TestCase):
    def setUp(self) -> None:
        self.c = TestDesign().circuit.nrf
        self.m = self.c.module

    def test_supply_normal_voltage_mode(self) -> None:
        c, m = self.c, self.m
        # PS Figure 212: VDDH joins VDD; DCCH (AB2) is left unconnected.
        self.assertCountEqual(list(c.P3V3), [c.v3v3.Vp, m.VCC, m.VDDH, c.swd.VCC])
        # No external capacitor on VDD (module caps already at CVDD max, PS p.80).
        for st in extract(c, ShortTrace):
            self.assertNotIn(m.VCC, list(st))
            self.assertNotIn(m.VDDH, list(st))
        self.assertEqual(len(list(extract(c, Capacitor))), 3)  # c_vbus + two LFXO load caps
        for net in (c.P3V3, c.GND, c.VBUS, c.VBUS_NRF):
            self.assertNotIn(m.DCCH, list(net))

    def test_vbus_series_resistor(self) -> None:
        c, m = self.c, self.m
        # Port -> R1 -> pad 27; the 4.7 uF sits on the pad side (PS Figure 210 p.585, Figure 212).
        self.assertCountEqual(list(c.VBUS), [c.vbus.Vp, c.r_vbus.p1])
        self.assertCountEqual(list(c.VBUS_NRF), [c.r_vbus.p2, m.VBUS])
        self.assertCountEqual(list(c.st_c_vbus), [c.c_vbus.p1, m.VBUS])
        self.assertAlmostEqual(c.r_vbus.resistance, 4.7 * ohm)
        # Drop at USB-active current keeps a 4.40 V (drooped) VBUS above the 4.35 V minimum.
        self.assertGreater(4.40 - 2.4e-3 * c.r_vbus.resistance / ohm, 4.35)

    def test_ground(self) -> None:
        c, m = self.c, self.m
        caps = (c.c_vbus, *c.c_xl)
        expected = [c.v3v3.Vn, c.vbus.Vn, *m.GND, c.swd.GND, c.sw_user.C, c.sw_user.D, *(k.p2 for k in caps)]
        self.assertCountEqual(list(c.GND), expected)

    def test_decoupling_values(self) -> None:
        c = self.c
        self.assertAlmostEqual(c.c_vbus.capacitance, 4.7 * uF)  # PS Table 153 C21
        for cap in c.c_xl:
            self.assertEqual(cap.temperature_coefficient_code, "C0G")

    def test_crystal(self) -> None:
        c, m = self.c, self.m
        self.assertCountEqual(list(c.XL1), [m.XL1, c.xtal.XTAL[0]])
        self.assertCountEqual(list(c.XL2), [m.XL2, c.xtal.XTAL[1]])
        self.assertEqual(len(c.c_xl), 2)

    def test_debug(self) -> None:
        c, m = self.c, self.m
        swo = c.swd.swd.swo
        assert swo is not None
        self.assertCountEqual(list(c.SWDIO), [c.swd.swd.swdio, m.SWDIO])
        self.assertCountEqual(list(c.SWDCLK), [c.swd.swd.swdclk, m.SWDCLK])
        self.assertCountEqual(list(c.SWO), [swo, m.P1_00])  # PS Table 142 AD22: TRACEDATA[0]/SWO
        # P0.18 / nRESET straight to the probe, no external pull-up (PS Figure 212).
        self.assertCountEqual(list(c.RESET), [c.swd.nRESET, m.RESET])

    def test_usb_nfc_button(self) -> None:
        c, m = self.c, self.m
        self.assertCountEqual(list(c.USB_DP), [c.usb.data.p, m.D_P])
        self.assertCountEqual(list(c.USB_DN), [c.usb.data.n, m.D_N])
        self.assertCountEqual(list(c.NFC1), [c.nfc1, m.NFC1])
        self.assertCountEqual(list(c.NFC2), [c.nfc2, m.NFC2])
        # TS-1187A: A-B one contact, C-D the other.
        self.assertCountEqual(list(c.BUTTON), [c.button, c.sw_user.A, c.sw_user.B])
