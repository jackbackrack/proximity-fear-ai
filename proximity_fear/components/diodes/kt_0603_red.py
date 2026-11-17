"""Hubei KENTO KT-0603R - red 0603 LED (charge-status indicator).

Ported unchanged from socialbadge-ai rev 2 (fabbed and brought up).

Source: KENTO "Specification for approval" (0603-0.6 red) Rev A.0, 2018-12-06,
saved as ``datasheets/KT-0603R.pdf``.
- p.2 "Package Profile & Soldering PAD Suggested": 1.6 x 0.8 x 0.6 mm body;
  pin 1 (+) anode, pin 2 cathode (green mark); suggested pads 0.70 x 0.70 on
  a 0.70 mm gap.
- p.3 "Absolute Maximum Ratings": IF 25 mA DC, VR 5 V; "Electrical Optical
  Characteristics": VF 1.8..2.4 V at 20 mA, lambda_d 615..630 nm.

Footprint: EasyEDA ``LED-SMD_L1.6-W0.8-R-RD`` (``kicad_footprints/led_0603_red.kicad_mod``):
0.8 x 0.8 pads on 1.5 mm centres (0.7 mm gap, as suggested; pads 0.1 mm larger).
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

# ======================================================================
# Pad shape definitions
# ======================================================================


class Pad1(Pad):
    """SMD pad (0.8 x 0.8 mm)."""

    shape = rectangle(0.8, 0.8)
    soldermask = Soldermask(rectangle(0.8, 0.8))
    paste = Paste(rectangle(0.8, 0.8))


# ======================================================================
# Landpattern
# ======================================================================
# NOTE: KiCad Y-axis is inverted vs JITX (KiCad Y+ = down, JITX Y+ = up)
# All Y coordinates are negated during conversion.
# Pads and the landpattern class are declared at module scope (not inside
# Component.__init__) because jitx 4.4 forbids creating new JITX classes
# during instantiation.

_pad_K = Pad1().at(-0.75, -0)
_pad_A = Pad1().at(0.75, -0)


@jitx.container.inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:LED-SMD_L1.6-W0.8-R-RD"
    p = {
        1: _pad_A,
        2: _pad_K,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 4)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -4)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.25, [(0.2, 0.7), (1.47, 0.7)])),
        Silkscreen(Polyline(0.25, [(1.47, 0.7), (1.47, -0.7)])),
        Silkscreen(Polyline(0.25, [(1.47, -0.7), (0.2, -0.7)])),
        Silkscreen(Polyline(0.25, [(0.09, 0), (-0.12, 0)])),
        Silkscreen(Polyline(0.25, [(-0.3, 0.7), (-1.4, 0.7)])),
        Silkscreen(Polyline(0.25, [(-1.4, 0.7), (-1.7, 0.4)])),
        Silkscreen(Polyline(0.25, [(-1.7, 0.4), (-1.7, -0.4)])),
        Silkscreen(Polyline(0.25, [(-1.7, -0.4), (-1.4, -0.7)])),
        Silkscreen(Polyline(0.25, [(-1.4, -0.7), (-0.3, -0.7)])),
        Silkscreen(Polyline(0.25, [(0.09, 0.4), (0.09, -0.38)])),
        Silkscreen(ArcPolyline(0.1, [Arc((0.8, 0.4), 0.05, 0, -360)])),
    ]
    courtyard = Courtyard(rectangle(1.6, 0.8))


# ======================================================================
# Component
# ======================================================================


class KT_0603R(jitx.Component):
    "Red 645nm LED 0603 2V 20mA"

    mpn = "KT-0603R"
    manufacturer = "Hubei KENTO"
    reference_designator_prefix = "D"
    # Pad numbering follows the LCSC/EasyEDA footprint and the KENTO drawing
    # (p.2): pad 1 = anode (+0.75 mm), pad 2 = cathode, so the JLCPCB exporter's
    # pad-label match gives the right polarity without an orientation override.
    lcsc = LCSCPart("C2286")
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/011ec3e8cb1e825f6961d29bc4db4c7a.pdf"

    # --- Ports ---
    A = Port()  # Pad "A"
    K = Port()  # Pad "K"

    landpattern = _Landpattern

    # --- Symbol ---
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(K, A),
        ),
    )

    def __init__(self) -> None:
        # --- Pad Mapping ---
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.A: lp.p[1],
                self.K: lp.p[2],
            }
        )


Device: type[KT_0603R] = KT_0603R


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
