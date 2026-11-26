/*
 * Proximity Fear Badge (nRF52840, Ebyte E73-2G4M08S1CX) board definition for the
 * Adafruit nRF52 UF2 bootloader. Pins from the frozen GPIO map in
 * proximity_fear/main.py.
 */
#ifndef _PROXIMITY_FEAR_BADGE_H
#define _PROXIMITY_FEAR_BADGE_H

/*------------------------------------------------------------------*/
/* LED: no discrete LED on an nRF pin; status shows on the first
 * WS2812C of the ring chain. LED_EN (P0.29, high = VLED on) powers it.
 *------------------------------------------------------------------*/
#define LEDS_NUMBER          0
#define LED_PRIMARY_PIN      PINNUM(0, 13)  // unused (LEDS_NUMBER 0); the LED_DATA pin
#define LED_STATE_ON         1

#define LED_NEOPIXEL         PINNUM(0, 13)  // LED_DATA
#define NEOPIXEL_POWER_PIN   PINNUM(0, 29)  // LED_EN
#define NEOPIXELS_NUMBER     1
#define BOARD_RGB_BRIGHTNESS 0x040404

/*------------------------------------------------------------------*/
/* BUTTON: the one user button (P1.04, to GND, internal pull-up).
 * Hold it while plugging in USB / resetting to stay in the bootloader.
 *------------------------------------------------------------------*/
#define BUTTON_DFU           PINNUM(1, 4)
#define BUTTON_PULL          NRF_GPIO_PIN_PULLUP

/*------------------------------------------------------------------*/
/* Power: the E73 module carries the REG1 DC/DC inductor; VDDH = VDD
 * (normal voltage mode), so REG0 stays off.
 *------------------------------------------------------------------*/
#define ENABLE_DCDC_1        1

//--------------------------------------------------------------------+
// BLE OTA
//--------------------------------------------------------------------+
#define BLEDIS_MANUFACTURER  "Proximity Fear"
#define BLEDIS_MODEL         "Proximity Fear Badge"

//--------------------------------------------------------------------+
// USB (Adafruit VID with the nRF52840 DK bootloader PID, as many
// one-off boards in this repo do; change if the badge ever ships)
//--------------------------------------------------------------------+
#define USB_DESC_VID          0x239A
#define USB_DESC_UF2_PID      0x00DA
#define USB_DESC_CDC_ONLY_PID 0x00DA

#define UF2_PRODUCT_NAME      "Proximity Fear Badge"
#define UF2_VOLUME_LABEL      "FEARBOOT   "
#define UF2_BOARD_ID          "nRF52840-ProximityFear-r1"
#define UF2_INDEX_URL         "https://github.com/jackbackrack/proximity-fear-ai"

#endif // _PROXIMITY_FEAR_BADGE_H
