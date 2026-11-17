"""Checks for the E73-2G4M08S1CX model against the Ebyte manual and the LCSC footprint."""

# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention

import re
from pathlib import Path

from jitx.feature import Courtyard
from jitx.inspect import visit
from jitx.landpattern import Pad, PadMapping
from jitx.net import Port
from jitx.sample import SampleSubstrate
from jitx.shapes.primitive import Polygon
from jitx.test import TestCase

from proximity_fear.components.mcus.ebyte_E73_2G4M08S1CX import E73_2G4M08S1CX

KICAD_MOD = Path(__file__).resolve().parents[3] / "kicad_footprints" / "E73-2G4M08S1CX.kicad_mod"
PAD_RE = re.compile(r"\(pad (\d+) smd rect \(at ([-\d.]+) ([-\d.]+)")


def kicad_pad_centres() -> dict[int, tuple[float, float]]:
    """Pad centres from the .kicad_mod, y negated into the JITX frame."""
    text = KICAD_MOD.read_text()
    return {int(n): (float(x), -float(y)) for n, x, y in PAD_RE.findall(text)}


class TestE73(TestCase):
    def test_pads_and_ports(self) -> None:
        SampleSubstrate()
        part = E73_2G4M08S1CX()
        # Manual p.7: "Pad quantity: 43".
        self.assertEqual(sum(1 for _ in visit(part.landpattern, Pad)), 43)
        self.assertEqual(sum(1 for _ in visit(part, Port)), 43)
        self.assertIsNone(part.value)
        self.assertEqual(part.mpn, "E73-2G4M08S1CX")
        # Body courtyard plus the IPEX keep-clear courtyard (PLAN comp-01).
        self.assertEqual(sum(1 for _ in visit(part.landpattern, Courtyard)), 2)

    def test_pad_positions_match_kicad(self) -> None:
        SampleSubstrate()
        part = E73_2G4M08S1CX()
        ref = kicad_pad_centres()
        self.assertEqual(len(ref), 43)
        for n, pad in part.landpattern.p.items():
            t = pad.transform
            assert t is not None
            x, y = t.translation
            rx, ry = ref[n]
            self.assertAlmostEqual(x, rx, delta=0.035, msg=f"pad {n} x")
            self.assertAlmostEqual(y, ry, delta=0.035, msg=f"pad {n} y")

    def test_pin_mapping(self) -> None:
        SampleSubstrate()
        part = E73_2G4M08S1CX()
        mapping = part.mappings[0]
        assert isinstance(mapping, PadMapping)
        p = part.landpattern.p
        # Manual pp.7-9 pin table.
        expected = {
            part.P1_11: 1, part.P0_28: 4, part.GND[0]: 5, part.XL1: 11, part.XL2: 13,
            part.VCC: 19, part.GND[1]: 21, part.VDDH: 23, part.GND[2]: 24, part.DCCH: 25,
            part.RESET: 26, part.VBUS: 27, part.D_N: 29, part.D_P: 31, part.SWDIO: 37,
            part.SWDCLK: 39, part.NFC1: 41, part.NFC2: 43,
        }  # fmt: skip
        for port, n in expected.items():
            self.assertIs(mapping[port], p[n])
        self.assertEqual(len(set(map(id, (mapping[port] for port in part.analog_inputs())))), 8)

    def test_pad_shapes(self) -> None:
        SampleSubstrate()
        part = E73_2G4M08S1CX()
        p = part.landpattern.p
        # .kicad_mod: edge pads 0.9 x 2.0, bottom pads 0.9 x 0.9.
        for n, size in ((1, (2.0, 0.9)), (11, (0.9, 2.0)), (12, (0.9, 0.9)), (28, (0.9, 0.9)), (43, (2.0, 0.9))):
            shape = p[n].shape
            assert isinstance(shape, Polygon)
            xs = [pt[0] for pt in shape.elements]
            ys = [pt[1] for pt in shape.elements]
            self.assertAlmostEqual(max(xs) - min(xs), size[0], places=3)
            self.assertAlmostEqual(max(ys) - min(ys), size[1], places=3)
