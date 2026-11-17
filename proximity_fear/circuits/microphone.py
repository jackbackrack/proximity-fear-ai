"""PDM MEMS microphone: LinkMems LMD3526B261-OFA03 on the nRF52840 PDM peripheral.

Source: LinkMems spec M196 v1.0 via ``datasheets/LMD3526B261-OFA03.spec.md``.

- VDD from 3V3 (1.62-3.6 V, p.4) with 0.1 uF to GND at the pin, as the p.6
  "Measurement Circuit" draws it. That circuit is the only external part list:
  VDD cap and the L/R strap, nothing on CLK or DATA.
- L/R (pin 2) strapped to GND: left channel (p.6). With L/R = GND the mic drives
  DATA after the CLK falling edge and the host samples on the CLK rising edge
  (p.5 timing). Firmware therefore sets the nRF PDM ``MODE.EDGE`` to
  ``LeftRising`` (the nRF default ``LeftFalling`` samples on the falling edge,
  which with this strap would read the Hi-Z half-cycle).
- CLK and DATA go straight to nRF GPIOs (``pdm_clk``, ``pdm_din``). No series
  resistor: the spec does not call for one (p.6 shows none), the trace is a few
  millimetres on a 1-3 MHz clock, and DATA's load limit is 140 pF (p.4), far
  above a short trace plus one nRF input.

Placement: the circuit frame's origin is the acoustic port (the bottom-port hole
inside the GND ring), so the assembly's ``.at(4.5, 0)`` puts the port at
ARCHITECTURE.md's "mic (port) at (+4.5, 0)". The assembly mounts the circuit on
Bottom (Phase 3b A-03: a bottom-port mic hears the front through the port hole),
turned 180 deg about the port; the 0402 sits just past the body edge next to VDD
(pad 4), inside the r < 7.5 mm centre zone.
"""

from jitx import Circuit, Net
from jitx.common import Power
from jitx.net import Port, ShortTrace
from jitx.sample import SampleDesign
from jitx.units import V, nF
from jitxlib.parts import AtLeast, Capacitor, CapacitorQuery, Lock, LockMode, Minimize

from ..components.sensors.linkmems_LMD3526B261 import (
    BODY_LENGTH,
    COLUMN_X,
    LMD3526B261_OFA03,
    PORT_Y,
)

# Component origin is the body centre; shift it so the acoustic port is at (0, 0).
MIC_Y = -PORT_Y
# Decoupling cap: above the body in VDD's column, turned so its pads run along X
# (the resolved 0402's 1.1 mm courtyard side faces the mic) with p1 (3V3) on the
# +X side, under the VDD pad's outer edge. Its courtyard (half-height 0.55) keeps
# COURTYARD_GAP from the mic courtyard (body + 0.25 mm in Y): user board review,
# courtyards never overlap and stay >= 0.10 mm apart (0.02 mm float margin). The
# pads then sit 0.75 mm from the VDD pad.
COURTYARD_GAP = 0.12
CAP_COURTYARD_HALF = 0.55
DECOUPLING_X = COLUMN_X
DECOUPLING_Y = MIC_Y + BODY_LENGTH / 2 + 0.25 + COURTYARD_GAP + CAP_COURTYARD_HALF
DECOUPLING_ROTATE = 270.0  # resolved passives put p1 at local +y; 270 turns it to +x


class Microphone(Circuit):
    """LMD3526B261-OFA03, left channel, 100 nF at VDD."""

    v3v3 = Power()
    """3V3 rail (Vp) and GND (Vn)."""
    pdm_clk = Port()
    """To the nRF PDM CLK pin (nRF output)."""
    pdm_din = Port()
    """To the nRF PDM DIN pin (mic output)."""

    def __init__(self) -> None:
        self.mic = LMD3526B261_OFA03().at(0.0, MIC_Y)
        self.c_vdd = Capacitor(
            capacitance=100 * nF,
            rated_voltage_dc=AtLeast(10 * V),
            temperature_coefficient_code="X7R",
        ).at(DECOUPLING_X, DECOUPLING_Y, rotate=DECOUPLING_ROTATE)

        self.V3V3 = Net([self.v3v3.Vp, self.mic.VDD], name="3V3")
        self.GND = Net([self.v3v3.Vn, self.mic.GND, self.mic.LR, self.c_vdd.p2], name="GND")
        self.c_vdd_st = ShortTrace(self.c_vdd.p1, self.mic.VDD)

        self.PDM_CLK = self.pdm_clk + self.mic.CLK
        self.PDM_DIN = self.pdm_din + self.mic.DATA


class TestDesign(SampleDesign):
    """The microphone circuit alone, at the assembly's defaults for passives."""

    parts_lock = Lock(mode=LockMode.OFF)
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    circuit = Microphone()
