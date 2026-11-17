# ruff: noqa: N999
"""LinkMems LMD3526B261-OFA03 bottom-port PDM MEMS microphone.

Source: LinkMems "Specification of MEMS Microphone", NO: M196 Version 1.0
(``datasheets/LMD3526B261-OFA03.pdf``); spec note
``datasheets/LMD3526B261-OFA03.spec.md``.

Package: 3.50 x 2.65 x 1.00 mm LGA, four rectangular signal pads and a ring
ground pad (pin 5) around the bottom acoustic port (section 7.2 "Appearance
Drawing", p.7). Pin names come from the p.7 pin table: 1 DATA, 2 L/R, 3 CLK,
4 VDD, 5 GND.

Land pattern: section 8.1 "Recommended Solder Pad Layout" (p.8): 0.73 x 0.52 mm
pads on a 1.67 mm column pitch and 0.82 mm row pitch, ring pad Ø1.62 mm outer /
Ø1.03 mm inner. The row-to-port 1.25 mm and port-to-body-edge 1.04 mm offsets
come from the bottom view on p.7. Coordinates here are the top view (looking
down on the PCB), so the p.7 bottom view is mirrored in X: pin 1 sits at upper
left. Cross-checked against the LCSC/EasyEDA footprint for C41347997
(``kicad_footprints/LMD3526B261-OFA03.kicad_mod``, user-approved channel):
pads agree within 0.01 mm.

Acoustic port: the datasheet gives the package port (Ø0.32 ± 0.05 mm, p.7) but no
PCB through-hole diameter. This model uses a Ø0.50 mm non-plated hole, the
JLCPCB minimum NPTH drill, which is larger than the package port plus its
tolerance and leaves a 0.265 mm annulus to the ring pad's Ø1.03 mm inner edge.
The disc inside the ring is a keepout on every layer (pour, via, route), so the
inner planes pull back from the hole and nothing seals the sound path.

Facts with no JITX field: single-bit PDM output; VDD 1.62-3.6 V (p.4); clock
1.0-4.8 MHz standard mode, 150-900 kHz low-power mode, < 50 kHz sleep (p.4);
L/R = VDD drives DATA after the CLK rising edge (sample on the falling edge),
L/R = GND drives DATA after the falling edge (sample on the rising edge)
(timing diagram, p.5); 0.1 uF VDD decoupling in the measurement circuit (p.6);
MSL 1; reflow peak 260 C for 30 s max; do not wash, ultrasonic-clean or pull a
vacuum over the port (p.8).
"""

import jitx
import shapely
from jitx.anchor import Anchor
from jitx.container import inline
from jitx.feature import Courtyard, KeepOut, Silkscreen
from jitx.landpattern import Landpattern, PadMapping
from jitx.layerindex import LayerSet
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.shapes import Shape
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Circle, Polyline, Text
from jitx.shapes.shapely import ShapelyGeometry
from jitxlib.jlcpcb import LCSCPart
from jitxlib.landpatterns.pads import NPTHPad, SMDPad
from jitxlib.symbols.box import BoxSymbol, Column, PinGroup, Row

# Package body, section 7.2 table (p.7).
BODY_LENGTH = 3.50  # Y
BODY_WIDTH = 2.65  # X

# Recommended solder pad layout, section 8.1 (p.8); offsets from the p.7 bottom view.
SIGNAL_PAD_X = 0.73
SIGNAL_PAD_Y = 0.52
COLUMN_PITCH = 1.67
ROW_PITCH = 0.82
ROW_TO_PORT = 1.25
PORT_TO_BODY_EDGE = 1.04
RING_OUTER_DIAMETER = 1.62
RING_INNER_DIAMETER = 1.03

# Design choice (see module docstring): JLCPCB minimum NPTH drill.
PORT_HOLE_DIAMETER = 0.50

PORT_Y = -BODY_LENGTH / 2 + PORT_TO_BODY_EDGE
LOWER_ROW_Y = PORT_Y + ROW_TO_PORT
UPPER_ROW_Y = LOWER_ROW_Y + ROW_PITCH
COLUMN_X = COLUMN_PITCH / 2


def ring_shape(outer_diameter: float, inner_diameter: float) -> Shape:
    """An annulus centred on the origin."""
    outer = shapely.Point(0.0, 0.0).buffer(outer_diameter / 2, quad_segs=32)
    inner = shapely.Point(0.0, 0.0).buffer(inner_diameter / 2, quad_segs=32)
    return ShapelyGeometry(outer.difference(inner))


class LMD3526Landpattern(Landpattern):
    """Section 8.1 recommended pad layout plus the acoustic port hole."""

    def __init__(self) -> None:
        signal = rectangle(SIGNAL_PAD_X, SIGNAL_PAD_Y)
        self.p = {
            1: SMDPad(signal).at(-COLUMN_X, UPPER_ROW_Y),
            2: SMDPad(signal).at(-COLUMN_X, LOWER_ROW_Y),
            3: SMDPad(signal).at(COLUMN_X, LOWER_ROW_Y),
            4: SMDPad(signal).at(COLUMN_X, UPPER_ROW_Y),
            5: SMDPad(ring_shape(RING_OUTER_DIAMETER, RING_INNER_DIAMETER)).at(0.0, PORT_Y),
        }
        self.port_hole = NPTHPad(Circle(diameter=PORT_HOLE_DIAMETER)).at(0.0, PORT_Y)
        self.port_keepout = KeepOut(
            Circle(diameter=RING_INNER_DIAMETER).at(0.0, PORT_Y),
            layers=LayerSet.all(),
            pour=True,
            via=True,
            route=True,
        )

        silk_x = BODY_WIDTH / 2 + 0.1
        silk_y = BODY_LENGTH / 2 + 0.1
        self.outline = Silkscreen(
            Polyline(
                0.12,
                [(-silk_x, -silk_y), (-silk_x, silk_y), (silk_x, silk_y), (silk_x, -silk_y), (-silk_x, -silk_y)],
            )
        )
        self.pin1_marker = Silkscreen(Circle(diameter=0.25).at(-silk_x - 0.3, UPPER_ROW_Y))
        self.reference = Silkscreen(Text(">REF", 0.5, Anchor.C).at(0.0, silk_y + 0.6))
        self.courtyard = Courtyard(rectangle(BODY_WIDTH + 1.0, BODY_LENGTH + 0.5))


class LMD3526B261_OFA03(jitx.Component):
    """LinkMems LMD3526B261-OFA03 bottom-port PDM MEMS microphone, 1.62-3.6 V."""

    mpn = "LMD3526B261-OFA03"
    manufacturer = "LinkMems"
    datasheet = "https://www.lcsc.com/product-detail/C41347997.html"
    reference_designator_prefix = "MK"
    lcsc = LCSCPart("C41347997")

    DATA = Port()
    LR = Port()
    """L/R channel select (pin 2): GND = left, VDD = right."""
    CLK = Port()
    VDD = Port()
    GND = Port()

    symbol = BoxSymbol(
        rows=[
            Row(left=PinGroup(CLK), right=PinGroup(DATA)),
            Row(left=PinGroup(LR)),
        ],
        columns=Column(up=PinGroup(VDD), down=PinGroup(GND)),
    )

    def __init__(self) -> None:
        self.landpattern = LMD3526Landpattern()
        lp = self.landpattern
        self.pad_mapping = PadMapping(
            {
                self.DATA: lp.p[1],
                self.LR: lp.p[2],
                self.CLK: lp.p[3],
                self.VDD: lp.p[4],
                self.GND: lp.p[5],
            }
        )


Device: type[LMD3526B261_OFA03] = LMD3526B261_OFA03


class TestDesign(SampleDesign):
    """Single-microphone harness for ``jitx build``."""

    @inline
    class circuit(jitx.Circuit):
        mic = Device()
