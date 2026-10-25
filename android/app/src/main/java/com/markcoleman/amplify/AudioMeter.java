package com.markcoleman.amplify;

import java.util.ArrayDeque;

/**
 * Build 320: what the music sounds like right now, for Immersive View's glow and particles.
 *
 * <p>LevelingProcessor hands every block of the player's own audio (after leveling, on its way to
 * the speaker) to feed(). While the page has asked for it (enabled), the audio is mixed to mono,
 * cut into blocks of N samples and each block is measured: its loudness and the strength of nine
 * frequency bands (an FFT). No microphone and no permission: it is the decoded music itself.
 *
 * <p>The audio is measured before it is heard: it still has to pass through the sound buffer.
 * So each measurement carries the time it will actually be heard (now + the buffer's length +
 * the output's own small delay), and the page shows it at that moment.
 *
 * <p>Plain Java (no Android classes), so tests/java/AudioMeterTest.java runs it with javac.
 */
final class AudioMeter {
  static final int N = 1024;
  /** Band edges in Hz: sub-bass, bass, upper bass, low mids, mids, upper mids, presence, treble, air. */
  static final float[] EDGES = {20, 60, 120, 250, 500, 1000, 2000, 4000, 8000, 16000};
  static final int BANDS = EDGES.length - 1;
  static final int MAX_QUEUED = 96;
  /** The output's own delay after the buffer (speaker/DAC), roughly. */
  static final long OUTPUT_NS = 30_000_000L;

  static volatile boolean enabled;
  /** How long the sound buffer holds audio before it is heard; set from the buffer's size. */
  static volatile long latencyNs = 250_000_000L;

  private static final float[] block = new float[N];
  private static int fill;
  private static final float[] re = new float[N];
  private static final float[] im = new float[N];
  private static final float[] win = new float[N];
  private static final Object lock = new Object();
  private static final ArrayDeque<long[]> queue = new ArrayDeque<>();

  static {
    for (int i = 0; i < N; i++) win[i] = (float) (0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1)));
  }

  private AudioMeter() {}

  static void setEnabled(boolean on) {
    enabled = on;
    if (!on) reset();
  }

  /** From the sound buffer's size (frames) and the sample rate. */
  static void setBuffer(int bufferFrames, int sampleRate) {
    if (bufferFrames > 0 && sampleRate > 0) latencyNs = bufferFrames * 1_000_000_000L / sampleRate;
  }

  /** Interleaved samples (-1..1), frames x channels. Called on the player's audio thread. */
  static void feed(float[] samples, int frames, int channels, int sampleRate) {
    if (!enabled) {
      fill = 0;
      return;
    }
    if (channels < 1 || sampleRate <= 0) return;
    float inv = 1f / channels;
    for (int f = 0; f < frames; f++) {
      float m = 0;
      int base = f * channels;
      for (int c = 0; c < channels; c++) m += samples[base + c];
      block[fill++] = m * inv;
      if (fill == N) {
        fill = 0;
        int[] v = analyze(block, sampleRate);
        long[] e = new long[v.length + 1];
        e[0] = System.nanoTime() + latencyNs + OUTPUT_NS;
        for (int i = 0; i < v.length; i++) e[i + 1] = v[i];
        synchronized (lock) {
          queue.addLast(e);
          while (queue.size() > MAX_QUEUED) queue.removeFirst();
        }
      }
    }
  }

  /** A seek, a new stream: what was measured will never be heard. */
  static void reset() {
    fill = 0;
    synchronized (lock) {
      queue.clear();
    }
  }

  /**
   * Everything measured so far, oldest first, each as {ms until it is heard, level, band 0..8},
   * values 0..100. Removes them from the queue.
   */
  static int[][] drain(long nowNs) {
    synchronized (lock) {
      int[][] out = new int[queue.size()][];
      int i = 0;
      for (long[] e : queue) {
        int[] r = new int[e.length];
        r[0] = (int) ((e[0] - nowNs) / 1_000_000L);
        for (int k = 1; k < e.length; k++) r[k] = (int) e[k];
        out[i++] = r;
      }
      queue.clear();
      return out;
    }
  }

  /** {level, band 0..BANDS-1}, each 0..100 (a dB scale: 0 is silence, 100 full scale). */
  static int[] analyze(float[] x, int sampleRate) {
    double sq = 0;
    for (int i = 0; i < N; i++) {
      sq += x[i] * x[i];
      re[i] = x[i] * win[i];
      im[i] = 0;
    }
    fft(re, im);
    int[] out = new int[1 + BANDS];
    double rms = Math.sqrt(sq / N);
    out[0] = scale(20 * Math.log10(rms + 1e-9), 60);
    // A full-scale sine through the Hann window peaks at N/4.
    double ref = (N / 4.0) * (N / 4.0);
    double binHz = (double) sampleRate / N;
    for (int b = 0; b < BANDS; b++) {
      int lo = (int) Math.ceil(EDGES[b] / binHz);
      int hi = (int) Math.ceil(EDGES[b + 1] / binHz) - 1;
      lo = Math.max(1, lo);
      hi = Math.min(N / 2 - 1, Math.max(lo, hi));
      double p = 0;
      for (int k = lo; k <= hi; k++) p += re[k] * re[k] + im[k] * im[k];
      out[1 + b] = scale(10 * Math.log10(p / ref + 1e-12), 72);
    }
    return out;
  }

  private static int scale(double db, double range) {
    double v = (db + range) / range * 100;
    return (int) Math.round(Math.max(0, Math.min(100, v)));
  }

  /** In-place radix-2 FFT (N a power of two). */
  static void fft(float[] r, float[] m) {
    int n = r.length;
    for (int i = 1, j = 0; i < n; i++) {
      int bit = n >> 1;
      for (; (j & bit) != 0; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) {
        float t = r[i]; r[i] = r[j]; r[j] = t;
        t = m[i]; m[i] = m[j]; m[j] = t;
      }
    }
    for (int len = 2; len <= n; len <<= 1) {
      double ang = -2 * Math.PI / len;
      float wr = (float) Math.cos(ang), wi = (float) Math.sin(ang);
      for (int i = 0; i < n; i += len) {
        float cr = 1, ci = 0;
        for (int k = 0; k < len / 2; k++) {
          int a = i + k, b = a + len / 2;
          float xr = r[b] * cr - m[b] * ci, xi = r[b] * ci + m[b] * cr;
          r[b] = r[a] - xr; m[b] = m[a] - xi;
          r[a] += xr; m[a] += xi;
          float ncr = cr * wr - ci * wi;
          ci = cr * wi + ci * wr;
          cr = ncr;
        }
      }
    }
  }
}
