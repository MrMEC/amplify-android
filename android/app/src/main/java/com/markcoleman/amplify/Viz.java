package com.markcoleman.amplify;

import android.os.SystemClock;

/**
 * Build 600 (Mark: "an actual working visualizer"): the levels of the music actually playing.
 *
 * VizProcessor sits last in the player's audio chain (after the equalizer and the leveler, so it
 * measures what is heard) and, while the visualizer is on screen, turns the sound into BANDS
 * frequency bands every ~12 ms. The audio is processed ahead of the speaker by however much the
 * output buffer holds, so each set of bands is kept with the position (in frames since the last
 * flush) it was measured at, and current() hands back the set for the position being heard now:
 * the time actually spent playing since that flush (paused and buffering time don't count).
 */
final class Viz {
  static final int BANDS = 32;
  static volatile boolean enabled;

  private static final Object lock = new Object();
  private static final int RING = 512;
  private static final float[][] ring = new float[RING][BANDS];
  private static final long[] ringFrame = new long[RING];
  private static int head, count;
  private static int sampleRate = 44100;
  private static double playedBase;
  private static long playingSince = -1;

  private Viz() {}

  private static long now() { return SystemClock.elapsedRealtime(); }

  /** The player seeked, or a new stream started: positions start again from zero. */
  static void onFlush() {
    synchronized (lock) {
      head = 0; count = 0; playedBase = 0;
      if (playingSince >= 0) playingSince = now();
    }
  }

  static void setPlaying(boolean playing) {
    synchronized (lock) {
      long n = now();
      if (playing) {
        if (playingSince < 0) playingSince = n;
      } else if (playingSince >= 0) {
        playedBase += (n - playingSince) / 1000.0;
        playingSince = -1;
      }
    }
  }

  static void push(long atFrame, int rate, float[] bands) {
    synchronized (lock) {
      sampleRate = rate > 0 ? rate : sampleRate;
      System.arraycopy(bands, 0, ring[head], 0, BANDS);
      ringFrame[head] = atFrame;
      head = (head + 1) % RING;
      if (count < RING) count++;
    }
  }

  /** The bands for what is being heard now (0..1 each), or null if there are none. */
  static float[] current() {
    synchronized (lock) {
      if (count == 0) return null;
      double played = playedBase + (playingSince >= 0 ? (now() - playingSince) / 1000.0 : 0);
      long target = (long) (played * sampleRate);
      int best = -1;
      long bestFrame = Long.MIN_VALUE;
      for (int k = 0; k < count; k++) {
        int i = (head - 1 - k + RING) % RING;
        long f = ringFrame[i];
        if (f <= target && f > bestFrame) { bestFrame = f; best = i; }
        if (f < target) break; // older entries only get earlier
      }
      if (best < 0 || target - bestFrame > sampleRate / 5) return null;
      float[] out = new float[BANDS];
      System.arraycopy(ring[best], 0, out, 0, BANDS);
      return out;
    }
  }
}
