# 2.0-2P WT (PH2-2P) - SHOU HAN, JST-PH-compatible 2.0 mm 2-pin SMD right-angle header

Source: `datasheets/PH2-2P.pdf` (2002LT series drawing Rev 1.00 + spec); pages read: 1, 3, 4
Package: SMD right-angle, housing 7.9 x 6.2 x 5.4 mm, thermal pad: no (p.1)
Absolute maxima that bind this design: 2 A, 250 V AC/DC rated; -25..85 C; wire AWG 28-22 (p.3-4).

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | PIN1 | power | battery lead (polarity set in circuit; check the cell's lead order) |
| 2 | PIN2 | power | battery lead |
| nail | MOUNT1 | mechanical | solder tab; tie to GND or leave |
| nail | MOUNT2 | mechanical | solder tab |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| none | - | - | - |

## Layout, thermal and decoupling requirements
Recommended PCB layout (p.1): signal lands 1.0 x 3.5 mm on 2.0 mm; nails 1.5 x 3.5 mm, 1.1 mm outboard of the outer signal land; 2.2 mm between rows (5.7 mm centre-to-centre). Mating side faces the signal-land edge; keep the board edge on that side clear for the plug.

## Open questions
Drawing does not number the pins; the LiPo lead order (red/black) must be matched to PIN1/PIN2 in the power circuit.
