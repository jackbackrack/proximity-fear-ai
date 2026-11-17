"""NFC tag front end: Molex 1462360111 flex antenna on nRF52840 NFC1/NFC2.

Sources: nRF52840 Product Specification, NFCT chapter ("NFCT antenna
recommendations", "Pin configuration"); Nordic DevZone blog "NFC tag antenna
tuning"; antenna pads ``datasheets/1462360111.spec.md``.

Topology (PS NFCT antenna recommendations): the coil sits across NFC1 and NFC2,
and one tuning capacitor runs from each pin to GND. The two legs are in series
around the loop, so the coil sees

    C' = (C_tune + C_p + C_int) / 2,    f_res = 1 / (2 pi sqrt(L_ant C'))
    =>  C_tune = 2 / ((2 pi f_res)^2 L_ant) - C_p - C_int

with C_tune1 = C_tune2 and the total capacitance on NFC1 and NFC2 matched.
Sanity check against Nordic's own example: L_ant = 2 uH gives 2 / (7.259e15 x
2e-6) = 137.8 pF less ~8 pF = ~130 pF, the PS's "range of 130 pF on each pin".

Starting value for this board (assumptions in the constants below):

- L_ant = 3 uH (third-party listing for the 146236 ferrite antenna; Molex
  publishes no inductance on the drawing).
- C_int = 4 pF (DevZone blog: "C_int is approximately 4 pF").
- C_p = 4 pF per pin: each 2.0 x 3.5 mm antenna land on Bottom over the L3 GND
  plane, 0.0764 mm of 1080 prepreg (er ~3.9) away, is ~3.2 pF; the 0402 land
  and a short trace add ~1 pF.
- 2 / ((2 pi 13.56 MHz)^2 x 3 uH) = 91.8 pF; C_tune = 91.8 - 4 - 4 = 83.8 pF;
  nearest E12 C0G value 82 pF (C' = 45 pF, f_res ~ 13.70 MHz).

L_ant's uncertainty (+/-10 % moves C_tune by ~9 pF) swamps the E-series step,
so the 82 pF parts are a start: the first boards are measured (network-analyser
S11 dip or the blog's voltage-swing sweep) and retuned. If the resonance is
below 13.56 MHz the capacitance goes down, above it up (blog).

Matching (M-8, ov-nfc WARNING): the PS requires the total capacitance on NFC1
and NFC2 to be matched, and a mismatch dC shifts C' by dC / 2. The tuning caps
are queried at <= +/-2 % C0G (resolves to 82 pF +/-1 %, Murata
GRM1555C1H820FA01D, JLCPCB C162123), so the legs differ by <= 1.6 pF
(~0.9 % in f) instead of up to 8 pF at +/-5 %.

Trim footprints (M-8): one do-not-populate 0402 footprint in parallel with each
tuning cap (``TrimFootprints``: ``in_bom = False`` and ``soldered = False``, the
framework's DNP marking -- jitx.component.NonPopulatedComponent docs; the
JLCPCB export skips such parts in both the BOM and the CPL). After measuring
the first boards, a C0G of the needed increment is hand-fitted on both legs
alike (the resonance can only be lowered by adding; raising it means a smaller
main cap). The empty 0402 land adds ~0.1 pF to C_p, the same on both legs. The
two legs are identical: same query for both tuning caps, same trim footprint;
the assembly places them mirror-symmetric.

Pin rules (PS NFCT "Pin configuration"): with UICR NFCPINS.PROTECT = NFC (the
erased default) the pads' field-protection clamp is on and their GPIO function
is off; that is the setting this board uses. Used as GPIO (PROTECT = Disabled)
the chip is not protected against strong NFC fields, the pins have higher
capacitance and leak between each other, so both must be held at the same logic
level; on this board the coil shorts them at DC, so they must never be GPIO.
"""

import math

from jitx import Circuit, Net
from jitx.net import Port
from jitx.sample import SampleDesign
from jitx.units import V, pF
from jitxlib.parts import AtLeast, AtMost, Capacitor, CapacitorQuery, Lock, LockMode, Minimize

from ..components.antennas.nfc_pads import NFCAntennaPads

NFC_CARRIER_HZ = 13.56e6
"""ISO/IEC 14443 / NFC-A carrier."""
ANTENNA_INDUCTANCE_H = 3.0e-6
"""Molex 146236 ferrite antenna, third-party listing (see module docstring)."""
NRF_INTERNAL_CAPACITANCE_F = 4.0e-12
"""C_int per NFC pad, Nordic DevZone "NFC tag antenna tuning"."""
BOARD_PARASITIC_CAPACITANCE_F = 4.0e-12
"""C_p per pin: antenna land over L3 GND plus cap land and trace (estimate)."""
TUNING_CAPACITANCE = 82 * pF
"""Nearest E12 C0G value to ``tuning_capacitance()`` with the constants above."""


def tuning_capacitance(inductance_h: float, frequency_hz: float, c_int_f: float, c_p_f: float) -> float:
    """C_tune per pin (farads) from the nRF52 PS NFCT antenna recommendations."""
    omega = 2 * math.pi * frequency_hz
    return 2 / (omega**2 * inductance_h) - c_p_f - c_int_f


TUNING_TOLERANCE = 0.02
"""Maximum tuning-cap tolerance: keeps the two legs matched (PS NFCT antenna recommendations)."""
TRIM_FOOTPRINT_CAPACITANCE = 10 * pF
"""Nominal value printed on the DNP trim footprints; the fitted value comes from measurement."""


class TrimFootprints(Circuit):
    """One do-not-populate 0402 C0G footprint per NFC leg, in parallel with its tuning cap.

    ``in_bom = False`` / ``soldered = False`` mark every part in this circuit as DNP: the
    land pattern is on the board, nothing is bought or placed by the assembler.
    """

    in_bom = False
    soldered = False

    nfc1 = Port()
    nfc2 = Port()
    gnd = Port()

    def __init__(self) -> None:
        self.c_trim = [
            Capacitor(
                capacitance=TRIM_FOOTPRINT_CAPACITANCE,
                rated_voltage_dc=AtLeast(25 * V),
                temperature_coefficient_code="C0G",
                case="0402",  # a hand-fit land: 0402 regardless of the value finally fitted
            )
            for _ in range(2)
        ]
        self.NFC1 = Net([self.nfc1, self.c_trim[0].p1])
        self.NFC2 = Net([self.nfc2, self.c_trim[1].p1])
        self.GND = Net([self.gnd, *(c.p2 for c in self.c_trim)])


class NFCFrontEnd(Circuit):
    """Antenna pads across NFC1/NFC2, one matched C0G tuning cap per pin to GND, DNP trim lands."""

    nfc1 = Port()
    """To nRF NFC1 (P0.09, E73 pad 41)."""
    nfc2 = Port()
    """To nRF NFC2 (P0.10, E73 pad 43)."""
    gnd = Port()
    """Board GND, the tuning caps' return."""

    def __init__(self) -> None:
        self.antenna = NFCAntennaPads()
        self.c_tune = [
            Capacitor(
                capacitance=TUNING_CAPACITANCE,
                rated_voltage_dc=AtLeast(25 * V),
                temperature_coefficient_code="C0G",
                tolerance=AtMost(TUNING_TOLERANCE),
            )
            for _ in range(2)
        ]
        self.trim = TrimFootprints()
        self.NFC1 = Net([self.nfc1, self.antenna.p1, self.c_tune[0].p1, self.trim.nfc1])
        self.NFC2 = Net([self.nfc2, self.antenna.p2, self.c_tune[1].p1, self.trim.nfc2])
        self.GND = Net([self.gnd, *(c.p2 for c in self.c_tune), self.trim.gnd])


class TestDesign(SampleDesign):
    """The NFC front end alone, at the assembly's defaults for passives."""

    parts_lock = Lock(mode=LockMode.OFF)
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805"], rank=Minimize("case"))
    circuit = NFCFrontEnd()
