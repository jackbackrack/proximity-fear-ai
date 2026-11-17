# ruff: noqa: N999  -- <manufacturer>_<MPN>.py file naming is the project convention
"""ST VL53L4CXV0DH/1 - time-of-flight ranging sensor, up to 6 m, multi-target, optical LGA12.

Source: ST DS13805 Rev 3 (June 2022), saved as
``datasheets/VL53L4CXV0DH_1.pdf`` (LCSC C3178292 copy of ST's PDF; st.com
refused the download from this host).
- p.3 "Table 1. Technical specification": optical LGA12, 4.4 x 2.4 x 1 mm,
  2.6..3.5 V, I2C address 0x52.
- p.4 "Figure 2. VL53L4CX pinout (bottom view)" and "Table 2. VL53L4CX pin
  description": identical pin numbers, names and types to the VL53L4CD
  (DS13812 p.4).
- p.22 "Figure 17. Outline drawing (page 1/4)": body 4.40 +-0.05 x
  2.40 +-0.05; "PWB SOLDER PATTERN" twelve 0.50 x 0.50 pads, 0.80 pitch,
  3.70 x 2.10 overall, pin 1 at the top view's bottom-right -- the same
  drawing values as DS13812 p.21 Figure 17.
- p.33 "Table 19. Order codes": VL53L4CXV0DH/1, optical LGA12, tape and reel.

Because pinout and land pattern match the VL53L4CD, this class reuses the
shared ``VL53L4LGA12`` model (ports, ``LGA12Landpattern``, symbol, pad
mapping) from ``st_VL53L4CD.py``; only the ordering identity differs.
"""

from jitx.circuit import Circuit
from jitx.container import inline
from jitx.sample import SampleDesign
from jitxlib.jlcpcb import LCSCPart

from proximity_fear.components.sensors.st_VL53L4CD import VL53L4LGA12


class VL53L4CXV0DH_1(VL53L4LGA12):
    """Time-of-flight ranging sensor, up to 6 m, 18 deg FoV (DS13805 Rev 3).

    Datasheet facts with no JITX field: AVDD 2.6..3.5 V, IOVDD 1.6..3.5 V
    (p.17 Table 10); HW standby 5 uA typ, ranging 19 mA avg, 40 mA peak
    (p.18 Table 12); tBOOT 1.2 ms max (p.10); detection volume 18..22 deg,
    collector exclusion cone 25 deg (p.26 Table 16), emitter exclusion cone
    29 deg (p.24 Figure 19); cover-glass crosstalk calibration needed if a
    cover window is used (p.8).
    """

    mpn = "VL53L4CXV0DH/1"
    manufacturer = "STMicroelectronics"
    lcsc = LCSCPart("C3178292")
    datasheet = "https://www.st.com/resource/en/datasheet/vl53l4cx.pdf"


Device: type[VL53L4CXV0DH_1] = VL53L4CXV0DH_1


class TestDesign(SampleDesign):
    @inline
    class circuit(Circuit):
        dut = Device()
