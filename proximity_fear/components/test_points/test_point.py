"""Generic bare-copper test point (not populated, not in the BOM).

Ported unchanged from socialbadge-ai rev 2. A single 1.2 mm round SMD pad as
a probe landing spot; no datasheet (not a purchased part).
"""

from jitx.anchor import Anchor
from jitx.circuit import Circuit
from jitx.component import NonPopulatedComponent
from jitx.container import inline
from jitx.feature import Courtyard, Silkscreen
from jitx.landpattern import Landpattern
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.shapes.primitive import Circle, Text
from jitxlib.landpatterns.pads import SMDPad
from jitxlib.symbols.box import BoxSymbol

PAD_DIAMETER = 1.2  # mm — large enough for a multimeter probe tip or hook clip
REF_DES_TEXT_SIZE = 0.8  # mm
REF_DES_OFFSET = 1.3  # mm above pad center


class TestPointLandpattern(Landpattern):
    p1 = SMDPad(Circle(diameter=PAD_DIAMETER)).at(0, 0)
    courtyard = Courtyard(Circle(diameter=PAD_DIAMETER + 0.5))
    # ">REF" is a placeholder the gerber/export pipeline substitutes with
    # each instance's actual reference designator (e.g. "TP3") at export
    # time, even though this landpattern object is shared across instances.
    reference_designator = Silkscreen(Text(">REF", REF_DES_TEXT_SIZE, Anchor.C).at(0, REF_DES_OFFSET))


class TestPoint(NonPopulatedComponent):
    """A bare, unpopulated copper test point for probing a single net."""

    reference_designator_prefix = "TP"
    p1 = Port()
    landpattern = TestPointLandpattern()
    symbol = BoxSymbol()


Device: type[TestPoint] = TestPoint


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
