"""Diodes Inc. AP2112K-3.3TRG1 - 600 mA 3.3 V CMOS LDO with enable, SOT25.

Ported unchanged from socialbadge-ai rev 2 (fabbed and brought up).

Source: Diodes DS39724 Rev. 2-2, saved as ``datasheets/AP2112K-3.3TRG1.pdf``.
- "Pin Assignments" p.1 and "Pin Descriptions" p.2 (SOT25): 1 VIN, 2 GND,
  3 EN, 4 NC, 5 VOUT.
- "Package Outline Dimensions" SOT25, p.14: B (body width) 1.50..1.70,
  C (lead span) 2.70..3.00, H (body length) 2.90..3.10, K 1.00..1.30,
  L 0.35..0.55, D 0.95; "Suggested Pad Layout" Z 3.20, G 1.60, X 0.55, Y 0.80.

Land pattern deviation (kept deliberately): span 2.60..3.00 and length
2.80..3.04 are the JEDEC values used on the fabbed rev-2 board, not Diodes'
C / H rows; the difference is <= 0.1 mm and the generated lands cover the
Diodes suggested Z/G envelope.
No-field facts: CIN = COUT = 1 uF X5R/X7R (p.2 Note 4); EN high = on (p.2).
"""

# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention

import jitx
from jitx.circuit import Circuit
from jitx.container import inline
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.toleranced import Toleranced
from jitxlib.jlcpcb import LCSCPart
from jitxlib.landpatterns.generators.sot import SOT23_5, SOTLeadProfile
from jitxlib.landpatterns.ipc import DensityLevel
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.symbols.box import BoxSymbol, Column, PinGroup, Row


class AP2112K_33TRG1(jitx.Component):
    mpn = "AP2112K-3.3TRG1"
    manufacturer = "Diodes Incorporated"
    reference_designator_prefix = "U"
    # Verified against the real LCSC/EasyEDA footprint: our pad cloud aligns
    # pin-for-pin (same numbering) under a 270 deg correction, residual 0.08mm.
    lcsc = LCSCPart("C51118")
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/5b29baebdc4332b382a530ff21092301.pdf"

    VIN = Port()  # Pin 1
    GND = Port()  # Pin 2
    EN = Port()  # Pin 3
    NC = Port()  # Pin 4 -- no connection (marked in __init__)
    VOUT = Port()  # Pin 5

    landpattern = (
        SOT23_5()
        .lead_profile(
            SOTLeadProfile(
                span=Toleranced.min_max(2.60, 3.00),
            )
        )
        .package_body(
            RectanglePackage(
                width=Toleranced.min_max(1.50, 1.70),
                length=Toleranced.min_max(2.80, 3.04),
                height=Toleranced.min_max(1.00, 1.30),
            )
        )
        .density_level(DensityLevel.B)
    )

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(VIN, EN),
            right=PinGroup(VOUT, NC),
        ),
        columns=Column(
            down=PinGroup(GND),
        ),
    )

    def __init__(self) -> None:
        self.NC.no_connect()


Device: type[AP2112K_33TRG1] = AP2112K_33TRG1


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
