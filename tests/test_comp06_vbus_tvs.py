"""comp-06 VBUS surge TVS model: pads, ports, polarity and land geometry.

Expected values come from onsemi SMF5.0AT1/D Rev. 2 (``datasheets/SZSMF5.0AT1G.pdf``):
p.1 pin 1 = cathode, pin 2 = anode; p.6 SOD-123FL soldering footprint 0.91 x 1.22 mm
lands, 2.36 mm inner gap, 4.19 mm outer extent; body E <= 2.90, D <= 1.80.
"""

from jitx.feature import Courtyard
from jitx.inspect import extract, visit
from jitx.landpattern import Pad, PadMapping, PadShape
from jitx.net import Port
from jitx.sample import SampleSubstrate
from jitx.test import TestCase

from proximity_fear.components.protection.onsemi_SZSMF5_0AT1G import SZSMF5_0AT1G


def _pad(part: SZSMF5_0AT1G, port: Port) -> Pad:
    mapping = next(iter(extract(part, PadMapping)))
    pad = mapping[port]
    if not isinstance(pad, Pad):
        raise AssertionError("port maps to several pads")
    return pad


class VbusTvsTest(TestCase):
    def setUp(self) -> None:
        SampleSubstrate()
        self.d = SZSMF5_0AT1G()

    def test_identity(self) -> None:
        self.assertEqual(self.d.mpn, "SZSMF5.0AT1G")
        self.assertEqual(self.d.manufacturer, "onsemi")
        self.assertEqual(self.d.reference_designator_prefix, "D")
        self.assertIsNone(self.d.value)

    def test_counts(self) -> None:
        self.assertEqual(sum(1 for _ in visit(self.d, Pad)), 2)
        self.assertEqual(len(list(extract(self.d, Port))), 2)

    def test_lands(self) -> None:
        k, a = _pad(self.d, self.d.K), _pad(self.d, self.d.A)
        self.assertIs(k, self.d.landpattern.p[1])  # pin 1 = cathode (p.1)
        self.assertIs(a, self.d.landpattern.p[2])
        for pad in (k, a):
            shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            minx, miny, maxx, maxy = shape.to_shapely().g.bounds
            self.assertAlmostEqual(maxx - minx, 0.91, places=3)
            self.assertAlmostEqual(maxy - miny, 1.22, places=3)
        assert k.transform is not None and a.transform is not None
        kx, ky = k.transform.translation
        ax, ay = a.transform.translation
        self.assertLess(kx, ax)
        self.assertAlmostEqual(ky, 0.0)
        self.assertAlmostEqual(ay, 0.0)
        self.assertAlmostEqual((ax - kx) - 0.91, 2.36, delta=0.02)  # inner gap
        self.assertAlmostEqual((ax - kx) + 0.91, 4.19, places=3)  # outer extent

    def test_courtyard_covers_body(self) -> None:
        cy = next(iter(extract(self.d.landpattern, Courtyard)))
        minx, miny, maxx, maxy = cy.shape.to_shapely().g.bounds
        self.assertGreaterEqual(maxx - minx, 4.19)
        self.assertGreaterEqual(maxy - miny, 1.80)
