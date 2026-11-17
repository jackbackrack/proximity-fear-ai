"""SHOU HAN 2.0-2P WT - JST-PH-compatible 2.0 mm 2-pin SMD right-angle header (battery).

Ported unchanged from socialbadge-ai rev 2 (fabbed and brought up).

Source: SHOU HAN customer drawing 2002LT series Rev 1.00 + specification,
saved as ``datasheets/PH2-2P.pdf``.
- p.1 "Recommended PCB Layout": signal lands 1.0 x 3.5 on DIM.A = 2.0 mm,
  fitting nails 1.5 x 3.5, 1.1 mm from the outer signal land, rows 2.2 mm
  apart (centres 5.7 mm apart); housing 7.9 x 6.2 mm.
- p.4 "Electrical performance": 2 A rated current, 250 V; p.3 AWG 28-22.

Footprint: EasyEDA ``CONN-SMD_2.0-2PWT`` (``kicad_footprints/jstph_2p.kicad_mod``);
pads match the drawing (pins at x = +-1.0, nails at +-3.35, rows at y = +-2.85).
Pins are not numbered on the drawing: PIN1 / PIN2 follow the EasyEDA numbering
and battery polarity is assigned in the circuit. MOUNT1/2 are the nails.
Courtyard grown (aud-01 A-12) to enclose every land and the housing + 0.25 mm.
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
    """SMD pad (1 x 3.5 mm)."""

    shape = rectangle(1, 3.5)
    soldermask = Soldermask(rectangle(1, 3.5))
    paste = Paste(rectangle(1, 3.5))


class Pad2(Pad):
    """SMD pad (1.5 x 3.5 mm)."""

    shape = rectangle(1.5, 3.5)
    soldermask = Soldermask(rectangle(1.5, 3.5))
    paste = Paste(rectangle(1.5, 3.5))


# ======================================================================
# Landpattern
# ======================================================================
# Pads and the landpattern class are declared at module scope (not inside
# Component.__init__) because jitx 4.4 forbids creating new JITX classes
# during instantiation.

_pad_p1 = Pad1().at(1, -2.85)
_pad_p2 = Pad1().at(-1, -2.85)
_pad_p3 = Pad2().at(3.35, 2.85)
_pad_p4 = Pad2().at(-3.35, 2.85)


@jitx.container.inline
class _Landpattern(Landpattern):
    name = "easyeda2kicad:CONN-SMD_2.0-2PWT"
    p = {
        1: _pad_p1,
        2: _pad_p2,
        3: _pad_p3,
        4: _pad_p4,
    }
    reference_designator = Silkscreen(Text(">REF", 1, Anchor.W).at((0, 6.85)))
    value_label = Custom(Text(">VALUE", 1, Anchor.W).at((0, -6.85)), name="Fab")
    silkscreen = [
        Silkscreen(Polyline(0.25, [(-0.27, -1.5), (0.27, -1.5)])),
        Silkscreen(Polyline(0.25, [(4, -3.2), (4, 0.92)])),
        Silkscreen(Polyline(0.25, [(-2.37, 4.5), (2.37, 4.5)])),
        Silkscreen(Polyline(0.25, [(-4, -3.2), (-4, 0.92)])),
        Silkscreen(Polyline(0.25, [(1.73, -1.5), (3.3, -1.5)])),
        Silkscreen(Polyline(0.25, [(3.3, -1.5), (3.3, -3.2)])),
        Silkscreen(Polyline(0.25, [(3.3, -3.2), (4, -3.2)])),
        Silkscreen(Polyline(0.25, [(-4, -3.2), (-3.3, -3.2)])),
        Silkscreen(Polyline(0.25, [(-3.3, -3.2), (-3.3, -1.5)])),
        Silkscreen(Polyline(0.25, [(-3.3, -1.5), (-1.73, -1.5)])),
        Silkscreen(ArcPolyline(0.06, [Arc((4, -4), 0.03, 0, -360)])),
    ]
    # A-12: signal lands reach y -4.6 (-2.85 - 1.75) and nails x +-4.1 / y +4.6;
    # the housing is 7.9 wide (DIM.B, p.1) and sits between the land rows. Courtyard
    # = pad bounds + 0.25 mm IPC-7351B nominal excess. Pad copper unchanged.
    courtyard = Courtyard(rectangle(8.7, 9.7))


# ======================================================================
# Component
# ======================================================================


class PH2_2P(jitx.Component):
    "JST-PH 2mm 2-pin SMD right-angle battery connector"

    mpn = "2.0-2P WT"
    manufacturer = "SHOU HAN"
    reference_designator_prefix = "J"
    lcsc = LCSCPart("C668620")
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/dce18c3d77bfbed062e0f133b57b17e3.pdf"

    # --- Ports ---
    PIN1 = Port()  # Pad 1 — battery wire 1
    PIN2 = Port()  # Pad 2 — battery wire 2
    MOUNT1 = Port()  # Pad 3 — mechanical solder tab (tie GND)
    MOUNT2 = Port()  # Pad 4 — mechanical solder tab (tie GND)

    landpattern = _Landpattern

    # --- Symbol ---
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(PIN1, PIN2),
            right=PinGroup(MOUNT1, MOUNT2),
        ),
    )

    def __init__(self) -> None:
        # --- Pad Mapping ---
        lp = self.landpattern
        self.mappings = [
            PadMapping(
                {
                    self.PIN1: [lp.p[1]],
                    self.PIN2: [lp.p[2]],
                    self.MOUNT1: [lp.p[3]],
                    self.MOUNT2: [lp.p[4]],
                }
            )
        ]


Device: type[PH2_2P] = PH2_2P


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
