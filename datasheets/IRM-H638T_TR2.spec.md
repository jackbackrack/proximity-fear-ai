# IRM-H638T/TR2 - Everlight, 38 kHz infrared receiver module

Source: `datasheets/IRM-H638T_TR2.pdf` (DMO-0000008 Rev 3, 2025-01-01); pages read: 1, 2, 3, 5, 6
Package: SMD 5.00 x 4.00 x 2.50 mm body, 7.00 mm lead tip to tip, 2.54 mm pitch, R1.5 lens (p.6), thermal pad: no
Absolute maxima that bind this design: Vs 6 V; Topr -20..+80 C (p.3 Absolute Maximum Ratings)

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | GND | ground | lens side |
| 2 | GND | ground | |
| 3 | OUT | output | demodulated, internal pull-up R_PU (p.1 block diagram) |
| 4 | Vcc | power | lens side |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| series resistor in Vcc | 47-220 ohm | supply RC filter | p.2 Application Circuit |
| capacitor Vcc-GND | >= 2.2 uF | supply RC filter | p.2 |
| pull-up on OUT | >= 10 k, optional | | p.2 |

## Layout, thermal and decoupling requirements
- "The RC filter must be connected as close as possible to Vcc and GND pins" (p.2).
- Electrical (p.3, Vcc = 3.0 V): Vs 2.7-5.5 V, Icc 0.4 typ / 0.7 max mA, VH >= Vcc-0.4 V, VL <= 0.5 V at 2 mA sink; reception half angle +-45 deg.
- Recommended soldering pattern (p.6): 1.5 x 1.1 pads, 4.8 mm inner gap, 1.44 mm row gap (centres x +-3.15, y +-1.27).
- Model uses EasyEDA C91447 footprint: 1.5 x 0.9 pads at x +-2.95 (Vcc +2.92), y +-1.27; 0.2 mm inboard of the suggestion, fabbed on socialbadge rev 2.
- Lens faces up: mount on the front with a clear optical path.

## Open questions
- None.
