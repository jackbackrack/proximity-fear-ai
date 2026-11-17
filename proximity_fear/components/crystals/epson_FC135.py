# ruff: noqa: N999
"""Seiko Epson Q13FC13500004 (FC-135, 32.768 kHz, CL 12.5 pF) crystal unit.

Sources (spec note ``datasheets/Q13FC13500004.spec.md``):

- Epson "3.2 x 1.5 mm size 32.768 kHz Crystal Unit: FC-135", Document No
  FC-135_E_Ver2.0 (``datasheets/FC-135.pdf``, from epsondevice.com):
  "[7] Outline Drawing and Recommended Footprint" (p.4) for the body and land
  pattern.
- Epson part specification for Q13FC13500004xx (``datasheets/Q13FC13500004.pdf``,
  via LCSC C32346): sections 1-2 (p.1) for this ordering code's electrical
  limits, where it is tighter than the family document.

Land pattern: the p.4 recommended footprint, 1.0 mm (along the axis) x 1.8 mm
pads on 2.5 mm centres, built with the JITX ``MoldedTwoPin`` two-terminal
generator. The generator would size pads from IPC fillet tables; this subclass
supplies the datasheet's pad shape and centre spacing instead. The generator
lays the pads along Y (pad 1 at +Y). The p.4 shaded area between the pads
("Do not design any circuit patterns") is a top-layer keepout for pours, vias
and routes. Cross-checked against the LCSC/EasyEDA footprint for C32346
(``kicad_footprints/Q13FC13500004.kicad_mod``): same pads, rotated 90 degrees.

Facts with no JITX field: non-polar, the two terminals are both "X'tal" (p.4
pin table); terminal coating Au; MSL 1; no case/ground terminal.
"""

from typing import override

import jitx
from jitx.container import inline
from jitx.feature import KeepOut
from jitx.landpattern import PadMapping
from jitx.layerindex import LayerSet
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.shapes import Shape
from jitx.shapes.composites import rectangle
from jitx.symbol import SymbolMapping
from jitx.toleranced import Toleranced
from jitxlib.jlcpcb import LCSCPart
from jitxlib.landpatterns.grid_layout import GridPosition
from jitxlib.landpatterns.keepout import IntraKeepoutGenerator, KeepoutGenerator, KeepoutGeneratorMixin
from jitxlib.landpatterns.leads import SMDLead
from jitxlib.landpatterns.leads.protrusions import BigRectangularLeads
from jitxlib.landpatterns.twopin.molded import MoldedTwoPin
from jitxlib.symbols.crystal import CrystalSymbol

# Recommended footprint, FC-135_E_Ver2.0 "[7]" (p.4).
PAD_LENGTH = 1.0  # along the pad-to-pad axis
PAD_WIDTH = 1.8
PAD_PITCH = 2.5

# Outline drawing, same figure (p.4): terminals 0.65 long, 1.3 wide, 1.7 apart.
TERMINAL_LENGTH = 0.65
TERMINAL_WIDTH = 1.3
TERMINAL_GAP = 1.7


class ShadedAreaKeepout(KeepoutGenerator):
    """The interstitial region between the pads, kept free of pours, vias and routes on Top."""

    @override
    def make_keepout(self, target: KeepoutGeneratorMixin) -> KeepOut:
        between_pads = IntraKeepoutGenerator(horizontal=True).make_keepout(target)
        return KeepOut(between_pads.shape, layers=LayerSet(0), pour=True, via=True, route=True)


class FC135Landpattern(MoldedTwoPin):
    """``MoldedTwoPin`` with the FC-135 recommended pads in place of the IPC-computed ones."""

    def __init__(self) -> None:
        super().__init__(
            lead_span=Toleranced.exact(TERMINAL_GAP + 2 * TERMINAL_LENGTH),
            lead=SMDLead(
                length=Toleranced.exact(TERMINAL_LENGTH),
                width=Toleranced.exact(TERMINAL_WIDTH),
                lead_type=BigRectangularLeads,
            ),
        )
        self.keepout(ShadedAreaKeepout())

    # MoldedTwoPinBase computes both hooks from IPC fillet tables and its
    # ``_pad_shape`` sits ahead of the public ``pad_shape()`` setter in the MRO,
    # so the datasheet values go in through the two layout hooks instead.
    @override
    def _pad_shape(self, pos: GridPosition) -> Shape:
        # Generator frame: pads along Y, so the 1.8 mm pad width runs along X.
        return rectangle(PAD_WIDTH, PAD_LENGTH)

    @property
    @override
    def _lead_spacing(self) -> float:
        return PAD_PITCH


class Q13FC13500004(jitx.Component):
    """Epson FC-135 32.768 kHz crystal, CL 12.5 pF, +/-20 ppm, 3.2 x 1.5 mm."""

    mpn = "Q13FC13500004"
    manufacturer = "Seiko Epson"
    datasheet = "https://download.epsondevice.com/td/pdf/app/FC-135_en.pdf"
    reference_designator_prefix = "Y"
    lcsc = LCSCPart("C32346")

    # Electrical parameters for the load-capacitor calculation (SI units).
    frequency = 32.768e3
    """Nominal frequency, Hz (Q13FC13500004 spec p.1)."""
    load_capacitance = 12.5e-12
    """CL, F (Q13FC13500004 spec p.1)."""
    frequency_tolerance = 20e-6
    """+/- at +25 C, DL = 0.1 uW (Q13FC13500004 spec p.1)."""
    esr_max = 70e3
    """R1 max, ohms (Q13FC13500004 spec p.1)."""
    shunt_capacitance = 1.0e-12
    """C0 typ, F (Q13FC13500004 spec p.1)."""
    motional_capacitance = 3.4e-15
    """C1 typ, F (Q13FC13500004 spec p.1)."""
    max_drive_level = 0.5e-6
    """DL max, W (Q13FC13500004 spec p.1; the family document allows 1.0 uW only on request)."""

    XTAL = [Port(), Port()]
    """Terminals #1 and #2, both "X'tal" (FC-135_E_Ver2.0 p.4); non-polar."""

    landpattern = FC135Landpattern()
    symbol = CrystalSymbol()

    def __init__(self) -> None:
        self.pad_mapping = PadMapping(
            {
                self.XTAL[0]: self.landpattern.p[1],
                self.XTAL[1]: self.landpattern.p[2],
            }
        )
        self.symbol_mapping = SymbolMapping(
            {
                self.XTAL[0]: self.symbol.p[1],
                self.XTAL[1]: self.symbol.p[2],
            }
        )


Device: type[Q13FC13500004] = Q13FC13500004


class TestDesign(SampleDesign):
    """Single-crystal harness for ``jitx build``."""

    @inline
    class circuit(jitx.Circuit):
        xtal = Device()
