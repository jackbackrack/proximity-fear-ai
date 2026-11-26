/*
  Proximity Fear Badge variant for the Adafruit nRF52 Arduino core.
  Derived from the core's pca10056 variant (LGPL 2.1, Arduino LLC / Sandeep Mistry /
  Adafruit). Arduino pin N == nRF pin N (P0.00-P0.31 = 0-31, P1.00-P1.15 = 32-47).
  Signal pins: the frozen GPIO map in proximity_fear/main.py.
*/
#ifndef _VARIANT_PROXIMITY_FEAR_BADGE_
#define _VARIANT_PROXIMITY_FEAR_BADGE_

#define VARIANT_MCK       (64000000ul)

// The 32.768 kHz crystal (FC-135 on XL1/XL2) is a first-board check, so the core
// boots on the RC oscillator; firmware switches to the crystal once it has proved it.
#define USE_LFRC

#include "WVariant.h"

#ifdef __cplusplus
extern "C"
{
#endif

#define PINS_COUNT           (48)
#define NUM_DIGITAL_PINS     (48)
#define NUM_ANALOG_INPUTS    (1)
#define NUM_ANALOG_OUTPUTS   (0)

// ---- Badge signals ---------------------------------------------------------
#define PIN_PDM_CLK          (4)    // P0.04
#define PIN_PDM_DIN          (12)   // P0.12
#define PIN_LED_DATA         (13)   // P0.13  WS2812C chain DIN (33 ohm)
#define PIN_IR_TX            (17)   // P0.17  N-FET gate, high = IR LED on (38 kHz PWM)
#define PIN_TOF_XSHUT        (20)   // P0.20  10 k pull-up; keep high (standby, not shutdown)
#define PIN_TOF_INT          (22)   // P0.22  ToF GPIO1, open drain, active low
#define PIN_IR_RX            (24)   // P0.24  receiver OUT, active low; no pull while unpowered
#define PIN_LED_EN           (29)   // P0.29  high = VLED on (100 k pull-down)
#define PIN_VBAT_SENSE       (30)   // P0.30 / AIN6, 1.5 M / 1.5 M divider
#define PIN_CHG_STAT         (31)   // P0.31  MCP73831 STAT
#define PIN_IR_RX_EN         (34)   // P1.02  active low (100 k pull-up holds receiver off)
#define PIN_USER_BUTTON      (36)   // P1.04  to GND, internal pull-up
#define PIN_CHG_EN           (45)   // P1.13  high / released = charging enabled (100 k pull-up)

#define LED_RING_COUNT       (50)   // rings of 10 + 16 + 24, inner ring first

// ---- Core-required defines ---------------------------------------------------
// No discrete LED on an nRF pin: point the core's LED defines at two unconnected
// module pads (P1.10, P1.11) so nothing the core blinks reaches a real net.
#define PIN_LED1             (42)
#define PIN_LED2             (43)
#define LED_BUILTIN          PIN_LED1
#define LED_CONN             PIN_LED2
#define LED_RED              PIN_LED1
#define LED_BLUE             PIN_LED2
#define LED_STATE_ON         1

#define PIN_BUTTON1          PIN_USER_BUTTON

#define PIN_A0               PIN_VBAT_SENSE
#define PIN_A1               (0xff)
#define PIN_A2               (0xff)
#define PIN_A3               (0xff)
#define PIN_A4               (0xff)
#define PIN_A5               (0xff)
#define PIN_A6               (0xff)
#define PIN_A7               (0xff)
static const uint8_t A0  = PIN_A0 ;
static const uint8_t A1  = PIN_A1 ;
static const uint8_t A2  = PIN_A2 ;
static const uint8_t A3  = PIN_A3 ;
static const uint8_t A4  = PIN_A4 ;
static const uint8_t A5  = PIN_A5 ;
static const uint8_t A6  = PIN_A6 ;
static const uint8_t A7  = PIN_A7 ;
#define ADC_RESOLUTION       14

#define PIN_AREF             (2)
static const uint8_t AREF = PIN_AREF;

// NFC1/NFC2 stay NFC (antenna on P0.09 / P0.10): never define CONFIG_NFCT_PINS_AS_GPIOS.
#define PIN_NFC1             (9)
#define PIN_NFC2             (10)

// Serial1 and SPI are not wired on the badge; unconnected pads (P0.28, P1.06, P1.09).
#define PIN_SERIAL1_RX       (28)
#define PIN_SERIAL1_TX       (38)

#define SPI_INTERFACES_COUNT 1
#define PIN_SPI_MISO         (41)
#define PIN_SPI_MOSI         (28)
#define PIN_SPI_SCK          (38)
static const uint8_t SS   = 41 ;
static const uint8_t MOSI = PIN_SPI_MOSI ;
static const uint8_t MISO = PIN_SPI_MISO ;
static const uint8_t SCK  = PIN_SPI_SCK ;

#define WIRE_INTERFACES_COUNT 1
#define PIN_WIRE_SDA         (7)    // P0.07, 2.2 k pull-up
#define PIN_WIRE_SCL         (15)   // P0.15, 2.2 k pull-up

#ifdef __cplusplus
}
#endif

#endif
