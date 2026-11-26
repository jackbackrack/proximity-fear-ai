// Proximity Fear Badge bring-up (fw-01).
//
// Board: adafruit:nrf52:proximityfear (firmware/arduino, install_variant.sh).
// Prints a status line over USB serial every 500 ms; single-letter commands:
//   h help   r ring colours   l LED chase   x 32 kHz crystal test   i IR loopback test
//   v IR remote watch   g IR LED on 10 s   m mic level on/off   e flip PDM sampling edge   t ToF re-init
//
// Firmware rules honoured (proximity_fear/main.py docstring): IR receiver supply off
// (IR_RX_EN high) with no pull on IR_RX except during the IR test; ToF XSHUT kept
// high; CHG_EN released unless VBUS is present and VBAT sense reads < 2 V (reversed or
// missing pack); SAADC TACQ 40 us for the 1.5 M / 1.5 M divider; LED brightness kept
// low (USB current cap).

#include <Adafruit_NeoPixel.h>
#include <PDM.h>
#include <Wire.h>
#include <vl53l4cx_class.h>

static const uint8_t RING_COUNTS[3] = {10, 16, 24};  // inner, middle, outer (chain order)
static const uint8_t LED_LEVEL = 16;                 // of 255; ~40 mA for all 50 on one colour
static const float VBAT_DIVIDER = 2.0f;              // 1.5 M / 1.5 M
static const float CHG_CUTOFF_V = 2.0f;

Adafruit_NeoPixel ring(LED_RING_COUNT, PIN_LED_DATA, NEO_GRB + NEO_KHZ800);
VL53L4CX tof(&Wire, PIN_TOF_XSHUT);

static bool tofOk = false;
static int tofMm = -1;
static int tofStatus = -1;
static int tofObjects = 0;

static volatile int pdmSamplesRead = 0;
static int16_t pdmBuffer[256];
static bool micPrint = true;
static bool pdmRisingEdge = true;  // L/R strapped to GND: sample on CLK rising (microphone.py)
static float micRms = 0.0f;
static bool pdmOk = false;

static bool chargeInhibited = false;
static int lastButton = HIGH;
static uint32_t lastStatusMs = 0;

// ---------------------------------------------------------------------------
// Helpers

static bool vbusPresent() {
  return (NRF_POWER->USBREGSTATUS & POWER_USBREGSTATUS_VBUSDETECT_Msk) != 0;
}

static float readVbat() {
  analogReference(AR_INTERNAL);  // 0.6 V ref, gain 1/6: 3.6 V full scale
  analogReadResolution(12);
  analogSampleTime(40);          // TACQ 40 us for the 750 k source impedance
  uint32_t sum = 0;
  for (int i = 0; i < 8; i++) sum += analogRead(PIN_VBAT_SENSE);
  return (sum / 8.0f) * 3.6f / 4095.0f * VBAT_DIVIDER;
}

static void cycleDelayUs(uint32_t us) {  // busy wait on the DWT cycle counter (no RTOS tick)
  uint32_t start = DWT->CYCCNT;
  uint32_t cycles = us * (SystemCoreClock / 1000000);
  while ((DWT->CYCCNT - start) < cycles) {
  }
}

static void ringShow(bool on) {
  digitalWrite(PIN_LED_EN, on ? HIGH : LOW);
  if (on) delay(5);  // soft-start settles before data
  ring.show();
}

// ---------------------------------------------------------------------------
// 32.768 kHz crystal: switch LFCLK from RC to the crystal, time the start-up, then
// measure its frequency against the 32 MHz crystal (HFXO) using RTC1's counter.

static void lfxoTest() {
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

  NRF_CLOCK->EVENTS_HFCLKSTARTED = 0;
  NRF_CLOCK->TASKS_HFCLKSTART = 1;  // HFXO as the timing reference
  uint32_t t0 = DWT->CYCCNT;
  while (!NRF_CLOCK->EVENTS_HFCLKSTARTED && (DWT->CYCCNT - t0) < 64000000u / 10) {
  }
  bool hfxo = NRF_CLOCK->EVENTS_HFCLKSTARTED;

  NRF_CLOCK->TASKS_LFCLKSTOP = 1;
  while (NRF_CLOCK->LFCLKSTAT & CLOCK_LFCLKSTAT_STATE_Msk) {
  }
  NRF_CLOCK->LFCLKSRC = CLOCK_LFCLKSRC_SRC_Xtal << CLOCK_LFCLKSRC_SRC_Pos;
  NRF_CLOCK->EVENTS_LFCLKSTARTED = 0;
  NRF_CLOCK->TASKS_LFCLKSTART = 1;
  t0 = DWT->CYCCNT;
  while (!NRF_CLOCK->EVENTS_LFCLKSTARTED && (DWT->CYCCNT - t0) < 64000000u) {  // 1 s max
  }
  bool started = NRF_CLOCK->EVENTS_LFCLKSTARTED;
  float startMs = (DWT->CYCCNT - t0) / 64000.0f;

  if (!started) {
    NRF_CLOCK->TASKS_LFCLKSTOP = 1;
    while (NRF_CLOCK->LFCLKSTAT & CLOCK_LFCLKSTAT_STATE_Msk) {
    }
    NRF_CLOCK->LFCLKSRC = CLOCK_LFCLKSRC_SRC_RC << CLOCK_LFCLKSRC_SRC_Pos;
    NRF_CLOCK->TASKS_LFCLKSTART = 1;
    Serial.println("LFXO: FAIL - crystal did not start within 1 s; back on the RC oscillator");
    return;
  }

  // Frequency: RTC0 (unused without the SoftDevice) at prescaler 0 counts every LFCLK
  // cycle; 2 s of HF cycles gives ~15 ppm resolution.
  bool onXtal = ((NRF_CLOCK->LFCLKSTAT & CLOCK_LFCLKSTAT_SRC_Msk) >> CLOCK_LFCLKSTAT_SRC_Pos) ==
                CLOCK_LFCLKSTAT_SRC_Xtal;
  NRF_RTC0->TASKS_STOP = 1;
  NRF_RTC0->TASKS_CLEAR = 1;
  NRF_RTC0->PRESCALER = 0;
  NRF_RTC0->TASKS_START = 1;
  cycleDelayUs(20000);
  uint32_t c0 = NRF_RTC0->COUNTER;
  uint32_t h0 = DWT->CYCCNT;
  cycleDelayUs(2000000);
  uint32_t c1 = NRF_RTC0->COUNTER;
  uint32_t h1 = DWT->CYCCNT;
  NRF_RTC0->TASKS_STOP = 1;
  uint32_t ticks = (c1 - c0) & 0xFFFFFF;
  float seconds = (h1 - h0) / 64000000.0f;
  float hz = ticks / seconds;
  float ppm = (hz - 32768.0f) / 32768.0f * 1e6f;
  Serial.print("LFXO: ");
  Serial.print(onXtal ? "OK - LFCLK source reports the crystal" : "WARN - LFCLK source is not the crystal");
  Serial.print("; started in ");
  Serial.print(startMs, 1);
  Serial.print(" ms; ");
  Serial.print(hz, 1);
  Serial.print(" Hz (");
  Serial.print(ppm, 0);
  Serial.print(" ppm vs ");
  Serial.print(hfxo ? "the 32 MHz crystal" : "HFINT, +/-1.5%");
  Serial.println(")");
}

// ---------------------------------------------------------------------------
// LEDs

static void ringColours() {
  uint32_t colours[3] = {ring.Color(LED_LEVEL, 0, 0), ring.Color(0, LED_LEVEL, 0),
                         ring.Color(0, 0, LED_LEVEL)};
  int n = 0;
  for (int r = 0; r < 3; r++) {
    for (int i = 0; i < RING_COUNTS[r]; i++) ring.setPixelColor(n++, colours[r]);
  }
  ringShow(true);
  Serial.println("LEDs: inner ring red, middle green, outer blue - every LED should be lit");
}

static void ledChase() {
  Serial.println("LEDs: chase - one white LED walks the chain 0..49 (inner, middle, outer)");
  for (int n = 0; n < LED_RING_COUNT; n++) {
    ring.clear();
    ring.setPixelColor(n, ring.Color(LED_LEVEL, LED_LEVEL, LED_LEVEL));
    ringShow(true);
    delay(60);
  }
  ring.clear();
  ringShow(true);
}

// ---------------------------------------------------------------------------
// ToF

static void i2cScan() {
  Serial.print("I2C: devices at");
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print(" 0x");
      Serial.print(a, HEX);
      found++;
    }
  }
  Serial.println(found ? "" : " (none)");
}

static void tofInit() {
  tof.begin();
  tof.VL53L4CX_Off();
  VL53L4CX_Error err = tof.InitSensor(0x52);
  if (err == 0) err = tof.VL53L4CX_StartMeasurement();
  tofOk = (err == 0);
  Serial.print("ToF: ");
  Serial.println(tofOk ? "VL53L4CX initialised, ranging" : "FAIL - init error");
  if (!tofOk) {
    Serial.print("ToF: error ");
    Serial.println(err);
  }
}

static void tofPoll() {
  if (!tofOk) return;
  uint8_t ready = 0;
  if (tof.VL53L4CX_GetMeasurementDataReady(&ready) != 0 || !ready) return;
  VL53L4CX_MultiRangingData_t data;
  if (tof.VL53L4CX_GetMultiRangingData(&data) == 0) {
    tofObjects = data.NumberOfObjectsFound;
    tofMm = -1;
    tofStatus = -1;
    for (int j = 0; j < data.NumberOfObjectsFound; j++) {
      if (data.RangeData[j].RangeStatus == 0) {  // nearest valid target
        if (tofMm < 0 || data.RangeData[j].RangeMilliMeter < tofMm) {
          tofMm = data.RangeData[j].RangeMilliMeter;
        }
      }
      tofStatus = data.RangeData[j].RangeStatus;
    }
  }
  tof.VL53L4CX_ClearInterruptAndStartMeasurement();
}

// ---------------------------------------------------------------------------
// Mic

static void onPdmData() {
  int bytes = PDM.available();
  if (bytes > (int)sizeof(pdmBuffer)) bytes = sizeof(pdmBuffer);
  PDM.read(pdmBuffer, bytes);
  pdmSamplesRead = bytes / 2;
}

static void pdmSetEdge() {
  NRF_PDM->TASKS_STOP = 1;
  delay(2);
  NRF_PDM->MODE = (PDM_MODE_OPERATION_Mono << PDM_MODE_OPERATION_Pos) |
                  ((pdmRisingEdge ? PDM_MODE_EDGE_LeftRising : PDM_MODE_EDGE_LeftFalling)
                   << PDM_MODE_EDGE_Pos);
  NRF_PDM->TASKS_START = 1;
}

static void micInit() {
  PDM.setPins(PIN_PDM_DIN, PIN_PDM_CLK, -1);
  PDM.onReceive(onPdmData);
  pdmOk = PDM.begin(1, 16000);
  if (pdmOk) pdmSetEdge();
  Serial.println(pdmOk ? "Mic: PDM started (16 kHz mono, rising edge)" : "Mic: FAIL - PDM.begin");
}

static void micPoll() {
  if (!pdmSamplesRead) return;
  int n = pdmSamplesRead;
  double mean = 0;
  for (int i = 0; i < n; i++) mean += pdmBuffer[i];
  mean /= n;
  double acc = 0;
  for (int i = 0; i < n; i++) {
    double d = pdmBuffer[i] - mean;
    acc += d * d;
  }
  float rms = sqrt(acc / n);
  micRms = 0.8f * micRms + 0.2f * rms;
  pdmSamplesRead = 0;
}

// ---------------------------------------------------------------------------
// IR: power the receiver, send 38 kHz bursts, count the receiver's active-low pulses.

static volatile uint32_t irEdges = 0;
static void onIrEdge() { irEdges++; }

// 38 kHz carrier on PWM2 (16 MHz / 421 = 38.0 kHz, 50 % duty), independent of tone().
static uint16_t irSeq[1] = {210 | 0x8000};  // bit 15: polarity, high for the first 210 counts

static void irCarrier(bool on) {
  if (on) {
    NRF_PWM2->PSEL.OUT[0] = PIN_IR_TX;
    NRF_PWM2->MODE = PWM_MODE_UPDOWN_Up;
    NRF_PWM2->PRESCALER = PWM_PRESCALER_PRESCALER_DIV_1;
    NRF_PWM2->COUNTERTOP = 421;
    NRF_PWM2->LOOP = 0;
    NRF_PWM2->DECODER = PWM_DECODER_LOAD_Common | PWM_DECODER_MODE_RefreshCount;
    NRF_PWM2->SEQ[0].PTR = (uint32_t)irSeq;
    NRF_PWM2->SEQ[0].CNT = 1;
    NRF_PWM2->SEQ[0].REFRESH = 0;
    NRF_PWM2->SEQ[0].ENDDELAY = 0;
    NRF_PWM2->ENABLE = 1;
    NRF_PWM2->TASKS_SEQSTART[0] = 1;
  } else {
    NRF_PWM2->TASKS_STOP = 1;
    delayMicroseconds(50);
    NRF_PWM2->ENABLE = 0;
    NRF_PWM2->PSEL.OUT[0] = 0xFFFFFFFFUL;
    digitalWrite(PIN_IR_TX, LOW);
  }
}

static uint32_t irCount(bool transmit, uint32_t ms) {
  irEdges = 0;
  uint32_t end = millis() + ms;
  while ((int32_t)(end - millis()) > 0) {  // 600 us bursts, 1.8 ms gaps (remote-like)
    if (transmit) irCarrier(true);
    delayMicroseconds(600);
    if (transmit) irCarrier(false);
    delayMicroseconds(1800);
  }
  return irEdges;
}

static void irRxOn() {
  digitalWrite(PIN_IR_RX_EN, LOW);  // receiver supply on
  delay(50);
  pinMode(PIN_IR_RX, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_IR_RX), onIrEdge, FALLING);
}

static void irRxOff() {
  detachInterrupt(digitalPinToInterrupt(PIN_IR_RX));
  pinMode(PIN_IR_RX, INPUT);         // no pull before the supply goes off
  digitalWrite(PIN_IR_RX_EN, HIGH);  // receiver off
}

static void irRemoteWatch() {
  Serial.println("IR: receiver on for 8 s - point a TV remote at the front and press buttons");
  irRxOn();
  irEdges = 0;
  delay(8000);
  uint32_t n = irEdges;
  irRxOff();
  Serial.print("IR: receiver pulses from the remote: ");
  Serial.println(n);
}

static void irLedOn() {
  Serial.println("IR: transmitter LED on (38 kHz) for 10 s - look at the front through a phone camera");
  irCarrier(true);
  delay(10000);
  irCarrier(false);
  Serial.println("IR: transmitter off");
}

static void irTest() {
  irRxOn();
  uint32_t quiet = irCount(false, 1000);
  uint32_t lit = irCount(true, 1000);
  irRxOff();
  Serial.print("IR: receiver pulses - transmitter off ");
  Serial.print(quiet);
  Serial.print(", transmitter bursting ");
  Serial.print(lit);
  Serial.println(" (hold a hand or white card ~5 cm over the front for the reflection)");
}

// ---------------------------------------------------------------------------
// Charging rule: stop charging when VBUS is present but the pack reads < 2 V.

static void chargeRule(float vbat, bool vbus) {
  bool inhibit = vbus && vbat < CHG_CUTOFF_V;
  if (inhibit != chargeInhibited) {
    chargeInhibited = inhibit;
    if (inhibit) {
      pinMode(PIN_CHG_EN, OUTPUT);
      digitalWrite(PIN_CHG_EN, LOW);
    } else {
      pinMode(PIN_CHG_EN, INPUT);  // released: pull-up enables charging
    }
    Serial.println(inhibit ? "Charger: OFF (VBAT sense < 2 V with USB present)"
                           : "Charger: enabled");
  }
}

// ---------------------------------------------------------------------------

static void help() {
  Serial.println("Commands: h help | r ring colours | l LED chase | x crystal test | "
                 "i IR loopback | v IR remote watch | g IR LED on 10 s | m mic print on/off | e flip PDM edge | t ToF re-init");
}

void setup() {
  pinMode(PIN_USER_BUTTON, INPUT_PULLUP);
  pinMode(PIN_CHG_STAT, INPUT);

  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 10000) delay(10);
  Serial.println();
  Serial.println("=== Proximity Fear Badge bring-up (fw-01) ===");

  lfxoTest();

  float vbat = readVbat();
  chargeRule(vbat, vbusPresent());

  Wire.begin();
  Wire.setClock(400000);
  i2cScan();
  tofInit();
  micInit();

  ring.begin();
  ringColours();
  delay(2500);
  ledChase();
  ringColours();

  help();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'h': help(); break;
      case 'r': ringColours(); break;
      case 'l': ledChase(); break;
      case 'x': lfxoTest(); break;
      case 'i': irTest(); break;
      case 'm': micPrint = !micPrint; break;
      case 'e':
        pdmRisingEdge = !pdmRisingEdge;
        pdmSetEdge();
        Serial.println(pdmRisingEdge ? "PDM: rising edge" : "PDM: falling edge");
        break;
      case 't': tofInit(); break;
      case 'v': irRemoteWatch(); break;
      case 'g': irLedOn(); break;
      default: break;
    }
  }

  tofPoll();
  micPoll();

  int b = digitalRead(PIN_USER_BUTTON);
  if (b != lastButton) {
    lastButton = b;
    Serial.println(b == LOW ? "Button: pressed" : "Button: released");
  }

  if (millis() - lastStatusMs >= 500) {
    lastStatusMs = millis();
    float vbat = readVbat();
    bool vbus = vbusPresent();
    chargeRule(vbat, vbus);
    Serial.print("dist ");
    if (!tofOk) Serial.print("n/a");
    else if (tofMm >= 0) { Serial.print(tofMm); Serial.print(" mm"); }
    else { Serial.print("none (objects "); Serial.print(tofObjects); Serial.print(", status ");
           Serial.print(tofStatus); Serial.print(")"); }
    Serial.print(" | button ");
    Serial.print(lastButton == LOW ? "down" : "up");
    Serial.print(" | USB ");
    Serial.print(vbus ? "yes" : "no");
    Serial.print(" | VBAT ");
    Serial.print(vbat, 2);
    Serial.print(" V | STAT ");
    Serial.print(digitalRead(PIN_CHG_STAT) ? "high" : "low");
    Serial.print(" | charger ");
    Serial.print(chargeInhibited ? "off" : "on");
    if (micPrint) {
      Serial.print(" | mic rms ");
      Serial.print(micRms, 0);
    }
    Serial.println();
  }
  delay(10);
}
