"""Proximity Fear Badge: top-level circuit, board outline and net classes (asm-01).

The buildable ``Design`` (substrate, passive defaults, rule set) is ``proximity_fear.main``.

50 mm round badge on the JLC04161H_1080 4-layer stackup (ARCHITECTURE.md ``Board``).
Front (Top): three WS2812C LED rings (``LEDRings``) and the ToF / IR centre sensors.
Back (Bottom): the E73 nRF52840 module, the bottom-port PDM mic (its port hole at (+4.5, 0)
opens to the front through the board) and everything else.

Power (ARCHITECTURE Power Tree, Phase 3b A-01): the LED switch (``LEDRings.vin``) is fed
from SYS, so on USB the LEDs run from VBUS through the SS14 and on battery through the
load-share FET; VBAT has no load outside ``PowerSupply``. VLED: 300 mA firmware cap on
battery, ~150 mA on USB, 750 mA all-white.

Interfaces (ARCHITECTURE.md ``Interface Map``), all through the E73 provider's
provide/require offers (pin-01), no SI constraints on any of them (12 Mb/s USB FS over
~30 mm, 400 kHz I2C, 800 kHz LED data, 1-3 MHz PDM: all "SI constrained: no"):

- USB D+/D-: ``PowerSupply.usb`` (after the USBLC6) to the module's D+/D- pads.
- I2C x1 to the ToF, with the bus pull-ups here at the aggregation level (below).
- FastGPIO x2: LED chain data (through ``LEDRings.r_din``, 33 ohm) and IR TX.
- PDM x1: mic CLK / DIN.
- GPIO x8: LED rail enable, IR RX, IR RX supply enable (active low), ToF XSHUT, ToF GPIO1
  interrupt, user button, charge STAT, charge enable.
- Every require() is pinned to one pad by a restriction; the table is in ``main.py``.
- ADC x1: VBAT / 2.
- NFC1/NFC2 (fixed P0.09/P0.10) to the NFC antenna pads and tuning caps.

I2C pull-ups: 2.2 kOhm to 3V3. VL53L4CX DS13805 p.5 Table 3 / Figure 3 gives the
400 kHz pull-up range; the ToF circuit (cir-04) records a 3.6 kOhm maximum. Lower bound
from the I2C spec's 3 mA VOL sink at 0.4 V: (3.3 V - 0.4 V) / 3 mA = 0.97 kOhm. 2.2 kOhm
sits between them: rise time 0.8473 x 2.2 kOhm x ~30 pF (one device, ~40 mm of trace,
nRF + ToF pins) = 56 ns, far under the 300 ns fast-mode limit.

Placement (board frame, mm, origin = board centre = ToF, +y = 12 o'clock as seen from the
front; Bottom parts are placed with ``on=Side.Bottom``, so their coordinates are also
front-view coordinates):

- USB-C J1 on the 6 o'clock tab, rotation 0 (an exact multiple of 90 deg, socialbadge
  0b6f855), mouth at the tab edge 3.94 mm from its origin as on socialbadge rev 2; the tab
  keeps its shell slots >= 0.3 mm from all Top ring copper.
- E73 module turned 180 deg in the north half, IPEX connector toward 12 o'clock so the
  FPC antenna lead stays short and the keep-clear stays inside r 24 mm; the castellated
  XL1/XL2 pads (11/13) then face the board centre.
- JST-PH J2 at 3 o'clock, signal-land (mating) side toward the rim (PH2-2P spec note);
  reverse-battery FET north of it, VBAT sense divider and the LED switch (fed from SYS)
  beside it.
- Mic on Bottom turned 180 deg about its port, body toward -y clear of the E73. It sits
  under XL1/XL2, so the 32.768 kHz crystal is upright just east of the module (R-02):
  pad 1 north on XL1, pad 2 south on XL2, no crossing; estimated XL1 ~4.1 mm, XL2
  ~6.9 mm (XL2 runs east in the corridor below pad 11, >= 2 mm from mic CLK/DATA).
- IR receiver supply switch (``sensors.ir_receiver.q_en`` + gate pull-up) under the
  receiver at (-4.5, 0).
- User button at 9 o'clock on the rim.
- NFC antenna pads near the rim at 10-11 o'clock, beside the E73's NFC1/NFC2 pads (41/43);
  tuning and trim caps mirror-symmetric about the pads' centreline.
- TC2030 west of the module's SWD pads, its three alignment holes (+0.5 mm) clear of every
  Top courtyard (they sit in the gaps between the inner and middle ring parts).
- Everything else on Bottom near the part it serves (``place_back_side``).
"""

import math
from collections.abc import Callable

import shapely
from jitx import Circuit, Net, Pour
from jitx.board import Board
from jitx.common import ADC, GPIO
from jitx.component import Component
from jitx.constraints import Tag
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet, Side
from jitx.net import Port
from jitx.shapes.shapely import ShapelyGeometry
from jitx.transform import Transform
from jitx.units import kohm
from jitxlib.parts import AtMost, Resistor
from jitxlib.protocols.serial import I2C
from jitxlib.symbols.net_symbols import GroundSymbol, PowerSymbol

from ..circuits.centre_sensors import CentreSensors
from ..circuits.led_rings import LEDRings
from ..circuits.microphone import Microphone
from ..circuits.nfc import NFCFrontEnd
from ..circuits.nrf_pins import PDM, FastGPIO
from ..circuits.nrf_support import NRFSupport
from ..circuits.power import PowerSupply
from ..components.mcus.ebyte_E73_2G4M08S1CX import BODY_L, BODY_W, Y_BOTTOM, Y_TOP
from ..substrate import ProximityFearSubstrate

# --- Board geometry (ARCHITECTURE.md Board) ---------------------------------------------
BOARD_RADIUS = 25.0  # 50 mm circle
RIM_KEEPOUT = 1.0  # case snap lip: no copper or parts in the outer 1 mm
ARC_SEGMENTS = 128  # shapely quad_segs per quarter circle for the outline
# USB-C tab at 6 o'clock (ARCHITECTURE Board, user chose 2026-11-15). J1's through-board
# shell slots must clear every Top ring LED / cap: a sweep of J1's captured slot and hole
# copper against the captured ring copper gave 0.336 mm at y = -24.96 (courtyards clear by
# 0.057) and 0.531 mm at y = -25.16 (courtyards 0.253); y = -25.2 keeps both above the
# 0.3 mm target with the shortest tab. socialbadge rev 2 (fabbed) put J1's origin 3.94 mm
# inside its board edge (25 - 21.06): the tab edge (receptacle mouth) is that far below J1.
USB_AT = (0.0, -25.2)
USB_SETBACK = 3.94
TAB_EDGE_Y = USB_AT[1] - USB_SETBACK  # -29.14: 4.14 mm proud of the circle
TAB_HALF_WIDTH = 6.0  # J1 slot copper reaches x +-4.93; + 1 mm rim keepout, rounded up: 12 mm tab
TAB_FILLET = 1.5  # tab-to-circle corners, for the case (>= 1 mm)
TAB_CORNER = 0.5  # outer tab corners
# Rim-keepout exception at the receptacle mouth: the front slots sit 0.57 mm from the tab edge.
USB_ZONE_HALF_WIDTH = TAB_HALF_WIDTH - RIM_KEEPOUT

# --- Pours (ARCHITECTURE.md Board: L2 split, L3 solid GND) -------------------------------
CENTRE_DISC_RADIUS = 8.0  # 3V3 under the centre zone, VLED under the rings (r 8-24)
POUR_SPLIT = 0.5  # gap between the L2 3V3 disc and the VLED annulus (skill default: 4x the 0.125 clearance)

# --- Fixed back-side positions (board frame) ---------------------------------------------
MIC_PORT_AT = (4.5, 0.0)  # ARCHITECTURE Board: mic port at (+4.5, 0)
MIC_ROTATE = 180.0
E73_AT = (0.0, 9.7)  # inner courtyard edge 1.43, 0.14 mm clear of the Bottom mic's (1.29)
E73_ROTATE = 180.0
JST_AT = (18.75, 0.0)  # courtyard corners (A-12 courtyard) at r 23.99
JST_ROTATE = 90.0
BUTTON_AT = (-20.2, 0.0)
NFC_PADS_AT = (-13.0, 15.5)
TC2030_AT = (-12.0, -2.0)
TC2030_ROTATE = 270.0
XTAL_AT = (9.9, 1.6)  # courtyard 0.15 mm east of the module's (x 7.75), clear of the mic
NFC_CAP_PITCH = 2.0  # mm between neighbouring NFC caps, mirrored about the pads' centreline
NFC_CAP_Y = 12.38  # below the antenna pads: courtyards 0.12 mm under the antenna's (y >= 13.5)
# Plane anchors: an inner pour realizes only with a placed via or pad of its net on its
# layer. VLED vias sit on the free band between the inner ring's caps (r <= 11.7) and the
# middle ring (r >= 14.4); 3V3 vias in free spots of the centre disc (Top and Bottom).
VLED_VIA_RADIUS = 12.9
VLED_VIA_ANGLES = (-45.0, -140.0, 160.0)
V3V3_VIA_AT = ((3.0, -5.5), (-1.0, -7.0))

# --- I2C pull-ups (module docstring) -----------------------------------------------------
I2C_PULL_UP = 2.2 * kohm


class PowerTag(Tag):
    """Power rails: the 0.4 mm width."""


class GroundTag(Tag):
    """Ground: the 0.4 mm width."""


class VLEDTag(PowerTag):
    """Switched LED rail: 0.5 mm."""


class Rail3V3Tag(PowerTag):
    """3V3: 0.3 mm (lighter load; fits the 0.5 mm ToF and 0.52 mm mic pads)."""


class TagConnectTag(Tag):
    """TC2030 contact pads: drawing note 2 clearance."""


def board_outline() -> shapely.Polygon:
    """50 mm circle plus the USB-C tab at 6 o'clock, all corners rounded."""
    circle = shapely.Point(0.0, 0.0).buffer(BOARD_RADIUS, quad_segs=ARC_SEGMENTS)
    tab = shapely.box(-TAB_HALF_WIDTH, TAB_EDGE_Y, TAB_HALF_WIDTH, 0.0)
    joined = circle.union(tab)
    # Closing rounds the concave tab-to-circle corners; opening rounds the outer tab corners.
    filleted = joined.buffer(TAB_FILLET, quad_segs=ARC_SEGMENTS).buffer(-TAB_FILLET, quad_segs=ARC_SEGMENTS)
    outline = filleted.buffer(-TAB_CORNER, quad_segs=ARC_SEGMENTS).buffer(TAB_CORNER, quad_segs=ARC_SEGMENTS)
    if not isinstance(outline, shapely.Polygon):
        raise TypeError("board outline is not one polygon")
    return outline


def usable_area() -> shapely.Polygon:
    """Copper and parts area: the outline (circle and tab) less the 1 mm rim band (case lip)."""
    inner = board_outline().buffer(-RIM_KEEPOUT, quad_segs=ARC_SEGMENTS)
    if not isinstance(inner, shapely.Polygon):
        raise TypeError("rim keepout split the board outline")
    return inner


def signal_area() -> shapely.Polygon:
    """Usable area plus the rim exception in front of the USB-C receptacle."""
    usb_zone = shapely.box(-USB_ZONE_HALF_WIDTH, TAB_EDGE_Y, USB_ZONE_HALF_WIDTH, TAB_EDGE_Y + RIM_KEEPOUT + 0.1)
    area = usable_area().union(usb_zone)
    if not isinstance(area, shapely.Polygon):
        raise TypeError("signal area is not one polygon")
    return area


def centre_disc() -> shapely.Polygon:
    """L2 3V3 pour: the centre disc under the ToF / IR / mic zone."""
    return shapely.Point(0.0, 0.0).buffer(CENTRE_DISC_RADIUS - POUR_SPLIT / 2, quad_segs=ARC_SEGMENTS)


def ring_annulus() -> shapely.Polygon:
    """L2 VLED pour: the usable circle (not the tab) outside the centre disc, under the rings."""
    hole = shapely.Point(0.0, 0.0).buffer(CENTRE_DISC_RADIUS + POUR_SPLIT / 2, quad_segs=ARC_SEGMENTS)
    usable_circle = shapely.Point(0.0, 0.0).buffer(BOARD_RADIUS - RIM_KEEPOUT, quad_segs=ARC_SEGMENTS)
    annulus = usable_circle.difference(hole)
    if not isinstance(annulus, shapely.Polygon):
        raise TypeError("VLED annulus is not one polygon")
    return annulus


def module_body() -> shapely.Polygon:
    """E73 body outline in the board frame (180 deg turn of the module's own frame)."""
    x0, y0 = E73_AT
    # Turned 180 deg: the module frame's y range [Y_BOTTOM, Y_TOP] maps to [y0 - Y_TOP, y0 - Y_BOTTOM].
    body = shapely.box(x0 - BODY_W / 2, y0 - Y_TOP, x0 + BODY_W / 2, y0 - Y_BOTTOM)
    if abs((body.bounds[3] - body.bounds[1]) - BODY_L) > 1e-9:
        raise ValueError("E73 body outline does not match the module length")
    return body


def pinned(pin: Port) -> Callable[[Port], bool]:
    """Restriction for require(): permit only ``pin`` among the provider's candidates."""
    return lambda candidate: candidate is pin


class BadgeBoard(Board):
    """ARCHITECTURE.md Board: 50 mm circle, USB-C tab at 6 o'clock, 1 mm rim keepout."""

    shape = ShapelyGeometry(board_outline())
    signal_area = ShapelyGeometry(signal_area())


class BadgeCircuit(Circuit):
    """All six accepted circuits, the I2C pull-ups, rails, pours and fixed back-side parts."""

    def __init__(self) -> None:
        # --- Rails (symbols and tags only here, at the top level) ---
        self.GND = Net(name="GND", symbol=GroundSymbol())
        self.VBUS = Net(name="VBUS", symbol=PowerSymbol())
        self.VBAT = Net(name="VBAT", symbol=PowerSymbol())
        self.SYS = Net(name="SYS", symbol=PowerSymbol())
        self.V3V3 = Net(name="3V3", symbol=PowerSymbol())
        self.VLED = Net(name="VLED", symbol=PowerSymbol())
        GroundTag().assign(self.GND)
        PowerTag().assign(self.VBUS)
        PowerTag().assign(self.VBAT)
        PowerTag().assign(self.SYS)
        Rail3V3Tag().assign(self.V3V3)
        VLEDTag().assign(self.VLED)

        # --- Sub-circuits ---
        self.power = PowerSupply()
        self.nrf = NRFSupport()
        self.rings = LEDRings().at(0.0, 0.0)
        self.sensors = CentreSensors().at(0.0, 0.0)
        # Bottom-port mic on Bottom, port hole at (+4.5, 0) (ARCHITECTURE Board, A-03): sound
        # reaches it through the PCB from the front. Turned 180 deg so the body and its cap
        # extend toward -y, away from the E73's inner pad row (y >= 1.48).
        self.mic = Microphone().at(*MIC_PORT_AT, on=Side.Bottom, rotate=MIC_ROTATE)
        self.nfc = NFCFrontEnd()

        # The battery lead before the reverse FET (internal to PowerSupply, no port) carries
        # the battery current too (ARCHITECTURE Power Tree: 430 mA peak).
        PowerTag().assign(self.power.battery.BAT_P)

        # --- Power tree ---
        self.VBUS += self.power.vbus.Vp
        self.VBUS += self.nrf.vbus.Vp
        self.VBAT += self.power.vbat.Vp
        self.SYS += self.power.sys.Vp
        self.SYS += self.rings.vin.Vp  # LED switch on SYS (A-01): VLED is SYS when switched on
        self.V3V3 += self.power.v3v3.Vp
        self.V3V3 += self.nrf.v3v3.Vp
        self.V3V3 += self.sensors.v3v3.Vp
        self.V3V3 += self.mic.v3v3.Vp
        self.VLED += self.rings.vled.Vp
        self.GND += Net(
            [
                self.power.vbus.Vn,
                self.power.vbat.Vn,
                self.power.v3v3.Vn,
                self.power.sys.Vn,
                self.nrf.v3v3.Vn,
                self.nrf.vbus.Vn,
                self.rings.vin.Vn,
                self.rings.vled.Vn,
                self.sensors.v3v3.Vn,
                self.mic.v3v3.Vn,
                self.nfc.gnd,
            ]
        )

        # --- Fixed-function links ---
        self.USB = self.power.usb + self.nrf.usb
        self.NFC1 = self.nrf.nfc1 + self.nfc.nfc1
        self.NFC2 = self.nrf.nfc2 + self.nfc.nfc2

        # --- Pin-assigned links (pin-01 offers on the E73), frozen by restriction ---
        # Each require() keeps the provider's legality check (a pin outside the offered pool
        # cannot satisfy it) and a restriction pins it to one chosen pad (table in main.py).
        m = self.nrf.module
        i2c = self.nrf.require(I2C, restrictions=lambda b: {b.sda: pinned(m.P0_07), b.scl: pinned(m.P0_15)})
        self.r_sda = Resistor(resistance=I2C_PULL_UP, tolerance=AtMost(0.01))
        self.r_scl = Resistor(resistance=I2C_PULL_UP, tolerance=AtMost(0.01))
        self.I2C_SDA = Net([i2c.sda, self.sensors.i2c.sda, self.r_sda.p1])
        self.I2C_SCL = Net([i2c.scl, self.sensors.i2c.scl, self.r_scl.p1])
        self.V3V3 += Net([self.r_sda.p2, self.r_scl.p2])

        led_data = self.nrf.require(FastGPIO, restrictions=lambda b: {b.gpio: pinned(m.P0_13)})
        ir_tx = self.nrf.require(FastGPIO, restrictions=lambda b: {b.gpio: pinned(m.P0_17)})
        self.LED_DATA = led_data.gpio + self.rings.din
        self.IR_TX = ir_tx.gpio + self.sensors.ir_tx

        pdm = self.nrf.require(PDM, restrictions=lambda b: {b.clk: pinned(m.P0_04), b.din: pinned(m.P0_12)})
        self.PDM_CLK = pdm.clk + self.mic.pdm_clk
        self.PDM_DIN = pdm.din + self.mic.pdm_din

        def gpio_on(pin: Port) -> GPIO:
            return self.nrf.require(GPIO, restrictions=lambda b: {b.gpio: pinned(pin)})

        self.LED_EN = gpio_on(m.P0_29).gpio + self.rings.enable
        self.IR_RX = gpio_on(m.P0_24).gpio + self.sensors.ir_rx
        self.IR_RX_EN = gpio_on(m.P1_02).gpio + self.sensors.ir_rx_en
        self.TOF_XSHUT = gpio_on(m.P0_20).gpio + self.sensors.xshut
        self.TOF_INT = gpio_on(m.P0_22).gpio + self.sensors.tof_int
        self.BUTTON = gpio_on(m.P1_04).gpio + self.nrf.button
        self.CHG_STAT = gpio_on(m.P0_31).gpio + self.power.chg_stat
        self.CHG_EN = gpio_on(m.P1_13).gpio + self.power.chg_en

        vbat_adc = self.nrf.require(ADC, restrictions=lambda b: {b.adc: pinned(m.P0_30)})
        self.VBAT_SENSE = vbat_adc.adc + self.power.vbat_sense

        self.place_back_side()

        # --- Plane anchor vias ---
        via = ProximityFearSubstrate.StdViaPreferred
        self.vled_vias = [
            via().at(VLED_VIA_RADIUS * math.cos(math.radians(a)), VLED_VIA_RADIUS * math.sin(math.radians(a)))
            for a in VLED_VIA_ANGLES
        ]
        self.v3v3_vias = [via().at(x, y) for x, y in V3V3_VIA_AT]
        for v in self.vled_vias:
            self.VLED += v
        for v in self.v3v3_vias:
            self.V3V3 += v

        # --- Pours ---
        substrate = ProximityFearSubstrate
        self.vled_pour = Pour(ShapelyGeometry(ring_annulus()), layer=substrate.power_plane_layer)
        # At equal rank the disc captured Empty() although it does not touch the annulus
        # (it lies inside the annulus's bounding box); rank 1 realizes both (measured).
        self.v3v3_pour = Pour(ShapelyGeometry(centre_disc()), layer=substrate.power_plane_layer, rank=1)
        self.gnd_plane = Pour(ShapelyGeometry(usable_area()), layer=substrate.ground_plane_layer)
        self.gnd_bottom = Pour(ShapelyGeometry(usable_area()), layer=-1)
        self.VLED += self.vled_pour
        self.V3V3 += self.v3v3_pour
        self.GND += self.gnd_plane
        self.GND += self.gnd_bottom

        # E73 manual p.11: no high-frequency, analog or power routing on the layer under the
        # module. The module sits on Bottom, so that layer is L3: keep it solid GND there.
        self.e73_plane_keepout = KeepOut(
            ShapelyGeometry(module_body()), layers=LayerSet(substrate.ground_plane_layer), route=True, via=False
        )

        # TC2030 note 2: no other track within 0.508 mm of a contact pad.
        TagConnectTag().assign(self.nrf.swd)

    def place_back(self, part: Component, x: float, y: float, rotate: float = 0.0) -> None:
        """Fix a descendant part on Bottom at front-view board coordinates."""
        self.place(part, Transform((x, y), rotate), on=Side.Bottom)

    def place_back_side(self) -> None:
        """Every Bottom part (module docstring "Placement"), grouped by owner."""
        # Every courtyard keeps >= 0.10 mm from its same-side neighbours (user board review;
        # tests/test_asm01_top.py test_courtyards_clear_on_each_side).
        p, n, s, b = self.power, self.nrf, self.sensors, self.place_back
        # Edge and mechanical parts.
        b(p.usb_c.j1, *USB_AT)
        b(p.battery.j2, *JST_AT, JST_ROTATE)
        b(n.module, *E73_AT, E73_ROTATE)
        b(n.sw_user, *BUTTON_AT)
        b(n.swd, *TC2030_AT, TC2030_ROTATE)
        b(self.nfc.antenna, *NFC_PADS_AT)
        # NFC tuning network mirror-symmetric about the antenna pads' centreline x = -13
        # (ov-nfc W3): each leg's tuning cap under its own pad, its DNP trim cap outboard.
        # On Bottom the antenna land pattern is mirrored, so pad p1 (NFC1) lands at +x
        # (-11.75) and p2 (NFC2) at -x (-14.25); the NFC1 caps go east (closure audit W-1).
        b(self.nfc.c_tune[0], NFC_PADS_AT[0] + NFC_CAP_PITCH / 2, NFC_CAP_Y)
        b(self.nfc.c_tune[1], NFC_PADS_AT[0] - NFC_CAP_PITCH / 2, NFC_CAP_Y)
        b(self.nfc.trim.c_trim[0], NFC_PADS_AT[0] + 3 * NFC_CAP_PITCH / 2, NFC_CAP_Y)
        b(self.nfc.trim.c_trim[1], NFC_PADS_AT[0] - 3 * NFC_CAP_PITCH / 2, NFC_CAP_Y)
        # LFXO (R-02): the Bottom mic sits under XL1/XL2 (pads 11/13), so the crystal goes
        # east of the module, upright, pad 1 (XL1) north and pad 2 (XL2) south. XL1 leaves
        # pad 11 eastward along its exposed end (y ~2.1); XL2 drops into the corridor below
        # pad 11 (y ~1.1, over the mic GND ring, >= 2 mm from mic CLK/DATA) and runs east
        # under it: no crossing, no fast pin between (P0.26/P0.06/P0.05/P0.08 unused).
        b(n.xtal, *XTAL_AT)
        b(n.c_xl[0], XTAL_AT[0], XTAL_AT[1] + 3.6, 90.0)
        b(n.c_xl[1], XTAL_AT[0], XTAL_AT[1] - 3.52, 90.0)  # courtyard 0.12 mm below the crystal's
        # VBUS: 4.7 ohm series resistor (R-01) between the feed and pad 27, cap at the pad side.
        b(n.r_vbus, -8.8, 4.1, 180.0)  # p1 (feed) south, p2 (VBUS_NRF) north toward pad 27, N-a
        b(n.c_vbus, -9.0, 6.8)
        # VBUS TVS straight across J1's VBUS / GND pads; ESD and CC parts just inboard of J1.
        b(p.usb_c.tvs, 6.3, -20.23, 180.0)  # K (pad 1) west, toward VBUS pads 11/12
        b(p.usb_c.esd, 0.0, -18.0)
        b(p.usb_c.c_esd_vbus, 3.3, -16.5)
        b(p.usb_c.tp_vbus, 3.3, -13.6)
        b(p.usb_c.esd_cc1, -3.4, -19.3)
        b(p.usb_c.esd_cc2, -5.12, -19.3)
        b(p.usb_c.r_cc1, -3.4, -16.8)
        b(p.usb_c.r_cc2, -5.0, -16.8)
        # Charger south-east, between J1 (VBUS) and J2 (battery).
        b(p.charger.u1, 9.5, -12.5)
        b(p.charger.c_vdd, 6.0, -12.5)
        b(p.charger.c_vbat, 13.0, -12.5)
        b(p.charger.r_prog, 15.0, -12.5)
        b(p.charger.q_en, 17.72, -11.0)
        b(p.charger.r_en_pu, 17.6, -14.0, 90.0)
        b(p.charger.led, 9.5, -15.5)
        b(p.charger.r_led, 12.5, -15.5, 90.0)
        b(p.charger.r_stat_top, 9.5, -17.0, 90.0)
        b(p.charger.r_stat_bot, 12.5, -17.0, 90.0)
        # Power path and LDO south-west.
        b(p.path.d_usb, -10.18, -10.6)  # courtyard 0.12 mm east of the LDO's
        b(p.path.q_bat, -11.0, -14.0)
        b(p.path.r_pull, -7.8, -14.0)
        b(p.ldo.u1, -15.5, -10.5)
        b(p.ldo.c_in, -15.5, -13.9)
        b(p.ldo.c_out, -19.0, -8.0)
        b(p.ldo.tp_3v3, -19.3, -10.8)
        b(p.tp_gnd, -14.5, -16.5)
        # Battery: reverse FET and test point north of J2; VBAT sense divider beside it,
        # east of the crystal (AIN6 = P0.30, pad 10).
        b(p.battery.q_rev, 11.8, 7.5)
        b(p.battery.tp_vbat, 13.0, 10.0)
        b(p.battery.r_sense_top, 12.8, -0.6)
        b(p.battery.r_sense_bot, 12.8, -2.8)
        b(p.battery.c_sense, 12.8, 1.6)
        # LED switch (fed from SYS, A-01) south of J2, its SYS-side cap at the source.
        sw = self.rings.switch
        b(sw.q_switch, 13.3, -6.4, 90.0)
        b(sw.c_bulk, 13.3, -9.0, 90.0)
        b(sw.c_soft, 10.6, -3.6, 90.0)
        b(sw.r_gate_pu, 10.6, -5.0, 90.0)
        b(sw.r_gate_on, 10.6, -6.4, 90.0)
        b(sw.q_drive, 7.2, -6.3)
        b(sw.r_enable_pd, 7.2, -8.6, 90.0)
        b(sw.c_sys, 10.85, -8.9)  # SYS pad beside q_switch source (pad 1 at (12.35, -7.55)), N-b
        # 33 ohm LED data resistor straight out from P0.13 (pad 33, west edge).
        b(self.rings.r_din, -8.9, 10.46, 90.0)
        # Centre sensors' back parts and the I2C pull-ups, under the centre zone.
        b(s.ir_receiver.q_en, -6.8, -3.6, 90.0)
        b(s.ir_receiver.r_gate_pu, -4.6, -2.0)
        b(self.r_sda, -4.6, -4.4)
        b(self.r_scl, -3.3, -4.4)
        b(s.tof.r_xshut, -4.6, -6.6)
        b(s.tof.r_gpio1, -3.3, -6.6)
        b(s.ir_transmitter.r_gate_pd, -2.0, -6.6)
        b(s.ir_transmitter.q_drive, -4.0, -9.4)
        b(s.ir_transmitter.r_led, 1.5, -8.6)
