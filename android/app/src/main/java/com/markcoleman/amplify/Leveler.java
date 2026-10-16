package com.markcoleman.amplify;

/**
 * Volume leveling (build 231): evens out loudness between songs, stations and podcasts as they
 * play. It follows how loud the audio has been over the last few seconds and moves a gain towards
 * TARGET_RMS: quiet audio up (at most MAX_GAIN), loud audio down (at most MIN_GAIN), slowly, so
 * the music's own quiet and loud parts stay. Silence never raises it. A soft limiter keeps a
 * raised peak from clipping. After a new song or a seek (reset), it settles faster for a moment.
 *
 * Works on float samples in -1..1, interleaved. Plain Java (no Android classes), so it can be
 * tested with javac (tests/java/run_leveler.sh). LevelingProcessor feeds it the player's audio.
 */
final class Leveler {
  static final double TARGET_RMS = 0.2; // about -14 dBFS
  static final double MAX_GAIN = 2.8; // +9 dB
  static final double MIN_GAIN = 0.5; // -6 dB
  static final double GATE_MS = 3.2e-6; // below about -55 dBFS counts as silence
  static final double CHUNK_S = 0.01;
  static final double LOUD_TAU_S = 3.0, LOUD_TAU_FAST_S = 0.4;
  static final double DOWN_TAU_S = 0.3, UP_TAU_S = 2.5, UP_TAU_FAST_S = 0.5;
  static final double FAST_S = 1.5; // settle faster this long after a reset
  static final float KNEE = 0.8f;

  /** Leveling on or off (Settings). Off eases the gain back to 1, then passes audio through. */
  static volatile boolean enabled = true;

  private double env = -1; // mean square over the last few seconds; -1 = nothing heard yet
  private double gain = 1;
  private double sinceReset = FAST_S; // seconds of sound since the last reset

  double gain() {
    return gain;
  }

  /** A new song or a seek: keep the level, but settle faster for a moment. */
  void reset() {
    sinceReset = 0;
  }

  /** Processes frames in place: buf holds frames * channels samples from offset 0. */
  void process(float[] buf, int frames, int channels, int sampleRate) {
    if (frames <= 0 || channels <= 0 || sampleRate <= 0) return;
    if (!enabled && Math.abs(gain - 1) < 1e-4) {
      gain = 1;
      return; // untouched
    }
    int chunk = Math.max(1, (int) Math.round(sampleRate * CHUNK_S));
    for (int f0 = 0; f0 < frames; f0 += chunk) {
      int n = Math.min(chunk, frames - f0);
      double dt = n / (double) sampleRate;
      int a = f0 * channels, b = (f0 + n) * channels;
      double sum = 0;
      for (int i = a; i < b; i++) sum += buf[i] * (double) buf[i];
      double ms = sum / (b - a);
      double want;
      if (!enabled) {
        want = 1;
      } else {
        boolean fast = sinceReset < FAST_S;
        if (ms > GATE_MS) {
          if (env < 0) env = ms;
          else env += (ms - env) * (1 - Math.exp(-dt / (fast ? LOUD_TAU_FAST_S : LOUD_TAU_S)));
          sinceReset += dt;
        }
        want = env > 0 ? clamp(TARGET_RMS / Math.sqrt(env), MIN_GAIN, MAX_GAIN) : gain;
        // Silence: hold where it is rather than drifting.
        if (ms <= GATE_MS) want = gain;
      }
      double tau = want < gain ? DOWN_TAU_S : (sinceReset < FAST_S ? UP_TAU_FAST_S : UP_TAU_S);
      double g1 = gain + (want - gain) * (1 - Math.exp(-dt / tau));
      // Ramp the gain across the chunk, so it never steps.
      for (int fr = 0; fr < n; fr++) {
        float g = (float) (gain + (g1 - gain) * (fr + 1) / n);
        int base = (f0 + fr) * channels;
        for (int c = 0; c < channels; c++) buf[base + c] = soft(buf[base + c] * g);
      }
      gain = g1;
    }
  }

  /** Straight up to KNEE, then a smooth curve that never passes 1. */
  static float soft(float x) {
    float ax = Math.abs(x);
    if (ax <= KNEE) return x;
    float r = 1 - KNEE;
    float y = KNEE + r * (float) Math.tanh((ax - KNEE) / r);
    return x < 0 ? -y : y;
  }

  private static double clamp(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
  }
}
