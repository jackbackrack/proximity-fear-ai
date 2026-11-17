## Component check — comp-05 TC2030NL
Source: Tag-Connect DWG TC2030-IDC-NL-FP rev B (12/05/19) sheet 1 "PCB TOP LAYER" (pad dia .0310", pitch .0500", NPTH dia .0390", .2000"/.0400" hole offsets, notes 1-4); sheet 2 plug end view .39" x .240"; pinout: Tag-Connect TC2030-CTX sheet "6-Pin TC2030 Footprint" table
        Source reached by: fetched from https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/2019/12/TC2030-IDC-NL-Datasheet-Rev-B.pdf and .../TC2030-CTX_1.pdf; saved datasheets/TC2030-IDC-NL.pdf, datasheets/TC2030-CTX.pdf
        Probes: n/a (a source was reached)
        User-typed facts checked against it: PLAN pin map 1 VCC, 2 SWDIO, 3 nRESET, 4 SWCLK, 5 GND, 6 SWO — confirmed by CTX table; "6 pads + 3 NPTH" — confirmed sheet 1
        Disagreements found: NONE
References opened: component-guide.md; parts-sourcing.md "Mechanical / Vendor-Defined Footprints"
Identity: TC2030NL — mpn unset (board feature; cable TC2030-IDC-NL is a tool, note 4 "DNL"), manufacturer Tag-Connect, refdes J, datasheet URL set; MechanicalComponent
Pins: 6 ports (VCC, nRESET, GND, swd.swdio, swd.swdclk, swd.swo) / 6 contact pads; 3 NPTH holes carry no port
Landpattern: hand-built from sheet 1 (vendor-defined): 6 x dia 0.787 SMD pads, no paste; 3 x dia 0.991 NPTH; route+via KeepOut 2.54 x 1.27 between pad centres (note 1); courtyard = plug face 9.906 x 6.096; opposite-side courtyard over holes +0.5 mm. Cross-checked pad-for-pad with KiCad lib Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical (y negated)
Library defaults: SMDPad/NPTHPad soldermask = substrate registration; Density level: not used
Value / BOM: .value unset and mpn None — tests/test_tagconnect_tc2030.py::test_not_on_bom
No-field walk: note 2 (0.508 mm track clearance to contact pads) — top-level rule, recorded in docstring; note 5 TC2030-CLIP
Provenance: opposite-side pin-tip margin 0.5 mm (design choice); plug face assumed centred on pad array (as drawn on sheet 2)
Checks: pyright clean (own files); unittest 6 passed; build status: ok via python scripts/check.py proximity_fear/ --build proximity_fear.components.connectors.tagconnect_TC2030.TestDesign
Verdict: complete
