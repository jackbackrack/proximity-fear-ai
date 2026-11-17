"""LED rings: 50 WS2812C-2020 addressable LEDs on three concentric rings, one
chain, and the high-side switch that powers them from SYS.

Ported from socialbadge-ai rev 2 ``circuits/front_leds.py`` (LEDGrid +
LEDPower, fabbed and brought up); the grid became rings and the switch gained a
soft start for the 3x larger VLED capacitance. Primary evidence is the spec
notes ``datasheets/WS2812C-2020-V6_W.spec.md``, ``datasheets/AO3401A.spec.md``
and ``datasheets/BSS138.spec.md`` and their PDFs.

Rings (``LEDRings``, front, frame = board centre = ToF):
- ``RING_SPECS``: (9.5 mm, 10), (15.5 mm, 16), (21.5 mm, 24) = 50 LEDs
  (ARCHITECTURE.md Object-Hierarchy Decisions). LED ``k`` of a ring sits at
  ``radius * (cos t, sin t)``, ``t = angle_offset + 360 k / count`` (minus for a
  clockwise ring), every LED and cap fixed with ``.at()``.
- WS2812C model pads (EasyEDA C55160508, spec note "Layout"): DO (-0.92, +0.55),
  GND (-0.92, -0.55), DI (+0.92, -0.55), VDD (+0.92, +0.55). Data enters at +x
  and leaves at -x, so the LED's -x axis is the chain direction: the LED is
  turned ``t - 90`` on a counter-clockwise ring and ``t + 90`` on a clockwise
  one. Each DO then faces the next LED's DI across the tangential gap.
- On a counter-clockwise ring local +y points outward, so VDD and its cap are
  outside the circle; on a clockwise ring local +y points inward and they are
  inside. Inner and middle rings run counter-clockwise (caps outside, clear of
  the r < 7.5 mm centre zone); the outer ring runs clockwise (caps inside,
  clear of the 1 mm rim keepout at r 24 mm). Cap rows of neighbouring rings
  then face each other only across the middle/outer gap, where they still
  clear by about 1.4 mm.
- Each 100 nF sits just beyond the LED's VDD edge, pads tangential, p1 directly
  over the VDD pad (0.56 mm pad-to-pad), p2 to GND; its courtyard is 0.11 mm
  clear of the LED's (user board review: courtyards >= 0.10 mm apart). Data traces stay inside the
  LED rows (|y| <= 0.55 local), so no cap is in a data path.
- Radial hops: the inner ring's last DO is on its outer row and the middle
  ring's first DI on its inner row; ``angle_offset`` of the middle ring puts the
  two pads on one radius (4.9 mm hop). The outer ring's first DI is on its outer
  row; its offset puts the middle ring's last DO on the radius through the free
  gap behind that LED, so the hop runs straight out and turns onto DI
  (6.3 mm pad to pad, ~8 mm routed).
- 33 ohm series resistor on the chain input (socialbadge rev 2), left to the
  placer: it belongs next to the nRF pin on the back.

Switch (``LEDSwitch``, back, placed by the assembly):
- Input is SYS (``vin``, from ``PowerSupply.sys``), not VBAT (A-01): the
  MCP73831 output must feed only the cell (AN1149 p.5 "Connecting the system
  load to the battery"; the charger terminates at ITERM = 7.5 % of I_REG, which
  an LED load on VBAT would hide). SYS, and so VLED, spans about 3.0-5.2 V:
  VBAT on battery; VBUS - VF(SS14) on USB, where the light-load SS14 drop is
  only ~0.3-0.45 V (SS14 p.2 Fig. 3), so SYS reaches ~4.85-4.95 V at the USB 2.0
  5.25 V maximum and ~5.1-5.2 V on a 5.5 V Type-C source (re-audit N-03).
- SYS reservoir (re-audit N-06): 10 uF X5R (rated 16 V, so ~half survives
  5 V of DC bias) on ``q_switch`` source. Without it the only SYS capacitance is
  the AP2112K's 1 uF input cap ~25 mm away, so the soft-start pulse and the
  WS2812 PWM steps would be fed over the SYS trace.
- AO3401A high-side P-FET SYS -> VLED; 100 k gate-source pull-up to SYS keeps
  it off (VGS = 0 V against VGS(th) -0.5..-1.3 V, p.2). A BSS138 (gate from
  nRF ``enable``, 100 k pull-down so the LEDs stay off while the nRF boots or
  the pin floats) pulls the gate low through 10 k: on-state VGS = -SYS x
  100/110 = -3.1 V at 3.4 V (firmware cut-off) to -4.7 V at 5.2 V, inside the
  +-12 V VGS abs max (p.1); the pull-up then draws <= 5.2 V / 110 k = 47 uA.
- WS2812C at VLED 3.0-5.2 V: VDD max 5.3 V (p.2), 0.1 V above the 5.5 V Type-C
  corner. VIH = 0.55 VDD (p.3, tabled at 5 V) is 1.65-2.86 V. The nRF data pin
  drives only the DIN input (+-1 uA, p.3) through 33 ohm; its guaranteed
  VOH >= VDD - 0.4 V is specified at 0.5 mA standard drive (PS p.156 VOH,SD):
  2.85 V at the AP2112K's -1.5 % 3V3. Against VIH that is a 0.13 V margin at the
  USB 2.0 corner (SYS <= 4.95 V, VIH 2.72 V) and a 0.01 V shortfall on paper at
  the 5.5 V Type-C corner (VIH 2.86 V). At the ~1 uA DIN load the real VOH is
  close to VDD (~3.2 V), so the chain still reads; the paper margin is
  accepted, not fixed (no level shifter). Below VDD min 3.3 V firmware turns
  VLED off (VBAT < ~3.4 V).
- Soft start: 10 nF gate-drain (Miller) plus the 10 k limit the VLED slew to
  (SYS - |V_plateau|) / 10 k / 10 nF. With V_plateau -1.0..-1.6 V (VGS(th)
  -0.5..-1.3 V, p.2) that is 14 V/ms (3.0 V) to 42 V/ms (5.2 V), so charging
  the <= 15 uF on VLED draws 0.21-0.63 A for 0.12-0.21 ms instead of a
  resistance-limited spike of tens of amps that would pull SYS down. The local
  10 uF SYS reservoir supplies the pulse's leading edge; the rest arrives over
  the SYS trace from the power path.
- Load: all-white is 50 x 3 x 5 mA = 750 mA (WS2812C p.1); firmware caps it
  at 300 mA on battery and ~150 mA on USB (ARCHITECTURE Power Tree).
  RDS(on) <= 85 mOhm at VGS -2.5 V and <= 60 mOhm at -4.5 V (p.2): at the
  3.4 V cut-off 26 mV / 8 mW at 300 mA and 64 mV / 48 mW at 750 mA; on USB
  (VGS -4.45 V) 9 mV at 150 mA and 45 mV at 750 mA.
- Turn-off is slow (gate recharged through the 100 k across the 10 nF: ~3-4 ms);
  firmware blanks the chain before dropping ``enable``.
- Battery insertion (once, at assembly): SYS steps up with the cell while the
  discharged 10 nF and Ciss hold the gate near the 0 V drain, so the FET is
  fully on (VGS ~ -SYS), not soft-started. VLED follows SYS in a few-us step
  limited only by the cell, contact and FET resistances plus MLCC ESR (about
  0.25 ohm in all: ~15 A peak, tau ~4 us into <= 15 uF), inside the AO3401A's
  27 A pulsed IDM (p.1) and its 10 us single-pulse SOA (Fig 9 p.4: 27 A
  from VDS ~3 V up, RDS(on)-limited below). Once VLED has dragged
  the gate (through the 10 nF) up to the plateau the FET leaves full
  enhancement, and the 100 k pull-up turns it off within ~1 ms. The LEDs power
  up dark with DIN low and no data, which is harmless. A USB plug-in with the
  cell present lifts SYS by ~1 V with the gate held by the 10 nF: VGS can dip
  just past threshold, and VLED rises at most a few hundred mV, self-limited by
  the same gate-drain coupling, then decays: below WS2812C operation.
- BSS138 only sinks the 100 k pull-up (<= 45 uA at 4.9 V) and the gate charge,
  so the 3.3 V nRF drive (VGS(th) <= 1.5 V, BSS138 p.2) is ample regardless of
  LED load; its drain sees at most SYS (5.2 V).
- Bulk 10 uF X5R on VLED at the FET drain (0402 10 V; ~40-50 % left at 4 V DC
  bias) plus 50 x 100 nF at the LEDs: 9-15 uF effective. Against ~100 nH of
  battery lead a 300 mA step rings by I x sqrt(L/C) <= 0.3 x sqrt(100n/9u) = 32 mV.

Firmware: switch VLED off below ~3.4 V battery (WS2812C VDD min 3.3 V); drive DIN
low whenever VLED is off (back-power through the DIN protection diode).
"""

from dataclasses import dataclass
from itertools import pairwise

from jitx import Circuit, Design, Net
from jitx.board import Board
from jitx.common import Power
from jitx.landpattern import Pad
from jitx.net import Port, ShortTrace
from jitx.shapes.primitive import Circle
from jitx.transform import Transform
from jitx.units import F, V, ohm
from jitxlib.parts import AtLeast, Capacitor, CapacitorQuery, Minimize, Resistor, ResistorQuery

from ..components.leds.worldsemi_WS2812C_2020 import WS2812C_2020_V6
from ..components.transistors.aos_AO3401A import AO3401A
from ..components.transistors.diodes_BSS138 import BSS138
from ..substrate import ProximityFearSubstrate

BOARD_RADIUS = 25.0  # mm, ARCHITECTURE.md Board: 50 mm circle
RIM_KEEPOUT = 1.0  # mm, case lip band
# The 100 nF resolves to an 0402 (CL05B104KO5NNNC) whose land pattern only exists
# once the runtime resolves the part: pads 0.60 x 0.48 at +-0.51 on its y axis,
# p1 at +y, courtyard 1.1 x 2.0. Turned +90 deg in the LED frame its pads run
# tangentially with p1 at -x. tests/test_cir03_led_rings.py checks the realized
# geometry (courtyards, 0.15 mm pad clearance, cap p1 beside VDD).
CAP_PAD_HALF_PITCH = 0.51  # mm
CAP_COURTYARD_HALF_WIDTH = 0.55  # mm
# User requirement (board review): courtyards never abut; >= 0.10 mm between them. 0.11
# keeps a 0.01 mm margin over the floor against rotated-polygon float noise.
CAP_COURTYARD_GAP = 0.11  # mm


def cap_offset(led: WS2812C_2020_V6) -> Transform:
    """Cap pose in the LED's frame, from the LED model's VDD pad and courtyard.

    p1 sits directly over the VDD pad; the cap courtyard sits CAP_COURTYARD_GAP beyond the LED's.
    """
    pad = led.pad_mapping[led.VDD]
    if not isinstance(pad, Pad) or pad.transform is None:
        raise ValueError("WS2812C VDD maps to no single placed pad")
    vdd = pad.transform
    vdd_x, _ = vdd.translation
    _, _, _, courtyard_top = led.landpattern.courtyard.shape.to_shapely().g.bounds
    return Transform((vdd_x + CAP_PAD_HALF_PITCH, courtyard_top + CAP_COURTYARD_GAP + CAP_COURTYARD_HALF_WIDTH), 90.0)


@dataclass(frozen=True)
class RingSpec:
    """One ring of the chain, in the rings' frame (origin = board centre)."""

    radius_mm: float
    count: int
    angle_offset_deg: float
    clockwise: bool = False
    """Chain direction around the ring; also puts VDD and its cap inside (True) or outside."""

    def angle_deg(self, k: int) -> float:
        """Polar angle of LED ``k``."""
        step = 360.0 * k / self.count
        return self.angle_offset_deg - step if self.clockwise else self.angle_offset_deg + step

    def led_pose(self, k: int) -> Transform:
        """Pose of LED ``k``: on the circle, its -x axis (DI -> DO) along the chain."""
        t = self.angle_deg(k)
        centre = Transform.rotate(t) * (self.radius_mm, 0.0)
        return Transform(centre, t + 90.0 if self.clockwise else t - 90.0)

    def cap_pose(self, k: int, offset: Transform) -> Transform:
        """Pose of LED ``k``'s decoupling cap, ``offset`` (see ``cap_offset``) in that LED's frame."""
        return self.led_pose(k) * offset


RING_SPECS: tuple[RingSpec, ...] = (
    RingSpec(9.5, 10, 90.0),
    # inner ring's last DO (r 10.09, 90 + 324 + 5.2 deg) and this ring's first
    # DI (r 14.98, offset - 3.5 deg) on one radius
    RingSpec(15.5, 16, 62.8),
    # middle ring's last DO (r 16.08, 43.5 deg) runs out through the free gap
    # 7-11 deg counter-clockwise of this ring's first LED (between its cap and
    # the last LED), then turns onto that LED's outer-row DI
    RingSpec(21.5, 24, 34.5, clockwise=True),
)


class LEDSwitch(Circuit):
    """AO3401A high-side switch, SYS -> VLED, soft-started, default off."""

    vin = Power()  # SYS (PowerSupply.sys), 3.0-5.2 V; never VBAT (AN1149 p.5)
    vled = Power()  # switched output to the rings
    enable = Port()  # nRF GPIO, high = LEDs powered

    def __init__(self) -> None:
        self.q_switch = AO3401A()
        self.q_drive = BSS138()
        self.r_gate_pu = Resistor(resistance=100e3 * ohm)
        self.r_gate_on = Resistor(resistance=10e3 * ohm)
        self.c_soft = Capacitor(
            capacitance=10e-9 * F, rated_voltage_dc=AtLeast(10.0 * V), temperature_coefficient_code="X7R"
        )
        self.r_enable_pd = Resistor(resistance=100e3 * ohm)
        self.c_bulk = Capacitor(
            capacitance=10e-6 * F, rated_voltage_dc=AtLeast(10.0 * V), temperature_coefficient_code="X5R"
        )
        # SYS reservoir at the switch input (N-06); 16 V for DC-bias margin at 5.2 V.
        self.c_sys = Capacitor(
            capacitance=10e-6 * F, rated_voltage_dc=AtLeast(16.0 * V), temperature_coefficient_code="X5R"
        )

        self.VIN = Net([self.vin.Vp, self.q_switch.S, self.r_gate_pu.p2])
        self.VLED = Net([self.vled.Vp, self.q_switch.D, self.c_soft.p2])
        self.GND = Net([self.vin.Vn, self.vled.Vn, self.q_drive.S, self.r_enable_pd.p2, self.c_bulk.p2, self.c_sys.p2])
        self.GATE = Net([self.q_switch.G, self.r_gate_pu.p1, self.r_gate_on.p1, self.c_soft.p1])
        self.GATE_PULL = self.r_gate_on.p2 + self.q_drive.D
        self.ENABLE = Net([self.enable, self.q_drive.G, self.r_enable_pd.p1])
        self.c_bulk_st = ShortTrace(self.c_bulk.p1, self.q_switch.D)
        self.c_sys_st = ShortTrace(self.c_sys.p1, self.q_switch.S)


class LEDRings(Circuit):
    """Three concentric rings of chained WS2812C-2020 LEDs plus their switch."""

    vin = Power()  # connect to PowerSupply.sys (SYS, 3.0-5.2 V); Vn is GND
    din = Port()  # chain data in, from an nRF full-drive pin
    enable = Port()  # nRF GPIO, high = VLED on
    vled = Power()  # switched LED rail (Vp) and GND (Vn), for the assembly's VLED plane

    def __init__(self) -> None:
        self.switch = LEDSwitch()
        self.rings: list[list[WS2812C_2020_V6]] = [
            [WS2812C_2020_V6().at(spec.led_pose(k)) for k in range(spec.count)] for spec in RING_SPECS
        ]
        self.ring_caps: list[list[Capacitor]] = [
            [
                Capacitor(
                    capacitance=100e-9 * F, rated_voltage_dc=AtLeast(10.0 * V), temperature_coefficient_code="X7R"
                ).at(spec.cap_pose(k, cap_offset(led)))
                for k, led in enumerate(ring)
            ]
            for spec, ring in zip(RING_SPECS, self.rings, strict=True)
        ]
        self.r_din = Resistor(resistance=33.0 * ohm)

        leds = [led for ring in self.rings for led in ring]
        caps = [cap for ring in self.ring_caps for cap in ring]

        self.VIN = self.vin + self.switch.vin
        self.ENABLE = self.enable + self.switch.enable
        self.VLED_OUT = self.vled + self.switch.vled
        self.VLED = Net([self.switch.vled.Vp, *(led.VDD for led in leds)])
        self.GND = Net([self.vin.Vn, self.switch.vled.Vn, *(led.GND for led in leds), *(c.p2 for c in caps)])
        self.c_led_st = [ShortTrace(cap.p1, led.VDD) for led, cap in zip(leds, caps, strict=True)]

        self.DIN = self.din + self.r_din.p1
        self.DIN_LED = self.r_din.p2 + leds[0].DI
        self.DATA = [a.DO + b.DI for a, b in pairwise(leds)]
        leds[-1].DO.no_connect()


class RoundBoard(Board):
    """ARCHITECTURE.md Board: 50 mm circle, 1 mm rim keepout for the case lip."""

    shape = Circle(radius=BOARD_RADIUS)
    signal_area = Circle(radius=BOARD_RADIUS - RIM_KEEPOUT)


class TestDesign(Design):
    """LEDRings on the project substrate and board outline, with the assembly's passive defaults."""

    substrate = ProximityFearSubstrate()
    board = RoundBoard()
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    circuit = LEDRings()
