"""cir-01 power circuit connectivity.

Expected connections come from the datasheets / spec notes, not from power.py:
- TYPE-C-31-M-12: CC1/CC2 each 5.1 kOhm to GND (Type-C sink Rd); DP1+DP2 and
  DN1+DN2 tied; SBU unused.
- USBLC6-2SC6 (p.1 Fig 1, p.9 Fig 18): flow-through, connector on pins 1/3,
  host on 6/4; VBUS pin 5 on VBUS with 100 nF; pin 2 GND.
- PESD5V0S1BL on each CC to GND.
- VBUS surge TVS (comp-06, MCP73831 p.18 sec 6.1.1.2): cathode on a J1 VBUS
  pad, anode on GND.
- MCP73831 (p.11, p.15): VDD on VBUS, VBAT on battery, VSS GND, R_PROG
  (1000 V / 200 mA = 5 kOhm) to VSS through the charge-enable N-FET (PROG
  open = disabled, p.13 / p.18), gate pulled to 3V3 (on by default) and to the
  chg_en port; 4.7 uF on VDD, 10 uF on VBAT (M-8, >= 4.7 uF after DC bias).
- STAT divider: guaranteed VOH = VDD - 1 V (p.4) at VBUS 4.75 V reads above nRF
  VIH = 0.7 x 3.3495 V (PS p.156); VDD 5.25 V reads below VDD + 0.3 V at
  3V3 = 3.2505 V (PS p.612), with 1 % resistors.
- Load sharing (Microchip AN1149 Fig 2 p.2, Figs 5-7): SS14 anode on VBUS,
  cathode on SYS; AO3401A drain on VBAT, source on SYS (body diode VBAT->SYS),
  gate on VBUS, gate-to-GND pull-down that discharges <= 9.5 uF of VBUS
  caps in well under 0.2 s and stays inside 0402 dissipation at 5.25 V
  (A-08: 10 kOhm). SYS is a port (LED switch) separate from VBAT, which feeds
  only the cell (AN1149 p.5).
- AP2112K-3.3 (p.2): VIN and EN on SYS, VOUT 3V3, 1 uF each side, NC open.
- AO3401A reverse battery: D to J2 pin 1, S to VBAT, G to GND.
- VBAT sense: two equal resistors totalling > 2 MOhm at -1 % (MCP73831 ZNO_BAT,
  p.4) and at most 800 kOhm source impedance (PS SAADC TACQ 40 us, p.397),
  100 nF at the midpoint.
"""

from jitx.inspect import visit
from jitx.net import Net, Port
from jitx.test import TestCase
from jitx.units import kohm, nF, ohm, uF

from proximity_fear.circuits.power import PowerSupply, TestDesign


def _leaves(port: Port) -> list[tuple[str, Port]]:
    found = [(str(trace.path), p) for trace, p in visit(port, Port) if not list(visit(p, Port))[1:]]
    return found or [("", port)]


class _Connectivity:
    """Union-find over every net (ShortTraces included) under a circuit."""

    def __init__(self, circuit: PowerSupply) -> None:
        self.parent: dict[int, int] = {}
        for _, net in visit(circuit, Net):
            members = [m for m in list(net) if isinstance(m, Port)]
            if not members:
                continue
            groups = [_leaves(m) for m in members]
            first = dict(groups[0])
            for g in groups[1:]:
                for key, leaf in g:
                    self.union(first[key], leaf)

    def find(self, p: Port) -> int:
        k = id(p)
        self.parent.setdefault(k, k)
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def union(self, a: Port, b: Port) -> None:
        self.parent[self.find(a)] = self.find(b)

    def same(self, a: Port, b: Port) -> bool:
        return self.find(a) == self.find(b)


class PowerTest(TestCase):
    def setUp(self) -> None:
        # Passives resolve inside a design (its defaults and event context).
        self.c: PowerSupply = TestDesign().circuit.power
        self.k = _Connectivity(self.c)

    def assertJoined(self, *ports: Port) -> None:
        for p in ports[1:]:
            self.assertTrue(self.k.same(ports[0], p), f"{p} not joined to {ports[0]}")

    def assertApart(self, a: Port, b: Port) -> None:
        self.assertFalse(self.k.same(a, b), f"{a} shorted to {b}")

    def test_usb_c(self) -> None:
        u = self.c.usb_c
        gnd = u.j1.GND[0]
        self.assertJoined(u.j1.DP1, u.j1.DP2, u.esd.IO2[0])
        self.assertJoined(u.j1.DN1, u.j1.DN2, u.esd.IO1[0])
        self.assertJoined(u.esd.IO2[1], self.c.usb.data.p)
        self.assertJoined(u.esd.IO1[1], self.c.usb.data.n)
        self.assertApart(u.esd.IO2[0], self.c.usb.data.p)  # flow-through, no shortcut
        self.assertApart(u.j1.DP1, u.j1.DN1)
        self.assertJoined(u.j1.VBUS[0], u.j1.VBUS[1], u.esd.VBUS, u.c_esd_vbus.p1, self.c.vbus.Vp)
        self.assertJoined(gnd, *u.j1.GND, *u.j1.EH, u.esd.GND, u.c_esd_vbus.p2, self.c.vbus.Vn)
        self.assertEqual(u.c_esd_vbus.capacitance, 100 * nF)
        for cc, r, esd in ((u.j1.CC1, u.r_cc1, u.esd_cc1), (u.j1.CC2, u.r_cc2, u.esd_cc2)):
            self.assertEqual(r.resistance, 5.1 * kohm)
            self.assertJoined(cc, r.p1, esd.p1)
            self.assertJoined(gnd, r.p2, esd.p2)
            self.assertApart(cc, gnd)
        self.assertApart(u.j1.CC1, u.j1.CC2)
        # Surge TVS at the receptacle, unidirectional: cathode VBUS, anode GND.
        self.assertJoined(u.tvs.K, u.j1.VBUS[0], self.c.vbus.Vp, self.c.charger.u1.VDD)
        self.assertJoined(u.tvs.A, gnd)
        self.assertApart(u.tvs.K, u.tvs.A)

    def test_charger(self) -> None:
        ch = self.c.charger
        u1 = ch.u1
        self.assertJoined(u1.VDD, ch.c_vdd.p1, self.c.vbus.Vp, self.c.usb_c.j1.VBUS[0])
        self.assertJoined(u1.VBAT, ch.c_vbat.p1, self.c.vbat.Vp, self.c.battery.q_rev.S)
        self.assertJoined(u1.VSS, ch.c_vdd.p2, ch.c_vbat.p2, ch.q_en.S, self.c.usb_c.j1.GND[0])
        # PROG -> R_PROG -> N-FET drain; source GND: opening the FET floats PROG.
        self.assertJoined(u1.PROG, ch.r_prog.p1)
        self.assertJoined(ch.r_prog.p2, ch.q_en.D)
        self.assertApart(u1.PROG, u1.VSS)
        self.assertApart(ch.r_prog.p2, u1.VSS)
        # Gate: pull-up to 3V3 (charging on by default) and the chg_en port.
        self.assertJoined(ch.q_en.G, ch.r_en_pu.p1, self.c.chg_en)
        self.assertJoined(ch.r_en_pu.p2, self.c.v3v3.Vp)
        self.assertApart(ch.q_en.G, self.c.v3v3.Vp)
        self.assertApart(ch.q_en.G, u1.VSS)
        self.assertEqual(ch.r_en_pu.resistance, 100 * kohm)
        # 1000 V / (R_PROG + BSS138 RDS(on) <= 5 Ohm, p.3 Fig. 6) within 1 %
        # of the 200 mA in the Power Tree.
        r_prog = ch.r_prog.resistance / ohm
        for rds in (0.0, 5.0):
            self.assertAlmostEqual(1000 / (r_prog + rds), 0.200, delta=0.002)
        self.assertGreaterEqual(ch.c_vdd.capacitance, 4.7 * uF)
        self.assertGreaterEqual(ch.c_vbat.capacitance, 10 * uF)
        # LED lit while STAT sinks: anode side from VBUS through R, cathode on STAT.
        self.assertJoined(u1.STAT, ch.led.K, ch.r_stat_top.p1)
        self.assertJoined(ch.led.A, ch.r_led.p2)
        self.assertJoined(ch.r_led.p1, u1.VDD)
        self.assertApart(u1.STAT, self.c.v3v3.Vp)
        self.assertJoined(self.c.chg_stat, ch.r_stat_top.p2, ch.r_stat_bot.p1)
        self.assertJoined(ch.r_stat_bot.p2, u1.VSS)
        top = ch.r_stat_top.resistance / ohm
        bot = ch.r_stat_bot.resistance / ohm
        lo = bot * 0.99 / (bot * 0.99 + top * 1.01)
        hi = bot * 1.01 / (bot * 1.01 + top * 0.99)
        self.assertGreater((4.75 - 1.0) * lo, 0.7 * 3.3 * 1.015)  # VOH min vs VIH at 3V3 max
        self.assertLess(5.25 * hi, 3.3 * 0.985 + 0.3)  # VOH max vs abs max at 3V3 min

    def test_power_path_and_ldo(self) -> None:
        p, ldo = self.c.path, self.c.ldo
        self.assertJoined(p.d_usb.A, self.c.vbus.Vp)
        self.assertJoined(p.q_bat.D, self.c.vbat.Vp, self.c.battery.q_rev.S)
        self.assertJoined(p.d_usb.K, p.q_bat.S, ldo.u1.VIN, ldo.u1.EN, ldo.c_in.p1, self.c.sys.Vp)
        self.assertApart(self.c.charger.q_en.G, self.c.sys.Vp)
        self.assertJoined(self.c.sys.Vn, self.c.vbus.Vn)
        self.assertApart(self.c.sys.Vp, self.c.vbat.Vp)
        self.assertApart(self.c.sys.Vp, self.c.charger.u1.VBAT)
        self.assertJoined(p.q_bat.G, self.c.vbus.Vp, p.r_pull.p1)
        self.assertJoined(p.r_pull.p2, self.c.vbus.Vn)
        self.assertEqual(p.r_pull.resistance, 10 * kohm)
        r = p.r_pull.resistance / ohm
        self.assertLess(r * 9.5e-6, 0.2)  # VBUS discharge tau (s)
        self.assertLess(5.25**2 / r, 0.0625 / 4)  # 0402 1/16 W, 4x margin
        self.assertLess(5.25 / r, 0.001)  # under 1 mA drawn from VBUS
        self.assertApart(p.d_usb.K, self.c.vbus.Vp)
        self.assertApart(p.q_bat.S, self.c.vbat.Vp)
        self.assertApart(p.q_bat.G, p.q_bat.S)
        self.assertApart(p.q_bat.G, self.c.vbus.Vn)
        self.assertJoined(ldo.u1.VOUT, ldo.c_out.p1, self.c.v3v3.Vp, ldo.tp_3v3.p1)
        self.assertApart(ldo.u1.VOUT, ldo.u1.VIN)
        self.assertJoined(ldo.u1.GND, ldo.c_in.p2, ldo.c_out.p2, self.c.v3v3.Vn, self.c.tp_gnd.p1)
        self.assertEqual(ldo.c_in.capacitance, 1 * uF)
        self.assertEqual(ldo.c_out.capacitance, 1 * uF)
        self.assertNotIn(ldo.u1.NC, [p for _, n in visit(self.c, Net) for p in list(n)])

    def test_battery(self) -> None:
        b = self.c.battery
        self.assertJoined(b.j2.PIN1, b.q_rev.D)
        self.assertJoined(b.q_rev.S, self.c.vbat.Vp, b.r_sense_top.p1, b.tp_vbat.p1)
        self.assertJoined(b.q_rev.G, b.j2.PIN2, self.c.vbat.Vn)
        self.assertApart(b.j2.PIN1, self.c.vbat.Vp)
        self.assertJoined(self.c.vbat_sense, b.r_sense_top.p2, b.r_sense_bot.p1, b.c_sense.p1)
        self.assertJoined(b.r_sense_bot.p2, b.c_sense.p2, b.j2.PIN2)
        top = b.r_sense_top.resistance / ohm
        bot = b.r_sense_bot.resistance / ohm
        self.assertEqual(top, bot)  # VBAT / 2: 4.2 V -> 2.1 V
        self.assertGreater((top + bot) * 0.99, 2.0e6)  # ZNO_BAT >= 2 MOhm at -1 %
        self.assertLessEqual(top * bot / (top + bot), 800e3)  # SAADC TACQ 40 us bound
        self.assertEqual(b.c_sense.capacitance, 100 * nF)

    def test_test_points(self) -> None:
        self.assertJoined(self.c.usb_c.tp_vbus.p1, self.c.vbus.Vp)
        self.assertJoined(self.c.battery.tp_vbat.p1, self.c.vbat.Vp)
        self.assertJoined(self.c.ldo.tp_3v3.p1, self.c.v3v3.Vp)
        self.assertJoined(self.c.tp_gnd.p1, self.c.vbus.Vn, self.c.vbat.Vn)

    def test_rails_distinct(self) -> None:
        rails = [self.c.vbus.Vp, self.c.vbat.Vp, self.c.sys.Vp, self.c.v3v3.Vp, self.c.vbus.Vn]
        for i, a in enumerate(rails):
            for b in rails[i + 1 :]:
                self.assertApart(a, b)
