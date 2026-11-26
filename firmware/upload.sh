#!/bin/sh
# Build a sketch and upload it to the badge over USB: 1200-baud touch into the
# bootloader, then serial DFU. usage: firmware/upload.sh [sketch_dir]  (default bringup)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SKETCH=${1:-bringup}
LOG=$(mktemp)
if ! "$HERE/tools/arduino-cli" compile --fqbn adafruit:nrf52:proximityfear --output-dir "$HERE/$SKETCH/build" "$HERE/$SKETCH" >"$LOG" 2>&1; then
  grep -E "error|Error" "$LOG" | head -20; rm -f "$LOG"; echo "compile FAILED - nothing uploaded"; exit 1
fi
tail -2 "$LOG"; rm -f "$LOG"
PORT=$(ls /dev/cu.usbmodem* | head -1)
"$HERE/.venv/bin/python" - "$PORT" <<'PY'
import sys, time, serial
s = serial.Serial(sys.argv[1], 1200); s.dtr = False; time.sleep(0.1); s.close()
PY
sleep 3
PORT=$(ls /dev/cu.usbmodem* | head -1)
"$HERE/.venv/bin/adafruit-nrfutil" dfu serial -pkg "$HERE/$SKETCH/build/$SKETCH.ino.zip" -p "$PORT" -b 115200 --singlebank | tail -1
