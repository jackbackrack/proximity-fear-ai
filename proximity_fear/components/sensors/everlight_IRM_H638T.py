# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention
"""Everlight IRM-H638T/TR2 - 38 kHz infrared receiver module, SMD.

Ported from socialbadge-ai rev 2 (fabbed and brought up); pads unchanged.

Source: Everlight IRM-H6XXT/TR2 Series datasheet DMO-0000008 Rev 3
(2025-01-01), saved as ``datasheets/IRM-H638T_TR2.pdf``.
- p.1 "Pin Configuration": 1 GND, 2 GND, 3 OUT, 4 Vcc; pins 1 and 4 on the
  lens side.
- p.2 "Application Circuit": 47..220 ohm in series with Vcc and >= 2.2 uF to
  GND, "as close as possible to Vcc and GND pins"; >= 10 k pull-up optional.
- p.3 "Absolute Maximum Ratings": Vs 6 V; "Electro-Optical Characteristics":
  Vs 2.7..5.5 V, Icc 0.4 typ / 0.7 max mA, VL 0.5 V max at 2 mA sink.
- p.6 "Package Dimensions": 5.00 x 4.00 body, 7.00 lead tip to tip, 2.54 mm
  lead pitch, R1.5 lens; "Recommend soldering patterns": 1.5 x 1.1 pads,
  4.8 mm inner gap (centres +-3.15), 1.44 mm row gap (centres +-1.27).

Footprint: EasyEDA ``SENSOR-SMD_IRM-H638T-TR2-TL``
(``kicad_footprints/C91447.kicad_mod``): 1.5 x 0.9 pads (rotated 90) on
+-1.27 mm rows, x centres -2.95 / +2.95 (+2.92 for Vcc), i.e. 0.2 mm inboard
of the datasheet suggestion and 0.2 mm narrower; it reaches the 7.00 mm lead
tips (+-3.5) to within 0.2 mm and was fabbed on socialbadge rev 2, so kept.
Pad numbering matches the datasheet pins (1 top-left, lens side up).
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
    """SMD pad (0.9 x 1.5 mm, placed rotated 90), from the EasyEDA footprint."""

    shape = rectangle(0.9, 1.5)
    soldermask = Soldermask(rectangle(0.9, 1.5))
    paste = Paste(rectangle(0.9, 1.5))


# KiCad Y+ is down, JITX Y+ is up: every KiCad y is negated.
_pad_GND_0 = Pad1().at(-2.95, 1.27, rotate=90)
_pad_GND_1 = Pad1().at(-2.95, -1.27, rotate=90)
_pad_OUT = Pad1().at(2.95, -1.27, rotate=90)
_pad_VCC = Pad1().at(2.92, 1.27, rotate=90)


@inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:SENSOR-SMD_IRM-H638T-TR2-TL"
    p = {
        1: _pad_GND_0,
        2: _pad_GND_1,
        3: _pad_OUT,
        4: _pad_VCC,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 5.27)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -5.27)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.25, [(-2, 2.5), (2, 2.5), (2, -2.5), (-2, -2.5), (-2, 2.5)])),
        Silkscreen(ArcPolyline(0.06, [Arc((-3.5, 2.5), 0.03, 0, -360)])),
        # Lens outline (R1.5), offset toward pins 1 and 4.
        Silkscreen(ArcPolyline(0.25, [Arc((0, 0.76), 1.53, 0, -360)])),
    ]
    # The EasyEDA courtyard was the 4 x 5 mm body; the pads reach +-3.7 mm in x,
    # so it is grown to cover them.
    courtyard = Courtyard(rectangle(7.6, 5.0))


class IRM_H638T_TR2(jitx.Component):
    """38 kHz infrared receiver module.

    Datasheet facts with no JITX field: Vs 2.7..5.5 V, Icc 0.7 mA max (p.3);
    supply RC filter 47..220 ohm + >= 2.2 uF next to the part (p.2); OUT is a
    transistor output with an internal pull-up R_PU (p.1 block diagram);
    VH >= Vcc-0.4 V, VL <= 0.5 V at 2 mA sink (p.3).
    """

    mpn = "IRM-H638T/TR2"
    manufacturer = "Everlight Elec"
    lcsc = LCSCPart("C91447")
    datasheet = "https://www.everlighteurope.com/custom/files/datasheets/DMO-0000008.pdf"
    reference_designator_prefix = "U"

    GND = [Port() for _ in range(2)]
    OUT = Port()
    VCC = Port()

    landpattern = _Landpattern

    symbol = BoxSymbol(
        rows=Row(right=PinGroup(OUT)),
        columns=Column(up=PinGroup(VCC), down=PinGroup(*GND)),
    )

    def __init__(self) -> None:
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.GND[0]: lp.p[1],
                self.GND[1]: lp.p[2],
                self.OUT: lp.p[3],
                self.VCC: lp.p[4],
            }
        )


Device: type[IRM_H638T_TR2] = IRM_H638T_TR2


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
