# USBLC6-2SC6 - STMicroelectronics, 2-line + VBUS USB ESD protection

Source: `datasheets/USBLC6-2SC6.pdf` (Doc ID 11265 Rev 5); pages read: 1, 2, 8, 9, 12
Package: SOT23-6L, D 2.80-3.05 x E 1.50-1.75 mm, thermal pad: no (p.12 Table 4)
Absolute maxima that bind this design: VRM 5.25 V (IRM 150 nA max); VBR >= 6 V VBUS-GND; IEC 61000-4-2 15 kV air/contact (p.2).

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | IO1[0] | I/O | same line as pin 6 (p.1 Fig 1) |
| 2 | GND | ground | |
| 3 | IO2[0] | I/O | same line as pin 4 |
| 4 | IO2[1] | I/O | |
| 5 | VBUS | power | rail clamp reference |
| 6 | IO1[1] | I/O | |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| CBUS | 100 nF VBUS-GND at pin 5 | rail clamp decoupling | p.9 Fig 18 |

Electrical (p.2): VCL 12 V at 1 A, 17 V at 5 A (8/20 us); Ci/o-GND 2.5 typ / 3.5 pF max; VF 1.1 V.

## Layout, thermal and decoupling requirements
Route D+/D- through the part (connector on one pin, MCU on the opposite) (p.8 Fig 14, p.9 Fig 18). Place next to the USB-C connector; short GND. Footprint 0.60 x 1.20 lands, 2.30 inner / 3.50 outer, 0.95 pitch (p.12 Fig 22).

## Open questions
