"""pin-01 nRF52840 pin pools against the nRF52840 PS v1.1 aQFN73 table (Table 142, pp.575-578).

Expected pin sets are typed from the PS table, not taken from the circuit or the module model.
LFXO-adjacent pins from the Ebyte E73 manual p.7 drawing / p.8 pin table: pad 12 = P0.26 sits
between XL1 (pad 11) and XL2 (pad 13); pad 14 = P0.06 beside XL2 (re-audit R-03).
"""

from jitx.net import Port
from jitx.test import TestCase

from proximity_fear.circuits.nrf_pins import TestDesign


def ids(ports: tuple[Port, ...]) -> set[int]:
    return {id(p) for p in ports}


class NRFPinPoolsTest(TestCase):
    def setUp(self) -> None:
        self.nrf = TestDesign().circuit.nrf
        m = self.m = self.nrf.module
        # PS Table 142: AIN0..AIN7.
        self.ps_ain = (m.P0_02, m.P0_03, m.P0_04, m.P0_05, m.P0_28, m.P0_29, m.P0_30, m.P0_31)
        # PS Table 142: E73 GPIOs not marked "Standard drive, low frequency I/O only", less P1.00 (SWO).
        self.ps_full_drive = (
            m.P0_04, m.P0_05, m.P0_06, m.P0_07, m.P0_08, m.P0_12, m.P0_13,
            m.P0_15, m.P0_17, m.P0_20, m.P0_22, m.P0_24, m.P0_26, m.P1_09,
        )  # fmt: skip
        # E73 GPIO pads (Ebyte manual pp.7-9) marked "low frequency I/O only" in PS Table 142.
        self.ps_low_frequency = (
            m.P0_02, m.P0_03, m.P0_28, m.P0_29, m.P0_30, m.P0_31,
            m.P1_02, m.P1_04, m.P1_06, m.P1_10, m.P1_11, m.P1_13,
        )  # fmt: skip

    def test_fast_pool_is_full_drive_only(self) -> None:
        lfxo_adjacent = ids((self.m.P0_26, self.m.P0_06))
        self.assertEqual(ids(self.nrf.fast_gpios()), ids(self.ps_full_drive) - lfxo_adjacent)
        self.assertFalse(ids(self.nrf.fast_gpios()) & ids(self.ps_low_frequency))
        self.assertFalse(ids(self.nrf.fast_gpios()) & lfxo_adjacent)

    def test_pdm_never_on_lfxo_adjacent_pins(self) -> None:
        # Every PDM / I2C / FastGPIO offer resolves from fast_gpios(); P0.26 / P0.06 stay slow-only.
        self.assertIn(id(self.m.P0_26), ids(self.nrf.general_gpios()))
        self.assertIn(id(self.m.P0_06), ids(self.nrf.general_gpios()))
        self.assertNotIn(id(self.m.P0_26), ids(self.nrf.fast_gpios()))
        self.assertNotIn(id(self.m.P0_06), ids(self.nrf.fast_gpios()))

    def test_adc_pool_is_ain(self) -> None:
        self.assertEqual(ids(self.m.analog_inputs()), ids(self.ps_ain))

    def test_general_pool(self) -> None:
        general = ids(self.nrf.general_gpios())
        self.assertEqual(len(general), 26)
        self.assertEqual(general, ids(self.ps_full_drive + self.ps_low_frequency))

    def test_reserved_pins_never_offered(self) -> None:
        m = self.m
        reserved = ids((m.P1_00, m.RESET, m.XL1, m.XL2, m.NFC1, m.NFC2, m.SWDIO, m.SWDCLK, m.D_P, m.D_N))
        self.assertFalse(reserved & ids(self.nrf.general_gpios()))
        self.assertFalse(reserved & ids(m.analog_inputs()))

    def test_enough_pins(self) -> None:
        # Fast demand: SDA, SCL, LED data, IR TX, PDM CLK, PDM DIN.
        self.assertGreaterEqual(len(self.nrf.fast_gpios()), 6)
        # Slow demand (8: LED_EN, IR_RX, TOF_XSHUT, TOF_INT, BUTTON, CHG_STAT, IR_RX_EN,
        # CHG_EN) + VBAT AIN (1) fit beside the fast set.
        self.assertGreaterEqual(len(self.nrf.general_gpios()), 6 + 8 + 1)
