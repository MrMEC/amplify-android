package com.markcoleman.amplify;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Build 240: a five-band equalizer with a few presets (Settings > Equalizer). Bands: a low shelf
 * at 100 Hz, peaks at 400 Hz, 1.2 kHz and 3.5 kHz, a high shelf at 9 kHz (RBJ biquads). A boost
 * comes with an equal cut in level before the filters (headroom), so it can't clip; the volume
 * leveler after it brings the loudness back up.
 *
 * <p>Works on float samples in -1..1, interleaved, in place. Plain Java (no Android classes), so it
 * is tested with javac (tests/java/run_equalizer.sh). EqProcessor feeds it the player's audio.
 */
final class Equalizer {
  static final double[] FREQ = {100, 400, 1200, 3500, 9000};
  static final int LOW_SHELF = 0, HIGH_SHELF = 4;
  static final double Q = 0.9;

  /** Preset names (as shown) and their gains in dB, one per band. "Off" passes audio through. */
  static final Map<String, double[]> PRESETS = new LinkedHashMap<>();

  static {
    PRESETS.put("Off", new double[] {0, 0, 0, 0, 0});
    PRESETS.put("Bass Boost", new double[] {6, 2.5, 0, 0, 0});
    PRESETS.put("Treble Boost", new double[] {0, 0, 0, 2.5, 6});
    PRESETS.put("Vocal", new double[] {-2, -0.5, 3, 3.5, 1});
    PRESETS.put("Rock", new double[] {4, 1, -2, 2, 4});
    PRESETS.put("Pop", new double[] {-1, 2, 3.5, 1.5, -1});
    PRESETS.put("Jazz", new double[] {3, 1, -1, 1.5, 3});
    PRESETS.put("Classical", new double[] {3, 0, -1, 1, 3.5});
    PRESETS.put("Dance", new double[] {5.5, 1.5, -1, 1, 3});
    PRESETS.put("Late Night", new double[] {-4, -1, 1.5, 1, -3});
  }

  private static volatile String preset = "Off";
  private static volatile int version = 0;

  static String preset() {
    return preset;
  }

  /** Chooses a preset (an unknown name means Off). */
  static void setPreset(String name) {
    String p = name != null && PRESETS.containsKey(name) ? name : "Off";
    if (!p.equals(preset)) {
      preset = p;
      version++;
    }
  }

  static boolean active() {
    return !"Off".equals(preset);
  }

  // ---- per stream state ----
  private int builtFor = -1, builtRate = -1, builtChannels = -1;
  private double pre = 1;
  private final double[][] coef = new double[5][5]; // b0 b1 b2 a1 a2 (a0 = 1)
  private double[][] z = new double[0][]; // per channel, per band: x1 x2 y1 y2
  private boolean flat = true;

  /** A new song or a seek: the filters start from silence. */
  void reset() {
    for (double[] s : z) java.util.Arrays.fill(s, 0);
  }

  /** Processes frames in place: buf holds frames * channels samples from offset 0. */
  void process(float[] buf, int frames, int channels, int sampleRate) {
    if (frames <= 0 || channels <= 0 || sampleRate <= 0) return;
    if (builtFor != version || builtRate != sampleRate || builtChannels != channels) build(sampleRate, channels);
    if (flat) return;
    int bands = coef.length;
    for (int f = 0; f < frames; f++) {
      for (int c = 0; c < channels; c++) {
        int i = f * channels + c;
        double x = buf[i] * pre;
        double[] s = z[c];
        for (int b = 0; b < bands; b++) {
          double[] k = coef[b];
          int o = b * 4;
          double y = k[0] * x + k[1] * s[o] + k[2] * s[o + 1] - k[3] * s[o + 2] - k[4] * s[o + 3];
          s[o + 1] = s[o];
          s[o] = x;
          s[o + 3] = s[o + 2];
          s[o + 2] = y;
          x = y;
        }
        // Denormals and a stray overshoot: kept in range.
        if (x > 1) x = 1;
        else if (x < -1) x = -1;
        else if (Math.abs(x) < 1e-20) x = 0;
        buf[i] = (float) x;
      }
    }
  }

  private void build(int rate, int channels) {
    double[] g = PRESETS.get(preset);
    if (g == null) g = PRESETS.get("Off");
    flat = true;
    double maxBoost = 0;
    for (double v : g) {
      if (v != 0) flat = false;
      maxBoost = Math.max(maxBoost, v);
    }
    pre = Math.pow(10, -maxBoost / 20);
    for (int b = 0; b < FREQ.length; b++) {
      double f = Math.min(FREQ[b], rate * 0.45);
      coef[b] = biquad(b == LOW_SHELF ? 1 : b == HIGH_SHELF ? 2 : 0, f, g[b], rate);
    }
    if (z.length != channels) {
      z = new double[channels][FREQ.length * 4];
    } else {
      reset();
    }
    builtFor = version;
    builtRate = rate;
    builtChannels = channels;
  }

  /** kind 0 = peaking, 1 = low shelf, 2 = high shelf (Robert Bristow-Johnson's cookbook). */
  static double[] biquad(int kind, double f0, double dbGain, double fs) {
    double A = Math.pow(10, dbGain / 40);
    double w0 = 2 * Math.PI * f0 / fs;
    double cos = Math.cos(w0), sin = Math.sin(w0);
    double b0, b1, b2, a0, a1, a2;
    if (kind == 0) {
      double alpha = sin / (2 * Q);
      b0 = 1 + alpha * A;
      b1 = -2 * cos;
      b2 = 1 - alpha * A;
      a0 = 1 + alpha / A;
      a1 = -2 * cos;
      a2 = 1 - alpha / A;
    } else {
      double alpha = sin / 2 * Math.sqrt(2); // shelf slope 1
      double sq = 2 * Math.sqrt(A) * alpha;
      if (kind == 1) {
        b0 = A * ((A + 1) - (A - 1) * cos + sq);
        b1 = 2 * A * ((A - 1) - (A + 1) * cos);
        b2 = A * ((A + 1) - (A - 1) * cos - sq);
        a0 = (A + 1) + (A - 1) * cos + sq;
        a1 = -2 * ((A - 1) + (A + 1) * cos);
        a2 = (A + 1) + (A - 1) * cos - sq;
      } else {
        b0 = A * ((A + 1) + (A - 1) * cos + sq);
        b1 = -2 * A * ((A - 1) + (A + 1) * cos);
        b2 = A * ((A + 1) + (A - 1) * cos - sq);
        a0 = (A + 1) - (A - 1) * cos + sq;
        a1 = 2 * ((A - 1) - (A + 1) * cos);
        a2 = (A + 1) - (A - 1) * cos - sq;
      }
    }
    return new double[] {b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0};
  }
}
