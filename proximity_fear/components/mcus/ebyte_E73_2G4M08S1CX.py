"""Ebyte E73-2G4M08S1CX: nRF52840 BLE 5 module, 13 x 18 mm, IPEX antenna connector.

Source: Ebyte "E73-2G4M08S1CX User Manual" v1.2 (``datasheets/E73-2G4M08S1CX.pdf``),
manual page numbers below (PDF page = manual page + 1):

* p.7 "3 Size and pin definition": bottom-view drawing, pad quantity 43, pitch 1.27 mm,
  pin table pp.7-9.
* p.11 "5.1 Hardware design and circuit schematic diagram": module-internal schematic
  (REG1 DC/DC inductors L2 10 uH + L1 15 nH on DCC, 4.7 uF on VDD / VDDH / DECUSB,
  32 MHz crystal inside, no 32.768 kHz crystal) and the layout guidance.
* nRF52840 PS "Pin assignments", aQFN73 table (``datasheets/sourcing/nRF52840_PS-pins-aQFN73.txt``):
  AIN mapping and "standard drive, low frequency I/O only" pins.

Land pattern: LCSC/EasyEDA footprint for C2764963 (``kicad_footprints/E73-2G4M08S1CX.kicad_mod``,
third-party, user consent 2026-11-15), pad sizes and origin kept, pad centres placed on the
Ebyte drawing's 1.27 mm grid (Ebyte wins). Max deviation from the .kicad_mod is 0.03 mm (pad 3,
whose .kicad_mod y is off the 1.27 grid); the test asserts every pad within 0.035 mm.

Pad layout (top view, y up, origin = the LCSC footprint origin, 1.98 mm above body centre):

* pins 1-10: castellated, right edge, pin 1 lowest; 26, 27, 29 ... 43: castellated, left edge.
* pins 11, 13 ... 25: castellated, top edge, pin 11 rightmost.
* pins 12, 14 ... 24 and 28, 30 ... 42: 0.8 mm square module pads under the body (bottom pads),
  2.1 mm in from the top / left edge.
* IPEX connector on the module top, centred near the bottom edge (p.7 top view; LCSC silk box).

No-field facts (no JITX field): module height 3.00 +/- 0.1 mm (p.7); supply 1.7-5.5 V, abs max
5.5 V (p.5); 32.768 kHz crystal external on XL1/XL2 (p.6); pin 37 is SWDIO although p.8
describes it as "clock"; manual p.11: avoid high-frequency digital, analog and power routing on
the layer under the module.
"""

# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention

import jitx
from jitx.anchor import Anchor
from jitx.circuit import Circuit
from jitx.container import inline
from jitx.feature import Courtyard, Custom, Paste, Silkscreen, Soldermask
from jitx.landpattern import Landpattern, Pad, PadMapping
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Circle, Polyline, Text
from jitxlib.jlcpcb import LCSCPart
from jitxlib.symbols.box import BoxSymbol, Column, PinGroup, Row

# --- Geometry (mm), Ebyte manual p.7 drawing unless noted -----------------------------------
PITCH = 1.27  # "1.27" pad pitch
BODY_W = 13.0  # 13.0 +/- 0.1
BODY_L = 18.0  # 18.0 +/- 0.1
Y_TOP = 7.02  # body top edge in the LCSC footprint frame (.kicad_mod courtyard y = -7.02)
Y_BOTTOM = Y_TOP - BODY_L  # -10.98, .kicad_mod courtyard y = 10.98
X_EDGE = BODY_W / 2  # castellated pad centres sit on the body edge (.kicad_mod x = +/-6.50)
SIDE_FIRST = Y_TOP - 2.60  # "2.60": top edge to pins 10 / 26
TOP_FIRST = BODY_W / 2 - 2.06 + 0.005  # "2.06": side edge to pins 11 / 25 (2*2.06 + 7*1.27 = 13.01)
INNER_ROW_Y = Y_TOP - 2.1  # "2.1": top edge to the bottom-pad row 12-24
INNER_ROW_FIRST = BODY_W / 2 - 2.69  # "2.69": side edge to pin 12 (bottom view)
INNER_COL_X = -X_EDGE + 2.1  # "2.1": left edge (top view) to the bottom-pad column 28-42
INNER_COL_FIRST = Y_TOP - 4.505  # "4.505": top edge to pin 28

# IPEX connector (top view p.7; LCSC silkscreen box x +/-1.27, y -7.65..-10.19)
IPEX_CENTER_Y = -8.92
IPEX_SIZE = 2.54
# Keep-clear for hand-snapping the IPEX plug (PLAN comp-01): no part may sit within 3 mm of the
# body edge beside the connector. Design choice, not from the manual.
IPEX_CLEAR_W = 6.0
IPEX_CLEAR_D = 3.0


class CastellatedPadH(Pad):
    """Left/right edge pad: .kicad_mod 0.9 x 2.0 rotated 90 deg (2.0 mm along x)."""

    shape = rectangle(2.0, 0.9)
    soldermask = Soldermask(rectangle(2.0, 0.9))
    paste = Paste(rectangle(2.0, 0.9))


class CastellatedPadV(Pad):
    """Top edge pad: .kicad_mod 0.9 x 2.0 (2.0 mm along y)."""

    shape = rectangle(0.9, 2.0)
    soldermask = Soldermask(rectangle(0.9, 2.0))
    paste = Paste(rectangle(0.9, 2.0))


class BottomPad(Pad):
    """Under-body pad: .kicad_mod 0.9 x 0.9 for the module's 0.80 x 0.80 pad (p.7 "Bottom pad")."""

    shape = rectangle(0.9, 0.9)
    soldermask = Soldermask(rectangle(0.9, 0.9))
    paste = Paste(rectangle(0.9, 0.9))


class E73Landpattern(Landpattern):
    """43-pad land pattern, keyed by module pin number."""

    name = "E73-2G4M08S1CX"
    p = {
        # Pins 1-10: right edge, upward from pin 1.
        **{k: CastellatedPadH().at(X_EDGE, SIDE_FIRST - PITCH * (10 - k)) for k in range(1, 11)},
        # Pins 11, 13 ... 25: top edge, leftward from pin 11.
        **{11 + 2 * j: CastellatedPadV().at(TOP_FIRST - PITCH * j, Y_TOP) for j in range(8)},
        # Pins 12, 14 ... 24: bottom-pad row, leftward from pin 12.
        **{12 + 2 * j: BottomPad().at(INNER_ROW_FIRST - PITCH * j, INNER_ROW_Y) for j in range(7)},
        # Pin 26: left edge, level with pin 10.
        26: CastellatedPadH().at(-X_EDGE, SIDE_FIRST),
        # Pins 27, 29 ... 43: left edge, downward.
        **{27 + 2 * i: CastellatedPadH().at(-X_EDGE, SIDE_FIRST - PITCH * (i + 1)) for i in range(9)},
        # Pins 28, 30 ... 42: bottom-pad column, downward.
        **{28 + 2 * i: BottomPad().at(INNER_COL_X, INNER_COL_FIRST - PITCH * i) for i in range(8)},
    }
    courtyard = Courtyard(
        rectangle(BODY_W + 2.5, BODY_L + 1.5).at(0, (Y_TOP + 1.25 + Y_BOTTOM - 0.25) / 2),
    )
    ipex_keep_clear = Courtyard(
        rectangle(IPEX_CLEAR_W, IPEX_CLEAR_D).at(0, Y_BOTTOM - IPEX_CLEAR_D / 2),
    )
    ipex_outline = Custom(
        rectangle(IPEX_SIZE, IPEX_SIZE).at(0, IPEX_CENTER_Y),
        name="Fab",
    )
    ipex_label = Custom(Text("IPEX keep clear", 0.6, Anchor.C).at(0, Y_BOTTOM - IPEX_CLEAR_D / 2), name="Fab")
    reference_designator = Silkscreen(Text(">REF", 1.0, Anchor.C).at(0, Y_TOP + 2.0))
    value_label = Custom(Text(">VALUE", 1.0, Anchor.C).at(0, 0), name="Fab")
    silkscreen = [
        # Body outline below the last side pads (as the .kicad_mod silkscreen).
        Silkscreen(Polyline(0.2, [(-X_EDGE, -7.70), (-X_EDGE, Y_BOTTOM), (X_EDGE, Y_BOTTOM), (X_EDGE, -7.70)])),
        # IPEX connector box.
        Silkscreen(
            Polyline(
                0.2,
                [
                    (-IPEX_SIZE / 2, IPEX_CENTER_Y + IPEX_SIZE / 2),
                    (IPEX_SIZE / 2, IPEX_CENTER_Y + IPEX_SIZE / 2),
                    (IPEX_SIZE / 2, IPEX_CENTER_Y - IPEX_SIZE / 2),
                    (-IPEX_SIZE / 2, IPEX_CENTER_Y - IPEX_SIZE / 2),
                    (-IPEX_SIZE / 2, IPEX_CENTER_Y + IPEX_SIZE / 2),
                ],
            )
        ),
        # Pin 1 dot, right of and below pin 1 (.kicad_mod circle at 7.20, 8.42 - y negated).
        Silkscreen(Circle(radius=0.22).at(7.85, SIDE_FIRST - PITCH * 9 - 0.6)),
    ]


class E73_2G4M08S1CX(jitx.Component):
    """Ebyte E73-2G4M08S1CX nRF52840 module (IPEX antenna, no 32.768 kHz crystal inside).

    Port names: dedicated module functions by function (VCC = nRF VDD, VDDH, DCCH, VBUS,
    D_N/D_P, SWDIO, SWDCLK, RESET = P0.18, XL1 = P0.00, XL2 = P0.01, NFC1 = P0.09,
    NFC2 = P0.10); general GPIOs by nRF name (Ebyte's "AIx" pins are named by their GPIO).
    """

    mpn = "E73-2G4M08S1CX"
    manufacturer = "Chengdu Ebyte Electronic Technology"
    reference_designator_prefix = "U"
    datasheet = "https://www.cdebyte.com/products/E73-2G4M08S1CX"
    lcsc = LCSCPart("C2764963")

    # Power (p.8 pins 19, 23, 25, 27; GND 5, 21, 24)
    VCC = Port()  # 19, nRF VDD
    VDDH = Port()  # 23 "VDH", high-voltage supply
    DCCH = Port()  # 25 "DCH", REG0 DC/DC output
    VBUS = Port()  # 27 "VBS", USB 5 V input
    GND = [Port() for _ in range(3)]  # pins 5, 21, 24
    # USB, debug, reset, clocks, NFC
    D_N = Port()  # 29
    D_P = Port()  # 31
    SWDIO = Port()  # 37 "SWD"
    SWDCLK = Port()  # 39 "SWC"
    RESET = Port()  # 26 "RST", P0.18 / nRESET (active low when configured), QSPI CSN
    XL1 = Port()  # 11, P0.00
    XL2 = Port()  # 13, P0.01
    NFC1 = Port()  # 41 "NF1", P0.09, low-frequency I/O
    NFC2 = Port()  # 43 "NF2", P0.10, low-frequency I/O
    # Port 0 GPIOs (Ebyte pin in comment; LF = standard drive, low-frequency I/O only per nRF52840 PS)
    P0_02 = Port()  # 7 "AI0", AIN0, LF
    P0_03 = Port()  # 3, AIN1, LF
    P0_04 = Port()  # 18 "AI2", AIN2
    P0_05 = Port()  # 15 "AI3", AIN3
    P0_06 = Port()  # 14
    P0_07 = Port()  # 22
    P0_08 = Port()  # 16
    P0_12 = Port()  # 20 "P12"
    P0_13 = Port()  # 33
    P0_15 = Port()  # 28 "P15"
    P0_17 = Port()  # 30 "P17"
    P0_20 = Port()  # 32
    P0_22 = Port()  # 34
    P0_24 = Port()  # 35
    P0_26 = Port()  # 12
    P0_28 = Port()  # 4 "AI4", AIN4, LF
    P0_29 = Port()  # 8 "AI5", AIN5, LF
    P0_30 = Port()  # 10 "AI6", AIN6, LF
    P0_31 = Port()  # 9 "AI7", AIN7, LF
    # Port 1 GPIOs
    P1_00 = Port()  # 36
    P1_02 = Port()  # 38, LF
    P1_04 = Port()  # 40, LF
    P1_06 = Port()  # 42, LF
    P1_09 = Port()  # 17
    P1_10 = Port()  # 2, LF
    P1_11 = Port()  # 1, LF
    P1_13 = Port()  # 6, LF

    landpattern = E73Landpattern()

    symbols = [
        BoxSymbol(
            rows=Row(left=PinGroup(VCC, VDDH, VBUS), right=PinGroup(DCCH)),
            columns=Column(down=PinGroup(*GND)),
        ),
        BoxSymbol(
            rows=Row(
                left=PinGroup(RESET, SWDIO, SWDCLK, XL1, XL2),
                right=PinGroup(D_P, D_N, NFC1, NFC2),
            ),
        ),
        BoxSymbol(
            rows=Row(
                right=PinGroup(
                    P0_02, P0_03, P0_04, P0_05, P0_06, P0_07, P0_08, P0_12, P0_13, P0_15,
                    P0_17, P0_20, P0_22, P0_24, P0_26, P0_28, P0_29, P0_30, P0_31,
                ),
            ),
        ),
        BoxSymbol(rows=Row(right=PinGroup(P1_00, P1_02, P1_04, P1_06, P1_09, P1_10, P1_11, P1_13))),
    ]  # fmt: skip

    def __init__(self) -> None:
        p = self.landpattern.p
        self.mappings = [
            PadMapping(
                {
                    self.P1_11: p[1],
                    self.P1_10: p[2],
                    self.P0_03: p[3],
                    self.P0_28: p[4],
                    self.GND[0]: p[5],
                    self.P1_13: p[6],
                    self.P0_02: p[7],
                    self.P0_29: p[8],
                    self.P0_31: p[9],
                    self.P0_30: p[10],
                    self.XL1: p[11],
                    self.P0_26: p[12],
                    self.XL2: p[13],
                    self.P0_06: p[14],
                    self.P0_05: p[15],
                    self.P0_08: p[16],
                    self.P1_09: p[17],
                    self.P0_04: p[18],
                    self.VCC: p[19],
                    self.P0_12: p[20],
                    self.GND[1]: p[21],
                    self.P0_07: p[22],
                    self.VDDH: p[23],
                    self.GND[2]: p[24],
                    self.DCCH: p[25],
                    self.RESET: p[26],
                    self.VBUS: p[27],
                    self.P0_15: p[28],
                    self.D_N: p[29],
                    self.P0_17: p[30],
                    self.D_P: p[31],
                    self.P0_20: p[32],
                    self.P0_13: p[33],
                    self.P0_22: p[34],
                    self.P0_24: p[35],
                    self.P1_00: p[36],
                    self.SWDIO: p[37],
                    self.P1_02: p[38],
                    self.SWDCLK: p[39],
                    self.P1_04: p[40],
                    self.NFC1: p[41],
                    self.P1_06: p[42],
                    self.NFC2: p[43],
                }
            )
        ]

    def analog_inputs(self) -> tuple[Port, ...]:
        """GPIOs with SAADC inputs, indexed by AIN number (nRF52840 PS pin table)."""
        return (self.P0_02, self.P0_03, self.P0_04, self.P0_05, self.P0_28, self.P0_29, self.P0_30, self.P0_31)

    def low_frequency_gpios(self) -> tuple[Port, ...]:
        """GPIOs that are "standard drive, low frequency I/O only" (nRF52840 PS, aQFN73 table).

        Keep fast signals (LED data, PDM clock, SPI/I2S clocks) off these.
        """
        return (
            self.P0_02,
            self.P0_03,
            self.P0_28,
            self.P0_29,
            self.P0_30,
            self.P0_31,
            self.P1_02,
            self.P1_04,
            self.P1_06,
            self.P1_10,
            self.P1_11,
            self.P1_13,
            self.NFC1,
            self.NFC2,
        )


Device: type[E73_2G4M08S1CX] = E73_2G4M08S1CX


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
