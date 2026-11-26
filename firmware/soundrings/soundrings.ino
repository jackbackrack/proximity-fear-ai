// Proximity Fear Badge: sound-reactive rings.
//
// Board: adafruit:nrf52:proximityfear (firmware/arduino, install_variant.sh).
// The PDM mic level, relative to a tracked background-noise floor, fills the rings:
//   inner ring (blue)  - small sounds     ~1.3x .. 3x the floor
//   middle ring (green) - mid sounds      ~3x  .. 10x
//   outer ring (red)   - loud sounds      ~10x .. 25x
// Each ring fills around its circle as the level rises through its band, attack is
// immediate and the fill decays smoothly. Serial (USB) commands: '+' / '-' shift all
// bands more / less sensitive (x0.8 / x1.25); 's' prints the current floor and level.
//
// Firmware rules (proximity_fear/main.py): the variant leaves the IR receiver off and
// the ToF XSHUT released; CHG_EN is released unless USB is present and VBAT sense
// reads < 2 V; LED brightness stays under the USB current cap.

#include <Adafruit_NeoPixel.h>
#include <PDM.h>

static const uint8_t RING_COUNTS[3] = {10, 16, 24};  // inner, middle, outer (chain order)
static const uint8_t RING_START[3] = {0, 10, 26};
static const uint8_t MAX_LEVEL = 40;  // of 255 per channel: <= ~95 mA with every LED lit

// Band edges as multiples of the background floor: {low, high} per ring.
static const float BANDS[3][2] = {{1.3f, 3.0f}, {3.0f, 10.0f}, {10.0f, 25.0f}};
static const float DECAY = 0.90f;  // per 10 ms frame (~0.1 s time constant)

Adafruit_NeoPixel ring(LED_RING_COUNT, PIN_LED_DATA, NEO_GRB + NEO_KHZ800);

static int16_t pdmBuffer[256];
static volatile int pdmSamples = 0;

static float floorRms = 55.0f;  // background noise, tracked slowly
static float levelRms = 0.0f;   // latest block RMS
static float sensitivity = 1.0f;
static float fill[3] = {0, 0, 0};

static bool chargeInhibited = false;

static void onPdmData() {
  int bytes = PDM.available();
  if (bytes > (int)sizeof(pdmBuffer)) bytes = sizeof(pdmBuffer);
  PDM.read(pdmBuffer, bytes);
  pdmSamples = bytes / 2;
}

static void pdmRisingEdge() {  // L/R strapped to GND: sample on the CLK rising edge
  NRF_PDM->TASKS_STOP = 1;
  delay(2);
  NRF_PDM->MODE = (PDM_MODE_OPERATION_Mono << PDM_MODE_OPERATION_Pos) |
                  (PDM_MODE_EDGE_LeftRising << PDM_MODE_EDGE_Pos);
  NRF_PDM->TASKS_START = 1;
}

static bool vbusPresent() {
  return (NRF_POWER->USBREGSTATUS & POWER_USBREGSTATUS_VBUSDETECT_Msk) != 0;
}

static float readVbat() {
  analogReference(AR_INTERNAL);  // 3.6 V full scale
  analogReadResolution(12);
  analogSampleTime(40);          // TACQ 40 us for the 1.5 M / 1.5 M divider
  uint32_t sum = 0;
  for (int i = 0; i < 4; i++) sum += analogRead(PIN_VBAT_SENSE);
  return (sum / 4.0f) * 3.6f / 4095.0f * 2.0f;
}

static void chargeRule() {
  bool inhibit = vbusPresent() && readVbat() < 2.0f;
  if (inhibit == chargeInhibited) return;
  chargeInhibited = inhibit;
  if (inhibit) {
    pinMode(PIN_CHG_EN, OUTPUT);
    digitalWrite(PIN_CHG_EN, LOW);
  } else {
    pinMode(PIN_CHG_EN, INPUT);  // released: pull-up enables charging
  }
}

static void processAudio() {
  if (!pdmSamples) return;
  int n = pdmSamples;
  float mean = 0;
  for (int i = 0; i < n; i++) mean += pdmBuffer[i];
  mean /= n;
  float acc = 0;
  for (int i = 0; i < n; i++) {
    float d = pdmBuffer[i] - mean;
    acc += d * d;
  }
  pdmSamples = 0;
  levelRms = sqrtf(acc / n);
  // Floor: falls quickly to quiet blocks, creeps up slowly, so sounds don't raise it.
  if (levelRms < floorRms) floorRms = 0.95f * floorRms + 0.05f * levelRms;
  else floorRms = 0.9995f * floorRms + 0.0005f * levelRms;
  if (floorRms < 5.0f) floorRms = 5.0f;
}

static void render() {
  static const uint8_t COLOURS[3][3] = {{0, 0, 1}, {0, 1, 0}, {1, 0, 0}};  // blue, green, red
  float ratio = levelRms / (floorRms * sensitivity);
  for (int r = 0; r < 3; r++) {
    float lo = BANDS[r][0], hi = BANDS[r][1];
    float target = (ratio <= lo) ? 0.0f : (ratio >= hi) ? 1.0f : logf(ratio / lo) / logf(hi / lo);
    fill[r] = (target > fill[r]) ? target : fill[r] * DECAY;
    float lit = fill[r] * RING_COUNTS[r];
    for (int i = 0; i < RING_COUNTS[r]; i++) {
      float f = lit - i;  // 1 = full, fractional tail, <= 0 = off
      f = f < 0 ? 0 : (f > 1 ? 1 : f);
      uint8_t v = (uint8_t)(f * MAX_LEVEL);
      ring.setPixelColor(RING_START[r] + i, v * COLOURS[r][0], v * COLOURS[r][1], v * COLOURS[r][2]);
    }
  }
  ring.show();
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_LED_EN, OUTPUT);
  digitalWrite(PIN_LED_EN, HIGH);  // VLED on (soft start)
  delay(5);
  ring.begin();
  ring.clear();
  ring.show();

  PDM.setPins(PIN_PDM_DIN, PIN_PDM_CLK, -1);
  PDM.onReceive(onPdmData);
  if (PDM.begin(1, 16000)) pdmRisingEdge();

  chargeRule();
}

void loop() {
  static uint32_t lastFrame = 0, lastCharge = 0;

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '+') sensitivity *= 0.8f;
    if (c == '-') sensitivity *= 1.25f;
    if (c == '+' || c == '-' || c == 's') {
      Serial.print("floor ");
      Serial.print(floorRms, 0);
      Serial.print("  level ");
      Serial.print(levelRms, 0);
      Serial.print("  sensitivity x");
      Serial.println(1.0f / sensitivity, 2);
    }
  }

  processAudio();
  if (millis() - lastFrame >= 10) {
    lastFrame = millis();
    render();
  }
  if (millis() - lastCharge >= 1000) {
    lastCharge = millis();
    chargeRule();
  }
}
