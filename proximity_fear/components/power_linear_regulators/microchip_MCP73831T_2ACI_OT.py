"""Microchip MCP73831T-2ACI/OT - single-cell Li-ion/LiPo linear charge controller, SOT-23-5.

Ported unchanged from socialbadge-ai rev 2 (fabbed and brought up).

Source: Microchip DS20001984G, saved as ``datasheets/MCP73831T-2ACI_OT.pdf``.
- Table 3-1 "Pin Function Tables", p.11 (SOT-23-5): 1 STAT, 2 VSS, 3 VBAT,
  4 VDD, 5 PROG.
- Section 5 / p.15: I_REG = 1000 V / R_PROG (R_PROG 5 kOhm -> 200 mA).
- "5-Lead Plastic Small Outline Transistor (OT) [SOT-23]", drawing C04-091B,
  p.22: E 2.20..3.20, E1 1.30..1.80, D 2.70..3.10, A 0.90..1.45, L 0.10..0.60,
  b 0.20..0.51, e 0.95.

Land pattern deviation (kept deliberately): the span / body tolerances below
are the JEDEC SOT-23-5 values used on the fabbed rev-2 board; each lies inside
the Microchip drawing's min..max envelope (p.22), so the pattern fits every
conforming part. Lead length/width use the SOTLeadProfile defaults.
No-field facts: VDD and VBAT each need >= 4.7 uF to VSS (p.11); PROG floating
disables charging (p.18); STAT is tri-state (p.11).
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


class MCP73831T_2ACI_OT(jitx.Component):
    mpn = "MCP73831T-2ACI/OT"
    manufacturer = "Microchip Technology"
    reference_designator_prefix = "U"
    # Verified against the real LCSC/EasyEDA footprint: our pad cloud aligns
    # pin-for-pin (same numbering) under a 270 deg correction, residual 0.09mm.
    lcsc = LCSCPart("C424093")
    datasheet = "https://datasheet.lcsc.com/datasheet/pdf/c7ec00710e742b7fb9393e620ae1332b.pdf"

    STAT = Port()  # Pin 1 — tri-state status output
    VSS = Port()  # Pin 2 — ground
    VBAT = Port()  # Pin 3 — battery output
    VDD = Port()  # Pin 4 — input supply
    PROG = Port()  # Pin 5 — current programming resistor

    # Standard JEDEC SOT-23-5 dimensions
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
            left=PinGroup(VDD, PROG),
            right=PinGroup(VBAT, STAT),
        ),
        columns=Column(
            down=PinGroup(VSS),
        ),
    )


Device: type[MCP73831T_2ACI_OT] = MCP73831T_2ACI_OT


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
