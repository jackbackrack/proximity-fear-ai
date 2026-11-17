# ruff: noqa: N999  -- module named <manufacturer>_<MPN> per the component naming convention (PLAN.md comp-05)
"""Tag-Connect TC2030-NL (no legs) SWD programming footprint.

Board feature, not a placed part: the TC2030-IDC-NL Plug-of-Nails cable presses
spring pins onto six bare pads and locates on three non-plated holes. Nothing is
soldered and nothing is ordered for the board (drawing note 4: "specify DNL in
your BOM"), so the component is a ``MechanicalComponent`` with no MPN.

Geometry source: Tag-Connect drawing "FOOTPRINT FOR TC2030-IDC-NL" (DWG
TC2030-IDC-NL-FP rev B, 12/05/19), sheet 1, "PCB TOP LAYER" view, saved as
``datasheets/TC2030-IDC-NL.pdf``. Origin is the centre of the 2 x 3 pad array;
+x points from pins 1/2 toward pins 5/6, +y from the odd row to the even row.

- Contact pads: dia 0.0310" (0.787 mm) +/-0.076, 3 columns at 0.0500" (1.270 mm)
  pitch, rows 0.0500" (1.270 mm) apart: pins 1/3/5 on the lower row, 2/4/6 on the
  upper row, pin 1 bottom left. No solder paste on the pads (note 3).
- Alignment holes: dia 0.0390" (0.991 mm) +/-0.076, non-plated. One 0.0500"
  (1.270 mm) left of the pin 1/2 column on the array centre line; two 0.2000"
  (5.080 mm) to its right at +/-0.0400" (1.016 mm).
- Keep-out (note 1): no tracks or vias in the shaded rectangle between the pad
  centres (2.540 x 1.270 mm).
- Note 2 (no other track within 0.020" / 0.508 mm of a contact pad) is a net
  clearance rule and is applied by the top-level design.

Cross-check: KiCad library footprint
``Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical`` (saved under
``kicad_footprints/``) agrees pad for pad once its y axis is negated.

Pinout: Tag-Connect "TC2030-CTX" sheet, "6-Pin TC2030 Footprint" table
(``datasheets/TC2030-CTX.pdf``): 1 VCC, 2 SWDIO/TMS, 3 nRESET, 4 SWCLK/TCK,
5 GND (also GNDDetect), 6 SWO/TDO.

Courtyard: the plug face measures 0.39" x 0.240" (9.906 x 6.096 mm, sheet 2 end
view) and is drawn centred on the pad array, so the courtyard is that face. The
three alignment pins pass through the board: sheet 2 shows them 0.125" (3.175 mm)
beyond the plug face with the contact pins compressed, so on a 1.6 mm board each
tip stands ~1.6 mm proud of the far side, inside its 0.991 mm hole (the drawing
gives no separate pin diameter; the hole is the pin's footprint). Each hole gets
its own circular opposite-side courtyard, the hole grown by ``PIN_TIP_MARGIN``
(0.5 mm, design choice: hole tolerance +/-0.076 mm, the rounded tip's lateral
play, and room to see and seat the pin), rather than one box around all three, so
far-side parts may sit between the pins.
"""

import jitx
from jitx.anchor import Anchor
from jitx.component import MechanicalComponent
from jitx.container import inline
from jitx.feature import Courtyard, KeepOut, Silkscreen
from jitx.landpattern import Landpattern, PadMapping
from jitx.layerindex import LayerSet, Side
from jitx.net import Port
from jitx.sample import SampleBoard
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Circle, Text
from jitxlib.landpatterns.pads import NPTHPad, SMDPad
from jitxlib.protocols.serial import SWD
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row

from ...substrate import ProximityFearSubstrate

# Sheet 1 dimensions, inches converted to mm.
PAD_DIAMETER = 0.787  # dia 0.0310"
PAD_PITCH = 1.270  # 0.0500" column pitch and row spacing
HOLE_DIAMETER = 0.991  # dia 0.0390"
HOLE_LEFT_X = -2 * PAD_PITCH  # 0.0500" left of the pin 1/2 column
HOLE_RIGHT_X = HOLE_LEFT_X + 5.080  # 0.2000" from the left hole
HOLE_RIGHT_Y = 1.016  # 0.0400" above and below the array centre line

# Sheet 2 end view of the plug face.
PLUG_FACE_LENGTH = 9.906  # 0.39"
PLUG_FACE_WIDTH = 6.096  # 0.240"

HOLE_CENTRES = ((HOLE_LEFT_X, 0.0), (HOLE_RIGHT_X, HOLE_RIGHT_Y), (HOLE_RIGHT_X, -HOLE_RIGHT_Y))

# Opposite-side clearance around each alignment-pin hole (design choice, see module docstring).
PIN_TIP_MARGIN = 0.5
PIN_TIP_COURTYARD_DIAMETER = HOLE_DIAMETER + 2 * PIN_TIP_MARGIN


class TC2030NLLandpattern(Landpattern):
    """Six contact pads, three NPTH alignment holes, the pad keep-out."""

    name = "TC2030-IDC-NL"

    p: dict[int, SMDPad]
    holes: list[NPTHPad]

    def __init__(self) -> None:
        half_row = PAD_PITCH / 2
        # Odd pins on the lower row, even pins above them, pin 1 at the left.
        self.p = {
            2 * column + 1 + row: SMDPad(Circle(diameter=PAD_DIAMETER), paste=None).at(
                (column - 1) * PAD_PITCH, (2 * row - 1) * half_row
            )
            for column in range(3)
            for row in range(2)
        }
        self.holes = [NPTHPad(Circle(diameter=HOLE_DIAMETER)).at(x, y) for x, y in HOLE_CENTRES]
        # Note 1: no tracks or vias between the pad centres.
        self.keepout = KeepOut(rectangle(2 * PAD_PITCH, PAD_PITCH), layers=LayerSet(0), route=True, via=True)
        self.courtyard = Courtyard(rectangle(PLUG_FACE_LENGTH, PLUG_FACE_WIDTH))
        # One opposite-side courtyard per alignment pin tip, concentric with its hole.
        self.pin_tip_courtyards = [
            Courtyard(Circle(diameter=PIN_TIP_COURTYARD_DIAMETER).at(x, y), side=Side.Bottom) for x, y in HOLE_CENTRES
        ]
        # Pin 1 dot below pad 1, clear of its mask opening.
        self.pin1_marker = Silkscreen(Circle(radius=0.15).at(-PAD_PITCH, -half_row - PAD_DIAMETER / 2 - 0.35))
        self.reference_designator = Silkscreen(Text(">REF", 1.0, Anchor.C).at(0.0, PLUG_FACE_WIDTH / 2 + 0.8))


class TC2030NL(MechanicalComponent):
    """Tag-Connect TC2030-NL SWD pads (cable TC2030-IDC-NL, not on the BOM)."""

    manufacturer = "Tag-Connect"
    reference_designator_prefix = "J"
    datasheet = (
        "https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/2019/12/TC2030-IDC-NL-Datasheet-Rev-B.pdf"
    )

    VCC = Port()
    """Pin 1: target supply reference for the probe."""
    nRESET = Port()
    """Pin 3: target reset, active low."""
    GND = Port()
    """Pin 5: ground (the cable also uses it as GNDDetect)."""

    def __init__(self) -> None:
        self.swd = SWD(swo=True)
        """Pins 2 SWDIO, 4 SWCLK, 6 SWO."""
        swo = self.swd.swo
        if swo is None:
            raise ValueError("SWD bundle was built without its SWO line")

        self.landpattern = TC2030NLLandpattern()
        lp = self.landpattern
        self.mappings = [
            PadMapping(
                {
                    self.VCC: lp.p[1],
                    self.swd.swdio: lp.p[2],
                    self.nRESET: lp.p[3],
                    self.swd.swdclk: lp.p[4],
                    self.GND: lp.p[5],
                    swo: lp.p[6],
                }
            )
        ]
        self.symbol = BoxSymbol(
            rows=Row(
                left=PinGroup(self.VCC, self.nRESET, self.GND),
                right=PinGroup(self.swd.swdio, self.swd.swdclk, swo),
            ),
        )


Device: type[TC2030NL] = TC2030NL


class TestDesign(jitx.Design):
    """The footprint alone on the board substrate."""

    substrate = ProximityFearSubstrate()
    board = SampleBoard()

    @inline
    class circuit(jitx.Circuit):
        tc = TC2030NL()
