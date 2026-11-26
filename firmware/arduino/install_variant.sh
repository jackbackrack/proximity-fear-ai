#!/bin/sh
# Install the Proximity Fear Badge board into the Adafruit nRF52 Arduino core
# (variant + boards.local.txt). Re-run after a core update.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
CORE=$(ls -d "$HOME"/Library/Arduino15/packages/adafruit/hardware/nrf52/* | tail -1)
rm -rf "$CORE/variants/proximity_fear_badge"
cp -R "$HERE/variants/proximity_fear_badge" "$CORE/variants/"
cp "$HERE/boards.local.txt" "$CORE/boards.local.txt"
echo "installed into $CORE (FQBN adafruit:nrf52:proximityfear)"
