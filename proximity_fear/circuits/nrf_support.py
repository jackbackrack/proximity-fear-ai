"""nRF52840 support: E73 module supply, LFXO crystal, SWD Tag-Connect, reset, user button (cir-02).

``NRFSupport`` extends the pin-01 provider ``NRF52840Pins`` (it owns the module), so the
assembly requires GPIO interfaces straight from it and this file wires the fixed-function
pins. Sources:

* nRF52840 Product Specification v1.1 (``datasheets/nRF52840_PS.pdf``), section 7.3.3
  "Circuit configuration no. 3" (Figure 212 p.589, Table 153 p.590): VDDH = N/A, VDD =
  battery / external regulator, DCDCEN0 = DCDCEN1 = No, USB = Yes. This is the badge's
  case (normal-voltage mode, VDD = VDDH = 3V3, USB used). In Figure 212 VDDH (Y2) joins
  VDD (W1) on VDD_nRF and DCCH (AB2) is an unconnected pin stub; DECUSB has C20 4.7 uF; VBUS has C21 4.7 uF;
  P0.18/RESET has no external part; X2 32.768 kHz is "Optional" with C17/C18 to GND.
* Ebyte E73-2G4M08S1CX manual v1.2, p.11 "5.1 Hardware design and circuit schematic
  diagram" (``datasheets/E73-2G4M08S1CX.pdf`` PDF p.12): the module-internal schematic.
  Inside the module: 4.7 uF on VDD (C12), VDDH (C11) and DECUSB (C22); 100 nF on each VDD
  ball (C4, C23, C25); DEC1-DEC6 caps; REG1 DC/DC filter DCC -> L2 10 uH -> L1 15 nH ->
  DEC4; 32 MHz crystal; no cap on VBUS; no 32.768 kHz crystal. Comparing it with Table
  153 leaves one PS part outside the module: C21 4.7 uF on VBUS.
* PS 5.4.2.4 LFXO (pp.86-87) and the LFXO table 5.4.4.3 (p.97): CL = (C1' x C2') / (C1' + C2') with
  C1' = C1 + Cpcb1 + Cpin, so with equal legs C = 2 CL - Cpin - Cpcb; Cpin = 4 pF
  (XL1/XL2); CL_LFXO <= 12.5 pF, C0 <= 2 pF, ESR <= 100 kOhm, drive 0.5 uW.
  Load caps are 16 pF C0G +-5 % (closure audit W-2): with this board's strays (lands ~1.9 pF,
  ~0.12 pF/mm over 5.65 / 8.25 mm of XL1 / XL2 route, up to 0.5 pF inside the module) the
  worst-case effective CL is 12.0 pF; Nordic's 2 pF Cpcb (Table 153) under-counts this board.
* PS 6.9 GPIO (pp.148-149, 6.9.1 "Pin configuration"): SENSE / DETECT works in System OFF
  (button wake); RPU internal pull-up 11-16 kOhm (6.9.3.1, p.157).
* PS 4.8.1 DAP (p.51): SWDIO internal pull-up, SWDCLK internal pull-down; Rpull 13 kOhm (p.53).
* PS Table 142 (AD22, p.577): P1.00 = TRACEDATA[0] / SWO.

Engineering question (PLAN cir-02): no external DC/DC inductor. REG1's LC filter (10 uH +
15 nH, DCC -> DEC4) is inside the module (Ebyte p.11), so firmware may set DCDCEN = 1 for
REG1 (lower run current); with it off the module still works (PS config 3 runs both
regulators in LDO mode). REG0 is idle in normal-voltage mode, so DCCH (REG0 output) is
left unconnected as Figure 212 shows (marked no-connect on module pad 25).

Design choices (not in either source):

* No capacitor at the module VCC pad (M-8, ov-nrf WARNING): the module already carries
  4.7 uF on VDD (C12) and 4.7 uF on VDDH (C11) -- one net here, VDD = VDDH -- plus 100 nF
  per VDD ball (C4, C23, C25; Ebyte p.11). That is already above the PS limit on
  "effective decoupling capacitance on the VDD pin", CVDD 2.7 / 4.7 / 5.5 uF min/typ/max
  (PS 5.3.8.1, p.80); PS config 3 itself fits one 4.7 uF (C6, Figure 212 p.589). Any
  external VCC cap only adds to that excess, so none is fitted; the AP2112K's 1 uF output
  cap sits at the regulator.
* Button: no RC debounce. The internal pull-up holds the line, SENSE wakes System OFF on
  the first low level whatever the bounce, and firmware debounces in System ON (~20 ms).
* RESET: no external pull-up or capacitor (PS Figure 212 has none; a capacitor would also
  stretch tPINR, PS 5.3.8.3 p.81). Firmware must program UICR PSELRESET[0/1] = 18
  for pin reset (PS 4.5.1.4, p.45); until then P0.18 is a plain GPIO.
* USB VBUS series resistor (A-02): 4.7 Ohm 1 % between the VBUS port and module pad 27,
  ahead of the 4.7 uF. PS p.583: the reference schematics "include an optional series
  resistor on the USB supply for improved immunity to transient overvoltage during VBUS
  connection. Using the series resistor is recommended for new designs" (the general
  reference-circuit note on p.583); value from the config-1 BOM (Table 149, p.586:
  R1 4R7 +-1 % 0402; Figure 210 p.585). Config 3 (Figure 212 p.589 / Table 153 p.590)
  draws no R1, so the resistor is added to it per the p.583 bullet. The USBLC6 in cir-01 does not protect the pad
  here: its VBUS-to-GND breakdown is >= 6 V, above the nRF VBUS abs max of 5.8 V (PS p.612),
  so the resistor and the 4.7 uF are what tame the cable-attach ring. Drop: the USB
  regulator draws 2.4 mA from VBUS with USB active (IUSB,ACTIVE,VBUS, PS p.569), 11 mV across
  4.7 Ohm, so a host at the USB 4.75 V minimum (or a drooped 4.40 V) still leaves the pad
  above the 4.35 V VBUS minimum (PS p.611). Attach inrush into the 4.7 uF peaks at
  ~5 V / 4.7 Ohm = 1.1 A for tau = 22 us (59 uJ in the resistor), the PS's own 0402 duty.
"""

from jitx.circuit import Circuit
from jitx.common import Power
from jitx.container import inline
from jitx.net import Net, Port, ShortTrace
from jitx.sample import SampleDesign
from jitx.units import V, ohm, pF, uF
from jitxlib.parts import (
    AtLeast,
    AtMost,
    Capacitor,
    CapacitorQuery,
    Lock,
    LockMode,
    Minimize,
    Resistor,
    ResistorQuery,
)
from jitxlib.protocols.usb import USB2

from ..components.buttons.xkb_TS_1187A import TS_1187A_B_A_B
from ..components.connectors.tagconnect_TC2030 import TC2030NL
from ..components.crystals.epson_FC135 import Q13FC13500004
from .nrf_pins import NRF52840Pins

VBUS_SERIES_RESISTANCE = 4.7 * ohm
"""PS config-1 BOM R1 4R7 (Table 149, p.586); the series resistor is recommended for new designs (p.583)."""
LFXO_PIN_CAPACITANCE = 4 * pF
"""Cpin, input capacitance on XL1 and XL2 (PS 5.4.4.3 LFXO table, p.97)."""
LFXO_PAD_CAPACITANCE = 1.9e-12
"""Lands per leg on Bottom over L3 GND, 0.0764 mm of 1080 prepreg (Er 3.91, JLC04161H_1080):
0.453 pF/mm^2 parallel plate x (E73 castellated land 1.8 + FC-135 land 1.8 + 0402 land 0.29
mm^2) + 10 % fringe ~= 1.9 pF, in farads (closure audit W-2)."""
LFXO_TRACE_CAPACITANCE_PER_MM = 0.12e-12
"""Farads per mm: 0.125 mm microstrip over GND at 0.0764 mm, soldermask and coplanar pour."""
LFXO_TRACE_LENGTHS_MM = (4.1 + 1.55, 6.9 + 1.35)
"""XL1, XL2: module pad -> crystal pad as placed by asm-01, plus the load-cap stub."""
LFXO_MODULE_ROUTING_CAPACITANCE = 0.5e-12
"""Farads: upper bound for the E73's internal XL1/XL2 routing (unpublished; 0-0.5 pF assumed)."""
LFXO_LOAD_TOLERANCE = 0.05
"""C0G load cap tolerance asked of the part (J, +-5 %)."""
LFXO_LOAD_CAPACITOR = 16 * pF
"""Largest E24 value whose worst case (+5 % cap, both legs' strays, module routing) keeps the
effective CL within the PS 12.5 pF maximum: 16 pF -> 12.0 pF worst, 11.4 pF nominal; 18 pF
would give 13.1 pF worst (``lfxo_effective_load``). Pull at ~11.4 pF vs the FC-135's 12.5 pF:
about +5...+12 ppm, inside its +-20 ppm and the BLE +-500 ppm budget."""


def lfxo_pcb_capacitance(trace_mm: float) -> float:
    """Board stray per leg (farads): lands plus trace (``LFXO_*`` constants)."""
    return LFXO_PAD_CAPACITANCE + LFXO_TRACE_CAPACITANCE_PER_MM * trace_mm


def lfxo_load_capacitance(crystal_cl: float, c_pin: float, c_pcb: float) -> float:
    """Per-leg load capacitor (farads) for the nRF52840 LFXO, PS 5.4.2.4 (pp.86-87) with C1 = C2."""
    return 2 * crystal_cl - c_pin - c_pcb


def lfxo_effective_load(c1: float, c2: float, c_pin: float, c_pcb1: float, c_pcb2: float) -> float:
    """CL seen by the crystal, PS 5.4.2.4 (pp.86-87): C1' C2' / (C1' + C2'), Cx' = Cx + Cpcbx + Cpin."""
    a, b = c1 + c_pcb1 + c_pin, c2 + c_pcb2 + c_pin
    return a * b / (a + b)


class NRFSupport(NRF52840Pins):
    """E73 module in normal-voltage mode with its board-level support parts."""

    v3v3 = Power()
    """3V3 rail (Vp) and GND (Vn): module VCC = VDD and VDDH, the SWD probe VCC."""
    vbus = Power()
    """USB VBUS (Vp, from cir-01 ``vbus``), through 4.7 Ohm to module VBUS, pad 27; Vn = GND."""
    usb = USB2()
    """USB data from cir-01's USBLC6: data.p to D+ (pad 31), data.n to D- (pad 29)."""
    nfc1 = Port()
    """NFC1 = P0.09 (pad 41), to cir-06 ``nfc1``."""
    nfc2 = Port()
    """NFC2 = P0.10 (pad 43), to cir-06 ``nfc2``."""
    button = Port()
    """User button contact; the assembly nets it to ``require(GPIO).gpio`` (internal pull-up)."""

    def __init__(self) -> None:
        super().__init__()
        m = self.module
        self.xtal = Q13FC13500004()
        self.swd = TC2030NL()
        self.sw_user = TS_1187A_B_A_B()

        # Supply, PS config 3 (Figure 212): VDDH joins VDD; DCCH (REG0 output) unconnected.
        self.P3V3 = Net([self.v3v3.Vp, m.VCC, m.VDDH, self.swd.VCC])
        m.DCCH.no_connect()
        # No external VCC cap: the module's own 4.7 uF + 4.7 uF already exceed CVDD max (PS p.80).
        self.GND = Net([self.v3v3.Vn, self.vbus.Vn, *m.GND, self.swd.GND, self.sw_user.C, self.sw_user.D])

        # USB: VBUS -> R1 4.7 Ohm (PS p.583 note; value from config-1 BOM p.586) -> pad 27
        # with PS C21 4.7 uF (not inside the module, Ebyte p.11); D+/D- direct.
        self.r_vbus = Resistor(resistance=VBUS_SERIES_RESISTANCE, tolerance=AtMost(0.01))
        self.VBUS = Net([self.vbus.Vp, self.r_vbus.p1])
        self.VBUS_NRF = Net([self.r_vbus.p2, m.VBUS])
        self.c_vbus = Capacitor(
            capacitance=4.7 * uF,
            rated_voltage_dc=AtLeast(16 * V),  # 5 V VBUS: PS Table 153 C21 is 0603; >= 16 V limits DC-bias loss
            temperature_coefficient_code="X5R",
        )
        self.st_c_vbus = ShortTrace(self.c_vbus.p1, m.VBUS)
        self.GND += self.c_vbus.p2
        self.USB_DP = self.usb.data.p + m.D_P
        self.USB_DN = self.usb.data.n + m.D_N

        # LFXO: FC-135 across XL1/XL2, one C0G load cap per leg to GND.
        self.c_xl = [
            Capacitor(
                capacitance=LFXO_LOAD_CAPACITOR,
                tolerance=AtMost(LFXO_LOAD_TOLERANCE),
                rated_voltage_dc=AtLeast(25 * V),
                temperature_coefficient_code="C0G",
            )
            for _ in range(2)
        ]
        self.XL1 = Net([m.XL1, self.xtal.XTAL[0]])
        self.XL2 = Net([m.XL2, self.xtal.XTAL[1]])
        self.st_c_xl = [
            ShortTrace(self.c_xl[0].p1, m.XL1),
            ShortTrace(self.c_xl[1].p1, m.XL2),
        ]
        self.GND += Net([c.p2 for c in self.c_xl])

        # SWD Tag-Connect: SWDIO, SWDCLK, SWO = P1.00, nRESET = P0.18.
        swo = self.swd.swd.swo
        if swo is None:
            raise ValueError("TC2030NL SWD bundle has no SWO line")
        self.SWDIO = Net([self.swd.swd.swdio, m.SWDIO])
        self.SWDCLK = Net([self.swd.swd.swdclk, m.SWDCLK])
        self.SWO = Net([swo, m.P1_00])
        self.RESET = Net([self.swd.nRESET, m.RESET])

        # NFC antenna pins to cir-06.
        self.NFC1 = Net([self.nfc1, m.NFC1])
        self.NFC2 = Net([self.nfc2, m.NFC2])

        # User button: A/B contact to the GPIO side, C/D to GND (TS-1187A drawing).
        self.BUTTON = Net([self.button, self.sw_user.A, self.sw_user.B])


class TestDesign(SampleDesign):
    """The support circuit alone, at the assembly's passive defaults."""

    parts_lock = Lock(mode=LockMode.OFF)

    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))

    @inline
    class circuit(Circuit):
        def __init__(self) -> None:
            self.nrf = NRFSupport()
