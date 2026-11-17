# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention
"""Worldsemi WS2812C-2020-V6/W - addressable RGB LED, 2.0 x 2.0 mm, integrated driver.

Ported from socialbadge-ai rev 2 (fabbed and brought up); pads unchanged.

Source: Worldsemi WS2812C-2020-V6/W datasheet, saved as
``datasheets/WS2812C-2020-V6_W.pdf``.
- p.2 "机械尺寸" Top View / pin table: 1 DO, 2 GND, 3 DI, 4 VDD; top view has
  DI top-left, GND top-right, VDD bottom-left, DO bottom-right.
- p.2 "PCB Solder Pad": 0.7 x 0.7 pads, 1.13 mm inner gap (centres +-0.915),
  0.40 mm row gap (centres +-0.55).
- p.2 "最大额定值": VDD +3.3..+5.3 V; VI -0.3..VDD+0.7 V.

Footprint: EasyEDA ``LED-SMD_4P-L2.0-W2.0-TL_WS2812B-2020``
(``kicad_footprints/C55160508.kicad_mod``). Its pad centres (+-0.92, +-0.55)
match the datasheet; its pads are 0.9 mm in x (datasheet 0.7), 0.1 mm longer
at each end. The pattern is the datasheet top view turned 180 degrees (not
mirrored): DO top-left, VDD top-right, GND bottom-left, DI bottom-right.
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


class Pad1(Pad):
    """SMD pad (0.9 x 0.7 mm), from the EasyEDA footprint."""

    shape = rectangle(0.9, 0.7)
    soldermask = Soldermask(rectangle(0.9, 0.7))
    paste = Paste(rectangle(0.9, 0.7))


# KiCad Y+ is down, JITX Y+ is up: every KiCad y is negated.
_pad_DO = Pad1().at(-0.92, 0.55)
_pad_GND = Pad1().at(-0.92, -0.55)
_pad_DI = Pad1().at(0.92, -0.55)
_pad_VDD = Pad1().at(0.92, 0.55)


@inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:LED-SMD_4P-L2.0-W2.0-TL_WS2812B-2020"
    p = {
        1: _pad_DO,
        2: _pad_GND,
        3: _pad_DI,
        4: _pad_VDD,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 4.55)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -4.55)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.15, [(-0.25, 0.75), (-0.1, 0.75)])),
        Silkscreen(Polyline(0.15, [(-0.1, 0.75), (-0.1, -0.65)])),
        Silkscreen(Polyline(0.15, [(-0.1, -0.65), (-0.1, -0.7)])),
        Silkscreen(Polyline(0.15, [(-0.1, -0.7), (-0.25, -0.7)])),
        Silkscreen(Polyline(0.15, [(-0.25, 0.75), (-0.25, -0.7)])),
        Silkscreen(Polyline(0.25, [(-1.3, 1.15), (-1.3, 1.14)])),
        Silkscreen(Polyline(0.15, [(1, 1.1), (-1, 1.1)])),
        Silkscreen(Polyline(0.15, [(-1, -1.1), (1, -1.1)])),
        Silkscreen(ArcPolyline(0.06, [Arc((-1, 1), 0.03, 0, -360)])),
    ]
    # The EasyEDA courtyard was the 2 x 2 mm body; the pads reach +-1.37 mm in x
    # and +-0.9 mm in y, so it is grown to cover them.
    courtyard = Courtyard(rectangle(3.0, 2.2))


class WS2812C_2020_V6(jitx.Component):
    """Addressable RGB LED, 2.0 x 2.0 mm, integrated WS2812 driver.

    Datasheet facts with no JITX field: VDD 3.3..5.3 V (p.2); 5 mA per colour
    channel; DI and DO are interchangeable (p.2 pin table); 800 kb/s one-wire,
    reset low > 280 us (p.3).
    """

    mpn = "WS2812C-2020-V6/W"
    manufacturer = "Worldsemi"
    lcsc = LCSCPart("C55160508")
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/c46fb81601a669a9e6c1d3221ebfe144.pdf"
    reference_designator_prefix = "D"

    DO = Port()
    GND = Port()
    DI = Port()
    VDD = Port()

    landpattern = _Landpattern

    symbol = BoxSymbol(
        rows=Row(left=PinGroup(DI), right=PinGroup(DO)),
        columns=Column(up=PinGroup(VDD), down=PinGroup(GND)),
    )

    def __init__(self) -> None:
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.DO: lp.p[1],
                self.GND: lp.p[2],
                self.DI: lp.p[3],
                self.VDD: lp.p[4],
            }
        )


Device: type[WS2812C_2020_V6] = WS2812C_2020_V6


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
