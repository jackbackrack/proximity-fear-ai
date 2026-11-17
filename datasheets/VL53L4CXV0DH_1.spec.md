# VL53L4CXV0DH/1 - STMicroelectronics, ToF ranging sensor up to 6 m, multi-target

Source: `datasheets/VL53L4CXV0DH_1.pdf` = ST DS13805 Rev 3, June 2022 (LCSC C3178292 copy; st.com unreachable here). The task named DS13110; the VL53L4CX datasheet is DS13805. Pages read: 3-5, 8, 10, 17-19, 22, 24, 26, 33
Package: optical LGA12, 4.40 x 2.40 x 1.0 mm (p.3 Table 1, p.22 Figure 17), thermal pad: no
Absolute maxima that bind this design: AVDD, SCL, SDA, XSHUT, GPIO1 -0.5..3.6 V (p.17 Table 9)

## Pinout
1 AVDDVCSEL (supply), 2 AVSSVCSEL (gnd), 3 GND, 4 GND2, 5 XSHUT (in, active low), 6 GND3, 7 GPIO1 (open-drain interrupt), 8 DNC (leave floating), 9 SDA, 10 SCL, 11 AVDD (supply), 12 GND4 (p.4 Figure 2 bottom view, Table 2)

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| AVDD caps | 100 nF + 4.7 uF, as close as possible to AVDDVCSEL/AVSSVCSEL | supply | p.5 Figure 3 |
| XSHUT pull-up | 10 k (needed if host state unknown; XSHUT must always be driven) | | p.5 |
| GPIO1 pull-up | 10 k; leave GPIO1 open if unused | | p.5 |
| I2C pull-ups | 3.6 k (CL <= 90 pF, 400 kHz), once per bus | | p.5 Table 3 |

## Layout, thermal and decoupling requirements
- AVDD 2.6-3.5 V (2.8 typ); IOVDD 1.6-3.5 V; 3V3 rail is in range. XSHUT high only while AVDD is on (p.17 Table 10 note 1, p.10).
- I2C address 0x52 (8-bit form), up to 1 MHz (p.3 Table 1, Figure 10).
- Current (p.18 Table 12): HW standby 5 uA typ, SW standby 6 uA, ranging 19 typ / 21 max mA, peak 40 mA. tBOOT 1.2 ms max (p.10).
- PWB solder pattern (p.22 Figure 17): 0.50 x 0.50 pads, 0.80 pitch, 3.70 x 2.10 overall, pin 1 bottom-right in top view. Identical to DS13812 p.21, so the VL53L4CD land pattern is reused.
- FoV (p.26 Table 16): detection volume 22 deg at 100 mm, 18 deg at 1 m; collector exclusion cone 25 deg; emitter exclusion cone 29 deg (p.24 Figure 19). Cover window opening must be equal to or wider than the exclusion zone (p.26).
- Cover glass needs crosstalk calibration (p.8).

## Open questions
- The badge has no front cover in ARCHITECTURE.md; if one is added, size its aperture from p.24/p.26 cones.
