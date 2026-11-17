"""Proximity Fear Badge: buildable top-level design (asm-01).

``jitx build proximity_fear.main.ProximityFearBadge``. The circuit, board outline, pours,
placement and net-class tags are in ``proximity_fear.designs.badge``; this module adds the
substrate, the design-level passive defaults and the rule set.

No SI constraints: every interface in ARCHITECTURE.md ``Interface Map`` is "SI constrained:
no" (USB 2.0 FS 12 Mb/s, 400 kHz I2C, 800 kHz LED data, 1-3 MHz PDM, 38 kHz IR, NFC,
SWD), so there is no ``ReferencePlanes`` block and no ``check_si_main.py``.

Firmware rules this board depends on (ARCHITECTURE Design Notes, Phase 3b A-04):

- ``ir_rx_en`` (active low) is driven high or left disconnected (its 100 k pull-up holds
  the IR receiver supply off) before System OFF.
- The ``ir_rx`` input has no pull (internal pull-up off) whenever ``ir_rx_en`` is high, so
  nothing back-powers the unpowered receiver through OUT.
- ToF "off" is software standby with XSHUT held high, not XSHUT low (which burns ~330 uA
  in its 10 k pull-up). Clear the ToF GPIO1 interrupt before entering standby.
- Release ``chg_en`` (input or high; its 100 k pull-up enables charging) before System OFF.
- Stop charging (``chg_en`` low) if VBAT sense reads below ~2 V while VBUS is present.
- VBAT sense on the SAADC: acquisition time TACQ = 40 us (1.5 MOhm + 1.5 MOhm divider).
- On VBUS detect, switch the LED current cap to the USB value (~150 mA, ARCHITECTURE
  Power Tree); back to the battery cap (300 mA) when VBUS goes away.

Frozen GPIO map (M-8 R-03). Each ``require()`` in ``designs/badge.py`` carries a
``restrictions=`` that admits only this pin, so the provider still checks legality (a pin
outside the offered pool leaves the solver with no option: the runtime rejects the design)
and routing and firmware see one assignment. Chosen by placement: fast signals on the
west / centre pads away from XL1/XL2 (pads 11/13); the pads next to the crystal (P0.26
pad 12, P0.06 pad 14, P0.05 pad 15, P0.08 pad 16) stay unused; PDM on the inner-row pads
nearest the Bottom mic's west side; I2C on the inner pads nearest the centre sensors.

====================  ==========  ========  ===================================
Signal                nRF pin     E73 pad   Note
====================  ==========  ========  ===================================
PDM_CLK               P0.04       18        fast pool; AIN2 unused as analog
PDM_DIN               P0.12       20        fast pool
I2C_SDA               P0.07       22        fast pool, 2.2 k pull-up
I2C_SCL               P0.15       28        fast pool, 2.2 k pull-up
LED_DATA              P0.13       33        fast pool, west edge, 33 ohm r_din
IR_TX                 P0.17       30        fast pool (38 kHz PWM)
TOF_XSHUT             P0.20       32        slow
TOF_INT               P0.22       34        slow (ToF GPIO1, open drain)
IR_RX                 P0.24       35        slow (no pull while IR_RX_EN high)
IR_RX_EN              P1.02       38        slow, active low
BUTTON                P1.04       40        slow, internal pull-up, SENSE wake
LED_EN                P0.29       8         slow (east edge, toward the LED switch)
CHG_STAT              P0.31       9         slow
CHG_EN                P1.13       6         slow
VBAT_SENSE            P0.30/AIN6  10        SAADC
====================  ==========  ========  ===================================
"""

import os
from pathlib import Path

from jitx import Design
from jitx.constraints import AnyObject, BinaryDesignConstraint, IsCopper, IsPad, IsTrace, UnaryDesignConstraint
from jitx_warp_integration.layout_placements import layout_placements
from jitxlib.parts import CapacitorQuery, Minimize, ResistorQuery

from .designs.badge import BadgeBoard, BadgeCircuit, GroundTag, PowerTag, Rail3V3Tag, TagConnectTag, VLEDTag
from .substrate import ProximityFearSubstrate

# --- Design rules: JLC04161H-class (JLCPCBRules floor 0.09 mm width / space) ---------------
DEFAULT_TRACE_WIDTH = 0.125  # skill default: JLC04161H-class, above the 0.09 floor
DEFAULT_CLEARANCE = 0.125  # skill default: JLC04161H-class
POWER_TRACE_WIDTH = 0.4  # PLAN asm-01: VBAT / SYS / VBUS >= 0.4 mm (also GND)
VLED_TRACE_WIDTH = 0.5  # PLAN asm-01: VLED >= 0.5 mm; Bogatin 2019 tier: 0.5 mm carries 3 A (750 mA all-white)
RAIL_3V3_TRACE_WIDTH = 0.3  # PLAN asm-01: 3V3 >= 0.3 mm (130 mA peak, ARCHITECTURE Power Tree)
TC2030_PAD_CLEARANCE = 0.508  # TC2030-IDC-NL footprint drawing note 2: 0.020" to any other track

# rte-01: the Warp layout (placements, vias, route sketches), read from the working directory
# (the project root for ``jitx build``) as on socialbadge-ai rev 2.
LAYOUT_FILE = "jitx_export.json"


class ProximityFearBadge(Design):
    """Buildable top level: ``jitx build proximity_fear.main.ProximityFearBadge``."""

    substrate = ProximityFearSubstrate()
    board = BadgeBoard()

    # JLCPCB Standard PCBA (PLAN Requirements Lock): smallest case first among the SMD
    # ceramic / thick-film cases JLC places; 0805 is the largest any circuit needs (the IR
    # LED's 0.125 W resistor). Every circuit's TestDesign verified against these defaults.
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))

    circuit = BadgeCircuit()

    def __init__(self) -> None:
        # Priority ladder: 0 defaults; 1 power / ground width; 2 per-rail widths and the
        # TC2030 pad clearance.
        self.rules = [
            UnaryDesignConstraint(IsTrace).trace_width(DEFAULT_TRACE_WIDTH),
            BinaryDesignConstraint(IsCopper, IsCopper).clearance(DEFAULT_CLEARANCE),
            # skill default: gap = default clearance, 0.2 mm spokes, 4 spokes
            UnaryDesignConstraint(IsPad).thermal_relief(DEFAULT_CLEARANCE, 0.2, 4),
            UnaryDesignConstraint(PowerTag() | GroundTag(), priority=1).trace_width(POWER_TRACE_WIDTH),
            UnaryDesignConstraint(VLEDTag(), priority=2).trace_width(VLED_TRACE_WIDTH),
            UnaryDesignConstraint(Rail3V3Tag(), priority=2).trace_width(RAIL_3V3_TRACE_WIDTH),
            BinaryDesignConstraint(TagConnectTag() & IsPad, AnyObject, priority=2).clearance(TC2030_PAD_CLEARANCE),
        ]
        # rte-01 (socialbadge-ai rev 2 flow): replay the Warp layout when one exists.
        # apply_board_shape=False: BadgeBoard's outline (circle + USB-C tab) always wins over
        # the file's captured shape. Skipped when WARP_LIVE=1: a live Warp session pushes
        # placements through rd.layout, and the runtime rejects place() on anything already
        # placed. With no file the design builds exactly as before (no -input snapshot either).
        if Path(LAYOUT_FILE).exists() and os.environ.get("WARP_LIVE") != "1":
            layout_placements(LAYOUT_FILE, apply_board_shape=False)
