"""Centre sensors: VL53L4CX ToF, IR11-21C IR transmitter, IRM-H638T IR receiver.

Every front part is fixed here with ``.at()``. The frame is the board centre, so
the assembly places ``CentreSensors`` at (0, 0) on Top. ARCHITECTURE.md
``Board`` -> "Centre zone": ToF at (0, 0), IR TX at (0, +4.5), IR RX at
(-4.5, 0), all copper inside r < 7.5 mm. The IR TX sits at (0, +4.85) instead
(``IR_TX_AT``): no two courtyards may overlap, and they keep >= 0.10 mm apart. The mic spot (+4.5, 0) belongs to
cir-05 and stays free here.

ToF (``datasheets/VL53L4CXV0DH_1.spec.md``; DS13805 p.5 Figure 3):
- AVDD and AVDDVCSEL to 3V3 (AVDD 2.6-3.5 V, p.17 Table 10). 100 nF + 4.7 uF at
  AVDDVCSEL / AVSSVCSEL. All five grounds to GND. DNC floating (p.4).
- XSHUT and GPIO1 each get a 10 k pull-up to 3V3 (p.5): XSHUT must always be
  driven, and GPIO1 is open-drain. There are no I2C pull-ups here. The bus is
  shared, so asm-01 owns them (p.5 Table 3 suggests 3.6 k at 400 kHz for a
  bus load CL <= 90 pF).
- Off state (ARCHITECTURE Design Notes, System OFF): the ToF sits in
  *software* standby with XSHUT held high, 6 uA typ (p.5; p.18 Table 12).
  Firmware never parks it in hardware standby with XSHUT low: that would draw
  3.3 V / 10 k = 330 uA through the XSHUT pull-up. The nRF PIN_CNF registers
  are retained in System OFF (nRF52840 PS 6.9), so XSHUT stays driven high
  (or, as a disconnected input, is held high by the pull-up).
- Rotated 90 deg, so the long axis runs along y. Its courtyard (x +-1.2) then
  clears the IR RX courtyard (x >= -2.0) and the mic's (x >= +2.7). Pin 1
  (AVDDVCSEL) and the VCSEL emitter face the IR TX at +y. The collector faces
  -y, about 6 mm from the IR LED.

IR TX (``datasheets/IR11-21C_TR8.spec.md``, ``datasheets/BSS138.spec.md``):
- 3V3 -> R_LED -> anode. The cathode goes to the BSS138 drain, source to GND, and
  the gate to the nRF PWM pin (38 kHz carrier). A 100 k gate pull-down keeps
  the LED off while the nRF boots or the pin floats.
- R_LED = 47 ohm. With VF of about 1.27 V at 40 mA (IR11-21C p.4 Fig.3) and
  RDS(on) of about 3 ohm at VGS 2.75-3.3 V (BSS138 p.3 Fig.6):
  (3.3 - 1.27) / (47 + 3) = 41 mA typ. The highest case is a 3V3 of 3.37 V,
  VF 1.1 V and RDS 2 ohm: 46 mA. Both are under IF 65 mA continuous (p.3), so a
  pin stuck high is still safe. Fig.1 derates IF by about 1 mA/C above 25 C,
  so 42 mA DC is good to about 48 C ambient. The 38 kHz carrier (<= 50 % duty,
  in bursts) halves the average, which is good to about 70 C. The IR line in
  the ARCHITECTURE Power Tree is 45 mA. Because of the ToF interlock (below),
  it never adds to the ToF's 40 mA peak. LED dissipation is 1.3 V x 46 mA = 60 mW, under
  Pd 130 mW. R_LED dissipates 79 mW typ and 100 mW worst case at DC, so it is
  asked for at >= 0.125 W.

IR RX (``datasheets/IRM-H638T_TR2.spec.md``, p.2 application circuit;
``datasheets/AO3401A.spec.md``):
- 3V3 -> AO3401A high-side switch -> 100 ohm (47-220) -> Vcc, with 4.7 uF
  (>= 2.2 uF) Vcc to GND, the RC both next to the Vcc pin. OUT idles at Vcc
  (< 3V3), so it is safe on an nRF input. The datasheet's >= 10 k OUT pull-up
  is optional; the IRM has its own internal R_PU (p.1 block diagram).
- Switched supply (A-04): the IRM draws 0.4 typ / 0.7 max mA whenever powered
  (p.3), seven times the ~0.1 mA standby budget, so firmware cuts it in System
  OFF. A bare GPIO cannot feed it: switching on charges the 4.7 uF through the
  100 ohm, a 3.3 V / 100 ohm = 33 mA inrush peak (tau 0.47 ms), far over a
  GPIO's drive. The AO3401A (already in the BOM for the LED switch) carries
  it: source to 3V3, drain to the filter resistor, so the RC stays at Vcc and
  the 100 ohm also limits the FET's inrush.
- Polarity: active low, ``ir_rx_en`` low = receiver on. A 100 k gate pull-up
  to 3V3 holds VGS = 0 (off) at reset, at boot and in System OFF, because the
  nRF's reset PIN_CNF is an input with the buffer disconnected and no pull
  (nRF52840 PS 6.9). One FET and one resistor; the BSS138 + P-FET active-high
  variant would add a part for no gain. A BSS138 low-side switch in the IRM
  GND was rejected: a floating receiver ground lets OUT back-feed the IRM.
- AO3401A at VGS = -3.3 V (p.2): VGS(th) -0.5..-1.3 V, so 2 V of overdrive at
  the worst threshold; RDS(on) <= 85 mOhm is guaranteed already at -2.5 V, so
  it is lower at -3.3 V. At 0.7 mA the drop is 60 uV, so Vcc = 3.3 - 0.07
  (100 ohm) = 3.23 V, inside Vs 2.7-5.5 V; VH >= Vcc - 0.4 = 2.83 V, over the
  nRF VIH of 0.7 x 3.3 = 2.31 V. Off: IDSS <= 1 uA (at -30 V, p.2). While on,
  the pull-up draws 3.3 V / 100 k = 33 uA from the low GPIO, which only
  happens with the nRF awake.
- Back-power, supply off: the IRM rail decays to 0 V through Icc. OUT is tied
  to the IRM's Vcc through its internal R_PU (and ESD structure), so anything
  that holds the nRF ``ir_rx`` pin high would feed the dead receiver and its
  4.7 uF. Firmware rule: whenever ``ir_rx_en`` is high (and before System
  OFF), configure ``ir_rx`` as input, pull disabled (or pull-down), input
  buffer disconnected; never pull-up or output. The reverse path cannot
  occur: the IRM has no supply of its own, its rail never rises above 3V3,
  so the AO3401A body diode (drain to source) stays reverse biased, and the
  gate is insulated from the rail.

Optical: the ToF VCSEL and the IR LED are both 940 nm. Firmware never transmits
IR while the ToF ranges (ARCHITECTURE Design Notes). Exclusion cones are DS13805
p.24 Figure 19. The collector cone is 25 deg, 0.22 mm at datum A, and the
emitter cone is 29 deg, 0.38 mm at datum A. Datum A is the module top (1.0 mm).
Only the 1.5 mm IR LED and the 2.5 mm IR receiver stand above datum A. Both
stay >= 2 mm (horizontally) from the apertures, where the cones are under
0.6 mm in radius. The check is in ``tests/test_cir04_centre_sensors.py``.
"""

import jitx
from jitx import Circuit, Net
from jitx.common import Power
from jitx.net import Port, ShortTrace
from jitx.sample import SampleBoard
from jitx.units import V, W, kohm, nF, ohm, uF
from jitxlib.parts import AtLeast, AtMost, Capacitor, CapacitorQuery, Minimize, Resistor, ResistorQuery
from jitxlib.protocols.serial import I2C

from ..components.leds.everlight_IR11_21C import IR11_21C_TR8
from ..components.sensors.everlight_IRM_H638T import IRM_H638T_TR2
from ..components.sensors.st_VL53L4CX import VL53L4CXV0DH_1
from ..components.transistors.aos_AO3401A import AO3401A
from ..components.transistors.diodes_BSS138 import BSS138
from ..substrate import ProximityFearSubstrate

# Centre-zone spots (ARCHITECTURE.md Board, board-centre frame, mm / deg).
TOF_AT = (0.0, 0.0)
TOF_ROTATE = 90.0
# ARCHITECTURE lists (0, +4.5); at 4.5 the LED courtyard (4.6 x 1.8) overlapped the IR
# receiver's (top y 3.8) by 0.3 mm, so the LED moves 0.35 mm further from the ToF (user
# board review: courtyards >= 0.10 mm apart). Pads still reach only r 6.1.
IR_TX_AT = (0.0, 4.85)
IR_RX_AT = (-4.5, 0.0)
IR_RX_ROTATE = 270.0  # Vcc / OUT pads face -y, where the RC filter sits

IR_LED_RESISTOR = 47.0 * ohm  # ~41 mA typ, 46 mA worst (module docstring)
IR_LED_RESISTOR_POWER = 0.125 * W  # 100 mW worst-case DC dissipation
IR_RX_FILTER_RESISTOR = 100.0 * ohm  # IRM-H638T p.2: 47-220 ohm
IR_RX_FILTER_CAPACITOR = 4.7 * uF  # IRM-H638T p.2: >= 2.2 uF
IR_RX_GATE_PULLUP = 100.0 * kohm  # AO3401A off by default; 33 uA from the GPIO while on


def _bulk_capacitor(capacitance: float) -> Capacitor:
    return Capacitor(capacitance=capacitance, rated_voltage_dc=AtLeast(10 * V), temperature_coefficient_code="X5R")


class TofSensor(Circuit):
    """VL53L4CX with its AVDD decoupling and XSHUT / GPIO1 pull-ups (DS13805 p.5).

    The frame is the sensor centre in the component's own orientation. Pin 1
    (AVDDVCSEL) is at (+1.6, -0.8).
    """

    v3v3 = Power()
    """3V3 (Vp) and GND (Vn)."""
    i2c = I2C()
    """SDA / SCL to the nRF TWIM. The bus pull-ups are at the assembly."""
    xshut = Port()
    """nRF output. Firmware holds it high (software standby when off); low = hardware standby, 330 uA in the pull-up."""
    tof_int = Port()
    """GPIO1 open-drain interrupt, active low, to an nRF input."""

    def __init__(self) -> None:
        self.u1 = VL53L4CXV0DH_1().at(0.0, 0.0)
        self.u1.DNC.no_connect()

        self.V3V3 = Net([self.v3v3.Vp, self.u1.AVDD, self.u1.AVDDVCSEL], name="3V3")
        self.GND = Net(
            [
                self.v3v3.Vn,
                self.u1.AVSSVCSEL,
                self.u1.GND,
                self.u1.GND2,
                self.u1.GND3,
                self.u1.GND4,
            ],
            name="GND",
        )

        # Resolved passives (0402 here: pads at +-0.51, courtyard 1.1 x 2.0) put p1 at local
        # +y, p2 at -y; rotate 270 turns that axis onto +x. Courtyards keep >= 0.10 mm from
        # the ToF's and from each other (user board review), so both caps sit outside the
        # ToF courtyard (2.4 x 4.4) instead of over its pad row. In the board frame (ToF
        # turned 90, courtyard x +-1.2, y +-2.2):
        # - 100 nF centre (1.86, 1.09), pads along y: p1 (3V3) level with AVDDVCSEL, p2
        #   (GND) level with AVSSVCSEL, 0.51 mm pad gap; courtyard 0.11 mm east of the ToF's.
        # - 4.7 uF centre (1.3, 2.88), pads along x above the ToF courtyard (0.13 mm gap),
        #   p1 (3V3) directly above AVDDVCSEL, 0.73 mm pad gap; courtyard 0.52 mm below
        #   the IR LED's and short of the mic spot (x < 2.675).
        # Both are under 1 mm tall, below datum A, so they cannot enter the exclusion
        # cones. (cir-04 history: at (1.2, -1.75, rotate 180) the 100 nF GND pad overlapped
        # AVDDVCSEL, a 3V3-GND short.) Every pad keeps >= 0.15 mm to other-net copper (tested).
        self.c_hf = Capacitor(
            capacitance=100 * nF, rated_voltage_dc=AtLeast(10 * V), temperature_coefficient_code="X7R"
        ).at(1.09, -1.86, rotate=270.0)
        self.c_bulk = _bulk_capacitor(4.7 * uF).at(2.88, -1.3)
        self.c_hf_st = ShortTrace(self.c_hf.p1, self.u1.AVDDVCSEL)
        self.c_hf_gnd_st = ShortTrace(self.c_hf.p2, self.u1.AVSSVCSEL)
        self.c_bulk_st = ShortTrace(self.c_bulk.p1, self.u1.AVDDVCSEL)
        self.GND += self.c_bulk.p2

        self.SDA = self.i2c.sda + self.u1.SDA
        self.SCL = self.i2c.scl + self.u1.SCL

        # Pull-ups are left unplaced, for layout to put on the back.
        self.r_xshut = Resistor(resistance=10 * kohm, tolerance=AtMost(0.01))
        self.r_gpio1 = Resistor(resistance=10 * kohm, tolerance=AtMost(0.01))
        self.XSHUT = Net([self.xshut, self.u1.XSHUT, self.r_xshut.p1])
        self.TOF_INT = Net([self.tof_int, self.u1.GPIO1, self.r_gpio1.p1])
        self.V3V3 += Net([self.r_xshut.p2, self.r_gpio1.p2])


class IRTransmitter(Circuit):
    """IR11-21C 940 nm emitter, low-side BSS138 switch, 3V3 series resistor.

    The frame is the LED centre, with the anode pad at +x.
    """

    v3v3 = Power()
    """3V3 (Vp) and GND (Vn)."""
    ir_tx = Port()
    """nRF PWM output (38 kHz carrier). High turns the LED on."""

    def __init__(self) -> None:
        self.led = IR11_21C_TR8().at(0.0, 0.0)
        # Driver, resistor and pull-down are unplaced, for the back.
        self.r_led = Resistor(
            resistance=IR_LED_RESISTOR,
            tolerance=AtMost(0.05),
            max_power=AtLeast(IR_LED_RESISTOR_POWER),
            library="basic",  # 0603 at 0.125 W resolves extended (C220711); 0805 C17714 is basic
        )
        self.q_drive = BSS138()
        self.r_gate_pd = Resistor(resistance=100 * kohm, tolerance=AtMost(0.05))

        self.V3V3 = Net([self.v3v3.Vp, self.r_led.p1], name="3V3")
        self.GND = Net([self.v3v3.Vn, self.q_drive.S, self.r_gate_pd.p2], name="GND")
        self.IR_LED_A = self.r_led.p2 + self.led.A
        self.IR_LED_K = self.led.C + self.q_drive.D
        self.IR_TX = Net([self.ir_tx, self.q_drive.G, self.r_gate_pd.p1])


class IRReceiver(Circuit):
    """IRM-H638T 38 kHz receiver, its p.2 supply RC filter and an AO3401A supply switch.

    The frame is the receiver centre. Vcc is at (2.92, 1.27) and OUT at
    (2.95, -1.27).
    """

    v3v3 = Power()
    """3V3 (Vp) and GND (Vn)."""
    ir_rx = Port()
    """Demodulated output, active low, to an nRF input (no pull while the supply is off)."""
    ir_rx_en = Port()
    """nRF output, active low: low powers the receiver. 100 k pull-up holds it off."""

    def __init__(self) -> None:
        self.u1 = IRM_H638T_TR2().at(0.0, 0.0)
        # The RC filter sits past the Vcc end of the body, as close to Vcc as
        # the 7.6 x 5.0 courtyard allows (p.2: "as close as possible").
        # rotate 90 (asm-01): p1 (Vcc side) faces the Vcc pad. At 270 the GND pad sat
        # 0.08 mm from the receiver's Vcc pad, under the 0.09 mm fab floor.
        # Courtyard 0.15 mm clear of the receiver's (user board review: >= 0.10 mm).
        self.c_filter = _bulk_capacitor(IR_RX_FILTER_CAPACITOR).at(4.95, 1.3, rotate=90.0)
        self.r_filter = Resistor(resistance=IR_RX_FILTER_RESISTOR, tolerance=AtMost(0.05)).at(4.5, 3.5, rotate=270.0)

        # High-side switch and gate pull-up are unplaced, for the back.
        self.q_en = AO3401A()
        self.r_gate_pu = Resistor(resistance=IR_RX_GATE_PULLUP, tolerance=AtMost(0.05))

        self.V3V3 = Net([self.v3v3.Vp, self.q_en.S, self.r_gate_pu.p2], name="3V3")
        self.GND = Net([self.v3v3.Vn, *self.u1.GND, self.c_filter.p2], name="GND")
        self.IR_RX_EN = Net([self.ir_rx_en, self.q_en.G, self.r_gate_pu.p1])
        self.IR_RX_SW = self.q_en.D + self.r_filter.p1
        self.IR_RX_VCC = self.r_filter.p2 + self.u1.VCC
        self.c_filter_st = ShortTrace(self.c_filter.p1, self.u1.VCC)
        self.IR_RX = self.ir_rx + self.u1.OUT


class CentreSensors(Circuit):
    """ToF, IR TX and IR RX, fixed at their centre-zone spots (board-centre frame)."""

    v3v3 = Power()
    """3V3 (Vp) and GND (Vn)."""
    i2c = I2C()
    """ToF SDA / SCL to the nRF TWIM. Pull-ups are at the assembly."""
    xshut = Port()
    """ToF XSHUT. nRF output, held high; System OFF uses software standby (10 k pull-up inside)."""
    tof_int = Port()
    """ToF GPIO1 interrupt. nRF input, open drain (10 k pull-up inside)."""
    ir_tx = Port()
    """IR LED drive. nRF PWM output (100 k pull-down inside)."""
    ir_rx = Port()
    """IR receiver OUT. nRF input, active low; no pull while ``ir_rx_en`` is high."""
    ir_rx_en = Port()
    """IR receiver supply enable. nRF output, active low (100 k pull-up inside: off at boot / System OFF)."""

    def __init__(self) -> None:
        self.tof = TofSensor().at(*TOF_AT, rotate=TOF_ROTATE)
        self.ir_transmitter = IRTransmitter().at(*IR_TX_AT)
        self.ir_receiver = IRReceiver().at(*IR_RX_AT, rotate=IR_RX_ROTATE)

        self.V3V3 = self.v3v3 + self.tof.v3v3 + self.ir_transmitter.v3v3 + self.ir_receiver.v3v3
        self.I2C = self.i2c + self.tof.i2c
        self.XSHUT = self.xshut + self.tof.xshut
        self.TOF_INT = self.tof_int + self.tof.tof_int
        self.IR_TX = self.ir_tx + self.ir_transmitter.ir_tx
        self.IR_RX = self.ir_rx + self.ir_receiver.ir_rx
        self.IR_RX_EN = self.ir_rx_en + self.ir_receiver.ir_rx_en


Device = CentreSensors


class TestDesign(jitx.Design):
    """CentreSensors on the project substrate, with the assembly's passive defaults."""

    substrate = ProximityFearSubstrate()
    board = SampleBoard()
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    circuit = CentreSensors()
