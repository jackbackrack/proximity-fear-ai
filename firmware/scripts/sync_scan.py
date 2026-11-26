"""Listen for Proximity Fear badges' SYNC broadcasts (manufacturer 0xFFFF, 'PF' v1).
usage: sync_scan.py SECONDS"""
import asyncio, struct, sys, time
from bleak import BleakScanner

def on_adv(dev, adv):
    d = adv.manufacturer_data.get(0xFFFF)
    if not d or len(d) != 11 or d[:2] != b"PF":
        return
    ver, bid, ph, own, eff = struct.unpack("<BHHHH", d[2:])
    print(f"{time.strftime('%H:%M:%S')} badge {bid:04X} rssi {adv.rssi:4d} "
          f"phase {ph/65535:.2f} own {own/10:.0f} bpm beating {eff/10:.0f} bpm", flush=True)

async def main(secs):
    async with BleakScanner(on_adv):
        await asyncio.sleep(secs)

asyncio.run(main(float(sys.argv[1])))
