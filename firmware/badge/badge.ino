// Proximity Fear Badge: main firmware.
//
// Board: adafruit:nrf52:proximityfear (firmware/arduino, install_variant.sh).
// The button steps through four modes, FEAR -> SOUND -> BEAT -> SYNC (starts in FEAR);
// each mode announces itself with a short flash (red / green / blue / violet):
//
// FEAR (fw-02): the VL53L4CX measures the distance to whoever is in front and the heart
//   rate rises inversely with it: bpm = REST_BPM + FEAR_K / distance_m (clamped), so
//   ~180 bpm at 0.3 m, ~90 at 1 m, ~70 at 2 m, ~60 at 4 m, REST_BPM with nobody there.
//   Each beat is a lub-dub, each pulse radiating inner -> outer ring. Fast to fear,
//   slow to calm down; continuous beat phase; closer = brighter and hotter.
//
// SOUND: radar. A beam sweeps clockwise once every 1 s; each LED it passes takes the
//   current loudness (log scale over a tracked background floor) and fades slowly,
//   leaving a trail. Louder reaches further out (inner -> middle -> outer, ramped
//   smoothly) and shifts colour blue -> green -> red. Uses each LED's true angle.
//   Perceptual (after scottlawsonbc/audio-reactive-led-strip): loudness is the mean
//   log energy of 20 mel bands, colour is the balance of bass (red) / mids (green) /
//   treble (blue), each auto-ranged and squared; LEDs get gamma 2.2 with temporal
//   dithering so fades look even down to black.
//   Automatic gain (default): the display spans a tracked floor (the quiet gaps) to a
//   tracked ceiling (recent loud level, ~15 s memory), so any room uses the full
//   range. Long-press the button (0.8 s) to toggle auto / fixed (white sweep = auto,
//   dim flash = fixed).
//
// BEAT: music beat detection (beat.h): mel-band spectral flux with an adaptive
//   threshold finds onsets; a tempo tracker locks onto the beat period and predicts
//   each beat, carrying the pulse through short gaps. Colour follows timbre (the
//   spectral centroid, auto-ranged over the last ~15 s) on the spectrum in wavelength
//   order, low sounds red through orange, yellow, green, cyan, blue to violet for the
//   brightest: each beat's ripple takes the colour of that hit (kick red, snare green,
//   hats blue-violet), radiating inner -> outer, pale at the crest; under it a "mood" glow
//   (3 s timbre average) lit by each ring's band (outer bass, middle mids, inner
//   treble). Gamma 2.2 + dithering as in the radar.
//
// SYNC (fw-05): the fear heart, plus badge-to-badge beat sync over BLE. Each badge
//   broadcasts its beat phase and bpm in a non-connectable advertisement and listens
//   for the others (no pairing). Peers in range (weighted by RSSI) pull each other's
//   phase together (Kuramoto-style coupling). Every badge beats at a fixed SYNC_BPM
//   (60) here - distance doesn't change the rate - so only the phase has to lock.
//   Colour: magenta alone; hearing another badge, orange when the beats are a quarter
//   beat or more apart, blending to blue-violet as they lock into step.
//
// The sensor a mode doesn't use is idled (ToF ranging stopped with XSHUT high /
// PDM stopped). USB serial prints status twice a second; '+' / '-' change sound
// sensitivity; 'F' / 'S' / 'B' / 'Y' select FEAR / SOUND / BEAT / SYNC.
//
// Firmware rules (proximity_fear/main.py): the variant leaves the IR receiver off;
// ToF "off" is stopped ranging with XSHUT high, never XSHUT low; CHG_EN is released
// unless USB is present and VBAT sense reads < 2 V; LED brightness stays under the USB
// current cap.

#include <Adafruit_NeoPixel.h>
#include <PDM.h>
#include <bluefruit.h>
#include <Wire.h>
#include <vl53l4cx_class.h>

#include "beat.h"

// ---- Hardware --------------------------------------------------------------------
static const uint8_t RING_COUNTS[3] = {10, 16, 24};  // inner, middle, outer (chain order)
static const uint8_t RING_START[3] = {0, 10, 26};

Adafruit_NeoPixel ring(LED_RING_COUNT, PIN_LED_DATA, NEO_GRB + NEO_KHZ800);
VL53L4CX tof(&Wire, PIN_TOF_XSHUT);

enum Mode { MODE_FEAR, MODE_SOUND, MODE_BEAT, MODE_SYNC };
enum ButtonEvent { BUTTON_NONE, BUTTON_SHORT, BUTTON_LONG };
static Mode mode = MODE_FEAR;

// ---- FEAR tuning -----------------------------------------------------------------
static const float REST_BPM = 50.0f;
static const float MAX_BPM = 190.0f;
static const float FEAR_K = 39.0f;          // bpm * m: 50 + 39 / 0.3 = 180 bpm at 0.3 m
static const float FAR_M = 4.5f;            // treated as "nobody there"
static const uint32_t LOST_MS = 800;        // no valid target for this long -> far
static const float APPROACH_ALPHA = 0.5f;   // distance smoothing when coming closer
static const float RETREAT_ALPHA = 0.06f;   // ... and when moving away (slow calm-down)
static const uint8_t FEAR_PEAK = 48;        // of 255 at full fear; <= ~115 mA all rings red
static const float RING_GAIN[3] = {1.0f, 0.85f, 0.7f};
static const float LUB = 1.0f, DUB = 0.6f;

// ---- SOUND tuning ----------------------------------------------------------------
static const uint8_t SOUND_PEAK = 56;       // of 255 at full lightness (after gamma 2.2)

// ---- State -----------------------------------------------------------------------
static bool tofOk = false;
static float distM = FAR_M;
static float lastValidM = FAR_M;
static uint32_t lastValidMs = 0;
static float bpm = REST_BPM;

struct Pulse {
  uint32_t startMs;
  float strength;
};
static Pulse pulses[6];
static uint8_t pulseHead = 0;
static float phase = 0.0f;
static bool dubPending = false;
static uint32_t beatStartMs = 0;

static int16_t pdmBuffer[256];
static volatile int pdmSamples = 0;
static bool pdmRunning = false;
static float floorRms = 55.0f;
static float levelRms = 0.0f;
static float sensitivity = 1.0f;
// Automatic gain (log domain, natural log of RMS): floor follows the quiet gaps,
// ceiling follows the recent loud level; the display spans floor..ceiling.
static bool autoGain = true;
static float levelLog = 0.0f;
static float floorLog = 4.0f;               // ln(55)
static float ceilLog = 4.0f + 3.2f;         // ~25x the floor until it learns
static const float FLOOR_DOWN_TAU_S = 0.16f;  // follow quiet quickly
static const float FLOOR_UP_TAU_S = 16.0f;    // drift up very slowly
static const float CEIL_UP_TAU_S = 0.4f;      // rise on sustained loudness, not one click
static const float CEIL_DOWN_TAU_S = 15.0f;   // relax slowly
static const float MIN_SPAN_LOG = 1.386f;     // ceiling >= 4x the floor: silence stays dark
static const float NOISE_MARGIN_LOG = 0.262f; // 1.3x the floor still reads as dark

static bool chargeInhibited = false;

// ---- SYNC tuning / state ---------------------------------------------------------
static const uint16_t SYNC_COMPANY_ID = 0xFFFF;  // Bluetooth SIG "test / no company"
static const uint8_t SYNC_MAGIC[2] = {'P', 'F'};
static const uint8_t SYNC_VERSION = 1;
static const float SYNC_BPM = 60.0f;        // SYNC beats at this fixed rate (no distance)
static const uint32_t SYNC_TX_MS = 60;      // re-stamp and re-advertise this often
static const uint32_t PEER_TIMEOUT_MS = 1500;
static const int8_t RSSI_FAR = -105;        // weight 0 at or below this (no antennas yet)
static const int8_t RSSI_NEAR = -65;        // weight 1 at or above this
static const float PHASE_COUPLING = 2.0f;   // 1/s per unit weight
static const uint8_t MAX_PEERS = 8;

struct Peer {
  uint16_t id;
  uint32_t rxMs;      // when its last packet arrived
  float phase;        // its phase when that packet was sent (~ at rxMs)
  float ownBpm;       // its distance-driven rate
  float effBpm;       // the rate it is actually beating at
  int8_t rssi;
};
static Peer peers[MAX_PEERS];
static uint16_t myId = 0;
static float ownBpm = REST_BPM;   // this badge's distance-driven rate
static float coupling = 0.0f;     // sum of peer weights (0 = alone)
static float phaseErr = 0.0f;     // smoothed |phase difference| to peers, 0 .. 0.5 beat
static int peersNear = 0;
static bool bleRunning = false;
static bool advOk = false;
static volatile uint32_t rxAny = 0;    // every advertising report the scanner delivers
static bool scanOk = false;
static volatile uint32_t rxCount = 0;  // SYNC packets heard from any peer
static volatile int8_t rxRssi = 0;      // signal strength of the latest one

// ---- Power / charging ------------------------------------------------------------

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

// ---- ToF -------------------------------------------------------------------------

static void tofInit() {
  Wire.begin();
  Wire.setClock(400000);
  tof.begin();
  tof.VL53L4CX_Off();
  VL53L4CX_Error err = tof.InitSensor(0x52);
  if (err == 0) err = tof.VL53L4CX_SetDistanceMode(VL53L4CX_DISTANCEMODE_LONG);
  if (err == 0) err = tof.VL53L4CX_SetMeasurementTimingBudgetMicroSeconds(50000);
  tofOk = (err == 0);
}

static void tofStart() {
  if (tofOk) tof.VL53L4CX_StartMeasurement();
}

static void tofStop() {
  if (tofOk) tof.VL53L4CX_StopMeasurement();  // standby, XSHUT stays high
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

// ---- Mic -------------------------------------------------------------------------

static void onPdmData() {
  int bytes = PDM.available();
  if (bytes > (int)sizeof(pdmBuffer)) bytes = sizeof(pdmBuffer);
  PDM.read(pdmBuffer, bytes);
  pdmSamples = bytes / 2;
}

static void micStart() {
  PDM.setPins(PIN_PDM_DIN, PIN_PDM_CLK, -1);
  PDM.onReceive(onPdmData);
  pdmRunning = PDM.begin(1, 16000);
  if (!pdmRunning) return;
  // L/R strapped to GND: sample on the CLK rising edge (microphone.py).
  NRF_PDM->TASKS_STOP = 1;
  delay(2);
  NRF_PDM->MODE = (PDM_MODE_OPERATION_Mono << PDM_MODE_OPERATION_Pos) |
                  (PDM_MODE_EDGE_LeftRising << PDM_MODE_EDGE_Pos);
  NRF_PDM->TASKS_START = 1;
}

static void micStop() {
  if (pdmRunning) PDM.end();
  pdmRunning = false;
  pdmSamples = 0;
}

static void beatFeed(const int16_t* samples, int n);

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
  // Asymmetric followers in the log domain, timed by the block length (n samples at
  // 16 kHz). Floor: down fast / up slowly, so it settles on the gaps between sounds.
  // Ceiling: up over ~0.4 s / down over ~15 s, so it sits just under recent peaks.
  float dt = n / 16000.0f;
  levelLog = logf(levelRms > 1.0f ? levelRms : 1.0f);
  float tauF = (levelLog < floorLog) ? FLOOR_DOWN_TAU_S : FLOOR_UP_TAU_S;
  floorLog += (1.0f - expf(-dt / tauF)) * (levelLog - floorLog);
  if (floorLog < 1.609f) floorLog = 1.609f;  // ln(5)
  float tauC = (levelLog > ceilLog) ? CEIL_UP_TAU_S : CEIL_DOWN_TAU_S;
  ceilLog += (1.0f - expf(-dt / tauC)) * (levelLog - ceilLog);
  if (ceilLog < floorLog + MIN_SPAN_LOG) ceilLog = floorLog + MIN_SPAN_LOG;
  floorRms = expf(floorLog);
  if (mode == MODE_BEAT || mode == MODE_SOUND) beatFeed(pdmBuffer, n);
}

// Loudness 0..1 for the display: auto gain spans floor..ceiling; fixed spans
// 1.3x..25x the floor (the original behaviour). '+' / '-' shift either.
static float loudness() {
  float lvl = levelLog - logf(sensitivity);
  float lo = floorLog + NOISE_MARGIN_LOG;
  float hi = autoGain ? ceilLog : floorLog + 3.219f;  // ln(25)
  if (hi < lo + 0.3f) hi = lo + 0.3f;
  float x = (lvl - lo) / (hi - lo);
  return x < 0 ? 0 : (x > 1 ? 1 : x);
}

// ---- FEAR mode -------------------------------------------------------------------

static float peerWeight(const Peer& p, uint32_t now) {
  if (p.id == 0 || now - p.rxMs > PEER_TIMEOUT_MS) return 0.0f;
  float w = (float)(p.rssi - RSSI_FAR) / (float)(RSSI_NEAR - RSSI_FAR);
  return w < 0 ? 0 : (w > 1 ? 1 : w);
}

static float wrapHalf(float d) {  // into [-0.5, 0.5)
  while (d >= 0.5f) d -= 1.0f;
  while (d < -0.5f) d += 1.0f;
  return d;
}

static void fearUpdate(float dt, uint32_t now, bool sync) {
  float target = (now - lastValidMs > LOST_MS) ? FAR_M : lastValidM;
  if (target > FAR_M) target = FAR_M;
  float a = (target < distM) ? APPROACH_ALPHA : RETREAT_ALPHA;
  float k = 1.0f - powf(1.0f - a, dt / 0.05f);  // normalised to the 50 ms ToF rate
  distM += k * (target - distM);

  float d = distM < 0.05f ? 0.05f : distM;
  float b = (distM >= FAR_M - 0.01f) ? REST_BPM : REST_BPM + FEAR_K / d;
  ownBpm = sync ? SYNC_BPM : (b > MAX_BPM ? MAX_BPM : b);  // SYNC: one fixed rate
  bpm = ownBpm;

  float phasePull = 0.0f;
  coupling = 0.0f;
  peersNear = 0;
  if (sync) {
    float wSum = 1.0f, bpmSum = ownBpm, errSum = 0.0f;
    for (int i = 0; i < MAX_PEERS; i++) {
      float w = peerWeight(peers[i], now);
      if (w <= 0) continue;
      peersNear++;
      coupling += w;
      bpmSum += w * peers[i].ownBpm;
      wSum += w;
      // Where that peer is now: its stamped phase advanced at its own beating rate.
      float peerNow = peers[i].phase + (now - peers[i].rxMs) / 1000.0f * peers[i].effBpm / 60.0f;
      float d = wrapHalf(peerNow - phase);
      phasePull += w * d;
      errSum += w * fabsf(d);
    }
    bpm = bpmSum / wSum;  // shared heart: weighted average of everyone's own rate
    // Phase error for the display, smoothed over ~0.5 s.
    float err = coupling > 0 ? errSum / coupling : 0.0f;
    phaseErr += (1.0f - expf(-dt / 0.5f)) * (err - phaseErr);
  }

  float period = 60.0f / bpm;
  phase += dt / period + dt * PHASE_COUPLING * phasePull;
  if (phase < 0.0f) phase += 1.0f;  // pulled back past the beat: no extra beat
  if (phase >= 1.0f) {
    phase -= 1.0f;
    beatStartMs = now;
    pulses[pulseHead] = {now, LUB};
    pulseHead = (pulseHead + 1) % 6;
    dubPending = true;
  }
  float dubDelay = fminf(0.30f, 0.32f * period);  // lub -> dub, shorter when racing
  if (dubPending && (now - beatStartMs) >= (uint32_t)(dubDelay * 1000.0f)) {
    pulses[pulseHead] = {now, DUB};
    pulseHead = (pulseHead + 1) % 6;
    dubPending = false;
  }
}

static void fearRender(uint32_t now) {
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

  float peak = FEAR_PEAK * (0.45f + 0.55f * fear);
  for (int r = 0; r < 3; r++) {
    float v = level[r] > 1.0f ? 1.0f : level[r];
    float rgb[3];
    if (mode == MODE_SYNC) {
      // Alone: magenta. Hearing another badge: the colour shows how far apart the beats
      // are - orange when a quarter beat or more apart, through to blue-violet in step.
      static const float ALONE[3] = {1.0f, 0.0f, 0.35f};
      static const float APART[3] = {1.0f, 0.45f, 0.0f};
      static const float LOCKED[3] = {0.35f, 0.25f, 1.0f};
      float m = phaseErr / 0.25f;                     // 0 in step .. 1 a quarter beat or more
      m = m < 0 ? 0 : (m > 1 ? 1 : m);
      float heard = coupling * 2.0f;                  // fade in as the peer's signal firms up
      heard = heard > 1 ? 1 : heard;
      for (int k = 0; k < 3; k++) {
        float phaseCol = LOCKED[k] + (APART[k] - LOCKED[k]) * m;
        rgb[k] = ALONE[k] + (phaseCol - ALONE[k]) * heard;
      }
    } else {
      rgb[0] = 1.0f;
      rgb[1] = 0.18f * fear;                          // hotter when afraid
      rgb[2] = 0.0f;
    }
    uint8_t out[3];
    for (int k = 0; k < 3; k++) {
      float x = v * peak * rgb[k];
      if (rgb[k] > 0.2f && x < 1.0f) x = 1.0f;        // faint ember between beats
      out[k] = (uint8_t)x;
    }
    uint32_t c = ring.Color(out[0], out[1], out[2]);
    for (int i = 0; i < RING_COUNTS[r]; i++) ring.setPixelColor(RING_START[r] + i, c);
  }
  ring.show();
}

// ---- SOUND mode ------------------------------------------------------------------

// Radar: a beam sweeps clockwise (as seen from the front) once every SWEEP_S. As it
// passes each LED - by the LED's true angle on the board, so the rings' different
// spacings don't matter - the LED takes the current loudness and then fades slowly,
// leaving a trail that is a polar history of the last few seconds of sound.
// Loudness is one continuous value x in 0..1 (log scale over the background floor):
// it sets how far out the beam reaches (inner ring ramps in over x 0-0.33, middle
// 0.33-0.67, outer 0.67-1) and the colour (blue -> green -> red).
static const float SWEEP_S = 1.0f;
static const float TRAIL_TAU_S = 0.4f;       // fade time constant behind the beam
static const float ENV_RELEASE_S = 0.18f;    // so a short clap still paints an LED or two
// LED angles from proximity_fear/circuits/led_rings.py RING_SPECS (RingSpec.angle_deg).
static const float RING_OFFSET_DEG[3] = {90.0f, 62.8f, 34.5f};
static const bool RING_CLOCKWISE[3] = {false, false, true};
static float ledAngle[LED_RING_COUNT];
static float trail[LED_RING_COUNT][3];
static float beamDeg = 90.0f;
static float loudEnv = 0.0f;

static void radarInit() {
  for (int r = 0; r < 3; r++) {
    for (int k = 0; k < RING_COUNTS[r]; k++) {
      float step = 360.0f * k / RING_COUNTS[r];
      float a = RING_CLOCKWISE[r] ? RING_OFFSET_DEG[r] - step : RING_OFFSET_DEG[r] + step;
      a = fmodf(a, 360.0f);
      if (a < 0) a += 360.0f;
      ledAngle[RING_START[r] + k] = a;
    }
  }
}

static void radarClear() {
  for (int i = 0; i < LED_RING_COUNT; i++) trail[i][0] = trail[i][1] = trail[i][2] = 0;
  loudEnv = 0;
}

static void hueColour(float x, float rgb[3]) {  // 0 blue -> 0.5 green -> 1 red
  if (x < 0.5f) {
    float t = x / 0.5f;
    rgb[0] = 0; rgb[1] = t; rgb[2] = 1.0f - t;
  } else {
    float t = (x - 0.5f) / 0.5f;
    rgb[0] = t; rgb[1] = 1.0f - t; rgb[2] = 0;
  }
}

// Output: trail values are perceptual (0..1 lightness); LEDs get gamma 2.2 so equal
// steps look equal, with per-LED temporal dithering so faint tails fade smoothly
// instead of stepping to black at the bottom of the 8-bit range.
static const float RADAR_GAMMA = 2.2f;
static float ditherErr[LED_RING_COUNT][3];

static uint8_t perceptualOut(int i, int c, float v) {
  v = v < 0 ? 0 : (v > 1 ? 1 : v);
  float x = powf(v, RADAR_GAMMA) * SOUND_PEAK + ditherErr[i][c];
  int o = (int)x;
  if (o < 0) o = 0;
  if (o > 255) o = 255;
  ditherErr[i][c] = x - o;
  return (uint8_t)o;
}

static float radarLoudness();
static bool radarHue(float rgb[3]);

static void soundRender(float dt) {
  // Continuous loudness with instant attack and a short release.
  float x = radarLoudness();
  loudEnv = (x > loudEnv) ? x : loudEnv * expf(-dt / ENV_RELEASE_S);

  float sweep = 360.0f * dt / SWEEP_S;
  float prevBeam = beamDeg;
  beamDeg = fmodf(beamDeg - sweep + 360.0f, 360.0f);  // clockwise
  float fade = expf(-dt / TRAIL_TAU_S);
  float rgb[3];
  if (!radarHue(rgb) || !autoGain) hueColour(loudEnv, rgb);  // fixed gain: loudness colours

  for (int r = 0; r < 3; r++) {
    // Radial reach: this ring ramps in over its third of the loudness range.
    float lo = r / 3.0f;
    float reach = (loudEnv - lo) * 3.0f;
    reach = reach < 0 ? 0 : (reach > 1 ? 1 : reach);
    for (int k = 0; k < RING_COUNTS[r]; k++) {
      int i = RING_START[r] + k;
      for (int c = 0; c < 3; c++) trail[i][c] *= fade;
      // Did the beam just pass this LED? (angle between the new and previous beam)
      float behind = fmodf(ledAngle[i] - beamDeg + 360.0f, 360.0f);
      if (behind <= fmodf(prevBeam - beamDeg + 360.0f, 360.0f) && reach > 0) {
        for (int c = 0; c < 3; c++) {
          float v = rgb[c] * reach;
          if (v > trail[i][c]) trail[i][c] = v;
        }
      }
      // A faint beam head so the sweep is visible in silence.
      float head = 0.0f;
      if (behind < 20.0f) head = 0.22f * (1.0f - behind / 20.0f);
      uint8_t out[3];
      for (int c = 0; c < 3; c++) out[c] = perceptualOut(i, c, trail[i][c] + head * 0.6f);
      ring.setPixelColor(i, out[0], out[1], out[2]);
    }
  }
  ring.show();
}

// ---- BEAT mode ---------------------------------------------------------------------

BeatDetector beats;
TempoTracker tempo;
static uint32_t onsetCount = 0;
static int16_t audioCopy[256];

// Floor / ceiling follower for one band group (log domain), like the radar's gain.
struct Follower {
  float lo = 0, hi = 1;
  bool primed = false;
  void update(float v, float dt) {
    if (!primed) { lo = v; hi = v + 1.5f; primed = true; }
    lo += (1.0f - expf(-dt / (v < lo ? 0.3f : 10.0f))) * (v - lo);
    hi += (1.0f - expf(-dt / (v > hi ? 0.5f : 4.0f))) * (v - hi);
    if (hi < lo + 1.5f) hi = lo + 1.5f;   // min span: quiet stays dark
    if (hi > lo + 4.5f) hi = lo + 4.5f;   // max span: one bang can't park the ceiling high
  }
  float norm(float v) const {
    float x = (v - lo) / (hi - lo);
    return x < 0 ? 0 : (x > 1 ? 1 : x);
  }
};
static Follower groupGain[3];       // bass, mids, treble
static Follower loudGain;           // whole-spectrum loudness
static float specLoud = 0.0f;       // 0..1 auto-ranged perceptual loudness
// Timbre colour: spectral centroid over the auto-ranged mel bands, 0 dark .. 1 bright.
static float bandFloor[BeatDetector::BANDS];
static bool bandFloorPrimed = false;
static float curC = 0.3f;           // now (~0.1 s smoothing)
static float moodC = 0.3f;          // mood (~3 s smoothing)
static float beatC = 0.3f;          // the latest beat's colour
static float pulseC[6];             // colour of each ripple
static float cLo = 0.3f, cHi = 0.6f;  // auto-range of the timbre (darkest / brightest lately)

// Timbre auto-ranged to 0..1 over what has been heard in the last ~15 s, so any music
// uses the whole palette.
static float timbreNorm(float c) {
  float x = (c - cLo) / (cHi - cLo);
  return x < 0 ? 0 : (x > 1 ? 1 : x);
}
static float groupLevel[3] = {0, 0, 0};
static float groupRaw[3] = {0, 0, 0};    // latest group log energy (debug)
static uint32_t analysisFrames = 0;      // spectral frames analysed (debug: rate)
static const float GROUP_EDGES_HZ[2] = {250.0f, 2000.0f};

// Radar helpers (declared before soundRender).
static float radarLoudness() { return autoGain ? specLoud : loudness(); }

// Colour from the balance of bass / mids / treble (after audio-reactive-led-strip's
// scroll effect: red = lows, green = mids, blue = highs), each auto-ranged and squared
// so the dominant band wins; normalised so the strongest channel is 1.
static bool radarHue(float rgb[3]) {
  float b = groupLevel[0] * groupLevel[0], m = groupLevel[1] * groupLevel[1],
        t = groupLevel[2] * groupLevel[2];
  float mx = fmaxf(b, fmaxf(m, t));
  if (mx < 0.02f) return false;
  rgb[0] = b / mx;
  rgb[1] = m / mx;
  rgb[2] = t / mx;
  return true;
}

static void beatFeed(const int16_t* samples, int n) {
  memcpy(audioCopy, samples, n * sizeof(int16_t));
  // Gate: no onsets from room noise (the level must be ~2x the background floor).
  bool gate = levelLog > floorLog + 0.7f;
  if (beats.push(audioCopy, n, gate)) {
    static uint32_t lastAnalysisMs = 0;
    uint32_t nowMs = millis();
    float dtA = lastAnalysisMs ? (nowMs - lastAnalysisMs) / 1000.0f : BeatDetector::HOP / 16000.0f;
    if (dtA > 0.1f) dtA = 0.1f;
    lastAnalysisMs = nowMs;
    analysisFrames++;
    beatAnalysed(dtA);
    if (mode == MODE_BEAT && beats.onset) {
      onsetCount++;
      float strength = 0.5f + 0.25f * (beats.onsetStrength - 1.0f);
      strength = strength < 0.5f ? 0.5f : (strength > 1.0f ? 1.0f : strength);
      beatC = timbreNorm(curC);  // this hit's timbre colours its ripple
      if (tempo.onOnset(millis())) beatPulse(strength);
    }
  }
}

static void beatPulse(float strength) {
  pulseC[pulseHead] = beatC;  // predicted beats reuse the last hit's colour
  pulses[pulseHead] = {millis(), strength};
  pulseHead = (pulseHead + 1) % 6;
}

static void beatAnalysed(float dt) {
  float sum[3] = {0, 0, 0};
  int cnt[3] = {0, 0, 0};
  for (int b = 0; b < BeatDetector::BANDS; b++) {
    int g = beats.bandHz[b] < GROUP_EDGES_HZ[0] ? 0 : (beats.bandHz[b] < GROUP_EDGES_HZ[1] ? 1 : 2);
    sum[g] += beats.logMel[b];
    cnt[g]++;
  }
  // Perceptual loudness: mean log energy over the mel bands (a geometric mean, so a
  // bass rumble doesn't swamp it the way raw RMS does), auto-ranged like the groups.
  float all = 0;
  for (int b = 0; b < BeatDetector::BANDS; b++) all += beats.logMel[b];
  all /= BeatDetector::BANDS;
  loudGain.update(all, dt);
  // Spectral centroid of what stands above each band's own floor (so it reflects the
  // music's timbre, not the mic's fixed tilt), in band index -> 0..1.
  float wsum = 0, csum = 0;
  for (int b = 0; b < BeatDetector::BANDS; b++) {
    float v = beats.logMel[b];
    if (!bandFloorPrimed) bandFloor[b] = v;
    bandFloor[b] += (1.0f - expf(-dt / (v < bandFloor[b] ? 0.3f : 10.0f))) * (v - bandFloor[b]);
    float w = v - bandFloor[b] - 0.3f;
    if (w > 0) { wsum += w; csum += w * b; }
  }
  bandFloorPrimed = true;
  if (wsum > 0.5f) {
    float c = csum / wsum / (BeatDetector::BANDS - 1);
    curC += (1.0f - expf(-dt / 0.1f)) * (c - curC);
    moodC += (1.0f - expf(-dt / 3.0f)) * (c - moodC);
    cLo += (1.0f - expf(-dt / (curC < cLo ? 0.5f : 15.0f))) * (curC - cLo);
    cHi += (1.0f - expf(-dt / (curC > cHi ? 0.5f : 15.0f))) * (curC - cHi);
    if (cHi < cLo + 0.12f) {  // minimum span, so a steady sound doesn't flash every hue
      float mid = 0.5f * (cLo + cHi);
      cLo = mid - 0.06f;
      cHi = mid + 0.06f;
    }
  }
  float lx = loudGain.norm(all);
  specLoud = (lx > specLoud) ? lx : specLoud * 0.9f;  // fast rise, quick fall (per 16 ms)
  for (int g = 0; g < 3; g++) {
    float v = cnt[g] ? sum[g] / cnt[g] : 0;
    groupRaw[g] = v;
    groupGain[g].update(v, dt);
    float x = groupGain[g].norm(v);
    groupLevel[g] = (x > groupLevel[g]) ? x : groupLevel[g] * 0.85f;  // fast rise, quick fall
  }
}

// Palette: timbre 0 (dark, bassy) .. 1 (bright, hissy) runs the visible spectrum in
// wavelength order, red -> orange -> yellow -> green -> cyan -> blue -> violet (hue 0 to
// 275 deg): low sounds long-wavelength colours, high sounds short ones.
static void paletteRGB(float c, float sat, float rgb[3]) {
  c = c < 0 ? 0 : (c > 1 ? 1 : c);
  float h = fmodf(275.0f * c, 360.0f) / 60.0f;
  int sector = (int)h;
  float f = h - sector;
  float p = 1.0f - sat, q = 1.0f - sat * f, t = 1.0f - sat * (1.0f - f);
  switch (sector) {
    case 0: rgb[0] = 1; rgb[1] = t; rgb[2] = p; break;
    case 1: rgb[0] = q; rgb[1] = 1; rgb[2] = p; break;
    case 2: rgb[0] = p; rgb[1] = 1; rgb[2] = t; break;
    case 3: rgb[0] = p; rgb[1] = q; rgb[2] = 1; break;
    case 4: rgb[0] = t; rgb[1] = p; rgb[2] = 1; break;
    default: rgb[0] = 1; rgb[1] = p; rgb[2] = q; break;
  }
}

static void beatRender(uint32_t now) {
  const float ringDelay = 0.05f, attack = 0.015f, tau = 0.12f;
  static const int GROUP_FOR_RING[3] = {2, 1, 0};      // inner treble, middle mids, outer bass
  static const float RING_SHIFT[3] = {0.08f, 0.04f, 0.0f};  // slight hue offset per ring
  const float AMBIENT = 0.38f;                          // perceptual lightness of the glow

  for (int r = 0; r < 3; r++) {
    // Mood glow: the slow timbre colour, brightness from this ring's band.
    float col[3], acc[3];
    paletteRGB(timbreNorm(moodC) + RING_SHIFT[r], 0.8f, col);
    float a = AMBIENT * groupLevel[GROUP_FOR_RING[r]];
    for (int k = 0; k < 3; k++) acc[k] = col[k] * a;
    // Ripples: each beat's own colour, pale at the crest settling to full colour.
    for (int p = 0; p < 6; p++) {
      if (pulses[p].strength <= 0) continue;
      float age = (now - pulses[p].startMs) / 1000.0f;
      if (age > 1.5f) {
        pulses[p].strength = 0;
        continue;
      }
      float t = age - r * ringDelay;
      if (t < 0) continue;
      float e = (t < attack) ? t / attack : expf(-(t - attack) / tau);
      paletteRGB(pulseC[p] + RING_SHIFT[r], 0.9f - 0.4f * e, col);
      for (int k = 0; k < 3; k++) acc[k] += col[k] * e * pulses[p].strength;
    }
    for (int k = 0; k < 3; k++) acc[k] = acc[k] > 1 ? 1 : acc[k];
    for (int i = 0; i < RING_COUNTS[r]; i++) {
      int idx = RING_START[r] + i;
      ring.setPixelColor(idx, perceptualOut(idx, 0, acc[0]), perceptualOut(idx, 1, acc[1]),
                         perceptualOut(idx, 2, acc[2]));
    }
  }
  ring.show();
}

// ---- SYNC: BLE broadcast + listen --------------------------------------------------

static void putU16(uint8_t* b, uint16_t v) {
  b[0] = v & 0xFF;
  b[1] = v >> 8;
}

static uint16_t getU16(const uint8_t* b) { return b[0] | (b[1] << 8); }

// Manufacturer data: company(2) 'P' 'F' version id(2) phase(2) ownBpm*10(2) effBpm*10(2)
static void syncAdvertise() {
  uint8_t msd[13];
  putU16(msd, SYNC_COMPANY_ID);
  msd[2] = SYNC_MAGIC[0];
  msd[3] = SYNC_MAGIC[1];
  msd[4] = SYNC_VERSION;
  putU16(msd + 5, myId);
  putU16(msd + 7, (uint16_t)(phase * 65535.0f));
  putU16(msd + 9, (uint16_t)(ownBpm * 10.0f));
  putU16(msd + 11, (uint16_t)(bpm * 10.0f));
  // Restart so the first packet goes out right after the phase is stamped.
  Bluefruit.Advertising.stop();
  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAG_BR_EDR_NOT_SUPPORTED);
  Bluefruit.Advertising.addManufacturerData(msd, sizeof(msd));
  advOk = Bluefruit.Advertising.start(0);
}

static void onScan(ble_gap_evt_adv_report_t* report) {
  rxAny++;
  uint8_t msd[16];
  uint8_t len = Bluefruit.Scanner.parseReportByType(
      report, BLE_GAP_AD_TYPE_MANUFACTURER_SPECIFIC_DATA, msd, sizeof(msd));
  if (len == 13 && getU16(msd) == SYNC_COMPANY_ID && msd[2] == SYNC_MAGIC[0] &&
      msd[3] == SYNC_MAGIC[1] && msd[4] == SYNC_VERSION) {
    uint16_t id = getU16(msd + 5);
    if (id != myId) {
      rxCount++;
      rxRssi = report->rssi;
      uint32_t now = millis();
      int slot = -1, oldest = 0;
      for (int i = 0; i < MAX_PEERS; i++) {
        if (peers[i].id == id) { slot = i; break; }
        if (peers[i].rxMs < peers[oldest].rxMs) oldest = i;
      }
      if (slot < 0) slot = oldest;
      Peer& p = peers[slot];
      p.id = id;
      p.rxMs = now;
      p.phase = getU16(msd + 7) / 65535.0f;
      p.ownBpm = getU16(msd + 9) / 10.0f;
      p.effBpm = getU16(msd + 11) / 10.0f;
      p.rssi = report->rssi;
    }
  }
  Bluefruit.Scanner.resume();  // the library pauses scanning after each report
}

static void bleSetup() {
  Bluefruit.autoConnLed(false);
  Bluefruit.begin(1, 1);
  Bluefruit.setTxPower(4);
  Bluefruit.setName("PF Badge");
  Bluefruit.Advertising.setType(BLE_GAP_ADV_TYPE_NONCONNECTABLE_NONSCANNABLE_UNDIRECTED);
  Bluefruit.Advertising.setInterval(32, 32);    // 20 ms (0.625 ms units); restamped every 60 ms
  Bluefruit.Advertising.restartOnDisconnect(false);
  Bluefruit.Scanner.setRxCallback(onScan);
  Bluefruit.Scanner.useActiveScan(false);
  Bluefruit.Scanner.setInterval(160, 80);   // 100 ms interval, 50 ms window (room to advertise)
  myId = (uint16_t)(NRF_FICR->DEVICEID[0] & 0xFFFF);
  if (myId == 0) myId = 1;
}

static void bleStart() {
  for (int i = 0; i < MAX_PEERS; i++) peers[i].id = 0;
  scanOk = Bluefruit.Scanner.start(0);
  syncAdvertise();
  bleRunning = true;
}

static void bleStop() {
  if (!bleRunning) return;
  Bluefruit.Scanner.stop();
  Bluefruit.Advertising.stop();
  bleRunning = false;
  coupling = 0;
  peersNear = 0;
}

// ---- Mode switching --------------------------------------------------------------

static void modeFlash(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < LED_RING_COUNT; i++) ring.setPixelColor(i, r, g, b);
  ring.show();
  delay(250);
  ring.clear();
  ring.show();
}

static void enterMode(Mode m) {
  mode = m;
  if (m != MODE_SYNC) bleStop();
  if (m == MODE_FEAR) modeFlash(24, 0, 0);
  else if (m == MODE_SOUND) modeFlash(0, 24, 0);
  else if (m == MODE_BEAT) modeFlash(0, 0, 24);
  else modeFlash(16, 0, 24);
  if (m == MODE_FEAR || m == MODE_SYNC) {
    micStop();
    distM = FAR_M;
    lastValidMs = 0;
    bpm = REST_BPM;
    phase = 0.9f;  // first beat comes almost at once
    for (int p = 0; p < 6; p++) pulses[p].strength = 0;
    tofStart();
    if (m == MODE_SYNC) bleStart();
    Serial.println(m == MODE_SYNC ? "mode: SYNC" : "mode: FEAR");
  } else {
    tofStop();
    radarClear();
    for (int p = 0; p < 6; p++) pulses[p].strength = 0;
    tempo = TempoTracker();
    for (int g = 0; g < 3; g++) { groupGain[g] = Follower(); groupLevel[g] = 0; }
    loudGain = Follower();
    specLoud = 0;
    bandFloorPrimed = false;
    cLo = 0.3f;
    cHi = 0.6f;
    micStart();
    Serial.println(m == MODE_BEAT ? "mode: BEAT" : "mode: SOUND");
  }
}

static const uint32_t LONG_PRESS_MS = 800;

// Debounced: SHORT on release of a press under LONG_PRESS_MS; LONG once, while still
// held, when the press reaches LONG_PRESS_MS (its release is then ignored).
static ButtonEvent buttonEvent(uint32_t now) {
  static int stable = HIGH, lastRaw = HIGH;
  static uint32_t changedMs = 0, pressedMs = 0;
  static bool longSent = false;
  int raw = digitalRead(PIN_USER_BUTTON);
  if (raw != lastRaw) {
    lastRaw = raw;
    changedMs = now;
  }
  if (now - changedMs > 30 && raw != stable) {
    stable = raw;
    if (stable == LOW) {
      pressedMs = now;
      longSent = false;
    } else if (!longSent) {
      return BUTTON_SHORT;
    }
  }
  if (stable == LOW && !longSent && now - pressedMs >= LONG_PRESS_MS) {
    longSent = true;
    return BUTTON_LONG;
  }
  return BUTTON_NONE;
}

// Confirm the auto-gain setting: auto = a white sweep once round the rings (by true
// angle); fixed = one dim white flash.
static void gainFlash() {
  if (autoGain) {
    for (int step = 0; step <= 36; step++) {
      float beam = fmodf(90.0f - step * 10.0f + 720.0f, 360.0f);
      for (int i = 0; i < LED_RING_COUNT; i++) {
        float behind = fmodf(ledAngle[i] - beam + 360.0f, 360.0f);
        uint8_t v = behind < 40.0f ? (uint8_t)(20.0f * (1.0f - behind / 40.0f)) : 0;
        ring.setPixelColor(i, v, v, v);
      }
      ring.show();
      delay(12);
    }
  } else {
    for (int i = 0; i < LED_RING_COUNT; i++) ring.setPixelColor(i, 6, 6, 6);
    ring.show();
    delay(300);
  }
  ring.clear();
  ring.show();
  Serial.println(autoGain ? "gain: AUTO" : "gain: FIXED");
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_USER_BUTTON, INPUT_PULLUP);

  pinMode(PIN_LED_EN, OUTPUT);
  digitalWrite(PIN_LED_EN, HIGH);  // VLED on (soft start)
  delay(5);
  ring.begin();
  radarInit();
  beats.begin(16000.0f);

  tofInit();
  bleSetup();
  chargeRule();
  enterMode(MODE_FEAR);
}

void loop() {
  static uint32_t lastFrame = millis(), lastCharge = 0, lastPrint = 0;
  uint32_t now = millis();

  ButtonEvent ev = buttonEvent(now);
  if (ev == BUTTON_SHORT) {
    enterMode(mode == MODE_FEAR ? MODE_SOUND : mode == MODE_SOUND ? MODE_BEAT
              : mode == MODE_BEAT ? MODE_SYNC : MODE_FEAR);
  } else if (ev == BUTTON_LONG) {
    autoGain = !autoGain;
    gainFlash();
  }

  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'U') enterUf2Dfu();          // reboot into the FEARBOOT drive (upload.sh)
    if (c == 'F') enterMode(MODE_FEAR);   // serial mode select (bench testing)
    if (c == 'S') enterMode(MODE_SOUND);
    if (c == 'B') enterMode(MODE_BEAT);
    if (c == 'Y') enterMode(MODE_SYNC);
    if (c == '+') sensitivity *= 0.8f;
    if (c == '-') sensitivity *= 1.25f;
  }

  if (mode == MODE_SOUND || mode == MODE_BEAT) processAudio();
  else tofPoll();

  if (now - lastFrame >= 10) {
    float dt = (now - lastFrame) / 1000.0f;
    lastFrame = now;
    if (mode == MODE_SOUND) {
      soundRender(dt);
    } else if (mode == MODE_BEAT) {
      if (tempo.tick(now)) beatPulse(0.75f);
      beatRender(now);
    } else {
      fearUpdate(dt, now, mode == MODE_SYNC);
      fearRender(now);
    }
  }
  static uint32_t lastTx = 0;
  if (mode == MODE_SYNC && now - lastTx >= SYNC_TX_MS) {
    lastTx = now;
    syncAdvertise();
  }
  if (now - lastCharge >= 1000) {
    lastCharge = now;
    chargeRule();
  }
  if (now - lastPrint >= 500) {
    lastPrint = now;
    if (mode == MODE_BEAT) {
      Serial.print("BEAT  ");
      Serial.print(tempo.locked() ? "locked " : "listening ");
      Serial.print(tempo.bpm(), 0);
      Serial.print(" bpm  onsets ");
      Serial.print(onsetCount);
      Serial.print("  flux ");
      Serial.print(beats.flux, 2);
      Serial.print(" / thr ");
      Serial.print(beats.threshold, 2);
      Serial.print("  bass/mid/treble ");
      Serial.print(groupLevel[0], 2); Serial.print(" ");
      Serial.print(groupLevel[1], 2); Serial.print(" ");
      Serial.println(groupLevel[2], 2);
    } else if (mode != MODE_SOUND) {
      Serial.print(mode == MODE_SYNC ? "SYNC  dist " : "FEAR  dist ");
      if (!tofOk) Serial.print("ToF FAIL");
      else if (distM >= FAR_M - 0.01f) Serial.print("nobody");
      else { Serial.print(distM, 2); Serial.print(" m"); }
      Serial.print("  bpm ");
      Serial.print(bpm, 0);
      if (mode == MODE_SYNC) {
        Serial.print("  own ");
        Serial.print(ownBpm, 0);
        Serial.print(advOk ? "  adv ok" : "  adv FAIL");
        Serial.print(scanOk ? "  scan ok" : "  scan FAIL");
        Serial.print("  any ");
        Serial.print(rxAny);
        Serial.print("  heard ");
        Serial.print(rxCount);
        Serial.print(" (rssi ");
        Serial.print(rxRssi);
        Serial.print(")  err ");
        Serial.print(phaseErr, 2);
        Serial.print("  peers ");
        Serial.print(peersNear);
        for (int i = 0; i < MAX_PEERS; i++) {
          if (peerWeight(peers[i], now) <= 0) continue;
          float peerNow = peers[i].phase + (now - peers[i].rxMs) / 1000.0f * peers[i].effBpm / 60.0f;
          Serial.print("  [");
          Serial.print(peers[i].id, HEX);
          Serial.print(" rssi ");
          Serial.print(peers[i].rssi);
          Serial.print(" dphase ");
          Serial.print(wrapHalf(peerNow - phase), 2);
          Serial.print("]");
        }
      }
      Serial.println();
    } else {
      Serial.print(autoGain ? "SOUND  auto  floor " : "SOUND  fixed  floor ");
      Serial.print(floorRms, 0);
      Serial.print("  ceiling ");
      Serial.print(expf(ceilLog), 0);
      Serial.print("  x ");
      Serial.print(loudness(), 2);
      Serial.print("  level ");
      Serial.print(levelRms, 0);
      Serial.print("  sensitivity x");
      Serial.println(1.0f / sensitivity, 2);
    }
  }
}
