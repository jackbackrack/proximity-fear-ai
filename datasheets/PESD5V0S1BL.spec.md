# PESD5V0S1BL,315 - Nexperia, 5 V bidirectional ESD diode

Source: `datasheets/PESD5V0S1BL.pdf` (Rev 04, 2009); `datasheets/SOD882_package.pdf`; pages read: PESD 1-3, 5, 11; SOD882 2-3
Package: SOD882 (DFN1006-2), 1.0 x 0.6 x 0.48 mm, thermal pad: no (SOD882 Fig 1 p.2)
Absolute maxima that bind this design: VRWM 5 V; PPP 130 W, IPP 12 A (8/20 us); IEC 61000-4-2 30 kV contact (p.1-3).

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | p1 | cathode 1 | bidirectional, no polarity (Table 3, p.2) |
| 2 | p2 | cathode 2 | |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| none | - | - | - |

Electrical (p.5): IRM 5 nA typ / 100 nA max at 5 V; V(CL)R 10 V at 1 A, 14 V at 12 A; Cd 35 typ / 45 pF max at 0 V (too high for USB D+/D-: use on CC/VBUS/button lines).

## Layout, thermal and decoupling requirements
Reflow footprint (SOD882 Fig 2 p.3): lands 0.4 x 0.7 mm on 0.7 mm centres, resist 0.5 x 0.8, paste 0.3 x 0.6. Place at the connector, short to GND.

## Open questions
