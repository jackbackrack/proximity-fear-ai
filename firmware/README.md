# Proximity Fear Badge firmware

Arduino (Adafruit nRF52 core) firmware for the badge, plus the bootloader board
definition. Pins come from the frozen GPIO map in `proximity_fear/main.py`.

| Folder | What |
|---|---|
| `badge/` | Main firmware. Starts in SYNC; button cycles SYNC -> FEAR -> SOUND (radar) -> BEAT; double press restarts sync; long press toggles auto gain. Serial: `F`/`S`/`B`/`Y` select a mode, `U` reboots into the FEARBOOT drive, `+`/`-` sound sensitivity. |
| `bringup/` | fw-01 bring-up / hardware test sketch (serial commands, `h` for help). |
| `fearheart/`, `soundrings/` | Earlier single-mode sketches. |
| `arduino/` | Board variant (`adafruit:nrf52:proximityfear`) and `install_variant.sh`. |
| `bootloader/proximity_fear_badge/` | Board files for the Adafruit nRF52 UF2 bootloader. |
| `scripts/` | `badge_serial.py` (read serial / send commands), `sync_scan.py` (watch SYNC broadcasts from a Mac). |
| `upload.sh` | Build a sketch and upload it over USB: reboots the badge into its FEARBOOT drive and copies a UF2 (falls back to 1200-baud touch + serial DFU). `BADGE_PORT=/dev/cu.usbmodemX` picks a badge when several are plugged in. |
| `flash_bootloader.sh` | Flash the bootloader + SoftDevice over SWD with a J-Link and check the badge enumerates (one step per new board). |

## Setup (once)

1. `arduino-cli` in `firmware/tools/` (git-ignored), with the Adafruit board index
   `https://adafruit.github.io/arduino-board-index/package_adafruit_index.json`,
   `arduino-cli core install adafruit:nrf52`, and the libraries
   `Adafruit NeoPixel` and `STM32duino VL53L4CX`.
2. `arduino/install_variant.sh` (again after any core update).
3. `python3 -m venv firmware/.venv && firmware/.venv/bin/pip install adafruit-nrfutil pyserial intelhex bleak`.

## Bootloader (first flash, needs SWD)

Clone `adafruit/Adafruit_nRF52_Bootloader` into `firmware/` (git-ignored), copy
`bootloader/proximity_fear_badge` into its `src/boards/`, then
`make BOARD=proximity_fear_badge all` and flash
`_build/build-proximity_fear_badge/*_s140_6.1.1.hex` with a J-Link (erase first).
The badge then enumerates as `FEARBOOT`.

## Everyday use

    firmware/upload.sh badge          # build + upload the main firmware
    firmware/.venv/bin/python firmware/scripts/badge_serial.py 10      # watch status

Keep the LiPo unplugged while on USB until firmware with the reversed-pack charge
cut-off (all sketches here) is running.
