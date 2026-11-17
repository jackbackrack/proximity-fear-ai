"""NFC antenna pads against Molex drawing 1462360001 PSD rev B ("SOLDER PADS")."""

from jitx.feature import Paste
from jitx.inspect import extract, visit
from jitx.landpattern import Pad, PadShape
from jitx.test import TestCase

from proximity_fear.components.antennas.nfc_pads import NFCAntennaPads
from proximity_fear.substrate import ProximityFearSubstrate

# Drawing: tail pads 2.00 wide x 3.00 long, 0.50 gap.
TAIL_WIDTH = 2.00
TAIL_LENGTH = 3.00
TAIL_GAP = 0.50


def _bounds(pad: Pad) -> tuple[float, float, float, float]:
    placement = pad.transform
    if placement is None:
        raise AssertionError("pad has no placement")
    x, y = placement.translation
    shape = pad.shape
    if isinstance(shape, PadShape):
        shape = shape.shape
    minx, miny, maxx, maxy = shape.to_shapely().bounds
    return (round(minx + x, 3), round(miny + y, 3), round(maxx + x, 3), round(maxy + y, 3))


class NFCAntennaPadsTest(TestCase):
    def setUp(self) -> None:
        ProximityFearSubstrate()
        self.part = NFCAntennaPads()

    def test_two_pads(self) -> None:
        self.assertEqual(sum(1 for _ in visit(self.part.landpattern, Pad)), 2)

    def test_pitch_and_size_accept_the_tail(self) -> None:
        lp = self.part.landpattern
        b1 = _bounds(lp.p[1])
        b2 = _bounds(lp.p[2])
        # Same gap and width as the tail, so the tail laps straight on.
        self.assertAlmostEqual(b2[0] - b1[2], TAIL_GAP, places=3)
        self.assertAlmostEqual(b1[2] - b1[0], TAIL_WIDTH, places=3)
        # Longer than the tail pad, leaving iron / fillet access.
        self.assertGreater(b1[3] - b1[1], TAIL_LENGTH)

    def test_no_paste(self) -> None:
        for pad in self.part.landpattern.p.values():
            self.assertEqual(list(extract(pad, Paste)), [])

    def test_identity(self) -> None:
        self.assertEqual(self.part.mpn, "1462360111")
        self.assertEqual(self.part.manufacturer, "Molex")
        self.assertFalse(self.part.in_bom)
        self.assertIsNone(self.part.value)

    def test_pin_map(self) -> None:
        mapping = self.part.mappings[0]
        self.assertIs(mapping[self.part.p1], self.part.landpattern.p[1])
        self.assertIs(mapping[self.part.p2], self.part.landpattern.p[2])
