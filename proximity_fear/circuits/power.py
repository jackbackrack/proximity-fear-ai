"""Power: USB-C sink, MCP73831 charger, VBUS/VBAT load-sharing power path,
AP2112K 3V3 LDO, reverse-battery P-FET, battery connector and VBAT sense
divider (cir-01).

Ported from socialbadge-ai rev 2 (`circuits/usb_c.py`, `charger.py`,
`power_path.py`, `ldo_3v3.py` and the reverse-battery FET + J2 in
`designs/badge_main.py`), all brought up on rev 2. Changes from rev 2:

- USB D+/D- end at the nRF52840 with no series resistors. The 27 Ohm parts
  were the RP2040's; the E73 internal schematic (manual p.11) runs the nRF's
  D+ (AD6) and D- (AD4) straight to module pads 31/29, and the nRF52840 PS
  reference circuits likewise connect D+/D- directly to the connector.
- R_PROG 4.99 kOhm (E96; I_REG = 1000 V / R_PROG = 200 mA, MCP73831 p.15) for
  the ~500 mAh cell (ARCHITECTURE Power Tree), switched by a BSS138 so the nRF
  can stop charging (charge enable, M-8; see `Charger`).
- VBUS surge TVS (SZSMF5.0AT1G) at the receptacle (M-8; MCP73831 p.18
  sec 6.1.1.2; see `UsbC`).
- Charge LED is anchored on VBUS instead of 3V3, and STAT is also read by an
  nRF GPIO through a divider (see `Charger`).
- Battery side of the power path is an AO3401A load-sharing switch instead
  of rev 2's SS14 (Microchip AN1149; see `PowerPath`), so 3V3 stays
  regulated down to VBAT ~3.4 V.
- VBAT sense divider, 1.5 MOhm + 1.5 MOhm (ARCHITECTURE Design Notes; see `Battery`).
- SYS is a port (`PowerSupply.sys`): the LED switch hangs off SYS, not VBAT,
  so the charger output feeds only the cell (AN1149 p.5 "Connecting the
  system load to the battery"; MCP73831 terminates at ITERM = 7.5 % of
  I_REG, which a load on VBAT would mask).

Power tree (ARCHITECTURE.md):
    J1 VBUS ─┬─ TVS to GND (at the receptacle)
             ├─ MCP73831 VDD ─> VBAT (charge; PROG ─ R_PROG ─ BSS138 ─ GND, gate = chg_en)
             ├─ SS14 A─K ─────────────────────> SYS ─ AP2112K ─ 3V3
             ├─ gate of Q_bat (10 k to GND)
             └─ nRF VBUS (port vbus)
    J2 pin 1 ─ Q_rev D─S ─ VBAT ─ Q_bat D─S ──> SYS (port sys: LDO, LED switch)
"""

from jitx import Circuit, Net
from jitx.common import Power
from jitx.container import inline
from jitx.net import Port, ShortTrace
from jitx.sample import SampleDesign
from jitx.units import V, kohm, nF, ohm, uF
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

from ..components.connectors.hroparts_TYPE_C_31_M_12 import TYPE_C_31_M_12
from ..components.connectors.shouhan_PH2_2P import PH2_2P
from ..components.diodes.kt_0603_red import KT_0603R
from ..components.diodes.mdd_SS14 import SS14
from ..components.power_linear_regulators.diodes_AP2112K_33TRG1 import AP2112K_33TRG1
from ..components.power_linear_regulators.microchip_MCP73831T_2ACI_OT import MCP73831T_2ACI_OT
from ..components.protection.nexperia_PESD5V0S1BL import PESD5V0S1BL
from ..components.protection.onsemi_SZSMF5_0AT1G import SZSMF5_0AT1G
from ..components.protection.st_USBLC6_2SC6 import USBLC6_2SC6
from ..components.test_points.test_point import TestPoint
from ..components.transistors.aos_AO3401A import AO3401A
from ..components.transistors.diodes_BSS138 import BSS138

# Sink advertisement Rd (USB Type-C spec; TYPE-C-31-M-12 spec note).
R_CC = 5.1 * kohm
# MCP73831 I_REG = 1000 V / R_PROG (p.15 eq. 5-1; p.3 IREG 90-110 mA at 10 k).
# R_PROG is in series with the charge-enable BSS138, whose RDS(on) adds to it:
# ~2.9 Ohm at VGS 2.75 V / 25 C and 4.8 Ohm at 150 C (BSS138 p.3 Fig. 6; the
# gate sees 3V3 >= 3.25 V, so less). With <= 5 Ohm the 4.99 kOhm (E96) total is
# 4.990-4.995 kOhm -> 200.4-200.2 mA, a <= 0.1 % shift inside the 1 %
# resistor and the +-10 % IREG tolerance: no value change is needed.
R_PROG = 4.99 * kohm
# Charge-enable gate pull-up to 3V3: charging on by default; the nRF pulls the
# gate low to stop charging. 33 uA while held low; nothing on battery alone.
R_CHG_EN_PULLUP = 100 * kohm
# Charge LED: (5 V - VF 2.0 V) / 1 kOhm = 3 mA, STAT sinks up to 25 mA (p.4 ISINK).
R_CHG_LED = 1.0 * kohm
# STAT -> GPIO divider, ratio 180 / 280 = 0.643 (100k / 180k, 1 %: 0.638-0.647).
# - Low end: guaranteed VOH = VDD - 1 V (MCP73831 p.4, ISOURCE 4 mA; the
#   divider draws ~17 uA) at VBUS 4.75 V gives 3.75 V x 0.638 = 2.39 V, above the
#   nRF VIH = 0.7 x VDD (PS p.156) = 2.35 V even at 3V3 +1.5 % (3.3495 V,
#   AP2112K p.8). The old 100k/150k gave 2.25 V, below it (ov-power).
# - High end: VOH <= VDD = 5.25 V gives 5.25 x 0.647 = 3.40 V, under the nRF
#   VI/O abs max VDD + 0.3 V (PS p.612) = 3.55 V at 3V3 -1.5 % (3.2505 V).
R_STAT_TOP = 100 * kohm
R_STAT_BOT = 180 * kohm
# Load-share gate pull-down (AN1149 p.5 "Selecting The Pull-Down Resistor":
# any reasonable value, not so small that it wastes current). 10 kOhm (A-08):
# with USB present it draws 5 V / 10 k = 0.5 mA (0.1 % of the 500 mA budget)
# and dissipates 2.5 mW (5.25 V: 2.8 mW), 4 % of an 0402's 62.5 mW. On unplug
# it discharges the VBUS caps (USBLC6 100 nF + charger 4.7 uF + nRF 4.7 uF,
# <= 9.5 uF) with tau <= 95 ms instead of 0.95 s, so Q_bat turns on in
# ~25-65 ms (see `PowerPath`). The gate sits on VBUS, so it is also the VBUS
# bleed against SS14 reverse leakage from SYS when unplugged: VBUS stays under
# the nRF's 3.4 V VBUS-detect minimum (PS p.82) for any leakage below 340 uA,
# more than the SS14's 0.3 mA maximum at its full 40 V rating at 25 C.
R_GATE_PULL = 10 * kohm
# VBAT sense: 1.5 MOhm / 1.5 MOhm, 4.2 V -> 2.1 V, 1.4 uA. 3 MOhm (2.97 MOhm at
# -1 %) keeps VBAT above the MCP73831 no-battery impedance ZNO_BAT >= 2 MOhm
# (p.4; sec 4.2 p.13) with margin for FET and cap leakage in parallel; the old
# 1 M + 1 M was 1.98 MOhm at tolerance (ov-power). SAADC source impedance is
# 1.5 M || 1.5 M = 750 kOhm: firmware sets TACQ = 40 us (PS p.378 / p.397,
# <= 800 kOhm). The 100 nF holds the sample (CSAMPLE 2.5 pF max, PS p.397:
# < 0.01 % droop) and refills with tau = 750 k x 100 nF = 75 ms: sample no faster than
# ~1 Hz (5 tau = 0.4 s between samples).
R_VBAT_SENSE = 1.5e6 * ohm
C_VBAT_SENSE = 100 * nF


def _ceramic(capacitance: float, rated: float = 10 * V) -> Capacitor:
    """Supply ceramic: X5R, rated >= `rated` (10 V default for <= 4.6 V rails)."""
    return Capacitor(
        capacitance=capacitance,
        rated_voltage_dc=AtLeast(rated),
        temperature_coefficient_code="X5R",
    )


def _precise(resistance: float) -> Resistor:
    """1 % resistor for a value the circuit depends on."""
    return Resistor(resistance=resistance, tolerance=AtMost(0.01))


class UsbC(Circuit):
    """TYPE-C-31-M-12 as a USB 2.0 sink with ESD on CC, D+/D- and VBUS, plus a VBUS surge TVS.

    VBUS hot-plug (M-8): the cable inductance rings against the board's VBUS
    ceramics on attach. MCP73831 p.18 sec 6.1.1.2 asks for a transzorb from the
    connector's V+ to 0 V; the USBLC6's own VBUS clamp breaks down only at
    >= 6 V at 1 mA and is rated for ESD, not hot-plug energy (USBLC6 p.2). The
    SZSMF5.0AT1G (VBR 6.4-7.0 V at 10 mA, VC <= 9.2 V at 21.7 A, 200 W;
    onsemi SMF5.0AT1/D p.3) sits on the receptacle's second VBUS pad, cathode
    to VBUS, anode to GND. Choice, the hot-plug estimate and the residual
    worst case are in ``datasheets/SZSMF5.0AT1G.spec.md``.
    """

    vbus = Power()
    usb = USB2()

    def __init__(self) -> None:
        self.j1 = TYPE_C_31_M_12()
        self.esd = USBLC6_2SC6()
        self.esd_cc1 = PESD5V0S1BL()
        self.esd_cc2 = PESD5V0S1BL()
        self.tvs = SZSMF5_0AT1G()

        self.GND = Net(
            [
                self.vbus.Vn,
                *self.j1.GND,
                *self.j1.EH,
                self.esd.GND,
                self.esd_cc1.p2,
                self.esd_cc2.p2,
                self.tvs.A,
            ],
            name="GND",
        )
        self.VBUS = Net([self.vbus.Vp, *self.j1.VBUS], name="VBUS")
        # Surge TVS at the receptacle: cathode on J1's second VBUS pad (the
        # USBLC6 takes the first), anode to GND.
        self.st_tvs = ShortTrace(self.tvs.K, self.j1.VBUS[1])

        # D+/D- from both receptacle rows, flowing through the USBLC6:
        # connector on pins 3 (IO2[0]) / 1 (IO1[0]), nRF on 4 (IO2[1]) / 6 (IO1[1]).
        self.USB_DP_CONN = Net([self.j1.DP1, self.j1.DP2, self.esd.IO2[0]], name="USB_DP_CONN")
        self.USB_DN_CONN = Net([self.j1.DN1, self.j1.DN2, self.esd.IO1[0]], name="USB_DN_CONN")
        self.USB_DP = self.esd.IO2[1] + self.usb.data.p
        self.USB_DN = self.esd.IO1[1] + self.usb.data.n

        # USBLC6 VBUS rail clamp at the connector, 100 nF at pin 5 (p.9 Fig 18).
        self.st_esd_vbus = ShortTrace(self.j1.VBUS[0], self.esd.VBUS)
        self.c_esd_vbus = Capacitor(
            capacitance=100 * nF,
            rated_voltage_dc=AtLeast(10 * V),
            temperature_coefficient_code="X7R",
        )
        self.st_c_esd_vbus = ShortTrace(self.c_esd_vbus.p1, self.esd.VBUS)
        self.GND += self.c_esd_vbus.p2

        # CC: PESD5V0S1BL at each pin, then Rd 5.1 kOhm to GND.
        self.st_esd_cc1 = ShortTrace(self.j1.CC1, self.esd_cc1.p1)
        self.st_esd_cc2 = ShortTrace(self.j1.CC2, self.esd_cc2.p1)
        self.r_cc1 = _precise(R_CC)
        self.r_cc2 = _precise(R_CC)
        self.CC1 = Net([self.j1.CC1, self.r_cc1.p1], name="CC1")
        self.CC2 = Net([self.j1.CC2, self.r_cc2.p1], name="CC2")
        self.GND += Net([self.r_cc1.p2, self.r_cc2.p2])

        # Bring-up test point on VBUS at the receptacle.
        self.tp_vbus = TestPoint()
        self.st_tp_vbus = ShortTrace(self.tp_vbus.p1, self.j1.VBUS[0])

        # SBU1/SBU2 unused for USB 2.0; NC[0..1] are locating holes.
        self.j1.SBU1.no_connect()
        self.j1.SBU2.no_connect()


class Charger(Circuit):
    """MCP73831T-2ACI/OT: 200 mA from VBUS into the cell, firmware charge enable, STAT to LED and GPIO.

    STAT is tri-state (p.11 sec 3.3; Table 5-1 p.15): L charging, H complete
    (VOH = VDD - 0.4 V typ, VDD - 1 V min, p.4), Hi-Z shutdown / no battery.

    - LED: VBUS -> 1 kOhm -> LED -> STAT. Anchored on VBUS (rev 2 used 3V3)
      so that on battery alone (VDD = 0 V) no 3V3 reaches STAT, whose abs max
      is VDD + 0.3 V (p.3), and so a driven-high STAT cannot forward-bias it.
      Lit only while STAT sinks (charging).
    - GPIO: STAT drives ~VBUS when high, over the nRF's 3.6 V input abs max, so
      no pull-up to 3V3; a 100 k / 180 k divider to GND scales it (chg_stat;
      margins at ``R_STAT_TOP``). L -> 0 V (charging), H -> 2.4-3.4 V
      (complete). Hi-Z with VBUS present (no battery, fault, or charging
      disabled through chg_en) leaves ~2 V through the LED path, between VIL
      and VIH: firmware reads chg_stat only with VBUS detected and with
      charging enabled, and treats it as charge/no-charge.
    - Charge enable (ARCHITECTURE Design Notes, user decision 2026-11-15):
      PROG -> R_PROG -> BSS138 drain, source to GND. "If the PROG pin is open
      or floating, the MCP73831/2 are disabled ... the PROG pin acts as a
      charge enable and can be used as a manual shutdown" (sec 4.2 p.13;
      sec 5.2.2 p.15; sec 6.1.1.6 "Charge Inhibit" p.18). The guaranteed
      shutdown threshold is PROG impedance >= 200 kOhm (RPROG "Minimum Shutdown
      Impedance" 70-200 kOhm, p.4); the off BSS138 leaks <= 0.5 uA even at
      50 V (IDSS, BSS138 p.2), i.e. megohms at the ~1 V PROG level.
      Gate: 100 kOhm to 3V3 (charging ON by default) and the ``chg_en`` port
      (nRF GPIO; drive low = stop charging). VGS(th) <= 1.5 V (BSS138 p.2).
      With USB present SYS -> AP2112K -> 3V3 is up whenever VBUS is, and the
      nRF's GPIOs come out of reset as disconnected inputs (PIN_CNF reset
      0x00000002, PS p.155), so the pull-up holds charging on while the nRF
      is in reset, booting, or has no firmware; the nRF shares the 3V3 rail,
      so the gate can never be pulled high by a powered pull-up into an
      unpowered nRF pin. On battery alone VDD = 0 and the charger is off
      whatever the gate does. GPIO state is retained in System OFF: firmware
      releases chg_en (input or high) before System OFF unless it means
      charging to stay off.
    """

    vbus = Power()
    vbat = Power()
    v3v3 = Power()
    chg_stat = Port()
    chg_en = Port()

    def __init__(self) -> None:
        self.u1 = MCP73831T_2ACI_OT()
        self.led = KT_0603R()
        self.q_en = BSS138()

        self.GND = Net([self.vbus.Vn, self.vbat.Vn, self.v3v3.Vn, self.u1.VSS, self.q_en.S], name="GND")
        self.VBUS = Net([self.vbus.Vp, self.u1.VDD], name="VBUS")
        self.VBAT = Net([self.vbat.Vp, self.u1.VBAT], name="VBAT")

        # CIN >= 4.7 uF (p.11). COUT: 4.7 uF minimum for CV-loop stability
        # with no battery (sec 6.1.1.4 p.18); 10 uF (M-8) so the minimum
        # survives DC bias -- an X5R MLCC keeps roughly half its value at
        # 4.2 V. Rated 16 V for the same reason (resolves to 0603).
        self.c_vdd = _ceramic(4.7 * uF, rated=16 * V)
        self.st_c_vdd = ShortTrace(self.c_vdd.p1, self.u1.VDD)
        self.c_vbat = _ceramic(10 * uF, rated=16 * V)
        self.st_c_vbat = ShortTrace(self.c_vbat.p1, self.u1.VBAT)
        self.GND += Net([self.c_vdd.p2, self.c_vbat.p2])

        # PROG -> R_PROG -> charge-enable FET -> GND.
        self.r_prog = _precise(R_PROG)
        self.PROG = Net([self.u1.PROG, self.r_prog.p1], name="CHG_PROG")
        self.PROG_EN = Net([self.r_prog.p2, self.q_en.D], name="CHG_PROG_EN")
        self.r_en_pu = Resistor(resistance=R_CHG_EN_PULLUP)
        self.CHG_EN = Net([self.chg_en, self.q_en.G, self.r_en_pu.p1], name="CHG_EN")
        self.V3V3 = Net([self.v3v3.Vp, self.r_en_pu.p2], name="3V3")

        self.r_led = Resistor(resistance=R_CHG_LED)
        self.VBUS += self.r_led.p1
        self.CHG_LED_A = self.r_led.p2 + self.led.A
        self.STAT = Net([self.u1.STAT, self.led.K], name="CHG_STAT_RAW")

        self.r_stat_top = _precise(R_STAT_TOP)
        self.r_stat_bot = _precise(R_STAT_BOT)
        self.STAT += self.r_stat_top.p1
        self.CHG_STAT = Net([self.r_stat_top.p2, self.r_stat_bot.p1, self.chg_stat], name="CHG_STAT")
        self.GND += self.r_stat_bot.p2


class PowerPath(Circuit):
    """Load sharing per Microchip AN1149 (Fig 2 p.2, Figs 5-7 p.5-6).

    - VBUS -> SS14 (A on VBUS, K on SYS): AN1149's D1, blocks SYS back into VBUS.
    - VBAT -> AO3401A -> SYS: AN1149's Q1, drain on VBAT, source on SYS, so
      the body diode conducts VBAT -> SYS; gate on VBUS with a 10 kOhm
      pull-down to GND (R_PULL, also the VBUS bleed; see R_GATE_PULL).
    - VBUS present: VGS = VBUS - SYS = VF(SS14) >= 0, FET off (VGS(th) -0.5 to
      -1.3 V); SS14 feeds SYS (3V3 LDO and LED switch) while the charger
      charges the cell (VBAT carries only the cell and the ~2 uA sense
      divider). Body diode:
      SYS >= 4.75 V - 0.55 V (SS14 VF max at 1 A, more than at 430 mA) = 4.20 V
      against VBAT <= 4.232 V (VREG max), so VBAT - SYS <= 0.03 V, far below
      the ~0.7 V body-diode VSD: reverse-biased or off.
    - VBUS absent: gate pulled to 0 V, VGS = -SYS ~ -VBAT, FET on.
      RDS(on) <= 85 mOhm at VGS -2.5 V (60 mOhm at -4.5 V); at the 430 mA
      battery peak (3V3 130 mA + LED cap 300 mA, ARCHITECTURE Power Tree) that
      is <= 37 mV. 3V3 stays regulated down to VBAT ~ 3.3 V + AP2112K dropout
      (200 mV max at 300 mA, so less at its 130 mA) + 37 mV, about 3.4-3.55 V.
    - Unplug: once SYS falls to VBAT - VSD (body diode, ~0.7 V) the SS14
      reverse-biases and only R_PULL (10 k) discharges VBUS, from ~VBAT - 0.4 V
      down to the turn-on point SYS - |VGS(th)| = VBAT - 1.2..2.0 V. At
      VBAT 3.7 V that is 3.3 V -> 2.5..1.7 V, ln ratio 0.28..0.66, so with
      tau <= 95 ms Q_bat is on within ~25-65 ms (0.25-0.65 s with 100 k).
      Until then SYS rides one body-diode drop below VBAT and 3V3 sags with it
      (about 2.9-3.0 V at VBAT 3.7 V; nRF VDD minimum 1.7 V), briefly.
    """

    vbus = Power()
    vbat = Power()
    sys = Power()

    def __init__(self) -> None:
        self.d_usb = SS14()
        self.q_bat = AO3401A()
        self.r_pull = Resistor(resistance=R_GATE_PULL)
        self.GND = Net([self.vbus.Vn, self.vbat.Vn, self.sys.Vn, self.r_pull.p2], name="GND")
        self.VBUS = Net([self.vbus.Vp, self.d_usb.A, self.q_bat.G, self.r_pull.p1], name="VBUS")
        self.VBAT = self.vbat.Vp + self.q_bat.D
        self.SYS = Net([self.d_usb.K, self.q_bat.S, self.sys.Vp], name="SYS")


class Ldo3V3(Circuit):
    """AP2112K-3.3: SYS -> 3V3, EN tied to VIN (always on), NC pin unconnected."""

    vin = Power()
    vout = Power()

    def __init__(self) -> None:
        self.u1 = AP2112K_33TRG1()  # model marks NC (pin 4) no_connect
        self.GND = Net([self.vin.Vn, self.vout.Vn, self.u1.GND], name="GND")
        # EN has only a weak internal pull-down (RPD 3.0 MOhm typ, electrical
        # tables pp.4-8), not enough to define the pin by itself: tied to VIN,
        # always on (VIH 1.5 V min).
        self.SYS = Net([self.vin.Vp, self.u1.VIN, self.u1.EN], name="SYS")
        self.V3V3 = Net([self.vout.Vp, self.u1.VOUT], name="3V3")

        # 1 uF X5R/X7R on input and output (p.2 Note 4).
        self.c_in = _ceramic(1 * uF)
        self.st_c_in = ShortTrace(self.c_in.p1, self.u1.VIN)
        self.c_out = _ceramic(1 * uF)
        self.st_c_out = ShortTrace(self.c_out.p1, self.u1.VOUT)
        self.GND += Net([self.c_in.p2, self.c_out.p2])

        self.tp_3v3 = TestPoint()
        self.st_tp_3v3 = ShortTrace(self.tp_3v3.p1, self.u1.VOUT)


class Battery(Circuit):
    """J2 PH2-2P (pin 1 = BAT+, as rev 2), AO3401A reverse-battery FET, VBAT sense.

    The FET sits in the + lead: drain to J2 pin 1, source to VBAT, gate to GND
    (rev 2). A correct cell first conducts through the body diode, then
    VGS = -VBAT enhances the channel both ways (charging works); a reversed
    cell leaves VGS >= 0 and the body diode reverse-biased (on battery alone;
    with USB present the charger holds VBAT up and a reversed cell turns the FET
    on -- firmware stops charging through chg_en if VBAT sense reads < ~2 V with
    VBUS present, ARCHITECTURE Design Notes). VBAT sense is an unswitched
    1.5 M / 1.5 M divider with 100 nF at the midpoint. Its 3 MOhm (2.97 MOhm at
    -1 %) clears the MCP73831 no-battery impedance ZNO_BAT >= 2 MOhm (p.4;
    sec 4.2 p.13) with margin: the 6 uA detect current (IBAT_DET, p.4) still
    lifts VBAT past VREG + 100 mV with no cell. Source impedance 750 kOhm: the
    SAADC channel needs TACQ = 40 us (PS p.378 / p.397, <= 800 kOhm).
    """

    vbat = Power()
    vbat_sense = Port()

    def __init__(self) -> None:
        self.j2 = PH2_2P()
        self.q_rev = AO3401A()

        self.GND = Net([self.vbat.Vn, self.j2.PIN2, self.j2.MOUNT1, self.j2.MOUNT2, self.q_rev.G], name="GND")
        self.BAT_P = Net([self.j2.PIN1, self.q_rev.D], name="BAT_P")
        self.st_q_rev = ShortTrace(self.j2.PIN1, self.q_rev.D)
        self.VBAT = Net([self.q_rev.S, self.vbat.Vp], name="VBAT")

        self.r_sense_top = _precise(R_VBAT_SENSE)
        self.r_sense_bot = _precise(R_VBAT_SENSE)
        # Filter cap for the SAADC sample, not a power-rail capacitor.
        self.c_sense = Capacitor(
            capacitance=C_VBAT_SENSE,
            rated_voltage_dc=AtLeast(10 * V),
            temperature_coefficient_code="X7R",
        )
        self.VBAT += self.r_sense_top.p1
        self.VBAT_SENSE = Net(
            [self.r_sense_top.p2, self.r_sense_bot.p1, self.c_sense.p1, self.vbat_sense],
            name="VBAT_SENSE",
        )
        self.GND += Net([self.r_sense_bot.p2, self.c_sense.p2])

        self.tp_vbat = TestPoint()
        self.st_tp_vbat = ShortTrace(self.tp_vbat.p1, self.q_rev.S)


class PowerSupply(Circuit):
    """The badge's whole power tree behind typed ports.

    Ports and intended connections:
    - vbus: VBUS (to nRF support ``vbus``, which feeds pad 27 through 4.7 Ohm).
    - sys: SYS, the load-share output (3.0-4.9 V): feeds the LED switch
      (``LEDRings.vin``). Not VBAT: the charger output feeds only the cell.
    - vbat: VBAT after the reverse FET; no load belongs on it (test/inspection
      access only; the VBAT sense divider is inside).
    - v3v3: 3V3 (nRF VCC/VDDH and all 3V3 loads). Vn is GND on each rail.
    - usb: USB2 D+/D- from the USBLC6 to nRF D+ (pad 31) / D- (pad 29).
    - chg_stat: MCP73831 STAT scaled to 3.3 V logic (nRF GPIO input).
    - chg_en: charge enable, BSS138 gate with 100 k to 3V3 (nRF GPIO; leave as
      input or drive high = charging allowed, drive low = charging stopped).
    - vbat_sense: VBAT / 2 (nRF AIN).
    """

    vbus = Power()
    vbat = Power()
    sys = Power()
    v3v3 = Power()
    usb = USB2()
    chg_stat = Port()
    chg_en = Port()
    vbat_sense = Port()

    def __init__(self) -> None:
        self.usb_c = UsbC()
        self.charger = Charger()
        self.path = PowerPath()
        self.ldo = Ldo3V3()
        self.battery = Battery()

        self.VBUS = Net(
            [self.vbus.Vp, self.usb_c.vbus.Vp, self.charger.vbus.Vp, self.path.vbus.Vp],
            name="VBUS",
        )
        self.VBAT = Net(
            [self.vbat.Vp, self.battery.vbat.Vp, self.charger.vbat.Vp, self.path.vbat.Vp],
            name="VBAT",
        )
        self.SYS = Net([self.sys.Vp, self.path.sys.Vp, self.ldo.vin.Vp], name="SYS")
        self.V3V3 = Net([self.v3v3.Vp, self.ldo.vout.Vp, self.charger.v3v3.Vp], name="3V3")

        # GND test point: the GND pour reaches it; no copper object needed.
        self.tp_gnd = TestPoint()
        self.GND = Net(
            [
                self.vbus.Vn,
                self.vbat.Vn,
                self.sys.Vn,
                self.v3v3.Vn,
                self.usb_c.vbus.Vn,
                self.charger.vbus.Vn,
                self.charger.vbat.Vn,
                self.charger.v3v3.Vn,
                self.path.vbus.Vn,
                self.path.vbat.Vn,
                self.path.sys.Vn,
                self.ldo.vin.Vn,
                self.ldo.vout.Vn,
                self.battery.vbat.Vn,
                self.tp_gnd.p1,
            ],
            name="GND",
        )

        self.USB = self.usb + self.usb_c.usb
        self.CHG_STAT = self.chg_stat + self.charger.chg_stat
        self.CHG_EN = self.chg_en + self.charger.chg_en
        self.VBAT_SENSE = self.vbat_sense + self.battery.vbat_sense


class TestDesign(SampleDesign):
    # Mirrors the board's passive defaults (the assembly owns them).
    parts_lock = Lock(mode=LockMode.OFF)
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))

    @inline
    class circuit(Circuit):
        power = PowerSupply()
