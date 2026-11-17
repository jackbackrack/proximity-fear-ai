# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention
"""ST VL53L4CDV0DH/1 - time-of-flight proximity sensor, 1..1300 mm, optical LGA12.

Ported from socialbadge-ai rev 2 (fabbed and brought up); pad copper unchanged.
Also holds the land pattern and pin model shared with the pin-compatible
VL53L4CX (``st_VL53L4CX.py``).

Source: ST DS13812 Rev 5 (June 2022), saved as
``datasheets/VL53L4CDV0DH_1.pdf`` (LCSC copy of ST's PDF; st.com refused the
download from this host).
- p.4 "Figure 2. VL53L4CD pinout (bottom view)" and "Table 2. VL53L4CD pin
  description": 12 pins, names used below.
- p.21 "Figure 17. Outline drawing (page 1/4)": body 4.40 +-0.05 x
  2.40 +-0.05; "PWB SOLDER PATTERN" twelve 0.50 x 0.50 pads, 0.80 pitch,
  3.70 x 2.10 overall (centres x +-1.6, rows y -0.8 / 0 / +0.8); top view has
  pin 1 at the bottom-right corner.
- p.16 "Table 10. Recommended operating conditions": AVDD 2.6..3.5 V.

Change from socialbadge-ai: there the pad keys followed the VL53L0X KiCad
import (pad 1 = XSHUT) to keep legacy routes; here pad keys are the datasheet
pin numbers, each pad at the same place, so the JLCPCB exporter can match
pin 1 itself.
"""

import jitx
from jitx import PadMapping
from jitx.anchor import Anchor
from jitx.circuit import Circuit
from jitx.container import inline
from jitx.feature import Courtyard, Custom, Paste, Silkscreen, Soldermask
from jitx.landpattern import Landpattern, Pad
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Arc, ArcPolyline, Polyline, Text
from jitxlib.jlcpcb import LCSCPart
from jitxlib.symbols.box import BoxSymbol, Column, PinGroup, Row


class LGA12Pad(Pad):
    """SMD pad 0.50 x 0.50 mm (DS13812 / DS13805 PWB solder pattern)."""

    shape = rectangle(0.5, 0.5)
    soldermask = Soldermask(rectangle(0.5, 0.5))
    paste = Paste(rectangle(0.5, 0.5))


@inline
class LGA12Landpattern(Landpattern):
    """VL53L4CD / VL53L4CX optical LGA12, 4.4 x 2.4 mm, top view, pin 1 bottom-right.

    Keys are the datasheet pin numbers.
    """

    name = "LGA12_VL53L4"
    p = {
        1: LGA12Pad().at(1.6, -0.8),  # AVDDVCSEL
        2: LGA12Pad().at(0.8, -0.8),  # AVSSVCSEL
        3: LGA12Pad().at(0.0, -0.8),  # GND
        4: LGA12Pad().at(-0.8, -0.8),  # GND2
        5: LGA12Pad().at(-1.6, -0.8),  # XSHUT
        6: LGA12Pad().at(-1.6, 0.0),  # GND3
        7: LGA12Pad().at(-1.6, 0.8),  # GPIO1
        8: LGA12Pad().at(-0.8, 0.8),  # DNC
        9: LGA12Pad().at(0.0, 0.8),  # SDA
        10: LGA12Pad().at(0.8, 0.8),  # SCL
        11: LGA12Pad().at(1.6, 0.8),  # AVDD
        12: LGA12Pad().at(1.6, 0.0),  # GND4
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 4.875)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -4.875)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.15, [(-2.28, 0.41), (-2.28, 1.28), (-2.01, 1.28)])),
        Silkscreen(Polyline(0.15, [(2.28, 0.41), (2.28, 1.28), (2.01, 1.28)])),
        Silkscreen(Polyline(0.15, [(-2.28, -0.41), (-2.28, -1.28), (-2.01, -1.28)])),
        Silkscreen(Polyline(0.15, [(2.28, -0.41), (2.28, -1.28), (2.01, -1.28)])),
        # pin 1 marker
        Silkscreen(ArcPolyline(0.25, [Arc((1.65, -1.6), 0.12, 0, -360)])),
    ]
    courtyard = Courtyard(rectangle(4.4, 2.4))


class VL53L4LGA12(jitx.Component):
    """Pin model shared by the VL53L4CD and VL53L4CX (identical pin tables).

    Not orderable on its own: use ``VL53L4CDV0DH_1`` or ``VL53L4CXV0DH_1``.
    Datasheet facts with no JITX field (same text and page in DS13812 and
    DS13805 unless two pages are given, CD first): I2C address 0x52 (p.3
    Table 1); XSHUT active low, must always be driven (10 k pull-up if the
    host state is unknown) and raised only while AVDD is on (p.5; p.9 / p.10);
    GPIO1 open-drain interrupt, 10 k pull-up, leave open if unused (p.4, p.5);
    DNC must be left floating (p.4); 100 nF + 4.7 uF on AVDD as close as
    possible to AVDDVCSEL / AVSSVCSEL (p.5 Figure 3); peak current 40 mA
    (Table 12, p.17 / p.18).
    """

    reference_designator_prefix = "U"

    AVDDVCSEL = Port()
    AVSSVCSEL = Port()
    GND = Port()
    GND2 = Port()
    XSHUT = Port()
    GND3 = Port()
    GPIO1 = Port()
    DNC = Port()
    SDA = Port()
    SCL = Port()
    AVDD = Port()
    GND4 = Port()

    landpattern = LGA12Landpattern

    symbol = BoxSymbol(
        rows=Row(left=PinGroup(XSHUT, GPIO1, SCL, SDA, DNC)),
        columns=Column(
            up=PinGroup(AVDD, AVDDVCSEL),
            down=PinGroup(GND, GND2, GND3, GND4, AVSSVCSEL),
        ),
    )

    def __init__(self) -> None:
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.AVDDVCSEL: lp.p[1],
                self.AVSSVCSEL: lp.p[2],
                self.GND: lp.p[3],
                self.GND2: lp.p[4],
                self.XSHUT: lp.p[5],
                self.GND3: lp.p[6],
                self.GPIO1: lp.p[7],
                self.DNC: lp.p[8],
                self.SDA: lp.p[9],
                self.SCL: lp.p[10],
                self.AVDD: lp.p[11],
                self.GND4: lp.p[12],
            }
        )


class VL53L4CDV0DH_1(VL53L4LGA12):
    """Time-of-flight proximity sensor, 1..1300 mm (DS13812 Rev 5)."""

    mpn = "VL53L4CDV0DH/1"
    manufacturer = "STMicroelectronics"
    lcsc = LCSCPart("C3178291")
    datasheet = "https://www.st.com/resource/en/datasheet/vl53l4cd.pdf"


Device: type[VL53L4CDV0DH_1] = VL53L4CDV0DH_1


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
