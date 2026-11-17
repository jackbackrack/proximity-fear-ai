# comp-01 — Ebyte E73-2G4M08S1CX component check

## Component check
Source: Ebyte E73-2G4M08S1CX User Manual v1.2 (datasheets/E73-2G4M08S1CX.pdf): p.5 limits/supply; p.6 crystal, IPEX 50 ohm;
        p.7 drawing (43 pads, 1.27 pitch, 2.06/2.60/3.97/2.1/2.69/4.505/4.605 dims, bottom pads 0.80 sq) rendered and read visually;
        pp.7-9 pin table; p.11 internal schematic (rendered) + layout guidance. nRF52840 PS pin table
        (datasheets/sourcing/nRF52840_PS-pins-aQFN73.txt). LCSC channel record datasheets/sourcing/E73-2G4M08S1CX-lcsc.txt.
        Source reached by: local datasheets/E73-2G4M08S1CX.pdf; PS via docs.nordicsemi.com pin page (PDF gated: HTML served)
        Probes: nRF52840 PS PDF (docs-be / infocenter / docs.nordicsemi.com attach URLs returned HTML); power/ref-circuit pages >10 MB, not read
        User-typed facts checked: 43 pads 1.27 mm 13x18 (confirmed p.7); XL1 11, XL2 13, VCC 19, VDDH 23, DCCH 25, RESET 26, VBUS 27,
        D- 29, D+ 31, SWDIO 37, SWDCLK 39, NFC1 41, NFC2 43 (confirmed p.8-9). "43 castellated" is NOT confirmed: 15 are bottom pads.
        Disagreements found: 15 of 43 pads are under-body bottom pads, not castellations (p.7); Ebyte LF marking omits P1.11/P0.28/P1.02 (PS wins).
References opened: component task -> component-guide.md
Identity: E73_2G4M08S1CX — mpn "E73-2G4M08S1CX"; manufacturer, refdes U, datasheet URL, LCSCPart C2764963 set
Pins: 43 ports / 43 pads — 3 GND, VCC, VDDH, DCCH, VBUS present; names from pin table (AIx named by GPIO per PS)
Landpattern: LCSC .kicad_mod import (RF module, no generator) — 28 edge pads 2.0x0.9, 15 bottom pads 0.9x0.9; centres on Ebyte 1.27 grid,
        max 0.03 mm from .kicad_mod (pad 3); body 13.0x18.0x3.0 +/-0.1 (p.7)
Library defaults: none relied on; Density level: n/a (no generator)
Value / BOM: .value unset — asserted in test
No-field walk: height 3.0 mm, supply 1.7-5.5 V, external LFXO, SWDIO mislabel, under-module routing guidance — in docstring
Provenance: IPEX keep-clear courtyard 6x3 mm beyond the edge is a design choice (PLAN comp-01), labeled in code
Checks: pyright clean on proximity_fear/components/mcus/; unittest 4 passed; build status: ok via jitx build proximity_fear.components.mcus.ebyte_E73_2G4M08S1CX.TestDesign
Verdict: complete (project-wide pyright FAIL is in other tasks' files)
