// Proximity Fear Badge: main firmware.
//
// Board: adafruit:nrf52:proximityfear (firmware/arduino, install_variant.sh).
// The button steps through four modes, SYNC -> FEAR -> SOUND -> BEAT (starts in SYNC);
// each mode announces itself with a short flash (violet / red / green / blue). A quick
// double press restarts sync (forgets the lock, two violet flashes):
//
// FEAR (fw-02): the VL53L4CX measures the distance to whoever is in front and the heart
//   rate rises inversely with it: bpm = REST_BPM + FEAR_K / distance_m (clamped), so
//   ~180 bpm at 0.3 m, ~90 at 1 m, ~70 at 2 m, ~60 at 4 m, REST_BPM with nobody there.
//   Each beat is a lub-dub, each pulse radiating inner -> outer ring. Fast to fear,
//   slow to calm down; continuous beat phase. Purple; closer = brighter and pinker;
//   closer than 60 cm the rings start to sparkle a little, more and more the closer
//   someone comes, going wild at 10 cm or less.
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
// SYNC (fw-05): badge-to-badge beat sync, face to face over IR (SYNC_BLE = false):
//   the ToF gates the IR receiver/transmitter on when something is within 2 m; each
//   beat is sent as a 38 kHz burst after a random 40-160 ms delay that the burst length
//   encodes; a receiving badge pulls its phase toward the sender's beat, spread over
//   ~0.25 s so no beat is skipped. Fixed 60 bpm, so badges stay in step out of sight;
//   once linked, the badge keeps its sync state and colour indefinitely out of sight and
//   re-syncs when the badges see each other again (magenta only before first contact).
//   With SYNC_BLE = true (once antennas fit) the BLE version below is used instead:
//   Each badge
//   broadcasts its beat phase and bpm in a non-connectable advertisement and listens
//   for the others (no pairing). Peers in range (weighted by RSSI) pull each other's
//   phase together (Kuramoto-style coupling). Every badge beats at a fixed SYNC_BPM
//   (60) here - distance doesn't change the rate - so only the phase has to lock.
//   Colour: blue alone; hearing another badge, yellow when the beats are a quarter beat
//   or more apart, orange closing in, red when locked in step.
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
enum ButtonEvent { BUTTON_NONE, BUTTON_SHORT, BUTTON_DOUBLE, BUTTON_LONG };

// SYNC peer record (BLE path); defined up here so Arduino's generated prototypes see it.
struct Peer {
  uint16_t id;
  uint32_t rxMs;      // when its last packet arrived
  float phase;        // its phase when that packet was sent (~ at rxMs)
  float ownBpm;       // its distance-driven rate
  float effBpm;       // the rate it is actually beating at
  int8_t rssi;
};
static Mode mode = MODE_FEAR;

// ---- FEAR tuning -----------------------------------------------------------------
static const float REST_BPM = 50.0f;
static const float MAX_BPM = 190.0f;
static const float FEAR_K = 39.0f;          // bpm * m: 50 + 39 / 0.3 = 180 bpm at 0.3 m
static const float FAR_M = 4.5f;            // treated as "nobody there"
static const uint32_t LOST_MS = 800;        // no valid target for this long -> far
static const float APPROACH_ALPHA = 0.5f;   // distance smoothing when coming closer
static const float RETREAT_ALPHA = 0.06f;   // ... and when moving away (slow calm-down)
static const uint8_t FEAR_PEAK = 48;        // of 255 at full fear; <= ~115 mA all rings lit
static const uint8_t SPARK_PEAK = 64;       // of 255, brightest sparkle
static const float SPARK_START_M = 0.60f;   // a few sparkles begin closer than this
static const float SPARK_FULL_M = 0.10f;    // ... and go wild at or inside this
static const float RING_GAIN[3] = {1.0f, 0.85f, 0.7f};
static const float LUB = 1.0f, DUB = 0.6f;

// ---- SOUND tuning ----------------------------------------------------------------
static const uint8_t SOUND_PEAK = 56;       // of 255 at full lightness (after gamma 2.2)

// ---- State -----------------------------------------------------------------------
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
static const bool SYNC_BLE = false;         // BLE beat sync (needs antennas); IR is used instead
static float tofAnyM = 9.9f;                // nearest target of any status (SYNC presence gate)
static uint32_t tofAnyMs = 0;
static bool tofOk = false;
static void tofStart();
static void tofStop();

// ---- SYNC over IR ---------------------------------------------------------------
// Face to face: when the ToF sees something within IR_GATE_M, the IR receiver is powered
// and each beat is announced with one 38 kHz burst, sent a random 40/80/120/160 ms after
// the beat with a burst length (500/850/1200/1550 us) that says which delay was used.
// A receiving badge subtracts that delay to get the sender's beat time. The random delay
// keeps two locked badges from always transmitting at the same instant (each ignores its
// receiver while it transmits, so identical timing would make them deaf to each other).
static const float IR_GATE_M = 2.0f;
static const uint16_t IR_DELAY_MS[4] = {40, 80, 120, 160};
static const uint16_t IR_BURST_US[4] = {500, 850, 1200, 1550};
static const float IR_COUPLING = 0.4f;      // phase correction per received beat
static const uint32_t IR_HEARD_MS = 3000;   // a peer counts as present this long after a beat
static float irPendingCorr = 0.0f;          // phase correction still to apply (spread smoothly)
static uint32_t irPrevPeerBeat = 0;         // last candidate peer beat time (for the rhythm check)
static uint32_t irImplausible = 0;          // bursts dropped by the rhythm check

static bool irGateOn = false;
static bool irTofPaused = false;     // ToF stopped while the IR link is up
static uint32_t irLastBeatSeen = 0;         // beatStartMs already handled
static uint32_t irTxDueMs = 0;
static int irTxSlot = -1;
static volatile uint32_t irBlankUntilUs = 0;
static volatile uint32_t irFallUs = 0;
struct IrEvent { uint32_t ms; uint8_t slot; };
static volatile IrEvent irEvents[4];
static volatile uint8_t irHead = 0, irTail = 0;
static uint32_t irRxCount = 0, irTxCount = 0, irLastHeardMs = 0;
static volatile uint32_t irLastWidth = 0, irRejected = 0;
static uint16_t irSeq[1] = {210 | 0x8000};  // PWM2 duty: 50 % of 421 counts

static void irCarrier(bool on) {               // 38 kHz on PWM2 (16 MHz / 421)
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
    delayMicroseconds(20);
    NRF_PWM2->ENABLE = 0;
    NRF_PWM2->PSEL.OUT[0] = 0xFFFFFFFFUL;
    digitalWrite(PIN_IR_TX, LOW);
  }
}

static void onIrChange() {                     // receiver output is active low
  uint32_t us = micros();
  if (digitalRead(PIN_IR_RX) == LOW) {
    irFallUs = us;
    return;
  }
  if ((int32_t)(us - irBlankUntilUs) < 0) return;  // our own burst (or its reflection)
  uint32_t w = us - irFallUs;
  irLastWidth = w;
  int slot = -1;                               // must match one of our burst lengths
  for (int k = 0; k < 4; k++) {
    if ((int32_t)w > IR_BURST_US[k] - 175 && (int32_t)w < IR_BURST_US[k] + 175) slot = k;
  }
  if (slot < 0) {
    irRejected++;
    return;
  }
  uint8_t next = (irHead + 1) % 4;
  if (next == irTail) return;
  irEvents[irHead].ms = millis();
  irEvents[irHead].slot = slot;
  irHead = next;
}

static void irRxPower(bool on) {
  if (on) {
    digitalWrite(PIN_IR_RX_EN, LOW);           // receiver supply on
    delay(2);
    pinMode(PIN_IR_RX, INPUT_PULLUP);
    irBlankUntilUs = micros() + 100000;        // ignore power-up glitches for 100 ms
    attachInterrupt(digitalPinToInterrupt(PIN_IR_RX), onIrChange, CHANGE);
  } else {
    detachInterrupt(digitalPinToInterrupt(PIN_IR_RX));
    pinMode(PIN_IR_RX, INPUT);                 // no pull before the supply goes off
    digitalWrite(PIN_IR_RX_EN, HIGH);          // receiver off
  }
}

static void irSyncStop() {
  irTofPaused = false;
  if (irGateOn) irRxPower(false);
  irGateOn = false;
  irTxSlot = -1;
  irCarrier(false);
}

// Called every loop in SYNC: gate on the ToF, schedule and send this beat's burst.
static void irSyncTick(uint32_t now, uint32_t beatMs) {
  // Gate: on when the ToF sees anything within IR_GATE_M (any status - two facing
  // badges' ToF lasers jam each other's "valid" readings) or a peer's IR beat has been
  // heard in the last 5 s; off 3 s after neither.
  static uint32_t lastSeenMs = 0;
  bool peerHeard = irLastHeardMs && (now - irLastHeardMs < 5000);
  if (((now - tofAnyMs < 500) && tofAnyM < IR_GATE_M) || peerHeard) lastSeenMs = now;
  bool someone = lastSeenMs && (now - lastSeenMs < 3000);
  if (someone != irGateOn) {
    irGateOn = someone;
    irRxPower(someone);
    irTxSlot = -1;
  }
  // While the IR link is up the ToF isn't needed: stop its laser so it doesn't jam the
  // other badge's IR receiver and ToF (and save power); restart it when the link drops.
  if (peerHeard && !irTofPaused) {
    tofStop();
    irTofPaused = true;
  } else if (!peerHeard && irTofPaused) {
    tofStart();
    irTofPaused = false;
  }
  if (!irGateOn) return;
  if (beatMs != irLastBeatSeen) {              // a new beat: pick this beat's delay slot
    irLastBeatSeen = beatMs;
    irTxSlot = random(4);
    irTxDueMs = beatMs + IR_DELAY_MS[irTxSlot];
  }
  if (irTxSlot >= 0 && (int32_t)(now - irTxDueMs) >= 0) {
    uint16_t w = IR_BURST_US[irTxSlot];
    irBlankUntilUs = micros() + w + 15000;     // ignore our own burst, its echo and the receiver's recovery
    irCarrier(true);
    delayMicroseconds(w);
    irCarrier(false);
    irTxCount++;
    irTxSlot = -1;
  }
}
static const uint32_t SYNC_TX_MS = 60;      // re-stamp and re-advertise this often
static const uint32_t PEER_TIMEOUT_MS = 1500;
static const int8_t RSSI_FAR = -105;        // weight 0 at or below this (no antennas yet)
static const int8_t RSSI_NEAR = -65;        // weight 1 at or above this
static const float PHASE_COUPLING = 2.0f;   // 1/s per unit weight
static const uint8_t MAX_PEERS = 8;

static Peer peers[MAX_PEERS];
static uint16_t myId = 0;
static float ownBpm = REST_BPM;   // this badge's distance-driven rate
static float coupling = 0.0f;     // sum of peer weights (0 = alone)
static float phaseErr = 0.0f;     // smoothed |phase difference| to peers, 0 .. 0.5 beat
static int peersNear = 0;
static bool bleRunning = false;
static bool advOk = false;
static volatile uint32_t rxAny = 0;    // every advertising report the scanner delivers
static volatile uint32_t rxAnyMs = 0;  // when the last one arrived
static volatile uint32_t resumeFails = 0;
static uint32_t scanRestarts = 0;
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
      int mm = data.RangeData[j].RangeMilliMeter;  // presence (SYNC gate): any status
      if (mm > 20 && mm < 2000) {
        tofAnyM = mm / 1000.0f;
        tofAnyMs = millis();
      }
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
  if (sync && !SYNC_BLE) {
    // IR: each received burst is a peer's beat (its delay slot subtracted). Correct the
    // phase toward it once per burst; the colour uses the smoothed size of the error.
    float period0 = 60.0f / SYNC_BPM;
    while (irTail != irHead) {
      uint32_t ms = irEvents[irTail].ms;
      uint8_t slot = irEvents[irTail].slot;
      irTail = (irTail + 1) % 4;
      uint32_t peerBeat = ms - IR_DELAY_MS[slot];
      // Rhythm check: a real partner's beats come a whole number of periods apart
      // (+-80 ms); stray pulses (e.g. our own ToF laser's reflections) don't.
      uint32_t prev = irPrevPeerBeat;
      irPrevPeerBeat = peerBeat;
      uint32_t periodMs = (uint32_t)(period0 * 1000.0f);
      int32_t gap = (int32_t)(peerBeat - prev);
      int32_t nearestMul = (gap + (int32_t)periodMs / 2) / (int32_t)periodMs;
      if (prev == 0 || gap <= 0 || nearestMul < 1 || nearestMul > 8 ||
          labs(gap - nearestMul * (int32_t)periodMs) > 80) {
        irImplausible++;
        continue;
      }
      float myPhaseAtPeerBeat = phase - (now - peerBeat) / 1000.0f / period0;
      float d = wrapHalf(0.0f - myPhaseAtPeerBeat - irPendingCorr);  // + : the peer is ahead
      irPendingCorr += IR_COUPLING * d;            // applied gradually below: no skipped beats
      phaseErr += 0.5f * (fabsf(d) - phaseErr);
      irRxCount++;
      irLastHeardMs = now;
    }
    if (irLastHeardMs) {
      uint32_t since = now - irLastHeardMs;
      coupling = 1.0f;          // once linked, stay in the synced state (and colour) even
      if (since < IR_HEARD_MS)  // out of sight; seeing each other again just re-syncs
        peersNear = 1;
    }
  } else if (sync) {
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
  if (sync && !SYNC_BLE && irPendingCorr != 0.0f) {
    // Spread IR corrections over ~0.25 s: the heart briefly speeds up or slows down
    // instead of jumping, so a forward correction can't skip a beat.
    float step = irPendingCorr * (1.0f - expf(-dt / 0.25f));
    if (phase + step < 0.0f) step = -phase;        // never back up past the last beat
    phase += step;
    irPendingCorr -= step;
    if (fabsf(irPendingCorr) < 0.0005f) irPendingCorr = 0.0f;
  }
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

  // Sparkle (FEAR): on top of the racing heart, random LEDs twinkle once someone is
  // closer than SPARK_START_M, more and more of them the closer they come. Each spark
  // flashes up and fades over ~0.15 s.
  static float sparkle[LED_RING_COUNT];
  static uint32_t lastRenderMs = 0;
  float dtR = lastRenderMs ? (now - lastRenderMs) / 1000.0f : 0.01f;
  if (dtR > 0.1f) dtR = 0.1f;
  lastRenderMs = now;
  float spark = (mode == MODE_FEAR) ? (SPARK_START_M - distM) / (SPARK_START_M - SPARK_FULL_M) : 0.0f;
  spark = spark < 0 ? 0 : (spark > 1 ? 1 : spark);
  float sparkDecay = expf(-dtR / 0.15f);
  // Across all 50 LEDs: a light scatter (~12/s) just inside 60 cm, rising steeply to
  // ~400/s (8 per LED per second) at 10 cm and closer.
  bool inRange = (mode == MODE_FEAR) && distM < SPARK_START_M;
  float sparksPerSecond = inRange ? 400.0f * (0.03f + 0.97f * spark * spark) : 0.0f;
  for (int i = 0; i < LED_RING_COUNT; i++) {
    sparkle[i] *= sparkDecay;
    if (random(100000) < (long)(sparksPerSecond * dtR / LED_RING_COUNT * 100000.0f))
      sparkle[i] = 0.6f + random(400) / 1000.0f;
  }

  float peak = FEAR_PEAK * (0.45f + 0.55f * fear);
  for (int r = 0; r < 3; r++) {
    float v = level[r] > 1.0f ? 1.0f : level[r];
    float rgb[3];
    if (mode == MODE_SYNC) {
      // Alone: blue. Hearing another badge, the colour shows how far apart the beats
      // are: yellow when a quarter beat or more apart, orange closing in, red in step.
      static const float ALONE[3] = {0.0f, 0.15f, 1.0f};
      static const float APART[3] = {1.0f, 0.75f, 0.0f};   // yellow
      static const float NEAR[3] = {1.0f, 0.30f, 0.0f};    // orange
      static const float LOCKED[3] = {1.0f, 0.0f, 0.0f};   // red
      float m = phaseErr / 0.25f;                     // 0 in step .. 1 a quarter beat or more
      m = m < 0 ? 0 : (m > 1 ? 1 : m);
      float heard = coupling * 2.0f;                  // fade in as the peer's signal firms up
      heard = heard > 1 ? 1 : heard;
      for (int k = 0; k < 3; k++) {
        float phaseCol = (m < 0.5f) ? LOCKED[k] + (NEAR[k] - LOCKED[k]) * (m / 0.5f)
                                    : NEAR[k] + (APART[k] - NEAR[k]) * ((m - 0.5f) / 0.5f);
        rgb[k] = ALONE[k] + (phaseCol - ALONE[k]) * heard;
      }
    } else {
      // FEAR: purple, a little hotter (pinker) when afraid.
      rgb[0] = 0.55f + 0.25f * fear;
      rgb[1] = 0.0f;
      rgb[2] = 1.0f - 0.2f * fear;
    }
    uint8_t base[3];
    for (int k = 0; k < 3; k++) {
      float x = v * peak * rgb[k];
      if (rgb[k] > 0.2f && x < 1.0f) x = 1.0f;        // faint ember between beats
      base[k] = (uint8_t)x;
    }
    for (int i = 0; i < RING_COUNTS[r]; i++) {
      int idx = RING_START[r] + i;
      float sp = sparkle[idx] * SPARK_PEAK;           // lavender-white sparks on top
      int c0 = base[0] + (int)(sp * 1.0f), c1 = base[1] + (int)(sp * 0.75f), c2 = base[2] + (int)(sp * 1.0f);
      ring.setPixelColor(idx, c0 > 255 ? 255 : c0, c1 > 255 ? 255 : c1, c2 > 255 ? 255 : c2);
    }
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
  rxAnyMs = millis();
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
  if (!Bluefruit.Scanner.resume()) resumeFails++;  // the library pauses scanning after each report
}

static void bleSetup() {
  Bluefruit.autoConnLed(false);
  Bluefruit.begin(1, 1);
  Bluefruit.setTxPower(0);  // raised to +8 dBm only while SYNC runs (bleStart)
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
  Bluefruit.setTxPower(8);  // nRF52840 maximum, +8 dBm: badges reach each other without antennas
  for (int i = 0; i < MAX_PEERS; i++) peers[i].id = 0;
  Bluefruit.Scanner.stop();  // clear any scan left over from a previous SYNC session
  scanOk = Bluefruit.Scanner.start(0);
  rxAnyMs = millis();
  syncAdvertise();
  bleRunning = true;
}

static void bleStop() {
  if (!bleRunning) return;
  Bluefruit.Scanner.stop();
  Bluefruit.Advertising.stop();
  Bluefruit.setTxPower(0);
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
  if (m != MODE_SYNC) {
    bleStop();
    irSyncStop();
  }
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
    if (m == MODE_SYNC && SYNC_BLE) bleStart();
    if (m == MODE_SYNC) { irLastHeardMs = 0; phaseErr = 0; irPendingCorr = 0; irPrevPeerBeat = 0; }
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

static const uint32_t DOUBLE_GAP_MS = 350;

// Double press: start SYNC afresh - forget any lock, jump to a random point in the beat
// (so the re-sync is visible), back to magenta until a partner is heard again.
static void syncRestart() {
  if (mode != MODE_SYNC) enterMode(MODE_SYNC);
  irLastHeardMs = 0;
  phaseErr = 0;
  irPendingCorr = 0;
  irPrevPeerBeat = 0;
  phase = random(1000) / 1000.0f;
  for (int i = 0; i < LED_RING_COUNT; i++) ring.setPixelColor(i, 16, 0, 24);  // violet flash x2
  for (int k = 0; k < 2; k++) {
    for (int i = 0; i < LED_RING_COUNT; i++) ring.setPixelColor(i, 16, 0, 24);
    ring.show();
    delay(120);
    ring.clear();
    ring.show();
    delay(120);
  }
  Serial.println("sync: restarted");
}

// Debounced: a short press is reported as SHORT once DOUBLE_GAP_MS passes with no second
// press, or as DOUBLE if a second short press starts within that gap; LONG once, while
// still held, when a press reaches LONG_PRESS_MS (its release is then ignored).
static ButtonEvent buttonEvent(uint32_t now) {
  static int stable = HIGH, lastRaw = HIGH;
  static uint32_t changedMs = 0, pressedMs = 0, releasedMs = 0;
  static bool longSent = false, shortPending = false;
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
      if (shortPending && now - releasedMs < DOUBLE_GAP_MS + (now - pressedMs)) {
        shortPending = false;
        return BUTTON_DOUBLE;
      }
      shortPending = true;
      releasedMs = now;
    }
  }
  if (shortPending && stable == HIGH && now - releasedMs >= DOUBLE_GAP_MS) {
    shortPending = false;
    return BUTTON_SHORT;
  }
  if (stable == LOW && !longSent && now - pressedMs >= LONG_PRESS_MS) {
    longSent = true;
    shortPending = false;  // a long press cancels a pending single press
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
  enterMode(MODE_SYNC);
}

void loop() {
  static uint32_t lastFrame = millis(), lastCharge = 0, lastPrint = 0;
  uint32_t now = millis();

  ButtonEvent ev = buttonEvent(now);
  if (ev == BUTTON_SHORT) {
    enterMode(mode == MODE_SYNC ? MODE_FEAR : mode == MODE_FEAR ? MODE_SOUND
              : mode == MODE_SOUND ? MODE_BEAT : MODE_SYNC);
  } else if (ev == BUTTON_DOUBLE) {
    syncRestart();
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
  if (mode == MODE_SYNC && !SYNC_BLE) irSyncTick(now, beatStartMs);
  static uint32_t lastTx = 0;
  if (mode == MODE_SYNC && SYNC_BLE && now - lastTx >= SYNC_TX_MS) {
    lastTx = now;
    syncAdvertise();
  }
  // Scan watchdog: if nothing at all has been heard for 2 s, listening has stalled
  // (a missed resume leaves it paused for good) - restart it.
  if (mode == MODE_SYNC && SYNC_BLE && (int32_t)(millis() - rxAnyMs) > 2000) {  // signed: rxAnyMs is set from the BLE task
    Bluefruit.Scanner.stop();
    scanOk = Bluefruit.Scanner.start(0);
    rxAnyMs = millis();
    scanRestarts++;
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
      if (mode == MODE_SYNC && !SYNC_BLE) {
        Serial.print(irGateOn ? "  IR on" : "  IR off (nobody within 2 m)");
        Serial.print("  tx ");
        Serial.print(irTxCount);
        Serial.print("  rx ");
        Serial.print(irRxCount);
        Serial.print("  rejected ");
        Serial.print(irRejected);
        Serial.print("  off-rhythm ");
        Serial.print(irImplausible);
        Serial.print("  last width ");
        Serial.print(irLastWidth);
        Serial.print("  err ");
        Serial.print(phaseErr, 2);
        Serial.print(peersNear ? "  peer: yes" : "  peer: no");
      } else if (mode == MODE_SYNC) {
        Serial.print("  own ");
        Serial.print(ownBpm, 0);
        Serial.print(advOk ? "  adv ok" : "  adv FAIL");
        Serial.print(scanOk ? "  scan ok" : "  scan FAIL");
        Serial.print("  any ");
        Serial.print(rxAny);
        Serial.print("  resume-fail ");
        Serial.print(resumeFails);
        Serial.print("  restarts ");
        Serial.print(scanRestarts);
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
