"""onsemi SZSMF5.0AT1G -- 5 V, 200 W unidirectional TVS (zener transient suppressor), SOD-123FL.

VBUS hot-plug clamp at the USB-C receptacle (comp-06; MCP73831 DS20001984G
section 6.1.1.2 "Input Overvoltage Protection", p.18: "A transzorb connected
from the V+ input supply connector to the 0V ground reference will snub the
transients").

Sources
- onsemi data sheet "SMF5.0AT1 Series, Zener Transient Voltage Suppressor,
  SOD-123 Flat Lead Package", publication SMF5.0AT1/D, Rev. 2, May 2007,
  saved as ``datasheets/SZSMF5.0AT1G.pdf``
  (fetched from https://pccomponents.com/datasheets/ONSEMI-SMF5.pdf; onsemi.com
  serves only an HTML index page to this host).
  - p.1 pin drawing: pin 1 = CATHODE, pin 2 = ANODE; "Cathode Indicated by
    Polarity Band"; SOD-123FL CASE 498.
  - p.2 Maximum ratings: Ppk 200 W (10/1000 us) for SMF5.0A..SMF58A.
  - p.3 "ELECTRICAL CHARACTERISTICS" row SMF5.0A (marking KE): VRWM 5 V;
    VBR 6.4 / 6.7 / 7.0 V min/nom/max at IT 10 mA; IR <= 400 uA at VRWM;
    VC <= 9.2 V at IPP 21.7 A (10/1000 us).
  - p.6 "PACKAGE DIMENSIONS SOD-123FL CASE 498-01 ISSUE A": E 2.50..2.90
    (body length), D 1.50..1.80 (body width), A 0.90..1.00, HE 3.40..3.80,
    b 0.70..1.10, L 0.55..0.95. "SOLDERING FOOTPRINT": two 0.91 x 1.22 mm
    lands, 2.36 mm inner gap, 4.19 mm outer extent (so 3.28 mm centres).
- Channel evidence: JLCPCB/LCSC C5299833 "SZSMF5.0AT1G", onsemi, SOD-123FL,
  "200W 21.7A 400uA 5V 6.4V 9.2V", 8 881 in stock (JLC component API,
  2026-11-15). The SZ prefix is onsemi's site/change-controlled (AEC-Q101)
  ordering of the same SMF5.0A; the 2007 Rev. 2 sheet lists only SMF5.0AT1(G),
  so the SZ ordering code rests on the channel record (open item in the spec
  note). The non-SZ SMF5.0AT1G (C47022) has no JLC stock.

Footprint: hand-placed from onsemi's own "SOLDERING FOOTPRINT" (p.6), which no
IPC generator reproduces exactly; courtyard = body max + lands + 0.25 mm
(``landpattern_helpers.COURTYARD_EXCESS``). Silkscreen: body lines above and
below plus a cathode bar on the pin-1 end (polarity band side).

No-field facts: unidirectional -- forward-biases (VF 1.25 V at 200 mA, p.3
header) for a negative VBUS; IR is specified only at 5.0 V (VRWM), not at the
USB 2.0 maximum of 5.25 V (see the spec note's comparison and open items).
"""

# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention

from jitx import PadMapping
from jitx.circuit import Circuit
from jitx.component import Component
from jitx.container import inline
from jitx.landpattern import Landpattern
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import LCSCPart
from jitxlib.landpatterns.pads import SMDPad
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row

from .landpattern_helpers import courtyard_around, rect_at, silkscreen_outline

# onsemi SOD-123FL soldering footprint (p.6), mm.
LAND_X = 0.91  # along the part axis
LAND_Y = 1.22  # across
LAND_OUTER = 4.19  # outer edge to outer edge
LAND_PITCH = LAND_OUTER - LAND_X  # 3.28 mm centre to centre (inner gap 2.37 ~ 2.36)
# SOD-123FL body (p.6): E (length) and D (width) maxima.
BODY_L = 2.90
BODY_W = 1.80
# Silkscreen line distance beyond the land edge (labelled layout choice, as in
# nexperia_PESD5V0S1BL: clears mask registration + silk-to-mask + half width).
SILK_OFFSET = 0.35


class SOD123FLLandpattern(Landpattern):
    """onsemi SOD-123FL footprint: pin 1 (cathode) at -x, pin 2 (anode) at +x."""

    def __init__(self) -> None:
        h = LAND_PITCH / 2
        self.p = {n: SMDPad(rectangle(LAND_X, LAND_Y)).at(x, 0.0) for n, x in ((1, -h), (2, h))}
        pads = list(self.p.values())
        bx, by = BODY_L / 2, BODY_W / 2
        # Body edges along the part, plus the cathode band across the pin-1 end
        # of the body (clipped clear of the land's mask opening by the helper).
        cx = -bx + 0.15
        self.outline = silkscreen_outline(
            [[(-bx, by), (bx, by)], [(-bx, -by), (bx, -by)], [(cx, by), (cx, -by)]],
            pads,
        )
        self.courtyard = courtyard_around([rect_at(BODY_L, BODY_W, 0.0, 0.0)], pads)


class SZSMF5_0AT1G(Component):
    """onsemi SZSMF5.0AT1G 5 V unidirectional 200 W TVS, SOD-123FL."""

    mpn = "SZSMF5.0AT1G"
    lcsc = LCSCPart("C5299833", footprint="SOD-123FL")  # JLCPCB assembly
    manufacturer = "onsemi"
    reference_designator_prefix = "D"
    datasheet = "https://www.onsemi.com/download/data-sheet/pdf/smf5.0at1-d.pdf"

    K = Port()  # pin 1 -- cathode (polarity band)
    A = Port()  # pin 2 -- anode

    landpattern = SOD123FLLandpattern()
    symbol = BoxSymbol(rows=Row(left=PinGroup(K), right=PinGroup(A)))

    def __init__(self) -> None:
        lp = self.landpattern
        self.mappings = [PadMapping({self.K: lp.p[1], self.A: lp.p[2]})]


Device: type[SZSMF5_0AT1G] = SZSMF5_0AT1G


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = SZSMF5_0AT1G()
