/*
  Proximity Fear Badge variant (derived from the Adafruit nRF52 core's pca10056
  variant, LGPL 2.1).
*/
#include "variant.h"
#include "wiring_constants.h"
#include "wiring_digital.h"
#include "nrf.h"

const uint32_t g_ADigitalPinMap[] =
{
  0 , 1 , 2 , 3 , 4 , 5 , 6 , 7 ,
  8 , 9 , 10, 11, 12, 13, 14, 15,
  16, 17, 18, 19, 20, 21, 22, 23,
  24, 25, 26, 27, 28, 29, 30, 31,
  32, 33, 34, 35, 36, 37, 38, 39,
  40, 41, 42, 43, 44, 45, 46, 47
};

void initVariant()
{
  // Safe states before the sketch runs (main.py firmware rules).
  pinMode(PIN_IR_RX_EN, OUTPUT);       // receiver supply off
  digitalWrite(PIN_IR_RX_EN, HIGH);
  pinMode(PIN_IR_RX, INPUT);           // no pull into the unpowered receiver
  pinMode(PIN_IR_TX, OUTPUT);          // IR LED off
  digitalWrite(PIN_IR_TX, LOW);
  pinMode(PIN_LED_EN, OUTPUT);         // LED rings unpowered
  digitalWrite(PIN_LED_EN, LOW);
  pinMode(PIN_CHG_EN, INPUT);          // released: pull-up enables charging
  pinMode(PIN_TOF_XSHUT, INPUT);       // pull-up holds the ToF out of shutdown

  pinMode(PIN_LED1, OUTPUT);
  ledOff(PIN_LED1);
  pinMode(PIN_LED2, OUTPUT);
  ledOff(PIN_LED2);
}
