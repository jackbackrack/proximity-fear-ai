# VL53L4CDV0DH/1 - STMicroelectronics, ToF proximity sensor 1-1300 mm

Source: `datasheets/VL53L4CDV0DH_1.pdf` = ST DS13812 Rev 5, June 2022 (LCSC C3178291 copy; st.com download refused from this host). Pages read: 1, 3, 4, 5, 9, 16, 17, 21, 25, 32
Package: optical LGA12 with liner, 4.40 x 2.40 x 1.0 mm (p.3 Table 1, p.21 Figure 17, p.32 Table 19), thermal pad: no
Absolute maxima that bind this design: AVDD, SCL, SDA, XSHUT, GPIO1 -0.5..3.6 V (p.16 Table 9)

## Pinout
Identical to VL53L4CX (see `VL53L4CXV0DH_1.spec.md`): 1 AVDDVCSEL, 2 AVSSVCSEL, 3 GND, 4 GND2, 5 XSHUT, 6 GND3, 7 GPIO1 (open drain), 8 DNC (float), 9 SDA, 10 SCL, 11 AVDD, 12 GND4 (p.4 Figure 2, Table 2).

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| AVDD caps | 100 nF + 4.7 uF close to AVDDVCSEL/AVSSVCSEL | supply | p.5 Figure 3 |
| XSHUT / GPIO1 pull-ups | 10 k | | p.5 |
| I2C pull-ups | 3.6 k (CL <= 90 pF, 400 kHz) | | p.5 Table 3 |

## Layout, thermal and decoupling requirements
- AVDD 2.6-3.5 V; IOVDD 1.6-3.5 V (p.16 Table 10). I2C address 0x52 (p.3). Range 1-1300 mm (p.1).
- Current (p.17 Table 12): HW standby 5 uA, ranging 22 typ / 24 max mA, peak 40 mA. tBOOT 1.2 ms (p.9).
- PWB solder pattern (p.21 Figure 17): 0.50 x 0.50 pads, 0.80 pitch, 3.70 x 2.10 overall.
- FoV (p.25 Table 16): detection 22/18 deg, collector exclusion cone 25 deg; cover window must cover the exclusion zone.

## Open questions
- Kept as an alternate; the board uses the VL53L4CX (PLAN.md Data Sources).
