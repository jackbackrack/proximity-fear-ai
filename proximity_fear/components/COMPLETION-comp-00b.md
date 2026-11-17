## Task complete: comp-00b (port front-side models: LED, IR TX/RX, ToF + VL53L4CX)

| Field | Value |
|-------|-------|
| What was built | `proximity_fear/components/leds/worldsemi_WS2812C_2020.py` (`WS2812C_2020_V6`); `proximity_fear/components/leds/everlight_IR11_21C.py` (`IR11_21C_TR8`); `proximity_fear/components/sensors/everlight_IRM_H638T.py` (`IRM_H638T_TR2`); `proximity_fear/components/sensors/st_VL53L4CD.py` (`LGA12Pad`, `LGA12Landpattern`, shared pin model `VL53L4LGA12`, `VL53L4CDV0DH_1`); `proximity_fear/components/sensors/st_VL53L4CX.py` (`VL53L4CXV0DH_1(VL53L4LGA12)`); each module has its own `TestDesign`; `proximity_fear/components/leds/__init__.py` (new, empty); `tests/test_comp00b_components.py` (6 tests); `kicad_footprints/C55160508.kicad_mod`, `C19269752.kicad_mod`, `C91447.kicad_mod`; `datasheets/{WS2812C-2020-V6_W,IR11-21C_TR8,IRM-H638T_TR2,VL53L4CXV0DH_1,VL53L4CDV0DH_1}.pdf` + `.spec.md`. VL53L0X not ported. |
| Build | `python scripts/check.py proximity_fear/ --build proximity_fear.components.sensors.st_VL53L4CX.TestDesign` → `build          PASS   proximity_fear.components.sensors.st_VL53L4CX.TestDesign` / `status: ok`. Other TestDesigns built one after another with `jitx build`: WS2812C_2020 `status: ok`, IR11_21C `status: ok`, IRM_H638T `status: ok`, VL53L4CD `status: ok` |
| Primary source | `datasheets/VL53L4CXV0DH_1.spec.md` → ST DS13805 Rev 3 pp.3-5, 8, 10, 17-19, 22 (Fig. 17 PWB solder pattern), 24 (Fig. 19 exclusion cones), 26 (Table 16 FoV), 33 (Table 19 order codes); `datasheets/VL53L4CDV0DH_1.spec.md` → ST DS13812 Rev 5 pp.3-5, 9, 16-17, 21 (Fig. 17), 25, 32; `datasheets/WS2812C-2020-V6_W.spec.md` → Worldsemi WS2812C-2020-V6/W pp.2-3 (Top View, PCB Solder Pad, pin table); `datasheets/IR11-21C_TR8.spec.md` → Everlight DIR-0000945 Rev 4 pp.2-3; `datasheets/IRM-H638T_TR2.spec.md` → Everlight DMO-0000008 Rev 3 pp.1-3, 6. ST PDFs fetched from LCSC (C3178292 / C3178291 product pages) because st.com timed out / reset the HTTP/2 stream from this host (curl 92 and 28, WebFetch timeout); both are ST's own English PDFs with ST document numbers |
| Secondary references | socialbadge-ai rev 2 `components/leds/*.py`, `components/sensors/everlight_IRM_H638T.py`, `st_VL53L4CD.py`; `~/socialbadge-ai/lcsc.lock.json` (C19269752 orientation 180, C3178291 0, C91447 0, C55160508 0) |
| Footprint source | WS2812C, IR11-21C, IRM-H638T: EasyEDA/LCSC KiCad imports (`kicad_footprints/C55160508`, `C19269752`, `C91447`), as on socialbadge rev 2, each checked pad by pad against the datasheet drawing (centres agree; EasyEDA pads are bigger or sit a little further in, and are kept because the boards were fabbed and work). VL53L4CD/CX: pads placed from the datasheets' PWB solder pattern (DS13812 p.21 / DS13805 p.22 Fig. 17, which match each other); no vendor KiCad footprint, no generator for an optical LGA12 |

### Checks run

| Check | Result |
|-------|--------|
| Domain checklist | Component Modeling; 24/24; 2 fixed (IR11 pin 1 = anode per datasheet p.2, not the socialbadge cathode-on-pad-1 workaround; IRM and IR11 courtyards grown to cover pads); 6 N/A: thermal pad included / thermal-pad dimensions / paste subdivision (no package has an exposed pad), generator choice (KiCad import or datasheet PWB pattern: none are generator packages), Toleranced min/max (fixed vendor land patterns, not generator inputs), symbol split (>40 pins: all parts have ≤12) |
| General Gotcha Scrub | 22/22: 3 pass (class-level ports; datasheets downloaded and read; DNC kept as its own port so cir-04 can leave it open), 19 N/A: component task with no nets, wiring, pull-ups, top-level symbols or application circuit (those go to cir-03 / cir-04) |
| Layout rules | not applicable: component task, no layout-constraint code |
| SI measurements | not applicable: component task, no SI constraints |
| Physical realization | not applicable: component task, no pours or stitch vias |
| `ruff check` | `ruff check     PASS` |
| `ruff format` | `ruff format    PASS` |
| `pyright` | `pyright        PASS` |
| Grep gates | `grep gates     PASS   0 hard-fail, 0 review-required` |

#### Component check

```
## Component check
Source: ST DS13805 Rev 3 (06/2022) VL53L4CX; ST DS13812 Rev 5 (06/2022) VL53L4CD; Worldsemi WS2812C-2020-V6/W;
        Everlight DIR-0000945 Rev 4 (IR11-21C); Everlight DMO-0000008 Rev 3 (IRM-H6XXT); page/figure per claim in module docstrings
        Source reached by: ST: LCSC copies (datasheet.lcsc.com/.../b40b87ad...pdf, .../2a54ed8b...pdf) of ST's PDF; others: local ~/socialbadge-ai/datasheets
        Probes, when any source was recorded unreachable: st.com/resource/en/datasheet/vl53l4c{x,d}.pdf -> curl (92) HTTP/2 INTERNAL_ERROR; --http1.1 -> curl (28) 60 s timeout, 0 bytes; WebFetch -> 60 s timeout
        User-typed facts checked against it: "VL53L4CX datasheet DS13110" -> NOT confirmed: the VL53L4CX datasheet is DS13805 (the CD is DS13812, as typed); "LGA-12 2.4x4.4, pin-compatible" -> confirmed (DS13805 p.3, p.4, p.22); "C3178292" -> LCSC page lists VL53L4CXV0DH/1; "WS2812C rotated 180, not mirrored" -> confirmed (p.2 Top View)
        Disagreements found: DS13110 vs DS13805 document number (reported in the acceptance block)
References opened: component-guide.md (all component tasks) -> read; pin-file row not matched
Identity: WS2812C_2020_V6 mpn "WS2812C-2020-V6/W"; IR11_21C_TR8 "IR11-21C/TR8"; IRM_H638T_TR2 "IRM-H638T/TR2";
        VL53L4CDV0DH_1 "VL53L4CDV0DH/1" (DS13812 p.32 Table 19); VL53L4CXV0DH_1 "VL53L4CXV0DH/1" (DS13805 p.33 Table 19);
        manufacturer, prefix (D / D / U / U / U), datasheet URL, LCSCPart set on each class
Pins: 4/4, 2/2, 4/4, 12/12, 12/12 — every power, ground and DNC pad has a port; names from the pin tables (IRM OUT renamed from socialbadge VOUT to the datasheet's "OUT")
Landpattern: no generator. VL53L4: 12 x 0.50 sq pads, 0.80 pitch, 3.70 x 2.10 (DS13805 p.22 / DS13812 p.21 Fig.17), body 4.40+-0.05 x 2.40+-0.05; pad keys = datasheet pins (socialbadge used VL53L0X keys)
        WS2812C: 4 pads 0.9x0.7 at (+-0.92, +-0.55) vs datasheet 0.7x0.7 at (+-0.915, +-0.55) (p.2 PCB Solder Pad)
        IR11: 2 pads 1.485x1.62 at +-1.49 vs datasheet 0.9x1.3 at +-1.25 ("for reference only", p.2)
        IRM: 4 pads 1.5x0.9 at x +-2.95 (Vcc 2.92), y +-1.27 vs datasheet 1.5x1.1 at +-3.15, +-1.27 (p.6)
Library defaults: none relied on (no generator); Density level: n/a — no IPC generator used
Value / BOM: .value unset — asserted None in tests/test_comp00b_components.py::test_counts
No-field walk: in each class docstring (supply ranges, I2C 0x52, XSHUT/GPIO1 behaviour, decoupling, peak current, FoV/exclusion cones, IR ratings, IRM RC filter)
Provenance: values traceable to no datasheet page: EasyEDA pad sizes (fabbed rev 2, cross-checked centres); silkscreen and courtyard outlines (drafting, not datasheet)
Checks: pyright clean; unittest 6 passed; build status: ok for all five TestDesigns
Verdict: complete
```

### Interface notes

| Field | Value |
|-------|-------|
| Ports exposed | WS2812C: `DI`, `DO`, `VDD`, `GND`. IR11: `A`, `C` (pad 1 = A). IRM: `VCC`, `OUT`, `GND[0..1]` (was `VOUT` on socialbadge). VL53L4CD/CX: `AVDD`, `AVDDVCSEL`, `AVSSVCSEL`, `GND`, `GND2`, `GND3`, `GND4`, `XSHUT`, `GPIO1`, `SDA`, `SCL`, `DNC` (leave unconnected) |
| Power requirements | WS2812C 3.3-5.3 V (VLED). IR11 IF ≤ 65 mA, VF 1.2 V at 20 mA. IRM 2.7-5.5 V, 0.7 mA max, through 47-220 Ω + ≥2.2 µF. VL53L4CX AVDD 2.6-3.5 V (3V3 ok), 19 mA average, 40 mA peak, 5 µA HW standby; 100 nF + 4.7 µF at AVDDVCSEL/AVSSVCSEL |
| Constraints needed at top level | I²C pull-ups (3.6 kΩ at ≤90 pF, 400 kHz) at bus-aggregation level; XSHUT and GPIO1 10 kΩ pull-ups; nothing may sit in the ToF's 25° collector / 29° emitter exclusion cones (DS13805 p.24); IR11 / IRM / LED placement keeps clear of those cones |
| Verification design / assembly constraint parity | not applicable: component task, no SI constraint |

### Reviews

| Field | Result |
|-------|--------|
| JITX code review (self) | run (jitx-code-review, scope: the five component modules + tests/test_comp00b_components.py): 0 CRITICAL, 0 WARNING, 3 NOTE |
| JITX CRITICAL | none |
| JITX WARNING | none |
| JITX NOTE | `st_VL53L4CD.py` `class VL53L4LGA12`: shared base has no `mpn`, so instantiating it alone gives a part with no MPN. Its docstring says not orderable; designs use the two subclasses. / `worldsemi_WS2812C_2020.py`, `everlight_IR11_21C.py`, `everlight_IRM_H638T.py`: the pad instances (`_pad_*`) are created at module level, as in the socialbadge port and comp-00a. They are not a mutable parallel model. / `tests/test_comp00b_components.py` `_xy`: reads `pad.transform`. The landpattern frame is the frame the datasheet drawing uses, so this is the immediate-container carve-out (local-frame-transform-as-position). |
| Outside-voice review | not run: a component port is not on the per-task trigger list (no MCU/FPGA, RF, power, safety, high-speed or battery work) |
| Outside-voice CRITICAL | none |
| Outside-voice WARNING | none |
| Outside-voice NOTE | none |

**Verdict (self):** ready-for-review

**Open issues / deferred:**
- The brief named the VL53L4CX datasheet as DS13110. ST's VL53L4CX datasheet is DS13805 Rev 3, and that document is the one used and cited. The orchestrator should correct PLAN.md `Data Sources` (ToF row).
- The ST datasheets were saved from LCSC's copies because st.com was unreachable from this host. Both are ST's English PDFs (DS13805 Rev 3, DS13812 Rev 5). Re-download from st.com when possible and diff.
- Changes from socialbadge that cir-03/cir-04 must know about:
  - IRM port `VOUT` is now `OUT`.
  - IR11 pad 1 is now the anode, so no lcsc.lock orientation 180 is needed.
  - VL53L4 pad keys are now the datasheet pin numbers. Pad copper is unchanged.
- WS2812C VDD minimum is 3.3 V (p.2), while VBAT can drop to 3.0 V. This is a firmware/cir-03 concern and does not affect the model.
