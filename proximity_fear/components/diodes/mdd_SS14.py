"""MDD SS14 - 40 V 1 A Schottky rectifier, DO-214AC (SMA).

Ported unchanged from socialbadge-ai rev 2 (fabbed and brought up).

Source: MDD "SS12 thru SS1200" Rev 2025A5, saved as ``datasheets/SS14.pdf``.
- p.1 outline: body 4.50 max x 2.80 max; "Color band denotes cathode end".
- p.1 ratings: VRRM 40 V, I(AV) 1.0 A, IFSM 25 A, VF 0.55 V max at 1 A.
- p.3 "Suggested Pad Layout": A 1.68, B 1.52, C 3.93 (land centres), D 2.41.

Footprint: EasyEDA ``SMA_L4.2-W2.6-LS5.0-RD_1`` (``kicad_footprints/ss14.kicad_mod``):
1.52 x 1.68 pads on 3.92 mm centres -- matches the MDD suggested layout.
Courtyard grown (aud-01 A-12) to enclose the pads and the max body + 0.25 mm.
"""

# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention

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
    """SMD pad (1.52 x 1.68 mm)."""

    shape = rectangle(1.52, 1.68)
    soldermask = Soldermask(rectangle(1.52, 1.68))
    paste = Paste(rectangle(1.52, 1.68))


# ======================================================================
# Landpattern
# ======================================================================
# NOTE: KiCad Y-axis is inverted vs JITX (KiCad Y+ = down, JITX Y+ = up)
# All Y coordinates are negated during conversion.
# Pads and the landpattern class are declared at module scope (not inside
# Component.__init__) because jitx 4.4 forbids creating new JITX classes
# during instantiation.

_pad_A = Pad1().at(1.96, -0)
_pad_K = Pad1().at(-1.96, -0)


@jitx.container.inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:SMA_L4.2-W2.6-LS5.0-RD_1"
    p = {
        1: _pad_A,
        2: _pad_K,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 4)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -4)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.25, [(-0.72, -0), (0.75, -0)])),
        Silkscreen(Polyline(0.25, [(-0.25, 0.5), (-0.25, -0.5)])),
        Silkscreen(Polyline(0.25, [(0.25, 0.5), (-0.25, -0)])),
        Silkscreen(Polyline(0.25, [(-0.25, -0), (0.25, -0.5)])),
        Silkscreen(Polyline(0.25, [(0.25, -0.5), (0.25, 0.5)])),
        Silkscreen(Polyline(0.25, [(2.1, -1.07), (2.1, -1.3)])),
        Silkscreen(Polyline(0.25, [(2.1, 1.3), (2.1, 1.07)])),
        Silkscreen(Polyline(0.25, [(-2.1, 1.3), (2.1, 1.3)])),
        Silkscreen(Polyline(0.25, [(-2.1, 1.07), (-2.1, 1.3)])),
        Silkscreen(Polyline(0.25, [(-2.1, -1.3), (-2.1, -1.07)])),
        Silkscreen(Polyline(0.25, [(2.1, -1.3), (-2.1, -1.3)])),
        Silkscreen(ArcPolyline(0.06, [Arc((-2.63, -1.3), 0.03, 0, -360)])),
    ]
    # A-12: pads reach x +-2.72 (1.96 + 0.76) and the body is 4.50 x 2.80 max (p.1),
    # so the courtyard is pad / body bounds + 0.25 mm IPC-7351B nominal excess,
    # rounded up: x +-3.0, y +-1.65. Pad copper unchanged.
    courtyard = Courtyard(rectangle(6.0, 3.3))


# ======================================================================
# Component
# ======================================================================


class SS14(jitx.Component):
    "Schottky diode 40V 1A SMA"

    mpn = "SS14"
    manufacturer = "MDD"
    reference_designator_prefix = "D"
    # This landpattern's own pad numbering (A=p[1], K=p[2]) is the opposite of
    # the real catalogue part's (pin 1=K, pin 2=A). Since a 2-pin footprint is
    # 180 deg symmetric, geometry alone can't set the orientation and the
    # exporter falls back to matching pad number labels — which would silently
    # pair our anode with their cathode. Pinned to the value verified by
    # same-polarity position matching instead.
    lcsc = LCSCPart("C2480", orientation=0.0)
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/9977bb85cd7e349115b7bcb7054cfa0d.pdf"

    # --- Ports ---
    A = Port()  # Pad "A"
    K = Port()  # Pad "K"

    landpattern = _Landpattern

    # --- Symbol ---
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(A, K),
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


Device: type[SS14] = SS14


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
