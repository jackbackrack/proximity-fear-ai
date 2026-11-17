# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention
"""Everlight IR11-21C/TR8 - 940 nm infrared emitting diode, 1206 chip package.

Ported from socialbadge-ai rev 2 (fabbed and brought up); pad copper unchanged.

Source: Everlight IR11-21C/TR8 datasheet DIR-0000945 Rev 4 (2015-09-26),
saved as ``datasheets/IR11-21C_TR8.pdf``.
- p.2 "Package Dimensions": 3.0 x 1.5 mm body; pin 1 anode (right in the top
  view, "+"), pin 2 cathode (left, cathode mark).
- p.2 "Recommend soldering pad": 0.9 mm pads, 1.3 mm tall, 1.6 mm inner gap,
  3.4 mm outer (centres +-1.25).
- p.3 "Absolute Maximum Ratings": IF 65 mA continuous, VR 5 V, Pd 130 mW;
  "Electro-Optical Characteristics": VF 1.2 typ / 1.5 max V at 20 mA,
  lambda_p 940 nm, 2theta1/2 100 deg.

Footprint: EasyEDA ``LED1206-R-RD_RED`` (``kicad_footprints/C19269752.kicad_mod``):
1.485 x 1.62 pads on +-1.49 mm centres (inner gap 1.495, outer 4.46), larger
than the datasheet suggestion (which it says is "for reference only") and
fabbed on socialbadge rev 2, so kept. Its pad 1 (+1.49) is the anode, as in
the datasheet.

Change from socialbadge-ai: there pad 1 was mapped to the cathode to match a
legacy layout and corrected with an lcsc.lock orientation of 180. This board
has no legacy layout, so the mapping follows the footprint and the datasheet
(pad 1 = A, pad 2 = C) and the KiCad silkscreen is used unmirrored; the JLCPCB
exporter's pad match then needs no orientation override.
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
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row


class Pad1(Pad):
    """SMD pad (1.485 x 1.62 mm), from the EasyEDA footprint."""

    shape = rectangle(1.485, 1.62)
    soldermask = Soldermask(rectangle(1.485, 1.62))
    paste = Paste(rectangle(1.485, 1.62))


# KiCad Y+ is down, JITX Y+ is up: every KiCad y is negated.
_pad_A = Pad1().at(1.49, 0)
_pad_C = Pad1().at(-1.49, 0)


@inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:LED1206-R-RD_RED"
    p = {
        1: _pad_A,
        2: _pad_C,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 4)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -4)), name="Fab")
    silkscreen = [
        # Polarity triangle, base at +0.38 (anode side), apex toward the cathode.
        Silkscreen(Polyline(0.25, [(0.38, 0.63), (0.38, -0.63)])),
        Silkscreen(Polyline(0.25, [(0.38, 0.63), (-0.51, 0)])),
        Silkscreen(Polyline(0.25, [(-0.51, 0), (0.38, -0.63)])),
        # Anode-end bracket (square corners).
        Silkscreen(Polyline(0.15, [(0.83, -1.04), (2.46, -1.04), (2.46, 1.04), (0.83, 1.04)])),
        # Cathode-end bracket (chamfered corners) and the cathode bar.
        Silkscreen(
            Polyline(
                0.15,
                [(-0.83, -1.04), (-2.31, -1.04), (-2.46, -0.89), (-2.46, 0.89), (-2.31, 1.04), (-0.83, 1.04)],
            )
        ),
        Silkscreen(Polyline(0.15, [(-2.692, 0.886), (-2.692, -0.886)])),
        # Pin-1 (anode) dot.
        Silkscreen(ArcPolyline(0.06, [Arc((1.5, 0.75), 0.03, 0, -360)])),
    ]
    # The EasyEDA courtyard was the 3.0 x 1.5 mm body; the pads reach +-2.23 mm
    # in x and +-0.81 mm in y, so it is grown to cover them.
    courtyard = Courtyard(rectangle(4.6, 1.8))


class IR11_21C_TR8(jitx.Component):
    """940 nm infrared emitting diode, 1206.

    Datasheet facts with no JITX field: IF 65 mA max continuous, VR 5 V,
    VF 1.2 V typ at 20 mA, 100 deg viewing angle (p.3).
    """

    mpn = "IR11-21C/TR8"
    manufacturer = "Everlight Elec"
    lcsc = LCSCPart("C19269752")
    datasheet = "https://en.everlight.com/wp-content/plugins/ItemRelationship/product_files/pdf/IR11-21C-TR8.pdf"
    reference_designator_prefix = "D"

    A = Port()
    C = Port()

    landpattern = _Landpattern

    symbol = BoxSymbol(rows=Row(left=PinGroup(A), right=PinGroup(C)))

    def __init__(self) -> None:
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.A: lp.p[1],
                self.C: lp.p[2],
            }
        )


Device: type[IR11_21C_TR8] = IR11_21C_TR8


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
