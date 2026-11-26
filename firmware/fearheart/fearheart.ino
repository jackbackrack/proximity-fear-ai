// Proximity Fear Badge: the fear heart (fw-02).
//
// Board: adafruit:nrf52:proximityfear (firmware/arduino, install_variant.sh).
// The VL53L4CX measures the distance to whoever is in front. The heart rate rises
// inversely with that distance:
//     bpm = REST_BPM + FEAR_K / distance_m      (clamped to MAX_BPM)
// so ~180 bpm at 0.3 m, ~90 at 1 m, ~70 at 2 m, ~60 at 4 m, and REST_BPM (50) with
// nobody there. Each beat is a lub-dub: two pulses, each radiating from the inner ring
// to the outer ring. The heart reacts quickly when someone comes closer and calms down
// slowly when they leave; the beat phase is continuous, so rate changes never glitch.
// Closer = brighter and slightly hotter (towards orange).
//
// USB serial prints "dist / bpm" twice a second.
//
// Firmware rules (proximity_fear/main.py): the variant leaves the IR receiver off;
// ToF XSHUT stays high (the library drives it); CHG_EN is released unless USB is
// present and VBAT sense reads < 2 V; LED brightness stays under the USB current cap.

#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include <vl53l4cx_class.h>

// ---- Tuning ---------------------------------------------------------------------
static const float REST_BPM = 50.0f;
static const float MAX_BPM = 190.0f;
static const float FEAR_K = 39.0f;          // bpm * m: 50 + 39 / 0.3 = 180 bpm at 0.3 m
static const float FAR_M = 4.5f;            // treated as "nobody there"
static const uint32_t LOST_MS = 800;        // no valid target for this long -> far
static const float APPROACH_ALPHA = 0.5f;   // distance smoothing when coming closer
static const float RETREAT_ALPHA = 0.06f;   // ... and when moving away (slow calm-down)

static const uint8_t PEAK_LEVEL = 48;       // of 255 at full fear; <= ~115 mA all rings red
static const float RING_GAIN[3] = {1.0f, 0.85f, 0.7f};
static const float LUB = 1.0f, DUB = 0.6f;

// ---- Hardware ---------------------------------------------------------------------
static const uint8_t RING_COUNTS[3] = {10, 16, 24};  // inner, middle, outer (chain order)
static const uint8_t RING_START[3] = {0, 10, 26};

Adafruit_NeoPixel ring(LED_RING_COUNT, PIN_LED_DATA, NEO_GRB + NEO_KHZ800);
VL53L4CX tof(&Wire, PIN_TOF_XSHUT);

static bool tofOk = false;
static float distM = FAR_M;      // smoothed distance
static float lastValidM = FAR_M;
static uint32_t lastValidMs = 0;
static float bpm = REST_BPM;

// Pulses: a short ring buffer of (start time, strength).
struct Pulse {
  uint32_t startMs;
  float strength;
};
static Pulse pulses[6];
static uint8_t pulseHead = 0;

static float phase = 0.0f;       // 0..1 through the current beat
static bool dubPending = false;
static uint32_t beatStartMs = 0;

static bool chargeInhibited = false;

// ---------------------------------------------------------------------------------

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

static void tofInit() {
  Wire.begin();
  Wire.setClock(400000);
  tof.begin();
  tof.VL53L4CX_Off();
  VL53L4CX_Error err = tof.InitSensor(0x52);
  if (err == 0) err = tof.VL53L4CX_SetDistanceMode(VL53L4CX_DISTANCEMODE_LONG);
  if (err == 0) err = tof.VL53L4CX_SetMeasurementTimingBudgetMicroSeconds(50000);
  if (err == 0) err = tof.VL53L4CX_StartMeasurement();
  tofOk = (err == 0);
}

static void tofPoll() {
  if (!tofOk) return;
  uint8_t ready = 0;
  if (tof.VL53L4CX_GetMeasurementDataReady(&ready) != 0 || !ready) return;
  VL53L4CX_MultiRangingData_t data;
  if (tof.VL53L4CX_GetMultiRangingData(&data) == 0) {
    int nearest = -1;
    for (int j = 0; j < data.NumberOfObjectsFound; j++) {
      if (data.RangeData[j].RangeStatus == 0 &&
          (nearest < 0 || data.RangeData[j].RangeMilliMeter < nearest)) {
        nearest = data.RangeData[j].RangeMilliMeter;
      }
    }
    if (nearest > 0) {
      lastValidM = nearest / 1000.0f;
      lastValidMs = millis();
    }
  }
  tof.VL53L4CX_ClearInterruptAndStartMeasurement();
}

static void updateDistance(float dt) {
  float target = (millis() - lastValidMs > LOST_MS) ? FAR_M : lastValidM;
  if (target > FAR_M) target = FAR_M;
  // Per-frame smoothing normalised to 50 ms steps (the ToF rate).
  float a = (target < distM) ? APPROACH_ALPHA : RETREAT_ALPHA;
  float k = 1.0f - powf(1.0f - a, dt / 0.05f);
  distM += k * (target - distM);

  float d = distM < 0.05f ? 0.05f : distM;
  float b = (distM >= FAR_M - 0.01f) ? REST_BPM : REST_BPM + FEAR_K / d;
  bpm = b > MAX_BPM ? MAX_BPM : b;
}

static void addPulse(uint32_t now, float strength) {
  pulses[pulseHead].startMs = now;
  pulses[pulseHead].strength = strength;
  pulseHead = (pulseHead + 1) % 6;
}

static void updateBeat(float dt, uint32_t now) {
  float period = 60.0f / bpm;
  phase += dt / period;
  if (phase >= 1.0f) {
    phase -= 1.0f;
    beatStartMs = now;
    addPulse(now, LUB);
    dubPending = true;
  }
  // Dub follows the lub by ~0.3 s at rest, sooner as the heart races.
  float dubDelay = fminf(0.30f, 0.32f * period);
  if (dubPending && (now - beatStartMs) >= (uint32_t)(dubDelay * 1000.0f)) {
    addPulse(now, DUB);
    dubPending = false;
  }
}

static void render(uint32_t now) {
  float period = 60.0f / bpm;
  float fear = (bpm - REST_BPM) / (MAX_BPM - REST_BPM);  // 0 calm .. 1 terrified
  float ringDelay = fminf(0.085f, 0.16f * period);       // wave travel, inner -> outer
  float attack = 0.025f;
  float tau = fminf(0.14f, 0.22f * period);              // pulse decay

  float level[3] = {0, 0, 0};
  for (int p = 0; p < 6; p++) {
    if (pulses[p].strength <= 0) continue;
    float age = (now - pulses[p].startMs) / 1000.0f;
    if (age > 2.0f) {
      pulses[p].strength = 0;
      continue;
    }
    for (int r = 0; r < 3; r++) {
      float t = age - r * ringDelay;
      if (t < 0) continue;
      float e = (t < attack) ? t / attack : expf(-(t - attack) / tau);
      level[r] += pulses[p].strength * e * RING_GAIN[r];
    }
  }

  float peak = PEAK_LEVEL * (0.45f + 0.55f * fear);
  for (int r = 0; r < 3; r++) {
    float v = level[r] > 1.0f ? 1.0f : level[r];
    float red = v * peak;
    if (red < 1.0f) red = 1.0f;  // faint ember between beats
    float green = v * peak * 0.18f * fear;  // hotter when afraid
    uint32_t c = ring.Color((uint8_t)red, (uint8_t)green, 0);
    for (int i = 0; i < RING_COUNTS[r]; i++) ring.setPixelColor(RING_START[r] + i, c);
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

  tofInit();
  chargeRule();
}

void loop() {
  static uint32_t lastFrame = millis(), lastCharge = 0, lastPrint = 0;
  uint32_t now = millis();

  tofPoll();

  if (now - lastFrame >= 10) {
    float dt = (now - lastFrame) / 1000.0f;
    lastFrame = now;
    updateDistance(dt);
    updateBeat(dt, now);
    render(now);
  }
  if (now - lastCharge >= 1000) {
    lastCharge = now;
    chargeRule();
  }
  if (now - lastPrint >= 500) {
    lastPrint = now;
    Serial.print("dist ");
    if (!tofOk) Serial.print("ToF FAIL");
    else if (distM >= FAR_M - 0.01f) Serial.print("nobody");
    else { Serial.print(distM, 2); Serial.print(" m"); }
    Serial.print("  bpm ");
    Serial.println(bpm, 0);
  }
}
