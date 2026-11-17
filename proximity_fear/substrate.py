"""Board substrate: JLCPCB JLC04161H 4-layer 1.6 mm stackup with 1080 prepreg.

The same buildup socialbadge-ai rev 2 was fabricated on (``JLC04161H_1080`` from
``jitxlib-jlcpcb``): stackup, via set, JLCPCB fabrication rules and the 50 ohm
single-ended / 90 and 100 ohm differential routing structures all come from the
library class and are not restated here.

Inner-plane assignment (ARCHITECTURE.md ``Board``, as socialbadge-ai rev 2):
conductor index 1 (L2) carries the 3V3 plane and conductor index 2 (L3) the GND
plane, so the back side, where nearly all circuitry sits, references GND. The
planes themselves are pours authored by the top-level design; this class only
names which conductor each one lives on.
"""

import jitx
from jitx.sample import SampleBoard
from jitx.substrate import Substrate
from jitxlib.jlcpcb import JLC04161H_1080


class ProximityFearSubstrate(JLC04161H_1080):
    """JLC04161H_1080 with this board's inner-plane assignment."""

    power_plane_layer = 1
    """Conductor index of the 3V3 plane (L2)."""

    ground_plane_layer = 2
    """Conductor index of the GND plane (L3)."""


class TestDesign(jitx.Design):
    """Builds the substrate alone on the sample board outline."""

    substrate: Substrate = ProximityFearSubstrate()
    board = SampleBoard()

    circuit = jitx.Circuit()
