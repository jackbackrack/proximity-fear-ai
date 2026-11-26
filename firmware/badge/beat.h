// Beat detection for the badge's PDM mic (16 kHz mono).
//
// Analysis (after scottlawsonbc/audio-reactive-led-strip): 512-point FFT every 256
// samples (32 ms Hamming window, 16 ms hop, ~62 frames/s), power spectrum grouped
// into BANDS mel bands from 60 Hz to 7 kHz.
//
// Onsets (the adaptive idea from that repo's PR #101, made steadier): spectral flux
// of the log mel bands - the sum of positive band-energy jumps, bass bands weighted
// most - against an adaptive threshold (mean + K * std over the last ~1 s), with a
// refractory period so one drum hit counts once.
//
// Tempo (new): a tracker estimates the beat period from inter-onset intervals and,
// once several agree, predicts each next beat (phase-corrected by the onsets that
// land near it) and keeps beating through short gaps.
#pragma once

#include <Arduino.h>
#include <arm_math.h>

class BeatDetector {
 public:
  static const int N = 512;
  static const int HOP = 256;
  static const int BANDS = 20;

  void begin(float sampleRate);
  // Feed samples; returns true when at least one new frame was analysed.
  bool push(const int16_t* samples, int n, bool gateOpen);

  // Latest frame.
  float logMel[BANDS];        // ln(power) per mel band
  float bandHz[BANDS];        // centre frequency of each band
  float flux = 0;             // onset strength this frame
  float threshold = 0;        // adaptive threshold this frame
  bool onset = false;         // an onset was detected in the latest push()
  float onsetStrength = 0;    // flux / threshold at that onset (>= 1)

 private:
  void analyse(bool gateOpen);

  arm_rfft_fast_instance_f32 fft_;
  float window_[N];
  float ring_[N];             // last N samples, oldest first
  int fill_ = 0;              // samples gathered towards the next hop
  float frame_[N];
  float spectrum_[N];
  float prevLog_[BANDS];
  bool havePrev_ = false;

  // Mel filterbank: band b covers bins [start_[b], start_[b] + len_[b]) with weights
  // pool_[offset_[b] ...].
  uint16_t start_[BANDS], len_[BANDS], offset_[BANDS];
  float pool_[N];
  float weight_[BANDS];       // flux weighting (bass heavier)

  static const int HIST = 64; // ~1 s of flux history
  float hist_[HIST];
  int histPos_ = 0, histCount_ = 0;
  uint32_t lastOnsetMs_ = 0;
};

class TempoTracker {
 public:
  // Report a detected onset. Returns true if the display should beat now (an onset
  // while unlocked, or an onset that lands on the predicted beat early).
  bool onOnset(uint32_t ms);
  // Call every frame. Returns true when a predicted beat falls due while locked.
  bool tick(uint32_t ms);

  bool locked() const { return locked_; }
  float bpm() const { return period_ > 0 ? 60000.0f / period_ : 0; }

 private:
  float fold(float ioi) const;

  float period_ = 0;          // ms
  int agree_ = 0;             // consecutive intervals that matched the period
  int disagree_ = 0;
  bool locked_ = false;
  uint32_t lastOnsetMs_ = 0;
  uint32_t nextBeatMs_ = 0;   // predicted
  uint32_t lastFiredMs_ = 0;
  uint32_t lastHeardMs_ = 0;  // last onset that matched the beat
};
