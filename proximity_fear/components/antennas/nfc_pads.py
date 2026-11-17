"""Solder pads for the hand-attached Molex 1462360111 NFC antenna.

The antenna is a 23 x 27.3 mm ferrite-backed flex loop (Molex 146236 series,
material P/N 1462360111) stuck inside the back case and soldered to these two
pads after PCBA, either by lapping its flex tail onto them or with two short
28 AWG leads. It is not assembled by JLCPCB, so the component is
``NonPopulatedComponent`` (pads on the board, not on the assembly BOM) while
still carrying the antenna's MPN for the hand-assembly list.

Geometry source: Molex sales drawing "SD FOR RECTANGLE NFC ANTENNA", document
1462360001 PSD rev B (2019/10/28), Table A row 1462360111 (A 23, B 27.3) and the
"NFC ANTENNA WITH FERRITE" view, saved as ``datasheets/1462360111.pdf``:

- two "SOLDER PADS" on the flex tail, each 2.00 wide ("2.00 x2") by 3.00 long
  ("3.00 X2"), with a 0.50 gap between them, so 2.50 centre to centre;
- general tolerance for 2-place dimensions +/-0.2.

Land design (vendor-defined mechanical footprint, no vendor KiCad footprint):

- pitch 2.50 mm, matching the tail, so the tail can be lap-soldered directly;
- pad width 2.00 mm, equal to the tail pads;
- pad length 3.50 mm: the tail's 3.00 mm plus 0.50 mm exposed beyond the tail
  end for the iron tip and the solder fillet; a 28 AWG lead (0.32 mm conductor)
  fits the same land with room to spare;
- no solder paste: the pads are soldered by hand after reflow, and a reflowed
  solder bump would tilt the lapped flex.

The drawing does not name or polarise the two terminals; the loop is symmetric,
so the ports are positional ``p1``/``p2``.
"""

import jitx
from jitx.anchor import Anchor
from jitx.component import NonPopulatedComponent
from jitx.container import inline
from jitx.feature import Courtyard, Silkscreen
from jitx.landpattern import Landpattern, PadMapping
from jitx.net import Port
from jitx.sample import SampleBoard
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Text
from jitxlib.landpatterns.pads import SMDPad
from jitxlib.symbols.inductor import InductorSymbol

from ...substrate import ProximityFearSubstrate

TAIL_PAD_WIDTH = 2.00  # drawing "2.00 x2"
TAIL_PAD_LENGTH = 3.00  # drawing "3.00 X2"
TAIL_PAD_GAP = 0.50  # drawing "0.50"
PAD_PITCH = TAIL_PAD_WIDTH + TAIL_PAD_GAP
PAD_LENGTH = TAIL_PAD_LENGTH + 0.50  # iron / fillet access beyond the tail end
COURTYARD_MARGIN = 0.25


class NFCAntennaPadsLandpattern(Landpattern):
    """Two 2.0 x 3.5 mm hand-solder pads at 2.5 mm pitch, long axis along y."""

    name = "Molex_1462360111_solder_pads"

    p: dict[int, SMDPad]

    def __init__(self) -> None:
        self.p = {
            1: SMDPad(rectangle(TAIL_PAD_WIDTH, PAD_LENGTH), paste=None).at(-PAD_PITCH / 2, 0.0),
            2: SMDPad(rectangle(TAIL_PAD_WIDTH, PAD_LENGTH), paste=None).at(PAD_PITCH / 2, 0.0),
        }
        self.courtyard = Courtyard(
            rectangle(PAD_PITCH + TAIL_PAD_WIDTH + 2 * COURTYARD_MARGIN, PAD_LENGTH + 2 * COURTYARD_MARGIN)
        )
        self.reference_designator = Silkscreen(Text(">REF", 1.0, Anchor.C).at(0.0, PAD_LENGTH / 2 + 1.0))


class NFCAntennaPads(NonPopulatedComponent):
    """Pads for the Molex 1462360111 ferrite flex NFC antenna (hand-soldered)."""

    mpn = "1462360111"
    manufacturer = "Molex"
    reference_designator_prefix = "AE"
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/142092c32d49e6af8e30c666fbe783be.pdf"

    p1 = Port()
    """Antenna loop terminal at pad 1."""
    p2 = Port()
    """Antenna loop terminal at pad 2."""

    def __init__(self) -> None:
        self.landpattern = NFCAntennaPadsLandpattern()
        self.mappings = [PadMapping({self.p1: self.landpattern.p[1], self.p2: self.landpattern.p[2]})]
        self.symbol = InductorSymbol()


Device: type[NFCAntennaPads] = NFCAntennaPads


class TestDesign(jitx.Design):
    """The antenna pads alone on the board substrate."""

    substrate = ProximityFearSubstrate()
    board = SampleBoard()

    @inline
    class circuit(jitx.Circuit):
        ant = NFCAntennaPads()
