#!/bin/sh
# Build a sketch and upload it to a badge over USB.
#   1. ask the running firmware to reboot into its FEARBOOT drive ('U' over serial) and
#      copy a UF2 onto it;
#   2. if that drive doesn't appear (older firmware), 1200-baud touch into the serial
#      bootloader and use serial DFU, starting as soon as the port appears.
# usage: [BADGE_PORT=/dev/cu.usbmodemX] firmware/upload.sh [sketch_dir]   (default bringup)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SKETCH=${1:-bringup}
CORE=$(ls -d "$HOME"/Library/Arduino15/packages/adafruit/hardware/nrf52/* | tail -1)
BUILD="$HERE/$SKETCH/build"
LOG=$(mktemp)
if ! "$HERE/tools/arduino-cli" compile --fqbn adafruit:nrf52:proximityfear --output-dir "$BUILD" "$HERE/$SKETCH" >"$LOG" 2>&1; then
  grep -E "error|Error" "$LOG" | head -20; rm -f "$LOG"; echo "compile FAILED - nothing uploaded"; exit 1
fi
tail -2 "$LOG"; rm -f "$LOG"
"$HERE/.venv/bin/python" "$CORE/tools/uf2conv/uf2conv.py" "$BUILD/$SKETCH.ino.hex" -c -f 0xADA52840 -o "$BUILD/$SKETCH.uf2" >/dev/null

waitport() { for i in $(seq 1 50); do P=$(ls /dev/cu.usbmodem* 2>/dev/null | head -1); [ -n "$P" ] && { echo "$P"; return 0; }; sleep 0.2; done; echo "no badge serial port found" >&2; return 1; }
PORT=${BADGE_PORT:-$(waitport)}

# 1. UF2 drive
[ -d /Volumes/FEARBOOT ] && { echo "a FEARBOOT drive is already mounted - eject it first"; exit 1; }
"$HERE/.venv/bin/python" - "$PORT" <<'PY'
import sys, serial
s = serial.Serial(sys.argv[1], 115200, timeout=0.5); s.write(b"U"); s.flush(); s.close()
PY
for i in $(seq 1 40); do
  if [ -d /Volumes/FEARBOOT ]; then
    sleep 1
    cp "$BUILD/$SKETCH.uf2" /Volumes/FEARBOOT/ 2>/dev/null || true
    for j in $(seq 1 20); do [ -d /Volumes/FEARBOOT ] || break; sleep 0.5; done
    echo "Device programmed (UF2 via FEARBOOT on $PORT)."
    exit 0
  fi
  sleep 0.25
done

# 2. serial DFU fallback
echo "no FEARBOOT drive - trying serial DFU"
"$HERE/.venv/bin/python" - "$PORT" <<'PY'
import sys, time, serial
s = serial.Serial(sys.argv[1], 1200); s.dtr = False; time.sleep(0.1); s.close()
PY
# wait for the app's port to go away, then for the bootloader's port to come up
for i in $(seq 1 25); do [ -e "$PORT" ] || break; sleep 0.2; done
for i in $(seq 1 50); do [ -e "$PORT" ] && break; sleep 0.2; done
sleep 2.0   # let the bootloader's serial port settle before DFU starts
"$HERE/.venv/bin/adafruit-nrfutil" dfu serial -pkg "$BUILD/$SKETCH.ino.zip" -p "$PORT" -b 115200 --singlebank | tail -1
