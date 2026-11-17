# ruff: noqa: N999
"""Datasheet checks for the Epson Q13FC13500004 model.

Expected values come from Epson FC-135_E_Ver2.0 "[7] Outline Drawing and
Recommended Footprint" (p.4) and the Q13FC13500004 part specification (p.1).
"""

from jitx.feature import KeepOut
from jitx.inspect import visit
from jitx.landpattern import Pad
from jitx.sample import SampleSubstrate
from jitx.shapes import Shape
from jitx.test import TestCase
from shapely.geometry.base import BaseGeometry

from proximity_fear.components.crystals.epson_FC135 import Q13FC13500004


def pad_geometry(pad: Pad) -> BaseGeometry:
    """The pad's copper outline as shapely geometry (narrows ``Shape | PadShape``)."""
    shape = pad.shape
    if not isinstance(shape, Shape):
        raise TypeError(f"pad shape is a {shape!r}, not a plain Shape")
    return shape.to_shapely().g


class TestQ13FC13500004(TestCase):
    def test_metadata(self) -> None:
        SampleSubstrate()
        xtal = Q13FC13500004()
        self.assertEqual(xtal.mpn, "Q13FC13500004")
        self.assertEqual(xtal.manufacturer, "Seiko Epson")
        self.assertIsNone(xtal.value)
        self.assertAlmostEqual(xtal.load_capacitance, 12.5e-12)
        self.assertAlmostEqual(xtal.esr_max, 70e3)
        self.assertAlmostEqual(xtal.max_drive_level, 0.5e-6)
        self.assertAlmostEqual(xtal.frequency_tolerance, 20e-6)

    def test_recommended_footprint(self) -> None:
        SampleSubstrate()
        xtal = Q13FC13500004()
        pads = list(visit(xtal.landpattern, Pad))
        self.assertEqual(len(pads), 2)

        centres: list[tuple[float, float]] = []
        for trace, pad in pads:
            transform = pad.transform
            if transform is None or trace.transform is None:
                raise AssertionError("pad has no placement")
            # Pad centre in the landpattern frame: trace transform composed with the pad's own.
            centres.append((trace.transform * transform).translation)
            x0, y0, x1, y1 = pad_geometry(pad).bounds
            # 1.0 mm along the pad-to-pad axis (Y here), 1.8 mm across (p.4).
            self.assertAlmostEqual(x1 - x0, 1.8)
            self.assertAlmostEqual(y1 - y0, 1.0)
        # 2.5 mm pad centre spacing (p.4).
        self.assertAlmostEqual(abs(centres[0][1] - centres[1][1]), 2.5)
        self.assertAlmostEqual(centres[0][0], centres[1][0])

    def test_shaded_area_keepout(self) -> None:
        SampleSubstrate()
        xtal = Q13FC13500004()
        keepouts = [k for _, k in visit(xtal.landpattern, KeepOut)]
        self.assertEqual(len(keepouts), 1)
        keepout = keepouts[0]
        self.assertTrue(keepout.pour and keepout.via and keepout.route)
        _, y0, _, y1 = keepout.shape.to_shapely().g.bounds
        # Between the pads' inner edges: at most 2.5 - 1.0 = 1.5 mm (p.4).
        self.assertLessEqual(y1 - y0, 1.5 + 1e-9)
        self.assertGreater(y1 - y0, 1.0)
