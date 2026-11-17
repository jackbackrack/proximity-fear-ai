"""Substrate: JLC04161H 4-layer buildup with the ARCHITECTURE.md plane assignment."""

from jitx.test import TestCase
from jitxlib.jlcpcb import JLC04161H_1080

from proximity_fear.substrate import ProximityFearSubstrate


class SubstrateTest(TestCase):
    def test_is_jlc04161h_1080_with_four_conductors(self) -> None:
        sub = ProximityFearSubstrate()
        self.assertIsInstance(sub, JLC04161H_1080)
        self.assertEqual(len(sub.stackup.conductors), 4)

    def test_inner_planes(self) -> None:
        # ARCHITECTURE.md Board: L2 3V3, L3 GND (conductor indices 1 and 2).
        sub = ProximityFearSubstrate()
        self.assertEqual(sub.power_plane_layer, 1)
        self.assertEqual(sub.ground_plane_layer, 2)
