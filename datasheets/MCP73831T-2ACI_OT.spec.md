# MCP73831T-2ACI/OT - Microchip, single-cell Li-ion/LiPo linear charger

Source: `datasheets/MCP73831T-2ACI_OT.pdf` (DS20001984G); pages read: 1, 3, 11, 15, 17, 18, 22, 25
Package: SOT-23-5 (OT), D 2.70-3.10 x E1 1.30-1.80 mm, thermal pad: no (p.22)
Absolute maxima that bind this design: VDD 7.0 V; all pins -0.3 to VDD+0.3 V (p.3). Operating VDD 3.75-6 V (p.3).

## Pinout
| pin | name | type | note |
|-----|------|------|------|
| 1 | STAT | output, tri-state | charge status: LED or pull-up to host (p.11) |
| 2 | VSS | ground | battery - and input return (p.11) |
| 3 | VBAT | power out | to battery +; drain of internal PMOS (p.11) |
| 4 | VDD | power in | from VBUS (p.11) |
| 5 | PROG | analog | R_PROG to VSS; floating = charger disabled (p.11, p.18) |

## Required external components
| part | value | why | page |
|------|-------|-----|------|
| CIN | >= 4.7 uF VDD-VSS | input bypass | p.11 |
| COUT | >= 4.7 uF VBAT-VSS | CV-loop stability with no battery | p.11, p.18 |
| R_PROG | 5 kOhm -> I_REG = 1000 V / R_PROG = 200 mA | sets fast-charge current | p.15 |
| R_LED + LED | on STAT | status: L = charging, H = complete, Hi-Z = shutdown / no battery | p.15 Table 5-1, p.17 Fig 6-1 |

-2ACI options (p.25): VREG 4.20 V (4.168-4.232, p.3), AC = precondition 10 %, VPTH 66.5 %, termination 7.5 %, recharge 96.5 % of VREG.

## Layout, thermal and decoupling requirements
Place the battery connector close to VBAT/VSS (p.18 sec 6.2). SOT-23-5 enters thermal regulation at high (VDD - VBAT) x I; use copper on VDD/VBAT/VSS as a heat sink (p.18). A TVS on the input is recommended for hot-plug (p.18 6.1.1.2): SZSMF5.0AT1G at the receptacle (comp-06). PROG open = disabled; guaranteed shutdown needs PROG impedance >= 200 kOhm (RPROG min shutdown 70-200 k, p.4); charge-enable FET in series with R_PROG (cir-01).

## Open questions
Land pattern uses JEDEC tolerances inside the p.22 envelope (fab-proven on socialbadge rev 2).
