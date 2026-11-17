# TS-1187A-B-A-B - XKB, 5.1 x 5.1 mm SMD tactile switch, 1.5 mm actuator

Source: `datasheets/TS-1187A-B-A-B.pdf` (drawing TS-1187A-X-X-X Rev A0); pages read: 1
Package: 4-terminal SMD, 5.1 x 5.1 mm body, part code: force B = 160 gf, height A = 1.5 mm, keystake B = brass, thermal pad: no
Absolute maxima that bind this design: contact 50 mA, 12 V DC; -30..85 C.

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| A | A | contact | A-B internally joined |
| B | B | contact | |
| C | C | contact | C-D internally joined |
| D | D | contact | pressing joins A/B to C/D |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| pull-up | MCU internal or ~10 kOhm | define open state | (application) |

## Layout, thermal and decoupling requirements
PCB layout top view: lands 1.0 x 0.75 mm, x centres +-3.0 (5.0 / 7.0 mm inner/outer), y +-1.875 (3.0 / 4.5 mm). Model: y +-1.85 (EasyEDA, fab-proven). Travel 0.25 mm.

## Open questions
