# Architecture: Proximity Fear Badge

Round wearable badge: three concentric rings of chained WS2812C-2020 LEDs beat a
heart whose rate rises as the ToF sensor in the centre sees someone get closer.
nRF52840 module for BLE (badge-to-badge sync, heart-rate strap pairing), NFC
tag, and PDM microphone. Power and front-end blocks are carried over from
`~/socialbadge-ai` rev 2 (fabbed and brought up).

## Power Tree

| Rail | Voltage | Source | Regulator | Type | Loads | Current | Noise / ripple requirement | Sequence position |
|------|---------|--------|-----------|------|-------|---------|----------------------------|-------------------|
| VBUS | 5 V | USB-C | — | input | MCP73831 VDD, SS14 OR, nRF VBUS (USB detect + USB PHY) | 500 mA max | — | when plugged in |
| VBAT | 3.0–4.2 V | JST-PH LiPo via reverse-battery AO3401A | MCP73831 (charge, R_PROG 5 kΩ = 200 mA) | input | load-share P-FET → SYS, VBAT sense divider (charger output feeds only the cell, AN1149) | 430 mA peak on battery (300 LED cap + 130) | — | always |
| SYS | 3.0–4.9 V | VBUS (SS14) or VBAT (AO3401A load-share switch, gate from VBUS) | SS14 + AO3401A | load sharing | AP2112K, LED switch | 430 mA (on USB, firmware caps LEDs so VBUS stays ≤ 500 mA incl. 200 mA charge) | — | follows source |
| 3V3 | 3.3 V | SYS | AP2112K-3.3 | LDO | nRF52840 module (VDD + VDDH), ToF, IR RX, IR TX, PDM mic | 130 mA peak (radio 16 + ToF 40 + IR TX 45 + misc) | ToF AVDD clean: local 100 nF + 4.7 µF | after SYS |
| VLED | 3.0–4.9 V | SYS | AO3401A high-side, nRF GPIO enable | switch | 50 × WS2812C-2020 | 300 mA firmware cap on battery, ~150 mA on USB (750 mA all-white) | 100 nF per LED + bulk | firmware, after 3V3 |

## Interface Map

| Interface | From | To | Protocol | Speed | SI constrained | Impedance | Clock source |
|-----------|------|----|----------|-------|----------------|-----------|--------------|
| USB | USB-C D+/D− (through USBLC6) | nRF52840 D+/D− | USB 2.0 FS | 12 Mb/s | no | — | nRF |
| I²C | nRF TWIM | ToF SDA/SCL | I²C | 400 kHz | no | — | nRF |
| LED chain | nRF GPIO (I2S or PWM driven) | ring chain DIN, 33 Ω | WS2812 one-wire | 800 kHz | no | — | nRF |
| PDM | nRF PDM CLK/DIN | MEMS mic | PDM | 1–3 MHz | no | — | nRF |
| IR | nRF PWM / GPIO | IR11-21C via BSS138; IRM-H638T OUT | 38 kHz carrier | — | no | — | nRF |
| NFC | nRF NFC1/NFC2 (P0.09/P0.10) | Molex 146236-0111 flex antenna (2 solder pads) + 2 tuning caps | NFC-A type 2/4 tag | 13.56 MHz | no | — | field |
| SWD | nRF SWDIO/SWDCLK | Tag-Connect TC2030 pads on back | SWD | — | no | — | probe |
| BLE | E73-CX IPEX connector | stick-on 2.4 GHz FPC antenna in the case | BLE 5 | 2.4 GHz | no | module-integrated | nRF |

GPIO assignment is frozen in the `proximity_fear/main.py` docstring (owner; checked by `tests/test_asm01_top.py::test_frozen_pin_map`).

## Board

- **Dimensions:** 50 mm diameter circle plus a USB-C tab at 6 o'clock (12 mm wide, 4.14 mm proud of the circle — the shortest that clears the rings by ≥0.3 mm; user chose 2026-11-15) so the receptacle's through-board shell slots sit outside every LED ring; no holes
- **Layer count:** 4
- **Material:** FR-4
- **Fab house:** JLCPCB, Standard PCBA
- **Substrate class:** `ProximityFearSubstrate` (`JLC04161H_1080`, as socialbadge-ai rev 2). L2: VLED pour in the ring annulus (r ≈ 8–24 mm) + 3V3 pour in the centre disc (r < 8 mm); 3V3 to back-side loads as ≥0.3 mm traces. L3: solid GND.
- **USB-C:** on the 6 o'clock tab; shell slots clear of all Top ring copper/courtyards. Button and JST-PH on the rim, reachable through the case.
- **Courtyards:** no overlaps anywhere; same-side courtyard gap ≥ 0.10 mm (user requirement 2026-11-15; `tests/test_asm01_top.py::test_courtyards_clear_on_each_side`).
- **Front (Top):** three LED rings, ToF in the exact centre, IR TX + IR RX + mic port inside the inner ring. Nothing else.
- **Centre zone (r < 7.5 mm, board-centre frame):** ToF at (0, 0); IR TX at (0, +4.85); IR RX at (−4.5, 0); mic (port) at (+4.5, 0) on Bottom; their decoupling within the same disc. All outside the ToF exclusion cones (DS13805 p.24).
- **Back (Bottom):** E73 module (its IPEX connector reachable for hand assembly), power, USB-C and JST-PH at the edge, user button, SWD pads, NFC antenna pads.
- **Enclosure:** 3D-printed plastic back case; its lip snaps around the 50 mm PCB edge (1 mm copper/parts keepout at the rim). Holds a ~500 mAh flat LiPo (e.g. 503035), the clip / lanyard loop, the NFC antenna and the BLE FPC antenna; USB-C and button reachable through it.
- **Keepouts:** 1 mm edge band for the case lip. No board antenna keepout: both antennas live in the case.
- **Hand-assembled after PCBA:** NFC flex antenna (solder 2 tabs), BLE FPC antenna (snap IPEX), LiPo.

## Object-Hierarchy Decisions

- **LED rings (`circuits/led_rings.py`):**
  - **Shape:** `RING_SPECS: tuple[RingSpec, ...]` with `RingSpec(radius_mm, count, angle_offset_deg, clockwise)` (outer ring runs clockwise so its caps sit inside, clear of the rim); `LEDRings` holds `rings: list[list[WS2812C_2020_V6]]` and matching cap lists.
  - **Owner:** `LEDRings` circuit, fixed in its own frame centred on the ToF.
  - **Derivation:** LED `k` of ring `r` sits at `radius·(cos θ, sin θ)` with θ = offset + 360·k/count, rotated tangent so DO faces the next LED's DI. One chain: inner → middle → outer; each ring's last DO hops radially to the next ring's first DI. Starting spec: (9.5 mm, 10), (15.5 mm, 16), (21.5 mm, 24) = 50 LEDs.

## Design Notes

- nRF52840 runs in normal-voltage mode (VDD = VDDH = 3V3 from the AP2112K) so every 3V3 peripheral shares one rail; nRF VBUS comes from USB VBUS through 4.7 Ω (see below).
- Low-frequency clock is an external 32.768 kHz crystal (Epson FC-135) on the E73's XL1/XL2; the -CX module has none inside.
- NFC antenna is stuck to the inside of the case's back wall, ferrite side toward the battery, so a phone taps the back. Tuning caps are set by measurement on the first boards (~3 µH coil → ~46 pF total at 13.56 MHz).
- The BLE FPC antenna sits on the inside of the case's side or top wall, away from the battery and the ground planes.
- First flash is over SWD (UF2 bootloader); after that the badge is programmed over USB.
- Off = firmware System OFF from the user button: LED rail off, IR receiver supply switched off, ToF in software standby with XSHUT held high (6 µA; XSHUT low would burn 330 µA in its pull-up). Standby ≈ 70 µA typ / ~95 µA at datasheet maxima (AP2112K IQ 55/80 µA dominates) plus unspecified mic and SS14 leakage → ~7–9 months on 500 mAh.
- Charge enable: N-FET in series with the MCP73831 PROG resistor (PROG open = charge disabled), gate pulled up to 3V3 so charging is ON by default; an nRF GPIO pulls it low to stop charging. Firmware stops charging if VBAT sense reads < ~2 V while VBUS is present (reversed pack: q_rev alone only protects without USB) and flashes a warning (user chose 2026-11-15).
- VBUS hot-plug: onsemi SZSMF5.0AT1G TVS at the receptacle (MCP73831 §6.1.1.2). Accepted deviation (user, 2026-11-15): 5.0 V standoff < 5.25 V USB max (VBR ≥ 6.4 V, small leakage); estimated peaks typical cable ≈ 6.5 V VBUS / 6.1 V SYS (inside 7.0 V / 6.5 V abs max), worst-case long cable ≈ 7.1 V / 6.8 V (slightly over) — residual risk accepted for prototypes; an OVP switch IC is the upgrade path.
- Routing intent (rte-01, Warp): XL1/XL2 short, no vias in the crystal area, nothing fast between crystal and module; PDM nets ≥ 1 mm from XL traces; slow nets on E73 pads 8–10 leave east of the crystal; NFC1/NFC2 legs symmetric with no via on one leg only; TVS anode gets its own GND via; VLED ≥ 0.5 mm / power ≥ 0.4 mm / 3V3 ≥ 0.3 mm.
- USB D+/D− carry no SI constraint by design: full speed 12 Mb/s over ~30 mm is electrically short (accepted at Phase 3b, A-05); route side by side over GND.
- nRF VBUS pad gets a 4.7 Ω series resistor ahead of its 4.7 µF (PS p.583; USBLC6 does not clamp below the 5.8 V abs max).
- Mic (bottom-port) is mounted on Bottom so its port hole opens to the front through the board.
- VBAT sense: unswitched 1.5 MΩ / 1.5 MΩ divider + 100 nF into an nRF AIN (≈1.4 µA; > MCP73831's 2 MΩ no-battery threshold); 4.2 V → 2.1 V; SAADC TACQ 40 µs, sample ≤ ~1 Hz.
- ToF VCSEL and IR LED are both 940 nm: firmware never transmits IR while the ToF is ranging.
- WS2812C VDD min is 3.3 V but VLED follows SYS (≈VBAT on battery) down to 3.0 V: firmware switches VLED off below ~3.4 V battery.
- Drive the LED data line low whenever VLED is off (back-power through the DIN diode).
