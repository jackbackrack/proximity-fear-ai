## Phase 3b Audit (re-audit after M-7): Proximity Fear Badge

**Auditor:** read-only Phase 3b re-audit sub-agent (same model as the first audit)
**Audited from:** the M-7 code on disk at 2026-11-15 ~20:58, i.e. `proximity_fear/` (circuits/power.py, led_rings.py, centre_sensors.py, nrf_support.py, microphone.py, nrf_pins.py, designs/badge.py, main.py). PLAN.md and ARCHITECTURE.md changed on disk during the audit and now record M-8 (the outside-voice fixes). No `.py` file is newer than the audit start, so **none of the M-8 changes are in the audited code**. Where an M-8 item overlaps a finding below, the finding says so.
**Evidence base:** I re-extracted the datasheet PDFs in `datasheets/` (pdftotext, plus rendered pages for nRF52840 PS pp.585/589 and SS14 p.2). I checked the shipping assembly `proximity_fear.main.ProximityFearBadge` three ways: `scripts/check.py --build`, a full-netlist union-find, and a runtime submit + capture to measure placed geometry and the resolved pin map. The scratch probes are under `scratchpad/audit2/`.
**Build / tests:** `python scripts/check.py proximity_fear/ --build proximity_fear.main.ProximityFearBadge`: ruff and pyright pass, grep gates show 0 hard-fail and 4 review-required (the existing cap/ShortTrace dispositions), and the build reports `status: ok`. `python -m unittest discover -s tests`: 90 tests, OK.

### Verification of first-audit fixes

| ID | Fix | Datasheet check | Assembly check (`ProximityFearBadge`) | Status |
|----|-----|-----------------|----------------------------------------|--------|
| A-01 | LED switch from SYS | AN1149 PDF p.5 "Connecting the system load to the battery": a load on the cell is "not encouraged" with an auto-terminating charger. MCP73831 p.4 ITERM 7.5 % of IREG (5.6–9.4 %) | The SYS net holds `path.d_usb.K`, `path.q_bat.S`, `ldo.u1.VIN/EN`, `ldo.c_in`, `rings.switch.q_switch.S` and `r_gate_pu`. The VBAT net holds only `q_rev.S`, `charger.u1.VBAT`, `charger.c_vbat`, `r_sense_top`, `tp_vbat` and `q_bat.D`. No load is on VBAT. | **RESOLVED** |
| A-02 | 4.7 Ω on nRF VBUS | PS p.583: the series resistor is "recommended for new designs". The 4R7 ±1 % value is in the BOM on PS p.586. USBLC6 VBR ≥ 6 V (p.2) is above the 5.8 V VBUS abs max (PS p.612). VBUS minimum is 4.35 V (PS p.611). IUSB,ACTIVE,VBUS is 2.4 mA (PS p.569), so the drop across 4.7 Ω is 11 mV. | VBUS → `nrf.r_vbus` → module pad 27 + `nrf.c_vbus` (3-pin net): correct. **However, `nrf.r_vbus` has no placement. The capture shows it auto-dropped on Top, off the board, at (30.2…31.3, −29.1…−27.1).** See R-01. | **RESOLVED in the netlist.** Placement is still open (R-01). |
| A-03 | Mic on Bottom, port at (4.5, 0) | LMD3526 p.7: bottom port. p.8: pad layout. Ø0.5 mm NPTH plus an all-layer Ø1.03 keepout (model). | The captured mic is on Bottom, with GND ring pad 5 at (4.50, 0.00) and NPTH at (4.5, 0). The test `test_mic_on_bottom_port_at_spot` passes. Nothing on Top lies within 1.68 mm of the port keepout (nearest is `tof.c_hf`). | **RESOLVED.** But the move broke the LFXO routing corridor (R-02). |
| A-04 | IRM supply switched; ToF SW standby | IRM-H638T p.3: Icc 0.4 typ / 0.7 max mA; Vs 2.7–5.5 V; VH ≥ Vcc − 0.4 V. AO3401A p.2: VGS(th) −0.5…−1.3 V; RDS(on) ≤ 85 mΩ at −2.5 V; IDSS ≤ 1 µA (≤ 5 µA at 55 °C). VL53L4CX p.18 Table 12: SW standby 4/6/9 µA, HW standby 3/5/7 µA. p.5: XSHUT must be driven, 10 k pull-ups. | Source `q_en.S` on 3V3, drain `q_en.D` → `r_filter` → IRM VCC + 4.7 µF. Gate on `IR_RX_EN` (resolved to P0.12 in this capture) with 100 k to 3V3, so the FET is off at reset and in System OFF. Body diode (D→S) is reverse-biased because the IRM rail is never above 3V3. Polarity and orientation are correct (AO3401A model: pads S/D/G match the SOT-23 top view rotated 90°, the same model as the fabbed socialbadge). On, VGS = −3.3 V. Vcc is 3.23 V, so VH ≥ 2.83 V, which is above nRF VIH 2.31 V. | **RESOLVED** |
| A-05 | USB SI accepted | USB FS 12 Mb/s over ~30 mm. Electrically short (inference). PS reference designs have no external series R. | `main.py` docstring and ARCHITECTURE Design Notes record the acceptance and rationale. No constraint is in code. | **RESOLVED** (accepted with rationale; see N-09 for the gate record) |
| A-08 | Gate pull-down 10 k | AN1149 PDF p.5: "any reasonable value… 100 kΩ recommended… not too small". | At 10 k: 0.5 mA and 2.8 mW at 5.25 V. The VBUS bleed holds VBUS < 3.4 V (PS p.82 VBUS,DETECT min) for leakage < 340 µA. SS14 IR at 25 °C is ~1 µA at ~10 % VRRM (SS14 p.2 Fig.2). | Verified |
| A-12 | SS14/PH2 courtyards | — | The capture finds no Bottom courtyard overlaps apart from the mic and its own cap (N-02). | Verified |

### Pass 1: Circuit vs Datasheet Application Schematic (changed circuits only)

| IC | Datasheet page/figure | Datasheet externals | Code externals | Status | Findings |
|----|-----------|---------------------|----------------|--------|----------|
| nRF52840 (E73) VBUS | PS Fig 210 p.585 (config 1: R1 4R7 + C19 4.7 µF). Fig 212 p.589 (config 3: C21 only, no R1). | 2 (R1, C) | 2 (`r_vbus`, `c_vbus`) | match (R1 taken from config 1) | N-05 (page/config citation) |
| IRM-H638T | p.2 application circuit | 2 (R 47–220 Ω, C ≥ 2.2 µF) | 2 + switch (100 Ω, 4.7 µF, AO3401A, 100 k) | match | none |
| AO3401A LED switch | p.1–2 (load switch) | gate pull-up + drive | 100 k pull-up to SYS, 10 k + BSS138, 10 nF Miller, 10 µF bulk | match | none |
| LMD3526B261 | p.6 measurement circuit | 2 (0.1 µF, L/R strap) | 2 | match | N-02 (courtyard) |

### Pass 2: Assumption Compatibility (whole design)

| Circuit | Assumption | System evidence | Status | Finding ID |
|---------|------------|-----------------|--------|------------|
| LEDSwitch | Input range 3.0–4.9 V | On USB, SYS = VBUS − VF(SS14). SS14 p.2 Fig.3 gives ~0.45 V at 0.1 A and less at light load. With 5.25 V (USB 2.0), SYS ≈ 4.85–4.95 V. With a 5.5 V Type-C source, SYS ≈ 5.1–5.2 V. | Slightly exceeds the stated 4.9 V | N-03 |
| WS2812C DIN | VIH = 0.55·VDD ≤ nRF VOH (VDD − 0.4 V at 0.5 mA, PS p.156) | WS2812C p.3: VIH 0.55 VDD (tabled at 5 V). At VLED 4.9 V that is 2.70 V against VOH,min 2.85 V (3V3 −1.5 %, AP2112K p.8), a 0.15 V margin. At 5.2 V it is 2.86 V, a 0.01 V shortfall on guaranteed numbers. The real load is ~1 µA, so actual VOH ≈ 3.2 V. | Margin holds in practice and is marginal on paper | N-03 |
| WS2812C VDD | ≤ 5.3 V (p.2) | VLED ≤ ~5.2 V with a 5.5 V source | OK, close | N-03 |
| LEDSwitch gate drive | VGS ≥ −12 V and enough overdrive | VGS on = −SYS·100/110: −2.7 V at 3.0 V to −4.5 V at 4.95 V. The RDS(on) spec point is −2.5 V. | OK | none |
| BSS138 (LED) | Drain ≤ SYS | 50 V part, SYS ≤ 5.2 V | OK | none |
| PowerPath | q_bat off on USB (VGS = VF ≥ 0). Body diode reverse-biased (VBAT − SYS < 0.7 V). | With up to 150 mA of LED load now on SYS, SYS ≥ 4.75 − 0.5 = 4.25 V, which is ≥ VBAT 4.23 V max. With drooped 4.4 V VBUS, VBAT − SYS ≤ 0.3 V, below VSD 0.7 V (AO3401A p.2). | OK | none |
| PowerPath | SYS load ≤ SS14 1 A I(AV) (SS14 p.1) | On USB: 3V3 ≤ 130 mA + LED 150 mA cap = 280 mA. **All-white (firmware fault) = 880 mA** | OK only with the firmware cap | N-04 |
| VBUS 500 mA | Charger 200 mA + SYS ≤ 500 mA | MCP73831 IREG tolerance ±10 % (p.3 table), so 220 mA. 3V3 is 130 mA (Power Tree), or ~90 mA with the ToF/IR interlock. LED 150 mA. r_pull 0.5, nRF VBUS 2.4, charge LED 3, ISS 1.5 mA. Typical 447 mA. All maxima stacked: 507 mA. | Marginal at stacked maxima | N-04 |
| IRReceiver | Supply off in System OFF; OUT never pulled up while off | 100 k gate pull-up. Firmware rule recorded in `main.py:11-18`. | OK (firmware) | none |
| TofSensor | XSHUT held high in standby | VL53L4CX p.5. Rule recorded. GPIO1 must not be left asserted (10 k → 330 µA). | OK (firmware) | N-07 |
| Microphone | VDD 1.62–3.6 V. CLK idle → sleep (< 50 kHz, p.4) | 3V3 always on. **Sleep current is not specified in the M196 spec.** | Unquantified standby term | N-07 |
| LFXO (cir-02) | Cpcb ≈ 2 pF per leg (`nrf_support.py:85`), short traces, no fast signals nearby (PS p.609) | The capture shows the crystal pads and XL1/XL2 pads crossed, with the Bottom mic in between (R-02). PDM_CLK resolved to P0.26 (pad 12, between XL1 and XL2) (R-03). | **Broken** | R-02, R-03 |
| pin-01 | GPIO map is fixed at routing | Two captures this session resolved different maps. The earlier `real8.txt` capture had P0.26 unused; this capture puts PDM_CLK on P0.26. | Nondeterministic | R-03 |

### Pass 3: Interface-by-Interface Trace (changed interfaces)

| Interface | From | To | Hops verified | SI constraint? | Findings |
|-----------|------|----|---------------|----------------|----------|
| SYS / VLED | SS14 K + q_bat S (power path, SW quadrant, about (−10, −12)) | LDO VIN/EN + c_in 1 µF. LED switch S (at (13.3, −6.3), ~25 mm east). Switch D → c_bulk 10 µF + 50 LED VDD + 50 × 100 nF (103-pin VLED net) + L2 annulus pour. | netlist union-find, capture | n/a | N-06 (SYS decoupling at the switch, stale placement rationale) |
| IR_RX_EN | nRF P0.12 (this capture; slow pool) | q_en G + 100 k to 3V3. q_en S on 3V3, D → 100 Ω → IRM VCC + 4.7 µF. OUT → nRF P0.07 (IR_RX). | netlist, resolved pins | n/a | none |
| PDM (Bottom mic) | nRF PDM CLK = P0.26 (pad 12, at (3.81, 4.68) Bottom). DIN = P0.24 (pad 35). | Mic pad 3 CLK (5.34, −1.25), pad 1 DATA (3.66, −2.07), Bottom. L/R → GND. VDD + 100 nF. | netlist, capture | no (1–3 MHz, short) | R-02, R-03 |
| nRF VBUS | J1 VBUS / USBLC6 VBUS / charger VDD / SS14 A / q_bat G / r_pull (12-pin VBUS) | `r_vbus` → pad 27 (−6.50, 6.45). `c_vbus` (−9.0, 5.6…7.2), 1.5 mm from the pad. | netlist, capture | n/a | R-01, N-05 |
| USB D+/D− | J1 → USBLC6 → module pads 31/29 | unchanged | netlist | accepted without SI constraint (A-05) | N-09 |

### Pass 4: Power and Thermal (whole design)

| Rail | Regulator | Load sum | Rating | Margin | Thermal/package | Hot-plug | Finding ID |
|------|-----------|----------|--------|--------|-----------------|----------|------------|
| VBUS | USB host (500 mA default; CC lines are not readable by the nRF) | 447 mA typical peak / 507 mA stacked maxima (Pass 2) | 500 mA | ~10 % typical, −1 % stacked | — | Plug-in with LEDs at the 300 mA battery cap moves that load to VBUS until firmware reacts: ~590 mA for ms | N-04 |
| SYS (USB) | SS14 | 280 mA (capped). 880 mA all-white. | 1 A I(AV), RθJA 90 °C/W on 2"×2" Cu (p.1) | OK capped | 0.13 W at 280 mA. ~0.5 W all-white, about +75 °C on this board (inference). | Unplug: SYS rides the q_bat body diode ~25–65 ms (10 k bleed), so VLED ≈ VBAT − 0.7 V < WS2812C 3.3 V min briefly and 3V3 ≈ 2.9–3.0 V (nRF, ToF ≥ 2.6 V, IRM ≥ 2.7 V all OK) | N-04 |
| SYS (battery) | q_rev + q_bat AO3401A | 430 mA cap. 880 mA all-white. | 4 A, RDS(on) ≤ 85 mΩ at VGS −2.5 V (p.2) | large | 16 mW / 66 mW each, RθJA 125 °C/W, < +10 °C | Battery insertion: q_bat now in series ahead of the LED switch pulse path, which lowers the peak below the documented ~15 A | none |
| 3V3 | AP2112K-3.3 | 130 mA peak (≤ 90 mA with the interlock) | 600 mA min (AP2112K p.8) | > 4× | On USB (4.9 − 3.3) × 0.13 = 0.21 W × 184 °C/W = +38 °C peak | Start-up 20 µs, after SYS | none |
| VLED | AO3401A switch | 300 mA battery / 150 mA USB cap. 750 mA all-white. | 4 A | large | 9–64 mW | Soft start 0.21–0.59 A for ≤ 0.21 ms from SYS. SYS local cap is only the LDO's 1 µF, 25 mm away. | N-06 |
| IRM sub-rail | AO3401A (q_en) | 0.7 mA max | — | large | negligible | Enable inrush 33 mA, τ 0.47 ms (100 Ω × 4.7 µF), from 3V3 | none |
| nRF VBUS | 4.7 Ω + 4.7 µF | 2.4 mA | 0402 R | — | attach pulse 1.1 A / 22 µs, 59 µJ (the PS's own 0402 duty) | Damped attach ring at the pad | R-01 |
| Standby (System OFF, battery) | — | **Typical:** AP2112K IQ 55 + ToF SW standby 6 + VBAT divider 2.1 (4.2 V / 2 MΩ) + nRF OFF 0.4 (PS IOFF_RAMOFF_RESET) + MCP73831 IDISCHARGE 0.15 + SS14 IR ~1 + 2 × AO3401A IDSS ≪1 = **~65 µA**. **Max:** 80 + 9 + 2.1 + ~1.5 + 2 + ~5 + ≤2 = **~100 µA**. Plus mic sleep (unspecified). | target ≲ 0.1 mA | typical OK; ~0 at maxima | — | — | N-07 |

### Outside-Voice Review

**Outside-voice review:** not part of this re-audit. The `reviews/ov-*.md` files exist and PLAN.md M-8 records their dispositions. Those M-8 code changes are not yet in `proximity_fear/`, so they are not verified here.

### Findings and Loopback Decisions

| ID | Pass/source | Severity | Finding + evidence | Decision | Owner |
|----|-------------|----------|--------------------|----------|-------|
| R-01 | Pass 3 / fix regression (A-02) | **WARNING** | The new `nrf.r_vbus` (`proximity_fear/circuits/nrf_support.py:134`) is never placed. `place_back_side()` (`proximity_fear/designs/badge.py:344-415`) places `n.c_vbus` at `badge.py:363` but has no `n.r_vbus` line. After runtime capture the resistor sits on **Top, off the board**, at (30.2–31.3, −29.1…−27.1). It is the only unplaced part (capture probe). That breaks ARCHITECTURE Board "Front (Top): … Nothing else" and leaves VBUS→pad-27 routing intent undefined. `tests/test_asm01_top.py:138` (`test_top_parts_inside_rim`) skips parts whose transform is None before capture, so the test cannot see it. Evidence: capture (inference-free measurement). | Place `r_vbus` on Bottom between the VBUS feed and pad 27 (e.g. next to `c_vbus`, −9.0, ~8.5), and add a capture-time check that every component is placed and lies inside the outline. | asm-01 |
| R-02 | Pass 2/3 / fix regression (A-03) | **WARNING** | The Bottom mic now sits in the LFXO routing corridor, and the crystal's pads run in the opposite order to the XL pins. Captured positions: XL1 net crystal pad 1 at (−1.55, −0.90) → module XL1 pad 11 at (4.44, 2.58). XL2 net crystal pad 2 at (0.95, −0.90) → XL2 pad 13 at (3.17, 2.58). In x, XL1 starts west of XL2 and ends east of it, so the two traces must cross (via) or one must loop around. The mic copper (3.30…5.70, −2.33…0.81, Bottom) lies directly between the crystal and pads 11/13. The only corridor is 0.77 mm between the mic GND ring and the pad-11/13 ends (y 0.81 → 1.58). Any route passes within < 1 mm of the mic CLK/DATA pads. PS p.609: "Fast switching digital signals should not be routed close to the crystal". The longer loop also adds to the Cpcb = 2 pF per leg that the 18 pF load caps assume (`nrf_support.py:85-91`), which shifts CL and frequency (inference). With the mic on Top (pre-M-7) this Bottom corridor held only the Ø1.03 port keepout. Placement: `badge.py:237` (mic), `badge.py:359-361` (crystal and load caps). | Re-place the LFXO group so each crystal pad faces its XL pin with short uncrossed traces. Options: rotate the crystal 180° (or 270°) so pad 1 is east, and/or move the crystal and caps right up to pads 11/13. Alternatively move the mic port spot. Re-check that PDM routes stay ≥ 1 mm from XL1/XL2 copper with GND between. | asm-01 (placement), cir-02 (Cpcb assumption) |
| R-03 | Pass 2/3 | **WARNING** | The PDM CLK pool admits pins that can only be reached between the XL castellations. `nrf_pins.py:82` (`fast_gpios`) includes P0.26 (pad 12, inner row at (3.81, 4.68), centred between XL1 pad 11 and XL2 pad 13) and P0.06 (pad 14, (2.54, 4.68), reached between XL2 pad 13 and pad 15). This capture resolved **PDM_CLK = P0.26**, which puts a 1–3 MHz clock trace through the 0.37 mm gap between XL1 and XL2 (PS p.609). Pin assignment is also nondeterministic across captures (`scratchpad/real8.txt` had P0.26 unused), so the audit cannot verify the final map. PLAN M-8 records "P0.26 out of fast pool", but that is not in code yet, and P0.06 is not covered. | Remove P0.26 **and** P0.06 from the PDM/fast pool (or from PDM at least), and lock the GPIO map before rte-01. | pin-01 |
| N-01 | Pass 3 | NOTE | Top courtyard overlaps from cir-04 remain (capture): ToF×c_hf 0.50 mm², ToF×c_bulk 0.30, c_bulk×IR LED 0.22, IR LED×IRM 0.06, IRM×c_filter 0.33. The M-7 changes did not cause them. They are already on the 3→3b gate list ("cir-04 same-net pad contact"). | Carry to fin-01 JLC preview | cir-04 |
| N-02 | Pass 1 | NOTE | The mic `c_vdd` courtyard overlaps the mic courtyard by 0.15 mm (0.165 mm²). `microphone.py:42-45` says "0.6 mm clear", but the 0402 courtyard is 2.0 mm along y. The pad gap is 0.48 mm, so the overlap is benign. | Move the cap +0.15 mm or correct the comment | cir-05 |
| N-03 | Pass 2 | NOTE | `led_rings.py:51-57` bounds VLED at 4.9 V. On USB, SYS = VBUS − VF(SS14). Light-load VF is ≤ 0.45 V (SS14 p.2 Fig.3), so SYS is ~4.9–4.95 V at 5.25 V VBUS and ~5.1–5.2 V on a 5.5 V Type-C source. At 5.2 V, WS2812C VIH 0.55·VDD (p.3) = 2.86 V against guaranteed nRF VOH 2.85 V (PS p.156 at 0.5 mA), on paper. The real DIN load is ~1 µA, so actual VOH ≈ 3.2 V. VDD stays ≤ 5.3 V abs (p.2). The Power Tree "3.0–4.9 V" ceiling for SYS/VLED is slightly optimistic. (Inference from typical curves.) | Document the 5.5 V corner. Optional: run the chain's first LED off a level shifter, or accept. | cir-03 / ARCHITECTURE owner |
| N-04 | Pass 4 | NOTE | With LEDs on SYS, the USB budget and the SS14 rating depend on firmware. All-white on USB is 880 mA through the SS14 (1 A I(AV), p.1) and ~1.09 A from VBUS. At stacked maxima (IREG +10 %, MCP73831 p.3; 3V3 130 mA; LED 150 mA cap) VBUS reaches 507 mA, and 447 mA typical. A plug-in while LEDs run at the 300 mA battery cap briefly draws ~590 mA. The nRF sees VBUS (pad 27) so firmware can switch caps, but the rule must be explicit. | fw-01: switch to the USB LED cap on USBDETECTED before charge starts, and consider ~120 mA. Record it in Design Notes. | fw-01 / ARCHITECTURE owner |
| N-05 | Pass 1 | NOTE | Citation error. `nrf_support.py:48` and `:82` say "config-3 BOM R1 4R7 (p.586)". PS p.586 is Table 149, the **config 1** BOM. Config 3 (Fig 212 p.589 / Table 153 p.590) has no R1. The value and topology (R then C at the pad) match Fig 210 p.585, and p.583 recommends the resistor for all new designs. | Fix the citation | cir-02 |
| N-06 | Pass 3/4 | NOTE | The only capacitance on SYS is the AP2112K `c_in` 1 µF at (−15.5, −13.9). The LED switch input is ~25 mm away at (13.3, −6.3), so the switch soft-start pulse (0.21–0.59 A, `led_rings.py:58-63`) and WS2812 PWM steps come over a 0.4 mm trace. That trace is fine for DC (~30 mΩ) but has no local reservoir. The `badge.py:396` comment "LED switch on the battery side" is stale rationale after A-01. | Add 4.7–10 µF X5R at `q_switch.S`, or move the switch group toward the power path. Update the comment. | cir-03 / asm-01 |
| N-07 | Pass 4 | NOTE | Fresh standby budget: ~65 µA typical, ~100 µA at datasheet maxima, before the mic. The LMD3526 M196 spec gives no sleep current (p.4 lists only the < 50 kHz sleep clock). That is consistent with the updated ARCHITECTURE line ("≈70 typ / ~95 max"). Firmware traps worth recording: ToF GPIO1 left asserted → 330 µA in its 10 k pull-up. XSHUT low → 330 µA (already recorded). | Measure on first boards. Add the GPIO1-clear-before-standby rule to `main.py` firmware rules. | fw-01 |
| N-08 | Doc | NOTE | Stale text: `nrf_pins.py:31` says "GPIO x6" (the assembly requires 7), and the pin-01 TestDesign also requires 6. ARCHITECTURE Design Notes still says "VLED follows VBAT down to 3.0 V" (it follows SYS ≈ VBAT − I·R on battery). Harmless. | Tidy | pin-01 / ARCHITECTURE owner |
| N-09 | Pass 3 / gate | NOTE | A-05 has a documented rationale, but the Phase 3b→4 gate item "Every high-speed interface has SI constraints applied" names USB. The gate block should quote who accepted the waiver (user or orchestrator) and when. | Record in the gate block | orchestrator |

**Re-audit needed:** yes, after R-01…R-03 land. Scope: a capture-time placement and geometry check for the LFXO, mic and VBUS groups, plus the resolved PDM pins. The M-8 code changes (charge enable on PROG, VBUS TVS, divider values, VBAT 10 µF, NFC caps) also need verifying once they are in `proximity_fear/`.

**Audit verdict (combined):** issues-pending (3 WARNING: R-01, R-02, R-03; 0 CRITICAL; 9 NOTE)

### First-audit findings status

- A-01: **RESOLVED**
- A-02: **RESOLVED** in the netlist and datasheet check. Its new resistor is unplaced (R-01, WARNING, asm-01).
- A-03: **RESOLVED** as specified. The move caused R-02 (WARNING, asm-01).
- A-04: **RESOLVED**
- A-05: **RESOLVED** (accepted with rationale; gate record N-09)

**Combined same-model verdict: issues-pending**
