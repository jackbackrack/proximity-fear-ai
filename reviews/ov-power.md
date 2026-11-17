# ov-power: outside-voice review of the power and battery-charging circuit

Scope: `proximity_fear/circuits/power.py` and `LEDSwitch` in `proximity_fear/circuits/led_rings.py`, checked against the PDFs in `datasheets/`.
The `.spec.md` notes and code comments were not trusted; every figure below was re-derived from a PDF.
Page numbers are the printed datasheet page (MCP73831 "DS20001984G-page N", AO3401A "Page N of 5").

## Findings

**WARNING — power.py:61-63 (R_STAT_TOP/R_STAT_BOT, 100k/150k) — the divider's logic-high margin is checked against the typical VOH, not the guaranteed one. At the guaranteed VOH (VDD−1 V, tested at 4 mA) and VBUS = 4.75 V, the divider gives 3.75 V × 0.6 = 2.25 V, below the 2.31 V VIH (0.7 × 3.3 V) that the comment assumes for the nRF. The comment's 2.61 V uses VOH = VDD−0.4 V, which is the typical value. A "charge complete" read could therefore fail on a worst-case part at low VBUS. Real VOH should sit near the typical value because the load is only about 15 µA, so this is a marginal worst-case issue, not a certain failure. A ratio of 0.62–0.66 (for example 100k/180k, or 91k/150k) satisfies both limits: at VDD = 5.25 V the divider output stays under the 3.6 V GPIO absolute maximum, and at the guaranteed VOH it stays above VIH.** — evidence: MCP73831 p.4 Status Indicator table, "VOH typ VDD−0.4 V, VDD−1 V (ISOURCE = 4 mA)"; p.3 absolute maximum STAT ≤ VDD+0.3 V. The nRF VIH and abs-max figures come from the code comment only (nRF PS is outside the packet).

**WARNING — power.py:269-292 (Battery.q_rev, gate to GND) — the reverse-battery FET does not protect against a miswired cell while VBUS is present.**
- With USB plugged in, VBAT is held near 4.2 V by the charger.
- A reversed cell puts about −3.7 V on the FET drain, so VGS = GND − VBAT = −4 V and the channel turns on.
- The charger then forces current (preconditioning, about 20 mA, because VBAT is below VPTH) into the reversed cell. VBAT settles near |VGS(th)| (about 1 V) and the FET dissipates roughly 0.1 W.
- STAT would also read "charging".
- The FET only protects when no other source holds VBAT up. The docstring's claim ("a reversed cell leaves VGS ≥ 0 and the body diode reverse-biased") holds only on battery alone.
- PH2-2P pin polarity is not defined on the drawing, so a reversed pack is a realistic fault.
- Mitigation: add a series element in the cell lead that blocks regardless of VBAT (for example a P-FET with gate tied through a divider to the cell side, or an ideal-diode controller), or accept the risk and document it.
- Evidence: inference from the topology plus AO3401A VGS(th) −0.5 to −1.3 V (p.2) and MCP73831 preconditioning behaviour (p.13 §4.4; 10 % ratio per the "AC" option, p.25).

**WARNING — power.py:34-55 and UsbC (no VBUS surge protection) — hot-plug overvoltage is not handled.**
- VBUS reaches MCP73831 VDD (absolute maximum 7.0 V, p.3) directly, and AP2112K VIN (absolute maximum 6.5 V, p.3) through the SS14.
- The only VBUS clamp is the USBLC6 pin 5 diode (VBR ≥ 6 V at 1 mA, USBLC6 p.2). The ST datasheet rates it for ESD only, not hot-plug energy.
- About 9.5 µF of low-ESR ceramic on VBUS (the code's own tally) plus cable inductance can ring to roughly 2× 5 V on attach.
- Microchip says input overvoltage protection "must be used" for hot-pluggable USB, and recommends a transzorb at the connector (MCP73831 p.18 §6.1.1.2).
- The Q_bat gate sits on VBUS and is safe (±12 V).
- Fix: add a surge-rated 5.x V TVS on VBUS at the connector, or a series damping element.
- Evidence: MCP73831 p.18 §6.1.1.2, AP2112 p.3, USBLC6 p.2. The magnitude of the overshoot is inference.

**NOTE — power.py:76 and Battery docstring (R_VBAT_SENSE, 1 MΩ + 1 MΩ) — "meets > 2 MΩ" is not strictly met.**
- The datasheet requires the VBAT impedance before the cell is connected to be greater than 2 MΩ (p.13 §4.2; ZNO_BAT min 2 MΩ, p.4).
- The two 1 % resistors give 1.98–2.02 MΩ, and Q_rev, Q_bat and cap leakage add in parallel.
- Consequence if the no-battery condition is mis-detected: the charger sits in CV with STAT low (charge LED lit) when no cell is fitted. This is cosmetic, not a hazard.
- Fix if you want margin: use 1.5 MΩ + 1.5 MΩ (3 MΩ total). The SAADC source impedance becomes 750 kΩ with the 100 nF filter.

**NOTE — power.py:55-58 (R_PROG = 4.99 kΩ) — the charge current is correct but fixed, and the USB budget has no headroom for the LEDs.**
- The IREG formula is right: 1000 V / 4.99 kΩ = 200 mA, tolerance about ±10 % (MCP73831 p.15 §5.1.2; p.3 shows 90–110 mA at 10 kΩ). That is 0.4 C for a 500 mAh cell.
- The −2ACI option set (VREG 4.20 V, 10 % preconditioning, VPTH 66.5 %, ITERM 7.5 %, recharge threshold 96.5 %) is correct for this cell (p.25 option "AC").
- The charger starts at the full 200 mA on attach. The Type-C default is 500 mA, but a USB 2.0 device is only entitled to 100 mA before enumeration (AN1149 p.6 note).
- Worst case on a 500 mA port is 200 mA charge + 130 mA 3V3 + 150 mA firmware-capped LEDs ≈ 480 mA, which is tight. 750 mA is the full-white value.
- Evidence: MCP73831 p.15, p.25; AN1149 p.6.

**NOTE — MCP73831 thermal — thermal regulation will engage at the start of the CC phase.**
- At VDD = 5.25 V and VBAT just above VPTH (2.79 V), dissipation is (5.25−2.79) × 0.22 A ≈ 0.54 W. With θJA 130–230 °C/W (SOT-23-5, p.5) the junction would exceed 105 °C, so current folds back.
- This is self-protecting but lengthens charge time. The copper area under the charger matters.
- Evidence: MCP73831 p.5, p.14 §4.6 and Fig. 4-2.

**NOTE — power.py:180-183 (charger caps) — 4.7 µF is the minimum for both CIN and COUT, with no DC-bias margin.**
- The datasheet says "minimum 4.7 µF" on VBAT (p.18 §6.1.1.4) and on VDD (p.11 §3.1).
- The code requests exactly 4.7 µF X5R at 16 V. An X5R 0603 loses roughly 30–50 % at 4.2–5 V bias, so effective capacitance may be 2.5–3.5 µF. That is at or below the datasheet figure, though the datasheet describes it only as "recommended".
- Consider 10 µF (or two parallel) on VBAT. The same applies to the 1 µF LDO caps (AP2112 p.2 Note 4 asks for 1 µF X5R/X7R).
- Evidence: MCP73831 p.11, p.18; inference for the derating figure.

**NOTE — power.py:75 (R_GATE_PULL, 10 kΩ) and PowerPath docstring — SYS dips by one body-diode drop during both unplug and plug-in handover.**
- On unplug, SYS rides VBAT − VSD (0.7 typ, 1.0 max, AO3401A p.2) for tens of ms. At a 3.4 V battery that is about 2.4–2.7 V, so 3V3 sags to about 2.4–2.6 V. The nRF minimum of 1.7 V is fine, but a 2.6 V-minimum ToF sensor and the WS2812C (3.3 V minimum) will glitch if active.
- On plug-in there is a window with VBUS between roughly VBAT − 0.9 V and VBAT + VF where neither Q_bat nor the SS14 conducts, so SYS also rides the body diode for the VBUS rise time (about ≤ 1 ms).
- AN1149 recommends 100 kΩ (p.5). The 10 kΩ choice is defensible and consistent with the body-diode analysis in the code.
- Evidence: AO3401A p.2 (VSD); AN1149 p.5; inference.

**NOTE — UsbC (CC1/CC2 with PESD5V0S1BL, power.py:130-137) — CC clamp margin against 5.5 V is thin.**
- The PESD5V0S1BL is rated VRWM = 5 V with V(BR) min 5.5 V (p.3 Table 9).
- A Type-C CC pin can see VCONN (5 V nominal, 5.5 V max) from an active cable on the second CC pin.
- Leakage at 5 V is still ≤ 100 nA, so this works in practice.
- Capacitance is 35–45 pF, far under the Type-C 600 pF CC limit.
- Evidence: PESD5V0S1BL Table 9; the Type-C VCONN figure is inference.

**NOTE — power.py:58 and :61 — code-comment page references are off by one.** MCP73831 ISINK, VOL and VOH are on p.4 (the code says p.3); the STAT absolute maximum (VDD+0.3 V) is on p.3.

**NOTE — power.py:10-15 and :121 (USB D+/D- direct to the nRF, no series resistors).** The nRF PS is outside this packet; this was not verified.

## Checked and consistent with the PDFs

**Charger and cell path**
- R_PROG gives 200 mA (MCP73831 p.15); the SOT-23-5 pinout matches Table 3-1 (p.11; STAT 1, VSS 2, VBAT 3, VDD 4, PROG 5), and the component model matches.
- STAT is tri-state: L when charging, H at complete, Hi-Z for shutdown and no battery (Table 5-1, p.16).
- The LED is anchored on VBUS, so STAT stays inside −0.3 to VDD+0.3 V in all states (p.3). The Hi-Z case reads about 1.9–2.0 V through the LED path, which is between VIL and VIH, as the code says. Firmware gating on VBUS is needed.
- The divider's 3.15 V maximum at 5.25 V is under the 3.6 V GPIO limit.

**Load-sharing**
- AO3401A orientation matches AN1149 Figs 5–7, p.5 (RPULL pull-down, Q1 on the cell-to-load path, D1 from VIN to the load).
- The body diode (drain to source, anode on the drain) conducts VBAT to SYS and blocks SYS to VBAT.
- With USB present, VGS = VF(SS14) > 0, so Q_bat is off. The body-diode headroom arithmetic holds: SYS ≥ 4.75 − 0.55 = 4.20 V against VBAT ≤ 4.232 V (SS14 VF max 0.55 V at 1 A, SS14 p.1).
- The charger output feeds only the cell, the sense divider and the Q_bat drain. This is the AN1149 p.5 recommendation (§"Connecting the System Load to the Battery"), and the LED switch hangs off SYS.

**Reverse-battery FET without USB**
- Q_rev orientation: drain to J2 pin 1, source to VBAT, gate to GND. A correct cell conducts through the body diode, then through the channel (VGS = −VBAT); a reversed cell leaves VGS ≈ 0 and the body diode reverse-biased (without USB present).
- Rds(on) ≤ 85 mΩ at −2.5 V, ≤ 60 mΩ at −4.5 V (p.2); VGS(th) −0.5 to −1.3 V.

**LDO**
- AP2112K-3.3: SOT-25 pinout (VIN 1, GND 2, EN 3, NC 4, VOUT 5, p.1); EN has a 3 MΩ pull-down and VIH 1.5 V min, so tying it to VIN is correct; the NC pin is left open.
- Dropout at 3.3 V is 125 mV typ, 200 mV max at 300 mA (p.4 table), so at 130 mA the 3.4–3.55 V cut-off estimate is sound.
- Dissipation worst case is (4.95 − 3.3) × 0.13 ≈ 0.21 W; with θJA 184 °C/W (p.3) that is about +40 °C.
- VIN is 2.5–6.0 V recommended (p.3), and SYS stays at or below about 4.95 V.

**LEDSwitch**
- Topology: P-FET source on SYS and drain on VLED, so the body diode blocks SYS to VLED when off.
- Gate: 100 kΩ pull-up (keeps VGS = 0), BSS138 plus 10 kΩ pull-down, and a 10 nF Miller cap. On-state VGS = −0.91 × SYS = −3.1 V at 3.4 V and −4.45 V at 4.9 V, inside ±12 V (AO3401A p.1) and above VGS(th).
- The BSS138 turns on from 3.3 V: VGS(th) max 1.5 V, the load is under 0.5 mA, ±20 V gate rating (BSS138 p.2).
- Soft start re-derived: dV/dt = (SYS − |Vplateau|)/(10 kΩ × 10 nF), about 14–39 V/ms.
  - Inrush into ≤ 15 µF is about 0.2–0.6 A for roughly 0.13–0.2 ms.
  - That pulse sits well inside the AO3401A SOA (Fig. 9, p.4: about 10 A at 100 µs and 2.5 V; Fig. 10: tens of watts for ms).
- The slow turn-off (gate recharged through 100 kΩ, about 3–4 ms) dissipates at most about 0.3–1 W for ms against 15 W+ single-pulse capacity.
- The 10 nF X7R is rated 10 V and sees at most 4.9 V.
- Battery-insertion inrush (about 15 A for ~10 µs) is within IDM = −27 A (p.1).

**USB-C and ESD**
- The pad-to-signal map matches the drawing's pin table: SBU2, CC1, DN2, DP1, DN1, DP2, SBU1, CC2 at 0.5 mm pitch; VBUS at ±2.4 mm and GND at ±3.2 mm, both against the drawing.
- Rd = 5.1 kΩ 1 % on both CC pins (sink-only), with ESD on the connector side of Rd.
- D+/D- from both rows are tied together and routed through the USBLC6, which is wired as pass-through pairs (pin 1 to 6, pin 3 to 4, pin 5 VBUS, pin 2 GND), with 100 nF on pin 5 (USBLC6 Figs 17-18).
- SBU pins are no-connect.

**Footprint and part sanity**
- AO3401A and BSS138 pad assignment: G and S on one side, D alone opposite; the pin-1 dot sits at G; pitch 0.95 mm and pad width 0.6 mm are within the AOS SOT-23 package outline (e = 0.95, b = 0.30–0.50).
- BSS138 maps G=1, S=2, D=3, which matches the Diodes SOT-23 drawing.

## Not checked
- Anything outside the listed files and PDFs: the nRF pin voltages, WS2812C limits, layout and placement geometry, and the `parts.lock.json` sourcing.
- The SS14 land-pattern orientation fix (`orientation=0.0`) was read but not verified against a fab file.
