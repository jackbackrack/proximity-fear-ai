#!/bin/sh
# Flash the UF2 bootloader (+ S140 SoftDevice) onto a badge over SWD with a J-Link,
# then check the badge enumerates on USB. The badge must be powered from USB-C.
# usage: firmware/flash_bootloader.sh [hex]   (default: the local bootloader build)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
HEX=${1:-$(ls "$HERE"/Adafruit_nRF52_Bootloader/_build/build-proximity_fear_badge/proximity_fear_badge_bootloader-*_s140_6.1.1.hex | tail -1)}
[ -f "$HEX" ] || { echo "no bootloader hex (build it first, see README)"; exit 1; }
SCRIPT=$(mktemp)
cat > "$SCRIPT" <<JL
connect
mem32 0x10000060 2
erase
loadfile $HEX
mem32 0x10001014 1
r
g
exit
JL
OUT=$(JLinkExe -NoGui 1 -device nRF52840_xxAA -if SWD -speed 4000 -autoconnect 1 -CommanderScript "$SCRIPT" 2>&1)
rm -f "$SCRIPT"
VT=$(echo "$OUT" | grep -o "VTref=[0-9.]*V" | head -1)
ID=$(echo "$OUT" | grep "^10000060 =" | awk '{print $3 $4}')
echo "target power: ${VT:-unknown}   device id: ${ID:-unknown}"
if ! echo "$OUT" | grep -q "Cortex-M4 identified"; then
  echo "FAIL: could not connect to the nRF52840 (check wires, USB power, or the chip may be locked)"
  echo "$OUT" | grep -iE "error|secured|protect|could not|failed" | head -5
  exit 1
fi
if ! echo "$OUT" | grep -q "^10001014 = 000F4000"; then
  echo "FAIL: flash did not verify (bootloader address not set)"
  echo "$OUT" | grep -iE "error|fail" | head -5
  exit 1
fi
echo "flashed and verified: $(basename "$HEX")"
printf "waiting for USB enumeration"
for i in $(seq 1 15); do
  sleep 1; printf "."
  if ioreg -p IOUSB -l -w0 | grep -q '"USB Product Name" = "Proximity Fear Badge"'; then
    echo " OK - badge on USB as 'Proximity Fear Badge'"
    exit 0
  fi
done
echo " not seen on USB (is the badge's USB-C plugged into this Mac?)"
