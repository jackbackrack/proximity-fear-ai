# TYPE-C-31-M-12 - Korean Hroparts, 16-pin USB 2.0 Type-C receptacle

Source: `datasheets/TYPE-C-31-M-12.pdf` (HRO drawing Rev A, 2020-12-08, 1 sheet); pages read: 1
Package: mid-mount SMD + 4 THT shell legs, 8.94 x 7.35 mm, thermal pad: no
Absolute maxima that bind this design: 5 A / 20 V rating; -30..80 C (drawing notes 4-5).

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| A1/B12, B1/A12 | GND[0], GND[1] | ground | |
| A4/B9, B4/A9 | VBUS[0], VBUS[1] | power | |
| A5 / B5 | CC1 / CC2 | analog | each needs its own 5.1 kOhm to GND (USB-C sink; not on this drawing) |
| A6 / B6 | DP1 / DP2 | USB D+ | tie together |
| A7 / B7 | DN1 / DN2 | USB D- | tie together |
| A8 / B8 | SBU1 / SBU2 | - | leave unconnected |
| shell | EH[0..3] | shield | plated slots; tie to GND |
| holes | NC[0..1] | mechanical | locating holes, no net |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| Rd x2 | 5.1 kOhm CC1/CC2 to GND | sink advertisement (USB Type-C spec, not this drawing) | - |
| ESD | USBLC6-2SC6 on D+/D-/VBUS | protection | see USBLC6 note |

## Layout, thermal and decoupling requirements
Recommended layout (component side): signal lands on 0.50 mm pitch over 3.50 mm, VBUS at 4.80 mm, GND at 6.40 mm; shell slots on 8.65 mm, 4.18 mm front-to-rear; locating holes 0.60 mm on 5.78 mm; PCB edge reference shown. Model pads match; holes are 0.75 mm (EasyEDA, fab-proven). Slot pads carry top and bottom mask openings (socialbadge 0b6f855). Place at -180/0/90 deg exactly so gerber slots stay standard obrounds.

## Open questions
