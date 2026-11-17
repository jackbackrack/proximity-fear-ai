"""Alpha & Omega AO3401A - 30 V P-channel MOSFET, SOT-23.

Ported unchanged from socialbadge-ai rev 2 (fabbed and brought up).

Sources: AOS AO3401A Rev 3.1 (Dec 2023), saved as ``datasheets/AO3401A.pdf``
(p.1 SOT23 top view: G and S on one side, D opposite; VDS -30 V, VGS +-12 V,
ID -4 A; p.2 VGS(th) -0.5..-1.3 V, RDS(on) < 60 mOhm at -4.5 V);
AOS PO-00001 "SOT23 package outline" Rev M, saved as
``datasheets/AOS_SOT23_package.pdf`` (recommended land 0.80 x 0.80, rows
2.40 apart, e 0.95).

Footprint: EasyEDA ``SOT-23_L2.9-W1.3-P1.90-LS2.4-BR`` (``kicad_footprints/C15127.kicad_mod``):
1.0 x 0.6 lands, rows 2.30 apart -- kept from the fabbed board. Port-to-land
assignment matches the datasheet top view rotated 90 deg (D alone at -x).
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
    """SMD pad (1 x 0.6 mm)."""

    shape = rectangle(1, 0.6)
    soldermask = Soldermask(rectangle(1, 0.6))
    paste = Paste(rectangle(1, 0.6))


# ======================================================================
# Landpattern
# ======================================================================
# NOTE: KiCad Y-axis is inverted vs JITX (KiCad Y+ = down, JITX Y+ = up)
# All Y coordinates are negated during conversion.
# Pads and the landpattern class are declared at module scope (not inside
# Component.__init__) because jitx 4.4 forbids creating new JITX classes
# during instantiation.

_pad_S = Pad1().at(1.15, 0.95, rotate=180)
_pad_D = Pad1().at(-1.15, -0, rotate=180)
_pad_G = Pad1().at(1.15, -0.95, rotate=180)


@jitx.container.inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:SOT-23_L2.9-W1.3-P1.90-LS2.4-BR"
    p = {
        1: _pad_S,
        2: _pad_D,
        3: _pad_G,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 4.95)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -4.95)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.25, [(-0.7, 0.64), (-0.7, 1.5)])),
        Silkscreen(Polyline(0.25, [(-0.7, 1.5), (0.3, 1.5)])),
        Silkscreen(Polyline(0.25, [(0.7, -0.31), (0.7, 0.31)])),
        Silkscreen(Polyline(0.25, [(-0.7, -1.5), (-0.7, -0.64)])),
        Silkscreen(Polyline(0.25, [(-0.7, -1.5), (0.3, -1.5)])),
        Silkscreen(ArcPolyline(0.06, [Arc((1.2, -1.45), 0.03, 0, -360)])),
    ]
    # The EasyEDA courtyard was the 1.3 x 2.9 mm body; the pads reach ±1.65 mm
    # in x and ±1.25 mm in y, so it is grown to cover them (+0.25 mm).
    courtyard = Courtyard(rectangle(3.8, 3.0))


# ======================================================================
# Component
# ======================================================================


class AO3401A(jitx.Component):
    "P-channel MOSFET 30 V 4 A SOT-23"

    mpn = "AO3401A"
    manufacturer = "Alpha & Omega Semicon"
    lcsc = LCSCPart("C15127")
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/fee353dd1e9e0bc90b295f14f381aa4c.pdf"
    reference_designator_prefix = "Q"

    # --- Ports ---
    S = Port()  # Pad "S"
    D = Port()  # Pad "D"
    G = Port()  # Pad "G"

    landpattern = _Landpattern

    # --- Symbol ---
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(S, D, G),
        ),
    )

    def __init__(self) -> None:
        # --- Pad Mapping ---
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.S: lp.p[1],
                self.D: lp.p[2],
                self.G: lp.p[3],
            }
        )


Device: type[AO3401A] = AO3401A


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
