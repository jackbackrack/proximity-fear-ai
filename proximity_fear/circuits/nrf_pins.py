"""nRF52840 GPIO assignment: the E73 module's pin-muxing offers (pin-01).

The nRF52840 maps any digital peripheral (TWIM, PWM, I2S, PDM, GPIOTE) to any GPIO
through its PSEL registers, so every interface below is offered over a pin pool, not a
fixed pin, and the board's routing picks the mapping.

Sources:

* nRF52840 Product Specification v1.1 (``datasheets/nRF52840_PS.pdf``), section 7.1.1
  "aQFN73 ball assignments" (Table 142, pp.575-578): the "Standard drive, low frequency
  I/O only" pins and the AIN pins; its note (p.578): "Low frequency I/O is signals with a
  frequency up to 10 kHz". The same table is in ``datasheets/sourcing/nRF52840_PS-pins-aQFN73.txt``
  and is what the E73 model's ``low_frequency_gpios()`` / ``analog_inputs()`` return.
* PS Table 142 (AD22, p.577): P1.00 is TRACEDATA[0] / SWO, wired to the Tag-Connect in cir-02.
* PS 4.5.1.4 PSELRESET (p.45): nRESET is P0.18 (module ``RESET`` port), reserved.
* PS 5.4.2 LFXO (p.86): XL1/XL2 = P0.00/P0.01 (module ``XL1``/``XL2``), reserved.
* NFC1/NFC2 = P0.09/P0.10 (module ``NFC1``/``NFC2``), fixed to cir-06, never offered.

Pin pools (Ebyte E73 pad numbers in the module model):

* Full drive ("fast"): P0.04, P0.05, P0.07, P0.08, P0.12, P0.13, P0.15, P0.17, P0.20,
  P0.22, P0.24, P1.09 (12 pins). Every signal above 10 kHz goes here: I2C SDA/SCL
  (400 kHz), LED chain data (800 kHz, I2S SDOUT or PWM), IR TX (38 kHz PWM), PDM CLK
  (1-3 MHz) and PDM DIN -- 6 pins, so 6 spare. Keeping them off the low-frequency pins is
  the PS rule for the pins beside the radio.
* Kept out of the fast pool (and so out of PDM, I2C, LED data and IR TX): the two pins
  whose only route out runs between the LFXO pads (M-8; re-audit R-03, ov-nrf). Ebyte p.7
  drawing / p.8 pin table: P0.26 is bottom pad 12, centred between XL1 (pad 11) and XL2
  (pad 13); P0.06 is bottom pad 14, reached between XL2 (pad 13) and pad 15. PS p.609:
  "Fast switching digital signals should not be routed close to the crystal". Both stay in
  the general pool for slow (static-level) signals.
* Any general GPIO (low-frequency pins, the two LFXO-adjacent pins and the fast pool):
  slow signals, all below 10 kHz. The board needs 8: LED_EN, IR_RX (demodulated
  envelope), TOF_XSHUT, TOF_INT (ToF GPIO1), BUTTON, CHG_STAT, IR_RX_EN, CHG_EN. Pool:
  26 general pins less 6 fast and 1 AIN in use leaves 19 >= 8.
* AIN: AIN0-AIN7 = P0.02, P0.03, P0.04, P0.05, P0.28, P0.29, P0.30, P0.31 (VBAT sense).

What the assembly requires (asm-01): ``I2C`` x1, ``PDM`` x1, ``FastGPIO`` x2 (LED data,
IR TX), ``GPIO`` x8 (LED enable, IR RX, XSHUT, ToF INT, button, charge STAT, IR RX
enable, charge enable), ``ADC`` x1 (VBAT).
"""

from jitx.circuit import Circuit
from jitx.common import ADC, GPIO
from jitx.container import inline
from jitx.net import Net, Port, provide
from jitx.sample import SampleDesign
from jitxlib.parts import Lock, LockMode
from jitxlib.protocols.serial import I2C

from ..components.mcus.ebyte_E73_2G4M08S1CX import E73_2G4M08S1CX
from ..components.test_points.test_point import TestPoint

TWIM_COUNT = 2
"""TWIM0 and TWIM1 (PS 4.2.4 Instantiation, IDs 3 and 4, p.23; TWIM is section 6.31)."""


class FastGPIO(Port):
    """One full-drive GPIO for a signal above the PS's 10 kHz low-frequency limit."""

    gpio = Port()


class PDM(Port):
    """PDM microphone interface: clock out, data in (PS 6.15 PDM, p.234: CLK and DIN pins)."""

    clk = Port()
    din = Port()


class NRF52840Pins(Circuit):
    """E73-2G4M08S1CX module with its GPIO offered through provide/require.

    Fixed-function pins (power, USB, SWD, RESET = P0.18, XL1/XL2, NFC1/NFC2, SWO = P1.00)
    are left to the subclass that wires them (``nrf_support.NRFSupport``).
    """

    def __init__(self) -> None:
        self.module = E73_2G4M08S1CX()

    def general_gpios(self) -> tuple[Port, ...]:
        """Every module GPIO free for the application: all module GPIO ports less P1.00 (SWO)."""
        m = self.module
        return (
            m.P0_02, m.P0_03, m.P0_04, m.P0_05, m.P0_06, m.P0_07, m.P0_08, m.P0_12,
            m.P0_13, m.P0_15, m.P0_17, m.P0_20, m.P0_22, m.P0_24, m.P0_26, m.P0_28,
            m.P0_29, m.P0_30, m.P0_31, m.P1_02, m.P1_04, m.P1_06, m.P1_09, m.P1_10,
            m.P1_11, m.P1_13,
        )  # fmt: skip

    def lfxo_adjacent_gpios(self) -> tuple[Port, ...]:
        """GPIOs routed out between the LFXO pads: P0.26 (pad 12, between XL1/XL2) and
        P0.06 (pad 14, beside XL2), Ebyte p.7 drawing / p.8 pin table. Slow signals only."""
        m = self.module
        return (m.P0_26, m.P0_06)

    def fast_gpios(self) -> tuple[Port, ...]:
        """General GPIOs that are neither "standard drive, low frequency I/O only" (PS Table
        142) nor routed between the LFXO pads (``lfxo_adjacent_gpios``)."""
        excluded = (*self.module.low_frequency_gpios(), *self.lfxo_adjacent_gpios())
        return tuple(p for p in self.general_gpios() if not any(p is q for q in excluded))

    @provide(GPIO)
    def provide_gpio(self, g: GPIO) -> list[dict[Port, Port]]:
        """Slow signals (< 10 kHz): any general GPIO."""
        return [{g.gpio: p} for p in self.general_gpios()]

    @provide(FastGPIO)
    def provide_fast_gpio(self, g: FastGPIO) -> list[dict[Port, Port]]:
        """Signals above 10 kHz: full-drive pins only."""
        return [{g.gpio: p} for p in self.fast_gpios()]

    @provide(ADC)
    def provide_adc(self, a: ADC) -> list[dict[Port, Port]]:
        """SAADC inputs AIN0-AIN7."""
        return [{a.adc: p} for p in self.module.analog_inputs()]

    @provide(I2C)
    def provide_i2c(self, i2c: I2C) -> list[dict[Port, Port]]:
        """TWIM0 / TWIM1, SDA and SCL each on any fast pin."""
        return [{i2c.sda: self.require(FastGPIO).gpio, i2c.scl: self.require(FastGPIO).gpio} for _ in range(TWIM_COUNT)]

    @provide.one_of(PDM)
    def provide_pdm(self, pdm: PDM) -> list[dict[Port, Port]]:
        """The single PDM peripheral, CLK and DIN each on any fast pin."""
        return [{pdm.clk: self.require(FastGPIO).gpio, pdm.din: self.require(FastGPIO).gpio}]


class TestDesign(SampleDesign):
    """Requires the badge's full interface set, each signal ending on a test pad."""

    parts_lock = Lock(mode=LockMode.OFF)

    @inline
    class circuit(Circuit):
        def __init__(self) -> None:
            self.nrf = NRF52840Pins()
            i2c = self.nrf.require(I2C)
            pdm = self.nrf.require(PDM)
            fast = self.nrf.require(FastGPIO, count=2)
            slow = self.nrf.require(GPIO, count=8)
            vbat = self.nrf.require(ADC)
            self.tp_i2c = [TestPoint(), TestPoint()]
            self.tp_pdm = [TestPoint(), TestPoint()]
            self.tp_fast = [TestPoint() for _ in fast]
            self.tp_slow = [TestPoint() for _ in slow]
            self.tp_vbat = TestPoint()
            self.SDA = Net([i2c.sda, self.tp_i2c[0].p1])
            self.SCL = Net([i2c.scl, self.tp_i2c[1].p1])
            self.PDM_CLK = Net([pdm.clk, self.tp_pdm[0].p1])
            self.PDM_DIN = Net([pdm.din, self.tp_pdm[1].p1])
            self.FAST = [Net([f.gpio, tp.p1]) for f, tp in zip(fast, self.tp_fast, strict=True)]
            self.SLOW = [Net([s.gpio, tp.p1]) for s, tp in zip(slow, self.tp_slow, strict=True)]
            self.VBAT_SENSE = Net([vbat.adc, self.tp_vbat.p1])
