## Component check — comp-03 NFCAntennaPads
Source: Molex sales drawing "SD FOR RECTANGLE NFC ANTENNA", doc 1462360001 PSD rev B (2019/10/28), sheet 1: "SOLDER PADS" 2.00 x2 / 3.00 X2 / 0.50 gap; Table A row 1462360111 (A 23, B 27.3); title block 2-place tol +/-0.2
        Source reached by: fetched from https://datasheet.lcsc.com/datasheet/pdf/142092c32d49e6af8e30c666fbe783be.pdf (LCSC C17350773 page link); saved datasheets/1462360111.pdf (%PDF-, Molex title block)
        Probes: molex.com part page and pdm_docs/sd URLs: TLS connects then HTTP/2 INTERNAL_ERROR / 0 bytes (egress or bot-block); the LCSC copy is the Molex-authored drawing itself
        User-typed facts checked against it: "146236-0111, 23 x 27.3 mm, two solder tabs" — confirmed (Table A; two SOLDER PADS); "~3 uH" — not on the drawing (open question in spec note)
        Disagreements found: NONE
References opened: component-guide.md (any component task); parts-sourcing.md "Mechanical / Vendor-Defined Footprints"
Identity: NFCAntennaPads — mpn "1462360111" (as printed in Table A), manufacturer Molex, refdes AE, datasheet URL set; NonPopulatedComponent (hand-soldered after PCBA)
Pins: 2 ports (p1, p2) / 2 solder pads on the drawing; drawing names neither terminal, positional names used
Landpattern: hand-built (vendor-defined mechanical; no generator or vendor KiCad footprint): 2 SMD pads 2.00 x 3.50 mm at 2.50 pitch; tail pad 2.00 x 3.00, gap 0.50 from sheet 1; +0.50 length is a stated design choice for iron/fillet; no paste
Library defaults: SMDPad soldermask = substrate registration (JLC 0.0) — no source speaks; Density level: not used (no IPC generator)
Value / BOM: .value unset — tests/test_nfc_pads.py::test_identity asserts None
No-field walk: thickness 0.27 mm, adhesive 3M 9077, ferrite side — recorded in module/spec note
Provenance: pad length +0.5 mm (design rule: iron/fillet access), courtyard margin 0.25 mm
Checks: pyright clean (own files); unittest 5 passed; build status: ok via python scripts/check.py proximity_fear/ --build proximity_fear.components.antennas.nfc_pads.TestDesign
Verdict: complete
