# SZSMF5.0AT1G - onsemi, 5 V 200 W unidirectional TVS (VBUS hot-plug clamp)

Source: `datasheets/SZSMF5.0AT1G.pdf` (onsemi SMF5.0AT1/D Rev. 2, May 2007; fetched from https://pccomponents.com/datasheets/ONSEMI-SMF5.pdf because onsemi.com returns only an HTML index to this host); pages read: 1, 2, 3, 6
Package: SOD-123FL (CASE 498-01), E 2.50-2.90 x D 1.50-1.80 x A 0.90-1.00 mm, HE 3.40-3.80, thermal pad: no (p.6)
Absolute maxima that bind this design: Ppk 200 W (10/1000 us); VRWM 5.0 V; VBR 6.4 / 6.7 / 7.0 V min/nom/max at IT 10 mA; IR <= 400 uA at 5.0 V; VC <= 9.2 V at IPP 21.7 A (p.2-3).

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | K | cathode | polarity band (p.1) -> VBUS |
| 2 | A | anode | -> GND |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| none | - | - | - |

## Layout, thermal and decoupling requirements
Soldering footprint (p.6): two 0.91 x 1.22 mm lands, 2.36 mm inner gap, 4.19 mm outer (3.28 mm centres). Place at the USB-C receptacle VBUS pad with a short, wide return to the GND pins (MCP73831 DS20001984G sec 6.1.1.2 p.18: transzorb "from the V+ input supply connector to the 0V ground reference").

## Selection (comp-06)
Requirement (PLAN comp-06): unidirectional, standoff >= 5.25 V, clamp at hot-plug energies keeping MCP73831 VDD < 7.0 V abs max (DS20001984G p.3) and AP2112K VIN (behind the SS14) < 6.5 V abs max (AP2112K p.3); JLCPCB stocked. Stock from the JLC component API, 2026-11-15.

| candidate | VRWM | VBR @ IT | clamp | JLC | verdict |
|---|---|---|---|---|---|
| onsemi SZSMF5.0AT1G (SOD-123FL) | 5.0 V | 6.4-7.0 V @ 10 mA (tight 9 % spread) | 9.2 V @ 21.7 A (10/1000) -> Rdyn ~0.10 ohm | C5299833, 8 881 | **chosen** |
| Diodes D5V0S1U2WS-7 (SOD-323), DS37701 Rev 1-2 p.2 | 5.5 V | 6.2-7.4 V @ 1 mA | 9 V max @ 5 A, 12 V @ 50 A (8/20) | C1869334, 9 172 | meets standoff; clamps worse at the few-amp hot-plug level (9 V @ 5 A vs ~7.5 V) |
| Diodes D5V0S1UN2LP1610-7 (DFN1610), DS41793 Rev 3-2 p.2-3 | 5.0 V | >= 5.1 V @ 1 mA (no max) | snapback: TLP trigger ~7.7 V at ~5 A, then ~6 V (Fig. 6 p.3) | C1978729, 6 183 | rejected: triggers above 7 V at hot-plug currents |
| TI TVS0500 (WSON-6) | 5.0 V | 7.5-8.4 V @ 1 mA | 9.2 V @ 43 A flat | C609571, 2 712 | rejected: breakdown above both abs maxima |
| SMF6.0A (SOD-123FL) | 6.0 V | 6.67-7.37 V @ 10 mA | 10.3 V @ 19.4 A | C178260 | rejected: VBR max over 7 V |

Hot-plug estimate (scratch model, inference): 5.25-5.5 V step through a cable of 0.5-2 uH / 0.1-0.3 ohm into 9.5 uF on VBUS, the SS14 into 11 uF on SYS (AP2112K 1 uF + LED-switch 10 uF reservoir, cir-03), cell at 4.2 V or absent.
- Typical cable (1 uH, 0.15 ohm): VBUS 6.4-6.5 V, SYS 6.0-6.1 V with any candidate; the SS14 + SYS capacitance does most of the damping and the TVS barely conducts.
- Stress cable (2 uH, 0.1 ohm, 5.5 V source): no TVS 7.7 V / SYS 7.3 V; SZSMF5.0A at VBR max 7.1-7.2 V / SYS 6.8-6.9 V, at VBR min 6.7-6.8 V / 6.4 V; D5V0S1U2WS at VBR max 7.4-7.5 V / 7.1 V.
Why SMF5.0A over the standoff-compliant D5V0S1U2WS: it is the better clamp at every corner (tighter, lower VBR max and lower Rdyn at amps), which is what protects the abs maxima.

## Open questions
- DEVIATION (accepted by the user 2026-11-15; see ARCHITECTURE.md Design Notes): VRWM is 5.0 V, below the 5.25 V standoff the task asks for. IR is guaranteed only at 5.0 V (<= 400 uA); at 5.25-5.5 V the leakage is unspecified but bounded by the 6.4 V VBR minimum (still > 1 V above). It flows only while USB is present (VBUS = 0 on battery, no standby cost). No stocked TVS found meets both VRWM >= 5.25 V and a VBR max <= 7.0 V.
- Residual risk (accepted by the user 2026-11-15 with the deviation above; ARCHITECTURE.md Design Notes): at VBR max on a stress cable VBUS can reach ~7.1-7.2 V and SYS ~6.8-6.9 V (model above), over the MCP73831 7.0 V / AP2112K 6.5 V abs maxima. A guaranteed bound needs an active OVP/load switch or series damping on VBUS, not a TVS alone.
- The SZ ordering code (AEC-Q101, site-controlled variant of SMF5.0AT1G) is confirmed only by the JLCPCB/LCSC record; the 2007 Rev. 2 sheet lists SMF5.0AT1/SMF5.0AT1G. Confirm against the current onsemi revision when reachable.
