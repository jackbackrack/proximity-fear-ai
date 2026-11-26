#include "beat.h"

static float hzToMel(float hz) { return 2595.0f * log10f(1.0f + hz / 700.0f); }
static float melToHz(float mel) { return 700.0f * (powf(10.0f, mel / 2595.0f) - 1.0f); }

static const float MIN_HZ = 60.0f;
static const float MAX_HZ = 7000.0f;
static const float BASS_HZ = 250.0f;       // bands centred below this weigh 1.0 in the flux
static const float TREBLE_WEIGHT = 0.3f;   // ... the rest weigh this
static const float K_STD = 1.6f;           // threshold = mean + K * std
static const float FLUX_FLOOR = 0.6f;      // absolute minimum flux for an onset
static const uint32_t REFRACTORY_MS = 250;

void BeatDetector::begin(float sampleRate) {
  arm_rfft_fast_init_f32(&fft_, N);
  for (int i = 0; i < N; i++) {
    window_[i] = 0.54f - 0.46f * cosf(2.0f * PI * i / (N - 1));  // Hamming
    ring_[i] = 0;
  }
  // Triangular mel filters on BANDS + 2 equally spaced mel points.
  float melLo = hzToMel(MIN_HZ), melHi = hzToMel(MAX_HZ);
  float binHz = sampleRate / N;
  int used = 0;
  for (int b = 0; b < BANDS; b++) {
    float f0 = melToHz(melLo + (melHi - melLo) * b / (BANDS + 1));
    float f1 = melToHz(melLo + (melHi - melLo) * (b + 1) / (BANDS + 1));
    float f2 = melToHz(melLo + (melHi - melLo) * (b + 2) / (BANDS + 1));
    bandHz[b] = f1;
    int k0 = (int)floorf(f0 / binHz), k2 = (int)ceilf(f2 / binHz);
    if (k0 < 1) k0 = 1;
    if (k2 <= k0) k2 = k0 + 1;
    if (k2 > N / 2) k2 = N / 2;
    start_[b] = k0;
    len_[b] = k2 - k0;
    offset_[b] = used;
    float sum = 0;
    for (int k = k0; k < k2; k++) {
      float f = k * binHz, w;
      if (f <= f1) w = (f1 > f0) ? (f - f0) / (f1 - f0) : 1.0f;
      else w = (f2 > f1) ? (f2 - f) / (f2 - f1) : 1.0f;
      if (w < 0) w = 0;
      if (len_[b] == 1) w = 1.0f;  // a band narrower than one bin keeps that bin
      pool_[used + (k - k0)] = w;
      sum += w;
    }
    if (sum <= 0) pool_[used] = 1.0f;
    used += len_[b];
    weight_[b] = (f1 < BASS_HZ) ? 1.0f : TREBLE_WEIGHT;
    logMel[b] = 0;
  }
}

bool BeatDetector::push(const int16_t* samples, int n, bool gateOpen) {
  bool analysed = false;
  onset = false;
  for (int i = 0; i < n; i++) {
    ring_[N - HOP + fill_] = samples[i];  // newest hop fills the end of the window
    if (++fill_ == HOP) {
      analyse(gateOpen);
      memmove(ring_, ring_ + HOP, (N - HOP) * sizeof(float));  // slide by one hop
      fill_ = 0;
      analysed = true;
    }
  }
  return analysed;
}

void BeatDetector::analyse(bool gateOpen) {
  float mean = 0;
  for (int i = 0; i < N; i++) mean += ring_[i];
  mean /= N;
  for (int i = 0; i < N; i++) frame_[i] = (ring_[i] - mean) * window_[i];
  arm_rfft_fast_f32(&fft_, frame_, spectrum_, 0);
  // spectrum_: [0] DC, [1] Nyquist, then (re, im) pairs for bins 1..N/2-1.

  float newFlux = 0;
  for (int b = 0; b < BANDS; b++) {
    float e = 0;
    for (int j = 0; j < len_[b]; j++) {
      int k = start_[b] + j;
      float re = spectrum_[2 * k], im = spectrum_[2 * k + 1];
      e += pool_[offset_[b] + j] * (re * re + im * im);
    }
    float l = logf(1.0f + e);
    if (havePrev_) {
      float d = l - prevLog_[b];
      if (d > 0) newFlux += weight_[b] * d;
    }
    prevLog_[b] = l;
    logMel[b] = l;
  }
  havePrev_ = true;
  flux = newFlux;

  // Adaptive threshold from the flux history (before adding this frame).
  float m = 0, s = 0;
  if (histCount_ > 0) {
    for (int i = 0; i < histCount_; i++) m += hist_[i];
    m /= histCount_;
    for (int i = 0; i < histCount_; i++) s += (hist_[i] - m) * (hist_[i] - m);
    s = sqrtf(s / histCount_);
  }
  threshold = m + K_STD * s;
  if (threshold < FLUX_FLOOR) threshold = FLUX_FLOOR;

  uint32_t now = millis();
  if (gateOpen && histCount_ == HIST && flux > threshold && now - lastOnsetMs_ >= REFRACTORY_MS) {
    onset = true;
    onsetStrength = flux / threshold;
    lastOnsetMs_ = now;
  }

  hist_[histPos_] = flux;
  histPos_ = (histPos_ + 1) % HIST;
  if (histCount_ < HIST) histCount_++;
}

// ---- Tempo -------------------------------------------------------------------------

static const float MIN_PERIOD = 300.0f;   // 200 bpm
static const float MAX_PERIOD = 1000.0f;  // 60 bpm
static const float MATCH = 0.12f;         // an interval within 12 % agrees
static const int LOCK_AFTER = 3;          // agreeing intervals to lock
static const int MISSES_TO_UNLOCK = 4;    // predicted beats with no onset near them

float TempoTracker::fold(float ioi) const {  // bring an interval into the period range
  while (ioi > MAX_PERIOD) ioi *= 0.5f;
  while (ioi < MIN_PERIOD) ioi *= 2.0f;
  return ioi;
}

bool TempoTracker::onOnset(uint32_t ms) {
  bool fire = false;
  if (lastOnsetMs_ != 0) {
    float ioi = ms - lastOnsetMs_;
    if (ioi > 150.0f && ioi < 2500.0f) {
      // Compare against the current period, also allowing half / double intervals.
      float candidate = fold(ioi);
      if (period_ > 0 && fabsf(candidate - period_) < MATCH * period_) {
        period_ += 0.25f * (candidate - period_);
        agree_++;
        disagree_ = 0;
      } else if (++disagree_ >= 3 || period_ == 0) {
        period_ = candidate;  // the music changed: start over at the new interval
        agree_ = 0;
        disagree_ = 0;
        locked_ = false;
      }
      if (!locked_ && agree_ >= LOCK_AFTER) {
        locked_ = true;
        nextBeatMs_ = ms + (uint32_t)period_;
        lastHeardMs_ = ms;
        lastFiredMs_ = ms;
        fire = true;
      }
    }
  }
  lastOnsetMs_ = ms;

  if (locked_ && !fire) {
    // Phase: is this onset near the predicted beat (or the one just fired)?
    float sinceFired = (float)(ms - lastFiredMs_);
    float untilNext = (float)((int32_t)(nextBeatMs_ - ms));
    if (untilNext >= 0 && untilNext < 0.2f * period_) {
      // Slightly early: beat now and re-anchor the prediction here.
      nextBeatMs_ = ms + (uint32_t)period_;
      lastFiredMs_ = ms;
      lastHeardMs_ = ms;
      fire = true;
    } else if (sinceFired < 0.2f * period_) {
      // Slightly late after a predicted beat: nudge the next prediction later.
      nextBeatMs_ += (uint32_t)(0.5f * sinceFired);
      lastHeardMs_ = ms;
    }
  } else if (!locked_) {
    fire = true;  // unlocked: show every onset
  }
  return fire;
}

bool TempoTracker::tick(uint32_t ms) {
  if (!locked_) return false;
  if ((int32_t)(ms - nextBeatMs_) >= 0) {
    if (ms - lastHeardMs_ > (uint32_t)(MISSES_TO_UNLOCK * period_)) {
      locked_ = false;  // the music stopped or changed: stop the flywheel
      agree_ = 0;
      return false;
    }
    lastFiredMs_ = nextBeatMs_;
    nextBeatMs_ += (uint32_t)period_;
    return true;
  }
  return false;
}
