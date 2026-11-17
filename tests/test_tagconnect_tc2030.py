"""TC2030-NL footprint against Tag-Connect drawing TC2030-IDC-NL-FP rev B, sheet 1.

Expected values are the drawing's inch dimensions converted here, not the
module's constants.
"""

from jitx.feature import Courtyard, Cutout, KeepOut, Paste, Soldermask
from jitx.inspect import extract, visit
from jitx.landpattern import Pad
from jitx.layerindex import Side
from jitx.shapes.primitive import Circle
from jitx.test import TestCase
from jitxlib.landpatterns.pads import NPTHPad

from proximity_fear.components.connectors.tagconnect_TC2030 import TC2030NL
from proximity_fear.substrate import ProximityFearSubstrate

IN = 25.4
# Pin -> (x, y) in mm: odd row below, even above, pin 1 bottom left; 0.050" grid.
EXPECTED_PADS = {
    1: (-0.050 * IN, -0.025 * IN),
    2: (-0.050 * IN, 0.025 * IN),
    3: (0.0, -0.025 * IN),
    4: (0.0, 0.025 * IN),
    5: (0.050 * IN, -0.025 * IN),
    6: (0.050 * IN, 0.025 * IN),
}
# Left hole 0.050" left of the pin 1/2 column; right holes 0.200" further, +/-0.040".
EXPECTED_HOLES = {
    (round(-0.100 * IN, 3), 0.0),
    (round(0.100 * IN, 3), round(0.040 * IN, 3)),
    (round(0.100 * IN, 3), round(-0.040 * IN, 3)),
}


def _xy(pad: Pad) -> tuple[float, float]:
    placement = pad.transform
    if placement is None:
        raise AssertionError("pad has no placement")
    x, y = placement.translation
    return (round(x, 3), round(y, 3))


class TC2030NLTest(TestCase):
    def setUp(self) -> None:
        ProximityFearSubstrate()
        self.part = TC2030NL()

    def test_pad_count_and_positions(self) -> None:
        lp = self.part.landpattern
        self.assertEqual(sum(1 for _ in visit(lp, Pad)), 6)
        for pin, (x, y) in EXPECTED_PADS.items():
            self.assertEqual(_xy(lp.p[pin]), (round(x, 3), round(y, 3)), f"pin {pin}")

    def test_pads_are_0787_mm_circles_without_paste(self) -> None:
        for pad in self.part.landpattern.p.values():
            shape = pad.shape
            self.assertIsInstance(shape, Circle)
            assert isinstance(shape, Circle)
            self.assertAlmostEqual(shape.diameter, 0.031 * IN, places=2)
            self.assertEqual(list(extract(pad, Paste)), [])
            self.assertEqual(len(list(extract(pad, Soldermask))), 1)
            self.assertEqual(list(extract(pad, Cutout)), [])

    def test_three_non_plated_alignment_holes(self) -> None:
        holes = list(extract(self.part.landpattern, NPTHPad))
        self.assertEqual(len(holes), 3)
        found = set()
        for hole in holes:
            cut = hole.cutout.shape
            self.assertIsInstance(cut, Circle)
            assert isinstance(cut, Circle)
            self.assertAlmostEqual(cut.diameter, 0.039 * IN, places=2)
            placement = hole.transform
            assert placement is not None
            x, y = placement.translation
            found.add((round(x, 3), round(y, 3)))
        self.assertEqual(found, EXPECTED_HOLES)

    def test_keepout_between_pads(self) -> None:
        keepouts = list(extract(self.part.landpattern, KeepOut))
        self.assertEqual(len(keepouts), 1)
        self.assertTrue(keepouts[0].route and keepouts[0].via)

    def test_courtyards(self) -> None:
        # Contact side: the plug face, 0.39" x 0.240" (sheet 2), centred on the array.
        # Far side: one circle per alignment hole, the 0.039" hole grown by 0.5 mm each way.
        top: list[Courtyard] = []
        bottom: list[Courtyard] = []
        for _, courtyard in visit(self.part.landpattern, Courtyard):
            (bottom if courtyard.side == Side.Bottom else top).append(courtyard)
        self.assertEqual(len(top), 1)
        top_bounds = top[0].shape.to_shapely().bounds
        self.assertAlmostEqual(top_bounds[2] - top_bounds[0], 0.39 * IN, places=2)
        self.assertAlmostEqual(top_bounds[3] - top_bounds[1], 0.240 * IN, places=2)
        self.assertEqual(len(bottom), 3)
        centres = set()
        for courtyard in bottom:
            # Circles are polygonised for shapely; allow the facet error.
            g = courtyard.shape.to_shapely()
            minx, miny, maxx, maxy = g.bounds
            self.assertAlmostEqual(maxx - minx, 0.039 * IN + 1.0, delta=0.01)
            self.assertAlmostEqual(maxy - miny, 0.039 * IN + 1.0, delta=0.01)
            centres.add((round(g.centroid.x, 3), round(g.centroid.y, 3)))
        self.assertEqual(centres, EXPECTED_HOLES)

    def test_pin_map(self) -> None:
        part = self.part
        mapping = part.mappings[0]
        lp = part.landpattern
        swo = part.swd.swo
        assert swo is not None
        expected = {
            part.VCC: 1,
            part.swd.swdio: 2,
            part.nRESET: 3,
            part.swd.swdclk: 4,
            part.GND: 5,
            swo: 6,
        }
        for port, pin in expected.items():
            self.assertIs(mapping[port], lp.p[pin])

    def test_not_on_bom(self) -> None:
        self.assertFalse(self.part.in_bom)
        self.assertFalse(self.part.soldered)
        self.assertIsNone(self.part.mpn)
        self.assertIsNone(self.part.value)
