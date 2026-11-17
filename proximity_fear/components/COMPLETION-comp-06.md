## Task complete: comp-06 (VBUS surge TVS)

| Field | Value |
|-------|-------|
| What was built | `proximity_fear/components/protection/onsemi_SZSMF5_0AT1G.py` (`SOD123FLLandpattern`, `SZSMF5_0AT1G`, `TestDesign`); `tests/test_comp06_vbus_tvs.py` (4 tests); `datasheets/SZSMF5.0AT1G.pdf` + `.spec.md` (candidate comparison, hot-plug estimate, open items) |
| Build | `python scripts/check.py proximity_fear/ --build proximity_fear.components.protection.onsemi_SZSMF5_0AT1G.TestDesign` -> `build PASS` / `status: ok` (run before cir-02 removed `c_vcc`; pyright on the whole package now fails only at `designs/badge.py:362` `c_vcc`, owned by asm-01) |
| Primary source | onsemi SMF5.0AT1/D Rev. 2: p.1 pinout (1 cathode, 2 anode), p.3 SMF5.0A row, p.6 SOD-123FL outline + soldering footprint |

#### Component check

```
## Component check
Source: onsemi SMF5.0AT1/D Rev. 2 (May 2007); p.1 pins, p.3 electrical, p.6 package + footprint
        Source reached by: fetched from https://pccomponents.com/datasheets/ONSEMI-SMF5.pdf (onsemi PDF, publication SMF5.0AT1/D)
        Probes: onsemi.com/download/data-sheet/pdf/smf5.0at1-d.pdf -> HTML index page; LCSC datasheet links -> HTML; WebFetch -> index page only
        User-typed facts checked against it: "standoff >= 5.25 V" -> NOT met (VRWM 5.0 V, p.3), reported as deviation
        Disagreements found: standoff requirement vs available parts (spec note "Open questions")
References opened: component-guide.md row matched (via skill), pin-file row not matched
Identity: SZSMF5_0AT1G - mpn "SZSMF5.0AT1G"; manufacturer onsemi, prefix D, datasheet URL, LCSCPart C5299833
Pins: 2 ports / 2 pads (K pin 1, A pin 2)
Landpattern: hand-placed from p.6 soldering footprint: 0.91 x 1.22 lands, 3.28 mm centres (2.36 gap, 4.19 outer); body E 2.90 max, D 1.80 max for courtyard (+0.25 mm)
Library defaults: none (no generator); density level n/a
Value / BOM: .value unset - asserted None in tests/test_comp06_vbus_tvs.py::test_identity
No-field walk: VBR/VC/IR/Ppk, polarity band, IR only specified at 5.0 V - in docstring
Provenance: silkscreen offset 0.35 mm and courtyard excess 0.25 mm are labelled layout rules
Checks: pyright clean on the component; unittest 4 passed; build status: ok
Verdict: open items: VRWM 5.0 V < 5.25 V requirement (user decision); SZ ordering code confirmed only by the JLC record
```
