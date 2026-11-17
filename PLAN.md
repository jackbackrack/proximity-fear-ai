# Project Plan: Proximity Fear Badge

## Requirements Lock

| Item | Source | Where it lives |
|------|--------|----------------|
| Programming / debug path | user-stated: USB-C charge + program; not specified — assuming: SWD Tag-Connect pads for the first bootloader flash | this row |
| UI count and class | user-stated: 3 concentric rings of the socialbadge's 2 mm chainable LEDs, one user button; not specified — assuming: keep the MCP73831 charge LED on the back | this row |
| Sensors | user-stated: socialbadge-type ToF distance sensor in the front centre, microphone, IR TX/RX kept; ~4 m range (user chose) | ARCHITECTURE.md `Interface Map` |
| Wireless | user-stated: BLE + writable NFC on an nRF52840 module; Ebyte E73-2G4M08S1CX with stick-on FPC antenna (user chose, Raytac out of stock); ferrite-backed flex NFC antenna (user chose) | this row |
| Quantity | user-stated: 2–5 badges in the first JLCPCB run | this row |
| Power rails | user-stated: battery powered, LiPo on JST-PH, USB-C charging as on socialbadge | ARCHITECTURE.md `Power Tree` |
| Assembly cost target / tier | not specified — assuming: JLCPCB Standard PCBA as socialbadge-ai | this row |
| RF / wireless module policy | user-stated: pre-certified nRF52840 module, no bare-chip RF layout | this row |
| Connector UX | user-stated: USB-C + JST-PH, as socialbadge | this row |
| Fab house / process | not specified — assuming: JLCPCB 4-layer as socialbadge-ai rev 2 | ARCHITECTURE.md `Board` |
| Mechanical / enclosure constraint | user-stated: ~50 mm round, keep all ring LEDs (no antenna cut-outs); 3D-printed back case with snap lip, no PCB holes | ARCHITECTURE.md `Board` |
| Firmware behaviour | user-stated: heart rate ∝ 1/distance; mic drives startle reflex or audio-reactive colour; stretch: BLE beat sync between nearby badges; stretch: wearer's real heartbeat via BLE heart-rate strap/watch | `Firmware` section below |

## Design Reference

See ARCHITECTURE.md sections `Power Tree`, `Interface Map`, `Board`, `Object-Hierarchy Decisions`, `Design Notes`.

## Data Sources

Models marked "reuse" are copied from `~/socialbadge-ai/src/socialbadge_ai/components/` (built, fabbed, brought up on rev 2).

| Component | MPN | Package | Datasheet source | Footprint method | Chosen over | Source status |
|-----------|-----|---------|------------------|------------------|-------------|---------------|
| BLE/NFC MCU module | Ebyte E73-2G4M08S1CX (C2764963, 978 at JLC) | 13×18 castellated, 1.27 mm | Ebyte E73-2G4M08S1CX User Manual v1.2 (cdebyte.com) | LCSC .kicad_mod (consent given 2026-11-15), cross-checked to Ebyte drawing (43 castellated pads, 1.27 mm) | Raytac MDBT50Q (0 JLC stock); E73-2G4M08S1C ceramic (22 stock, needs board antenna keepout) | source approved |
| ToF distance sensor | ST VL53L4CXV0DH/1 (C3178292, 19 at JLC), 6 m | LGA-12 2.4×4.4 | ST DS13805 Rev 3 | reuse `st_VL53L4CD.py` land pattern (pin-compatible) | VL53L1X C190004 (12 150 stock, new footprint; fallback if stock drops below 6) | source approved |
| PDM MEMS microphone | LinkMems LMD3526B261-OFA03 (C41347997, 3 520 at JLC), bottom port, PDM, 1.62–3.6 V | 3.5×2.65 LGA-5 | LinkMems spec M196 v1.0 (LCSC) | LCSC .kicad_mod, cross-checked to spec | -OA1 C5373238 (0 stock); analog mic (needs amp) | source approved |
| NFC antenna (hand-attached) | Molex 146236-0111 (C17350773), ferrite-backed, 23×27.3 mm, ~3 µH | flex, solder tabs | Molex 146236 product spec | two solder pads on the PCB | PCB rim coil (planes kill it); ST25DV tag (extra chip) | source approved |
| BLE antenna (hand-attached) | 2.4 GHz FPC antenna with IPEX lead matching the E73-CX connector | flex | vendor spec | none (snaps onto the module) | E73 ceramic (board keepout vs outer ring) | source approved (IPEX-1/U.FL assumed; confirm on the first module received) |
| 32.768 kHz crystal (LFXO) | Epson Q13FC13500004 FC-135, 12.5 pF (C32346, JLC basic) | 3215 2-pad | Epson FC-135 datasheet | JITX generator / LCSC .kicad_mod | LFRC only (worse timing for badge sync) | source approved |
| Addressable LED ×50 | WS2812C-2020-V6 (C55160508) | 2020 | datasheets/ws2812c-2020-v6.pdf | reuse | WS2812B-2020 (no JLC stock) | source approved |
| Li-ion charger | MCP73831T-2ACI/OT | SOT-23-5 | reuse | reuse | — | source approved |
| 3.3 V LDO | AP2112K-3.3TRG1 | SOT-23-5 | reuse | reuse | — | source approved |
| OR diodes ×2 | SS14 | SMA | reuse | reuse | — | source approved |
| USB-C | TYPE-C-31-M-12 | — | reuse | reuse | — | source approved |
| Battery connector | PH2-2P (SHOU HAN) | JST-PH SMD | reuse | reuse | — | source approved |
| Button | TS-1187A | SMD | reuse | reuse | — | source approved |
| USB ESD | USBLC6-2SC6, PESD5V0S1BL ×2 | SOT-23-6, SOD-323 | reuse | reuse | — | source approved |
| P-FET ×2 (LED switch, reverse battery) | AO3401A | SOT-23 | reuse | reuse | — | source approved |
| N-FET ×2 (LED gate drive, IR drive) | BSS138 | SOT-23 | reuse | reuse | — | source approved |
| IR emitter / receiver | IR11-21C, IRM-H638T | SMD | reuse | reuse | — | source approved |
| Charge LED | 0603 red (`kt_0603_red.py`) | 0603 | reuse | reuse | — | source approved |
| SWD pads | Tag-Connect TC2030-NL | pads | Tag-Connect drawing | mechanical footprint | 0.05" header (too tall) | source approved |
| Passives | jitxlib.parts JLCPCB query, as socialbadge-ai | per row | — | per row | n/a | stand-in: approval at the Phase 4 parts gate |

## Phase 1: Substrate + Components

### [sub-01] Substrate
- **Type / skill / deps:** substrate | — | —
- **Data:** ARCHITECTURE.md `Board`; `JLC04161H_1080`
- **Specifics:** same stackup and inner-plane assignment as socialbadge-ai rev 2
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.substrate.TestDesign`
- **Status:** accepted

### [comp-00a] Port reused power / connector / discrete models
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` rows: charger, LDO, OR diodes, USB-C, battery connector, button, USB ESD, P-FET, N-FET, charge LED; socialbadge-ai `components/` (incl. `protection/landpattern_helpers.py`, `test_points/`)
- **Specifics:** copy unchanged where they build; each module keeps or gains its own `TestDesign`; spec note per MPN
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.power_linear_regulators.microchip_MCP73831T_2ACI_OT.TestDesign` and every ported module's `TestDesign`
- **Status:** accepted

### [comp-00b] Port reused front-side models (LED, IR, ToF)
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` rows: addressable LED, IR emitter / receiver, ToF; socialbadge-ai `components/leds/`, `components/sensors/`
- **Specifics:** add a VL53L4CX class sharing the VL53L4CD land pattern; drop the VL53L0X model
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.sensors.st_VL53L4CX.TestDesign` and every ported module's `TestDesign`
- **Status:** accepted

### [comp-01] nRF52840 module
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` module row
- **Specifics:** castellated edge pads plus any bottom pads; mark the IPEX connector keep-clear so nothing tall sits beside it
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.mcus.ebyte_E73_2G4M08S1CX.TestDesign`
- **Status:** accepted

### [comp-02] PDM microphone
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` mic row
- **Specifics:** acoustic port hole is part of the land pattern (non-plated hole + keepout)
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.sensors.linkmems_LMD3526B261.TestDesign`
- **Status:** accepted

### [comp-03] NFC antenna pads
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` NFC antenna row
- **Specifics:** two hand-solder pads sized for the Molex flex tabs or 28 AWG wire, on Bottom near the rim
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.antennas.nfc_pads.TestDesign`
- **Status:** accepted

### [comp-04] 32.768 kHz crystal
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` 32.768 kHz crystal row
- **Specifics:** 2-pad 3215; record CL = 12.5 pF and ESR in the spec note for cir-02's load-cap calculation
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.crystals.epson_FC135.TestDesign`
- **Status:** accepted

### [comp-05] Tag-Connect TC2030-NL SWD footprint
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** `Data Sources` SWD pads row
- **Specifics:** 6 pads + 3 NPTH alignment holes per Tag-Connect drawing; pin 1 VCC, 2 SWDIO, 3 nRESET, 4 SWCLK, 5 GND, 6 SWO
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.connectors.tagconnect_TC2030.TestDesign`
- **Status:** accepted

### [comp-06] VBUS surge TVS
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** ARCHITECTURE.md `Design Notes` (VBUS hot-plug); MCP73831 §6.1.1.2; chosen part's datasheet
- **Specifics:** unidirectional, standoff ≥ 5.25 V, clamp at hot-plug energies below the AP2112K 6.5 V / MCP73831 7 V abs max; JLC stocked
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.components.protection.<file>.TestDesign`
- **Status:** accepted

## Phase 2: Circuits

### [cir-01] Power (USB-C, charger, power path, LDO, reverse battery, VBAT sense)
- **Type / skill / deps:** circuit | jitx-circuit-builder | comp-00a
- **Data:** socialbadge-ai `circuits/usb_c.py`, `charger.py`, `power_path.py`, `ldo_3v3.py`; ARCHITECTURE.md `Power Tree`
- **Specifics:** USB D+/D− end at the nRF (no 27 Ω resistors); R_PROG 5 kΩ; unswitched VBAT divider to an AIN; battery side of the power path is a P-FET load-share switch (user chose 2026-11-15), not an SS14
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.power.TestDesign`
- **Status:** accepted

### [cir-02] nRF52840 support
- **Type / skill / deps:** circuit | jitx-circuit-builder | comp-01, comp-00a, comp-04, comp-05
- **Data:** Ebyte E73 reference schematic + nRF52840 PS reference circuit; ARCHITECTURE.md `Design Notes`
- **Specifics:** normal-voltage mode (VCC = VDDH = 3V3), RESET pull-up, SWD Tag-Connect, user button, external 32.768 kHz crystal + load caps on XL1/XL2, NFC pins to cir-06
- **Engineering questions:**
  - Does the E73 need an external DC/DC inductor for REG1, or should firmware leave the DC/DC off? (Ebyte spec, power section; nRF52840 PS reference circuit)
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.nrf_support.TestDesign`
- **Status:** accepted

### [cir-03] LED rings + LED power switch
- **Type / skill / deps:** circuit | jitx-circuit-builder | comp-00a, comp-00b
- **Data:** socialbadge-ai `circuits/front_leds.py`; ARCHITECTURE.md `Object-Hierarchy Decisions`
- **Specifics:** decoupling caps fixed beside each LED on the front, alternating inside/outside the ring circle
- **Shape:** `RING_SPECS` tuple of `RingSpec`; `LEDRings.rings: list[list[WS2812C_2020_V6]]`
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.led_rings.TestDesign`
- **Status:** accepted

### [cir-04] Centre sensors (ToF, IR TX, IR RX)
- **Type / skill / deps:** circuit | jitx-circuit-builder | comp-00a, comp-00b
- **Data:** socialbadge-ai `circuits/distance_sensor.py`, `circuits/infrared.py`
- **Specifics:** ToF at the origin; IR parts fixed inside the inner ring radius minus LED clearance
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.centre_sensors.TestDesign`
- **Status:** accepted

### [cir-05] Microphone
- **Type / skill / deps:** circuit | jitx-circuit-builder | comp-02
- **Data:** mic datasheet application circuit
- **Specifics:** L/R select strapped; port hole inside the inner ring
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.microphone.TestDesign`
- **Status:** accepted

### [cir-06] NFC tag front end
- **Type / skill / deps:** circuit | jitx-circuit-builder | comp-03
- **Data:** nRF52840 PS NFCT section; Nordic NFC tag antenna tuning note
- **Specifics:** two tuning caps to GND, DNP-able values for tuning on first boards
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.nfc.TestDesign`
- **Status:** accepted

### [pin-01] nRF52840 GPIO assignment
- **Type / skill / deps:** pin-assignment | jitx-pin-assignment | comp-01
- **Data:** ARCHITECTURE.md `Interface Map`
- **Specifics:** NFC fixed to P0.09/P0.10; AIN-capable pin for VBAT sense; everything else free via provide/require
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.circuits.nrf_pins.TestDesign`
- **Status:** accepted

## Phase 3: Top-Level Assembly

### [asm-01] Top-level design
- **Type / skill / deps:** assembly | jitx-circuit-builder + jitx-physical-layout | sub-01, cir-01, cir-02, cir-03, cir-04, cir-05, cir-06, pin-01
- **Data:** accepted Phase 2 outputs; ARCHITECTURE.md `Board`
- **Specifics:** 50 mm circle with 1 mm rim keepout; rings + centre sensors fixed on Top, rest on Bottom
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.main.ProximityFearBadge`
- **Status:** accepted

## Phase 3b: Design Review and Loopback

### [aud-01] Design-level audit
- **Type / skill / deps:** audit | — | asm-01
- **Data:** top-level design; acceptance blocks; ARCHITECTURE.md
- **Specifics:** IPEX connector reachable; LED peak current vs battery and AO3401A; ToF field of view clear of IR LED crosstalk; mic port hole clear
- **Verify:** `python scripts/check.py proximity_fear/` exits 0 and the audit block is complete
- **Status:** accepted

## Phase 4: Build + Verify + Iterate

### [rte-01] Routing via Warp (socialbadge flow)
- **Type / skill / deps:** layout | jitx-physical-layout + jitx-layout-constraints | aud-01
- **Data:** `jitx-warp-integration` (local, editable): `design_report` export → user routes in Warp → layout JSON → `layout_placements` import; socialbadge-ai `scripts/import_layout.py`, `export_jlcpcb.py`
- **Specifics:** user routes; orchestrator exports the report, re-imports, and witnesses widths/clearances with a project layout-check script (owed by asm-01)
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.main.ProximityFearBadge` with the imported layout, then the layout-check script exits 0
- **Status:** in-progress

### [fin-01] Final verification
- **Type / skill / deps:** verify | — | rte-01
- **Data:** top-level design
- **Specifics:** JLCPCB export via socialbadge-ai `scripts/export_jlcpcb.py`; in JLC's placement preview confirm IR11-21C (pad 1 = anode, no 180° override, unlike socialbadge) and every polarised part
- **Verify:** `python scripts/check.py proximity_fear/ --build proximity_fear.main.ProximityFearBadge`
- **Status:** pending

## Firmware (after first boards; outside the JITX gates)

| ID | Feature | Notes |
|----|---------|-------|
| fw-01 | Bring-up: LEDs, ToF, button, USB, battery gauge | Arduino nRF52 (Adafruit core) or Zephyr; UF2 bootloader over SWD; flash firmware before connecting a pack with USB present (reversed-pack charge cut-off is firmware); rules in `main.py` docstring |
| fw-02 | Fear heart | beat interval ∝ distance (e.g. 60 bpm at ≥4 m → 180 bpm at 0.3 m), smoothed; lub-dub pulse radiates inner → outer ring |
| fw-03 | Mic | startle: sudden loudness spike jumps the rate then decays; ambient level tints colour |
| fw-04 | NFC | NDEF tag the phone can write (name / message / colour) and the badge reads back |
| fw-05 | Stretch: badge sync | BLE advertising carries beat phase; RSSI gates "nearby"; firefly-style phase coupling; optional IR face-to-face confirm |
| fw-06 | Stretch: real heartbeat | BLE central to the standard Heart Rate Service (chest strap / watch); real BPM replaces or biases the fear BPM |

## Gate status

| Gate | Verdict | Date | Deferred / blocking |
|------|---------|------|---------------------|
| 0 → 1 | advance | 2026-11-15 | — (Rosetta installed, runtime 4.6.0-rc.18 reachable, auth refreshed) |
| 1 → 2 | advance | 2026-11-15 | IPEX generation to confirm on first module; WS2812C VDD min 3.3 V vs VBAT → cir-03 |
| 2 → 3 | advance | 2026-11-15 | outside-voice review (no codex CLI) owed at Phase 3b for MCU/power/RF tasks; concrete GPIO map fixed only at routing |
| 3 → 3b | advance | 2026-11-15 | layout rules unwitnessed until routing; aud-01 items: SS14/PH2 courtyards, TC2030 pin-tip courtyard, cir-04 same-net pad contact, mic port path through case |
| 3b → 4 | advance | 2026-11-15 | outside voice via Sonnet (user-approved substitute); accepted: A-05 USB SI, TVS standoff/residual; first-board checks: NFC tune, LFXO, LED soft start; case mic opening at (+4.5, 0) |

## Modifications

| ID | Change | Files | Verdict |
|----|--------|-------|---------|
| M-11 | Courtyard rework after user review in JITX UI: 69 violations → 0 (ring cap gap, centre zone, IR TX → (0,+4.85), mic cap, Bottom nudges); reverse-flow check agrees; TC2030 pin-tip courtyard → 3 circles (comp-05) | ARCHITECTURE.md, PLAN.md | — |
| M-10 | rte-01 prep: layout import hook, export_jlcpcb.py, check_layout.py; check_layout found a real 3V3/GND pad overlap at the ToF decoupling cap (audits had called it same-net) → cir-04 fix + overlap tests | main.py, scripts/, PLAN.md | — |
| M-9 | Closure audit: NFC caps swapped to their own pads (W-1), LFXO caps 18→16 pF (W-2), TVS deviation accepted by user (W-3), routing intent recorded | ARCHITECTURE.md, PLAN.md | — |
| M-8 | Outside-voice findings: firmware charge enable on PROG (user chose), VBUS TVS, STAT divider 100k/180k, sense divider 1.5M+1.5M, VBAT cap 10 µF, drop extra nRF VCC 4.7 µF, P0.26 out of fast pool, NFC caps ±2 % + mirrored placement + DNP trim footprints | ARCHITECTURE.md, PLAN.md | — |
| M-7 | Phase 3b loopback: LED switch fed from SYS (A-01), nRF VBUS 4.7 Ω (A-02), mic to Bottom (A-03), IRM supply switched + ToF SW standby (A-04), USB SI accepted (A-05), load-share pull-down 10 k (A-08), SS14/PH2 courtyards (A-12) | ARCHITECTURE.md, PLAN.md | — |
| M-6 | rte-01 added: routing through Warp as on socialbadge (user chose); second opinion via a different Claude model (user chose, codex unavailable) | PLAN.md | — |
| M-5 | USB-C on a 6 o'clock board tab: its shell slots collided with the outer LED ring at any rim position (user chose tab over SMD part / bigger board) | ARCHITECTURE.md | — |
| M-4 | Power path: battery-side SS14 → AO3401A load-share switch so 3V3 stays regulated to ~3.4 V VBAT (user chose) | PLAN.md, ARCHITECTURE.md | — |
| M-3 | comp-00 split into comp-00a/00b; comp-04 crystal and comp-05 TC2030 added | PLAN.md | — |
| M-2 | OQ-6 closed from the E73-CX manual: 43 castellated pads, no internal 32.768 kHz crystal, so an Epson FC-135 is added | PLAN.md, ARCHITECTURE.md | — |
| M-1 | OQ-1..5 closed: flex NFC antenna, E73-CX + FPC (no tab, all LEDs), snap-lip case, LCSC footprint consent, VL53L4CX kept, LMD3526B261-OFA03 mic | PLAN.md, ARCHITECTURE.md | — |
