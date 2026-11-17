# TC2030-IDC-NL - Tag-Connect, 6-pin no-legs Plug-of-Nails programming cable footprint

Source: `datasheets/TC2030-IDC-NL.pdf` (DWG TC2030-IDC-NL-FP rev B, 12/05/19, tag-connect.com); pages read: 1 (footprint), 2 (cable / plug face). Pinout: `datasheets/TC2030-CTX.pdf` ("6-Pin TC2030 Footprint" table), page 1.
Package: board footprint only (no part on the BOM, note 4 "specify DNL"); 6 contact pads + 3 NPTH alignment holes; plug face 0.39" x 0.240" (9.906 x 6.096 mm, sheet 2); thermal pad: no
Absolute maxima that bind this design: none

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | VCC | power ref | target supply sense for the probe (CTX table) |
| 2 | SWDIO / TMS | bidir | |
| 3 | nRESET | input | target reset |
| 4 | SWCLK / TCK | input | |
| 5 | GND | ground | also GNDDetect |
| 6 | SWO / TDO | output | optional trace |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| none | - | pads only | - |

## Layout, thermal and decoupling requirements
Sheet 1: pads dia 0.0310" (0.787 mm) +/-0.003", 2 x 3 at 0.050" (1.270 mm); pins 1/3/5 bottom row, 2/4/6 top row, pin 1 bottom-left (PCB TOP LAYER view). NPTH dia 0.0390" (0.991 mm) +/-0.003": one 0.050" left of the pin 1/2 column on the centre line, two 0.200" (5.080 mm) to its right at +/-0.040" (1.016 mm). Note 1: no tracks or vias in the shaded area between pad centres. Note 2: no other track within 0.020" (0.508 mm) of any contact pad. Note 3: no solder paste on contact pads. Note 5: TC2030-CLIP may retain the cable from underneath via the alignment pins.

## Open questions
none
