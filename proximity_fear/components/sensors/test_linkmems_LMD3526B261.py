# ruff: noqa: N999
"""Datasheet checks for the LMD3526B261-OFA03 model.

Expected values come from LinkMems spec M196 v1.0: p.7 "Appearance Drawing"
(pin table, bottom-view offsets) and p.8 "Recommended Solder Pad Layout".
"""

import math

from jitx.feature import Cutout, KeepOut
from jitx.inspect import visit
from jitx.landpattern import Pad
from jitx.sample import SampleSubstrate
from jitx.shapes import Shape
from jitx.shapes.primitive import Circle
from jitx.test import TestCase
from shapely.geometry.base import BaseGeometry

from proximity_fear.components.sensors.linkmems_LMD3526B261 import LMD3526B261_OFA03


def pad_geometry(pad: Pad) -> BaseGeometry:
    """The pad's copper outline as shapely geometry (narrows ``Shape | PadShape``)."""
    shape = pad.shape
    if not isinstance(shape, Shape):
        raise TypeError(f"pad shape is a {shape!r}, not a plain Shape")
    return shape.to_shapely().g


class TestLMD3526B261(TestCase):
    def test_metadata(self) -> None:
        SampleSubstrate()
        mic = LMD3526B261_OFA03()
        self.assertEqual(mic.mpn, "LMD3526B261-OFA03")
        self.assertEqual(mic.manufacturer, "LinkMems")
        self.assertIsNone(mic.value)

    def test_pads(self) -> None:
        SampleSubstrate()
        mic = LMD3526B261_OFA03()
        pads = list(visit(mic.landpattern, Pad))
        # Five pins on the p.7 pin table: four signal pads plus the ground ring.
        self.assertEqual(len(pads), 5)

        centres: dict[int, tuple[float, float]] = {}
        for number, pad in mic.landpattern.p.items():
            transform = pad.transform
            if transform is None:
                raise AssertionError(f"pad {number} has no placement")
            x, y = transform.translation
            centres[number] = (x, y)

        # Top view: pin 1 upper left; 1.67 column pitch, 0.82 row pitch (p.8).
        self.assertAlmostEqual(centres[4][0] - centres[1][0], 1.67)
        self.assertAlmostEqual(centres[1][1] - centres[2][1], 0.82)
        self.assertLess(centres[1][0], 0.0)
        self.assertAlmostEqual(centres[2][1], centres[3][1])
        # Port centre 1.25 below the lower row and 1.04 above the body edge (p.7).
        self.assertAlmostEqual(centres[2][1] - centres[5][1], 1.25)
        self.assertAlmostEqual(centres[5][1] - (-3.50 / 2), 1.04)
        self.assertAlmostEqual(centres[5][0], 0.0)

        x0, y0, x1, y1 = pad_geometry(mic.landpattern.p[1]).bounds
        self.assertAlmostEqual(x1 - x0, 0.73)
        self.assertAlmostEqual(y1 - y0, 0.52)

        ring = pad_geometry(mic.landpattern.p[5])
        rx0, _, rx1, _ = ring.bounds
        self.assertAlmostEqual(rx1 - rx0, 1.62, places=3)
        inner_area = ring.convex_hull.area - ring.area
        self.assertAlmostEqual(math.sqrt(inner_area / math.pi) * 2, 1.03, places=2)

    def test_port_hole(self) -> None:
        SampleSubstrate()
        mic = LMD3526B261_OFA03()
        cutouts = list(visit(mic.landpattern, Cutout))
        self.assertEqual(len(cutouts), 1)
        hole = cutouts[0][1].shape
        if not isinstance(hole, Circle):
            raise TypeError(f"port hole is not a circle: {hole!r}")
        self.assertAlmostEqual(hole.diameter, 0.50)
        # Larger than the package port plus tolerance (p.7, Ø0.32 ± 0.05) and
        # inside the ring pad's inner diameter (p.8, Ø1.03).
        self.assertGreater(hole.diameter, 0.32 + 0.05)
        self.assertLess(hole.diameter, 1.03)

        keepouts = [k for _, k in visit(mic.landpattern, KeepOut)]
        self.assertEqual(len(keepouts), 1)
        self.assertTrue(keepouts[0].pour and keepouts[0].via and keepouts[0].route)
