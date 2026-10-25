package com.markcoleman.amplify;

/** Build 320: Immersive View's audio meter. Run: tests/java/run_audio_meter.sh */
public class AudioMeterTest {
  static int fails = 0;
  static void ok(boolean c, String name) { System.out.println((c ? "PASS " : "FAIL ") + name); if (!c) fails++; }
  static float[] sine(double hz, double amp, int frames, int ch, int sr) {
    float[] s = new float[frames * ch];
    for (int f = 0; f < frames; f++) for (int c = 0; c < ch; c++) s[f * ch + c] = (float) (amp * Math.sin(2 * Math.PI * hz * f / sr));
    return s;
  }
  static int maxBand(int[] r) { int b = 0; for (int i = 1; i < AudioMeter.BANDS; i++) if (r[2 + i] > r[2 + b]) b = i; return b; }
  public static void main(String[] a) {
    int sr = 44100;
    // nothing while off
    AudioMeter.setEnabled(false);
    AudioMeter.feed(sine(80, .8, 4096, 2, sr), 4096, 2, sr);
    ok(AudioMeter.drain(System.nanoTime()).length == 0, "off: nothing measured");
    AudioMeter.setEnabled(true);
    AudioMeter.setBuffer(sr / 2, sr); // half a second of buffer
    // 4096 stereo frames = 4 blocks
    AudioMeter.feed(sine(50, .9, 4096, 2, sr), 4096, 2, sr);
    int[][] d = AudioMeter.drain(System.nanoTime());
    ok(d.length == 4, "4 blocks from 4096 frames (" + d.length + ")");
    ok(d[0].length == 2 + AudioMeter.BANDS, "row is ms, level, 9 bands");
    ok(d[0][0] > 480 && d[0][0] <= 531, "heard after the buffer + output delay (" + d[0][0] + " ms)");
    ok(maxBand(d[1]) == 0, "50 Hz lands in the sub-bass band");
    ok(d[1][1] > 90, "a loud sine reads loud (" + d[1][1] + ")");
    ok(AudioMeter.drain(System.nanoTime()).length == 0, "drain empties the queue");
    double[] hz = {90, 180, 380, 700, 1500, 3000, 6000, 12000};
    for (int i = 0; i < hz.length; i++) {
      AudioMeter.feed(sine(hz[i], .5, 2048, 1, sr), 2048, 1, sr);
      int[][] r = AudioMeter.drain(System.nanoTime());
      ok(r.length == 2 && maxBand(r[1]) == i + 1, hz[i] + " Hz -> band " + (i + 1) + " (got " + maxBand(r[1]) + ")");
    }
    // 48 kHz too
    AudioMeter.feed(sine(3000, .5, 2048, 2, 48000), 2048, 2, 48000);
    int[][] r48 = AudioMeter.drain(System.nanoTime());
    ok(maxBand(r48[1]) == 6, "48 kHz: 3 kHz -> band 6");
    // quiet vs loud, silence
    AudioMeter.feed(sine(200, .05, 1024, 1, sr), 1024, 1, sr);
    AudioMeter.feed(sine(200, .9, 1024, 1, sr), 1024, 1, sr);
    AudioMeter.feed(new float[1024], 1024, 1, sr);
    int[][] q = AudioMeter.drain(System.nanoTime());
    ok(q[0][1] < q[1][1] - 25, "quiet < loud (" + q[0][1] + " vs " + q[1][1] + ")");
    ok(q[2][1] == 0 && q[2][3] == 0, "silence is 0");
    // a partial block waits; reset drops it
    AudioMeter.feed(sine(200, .5, 1000, 1, sr), 1000, 1, sr);
    ok(AudioMeter.drain(System.nanoTime()).length == 0, "a partial block waits for the rest");
    AudioMeter.reset();
    AudioMeter.feed(sine(200, .5, 100, 1, sr), 100, 1, sr);
    ok(AudioMeter.drain(System.nanoTime()).length == 0, "reset drops the partial block");
    // the queue stays bounded
    AudioMeter.feed(sine(200, .5, 1024 * 200, 1, sr), 1024 * 200, 1, sr);
    ok(AudioMeter.drain(System.nanoTime()).length == AudioMeter.MAX_QUEUED, "queue capped at " + AudioMeter.MAX_QUEUED);
    // speed: 10 s of stereo audio
    long t0 = System.nanoTime();
    float[] big = sine(440, .5, sr * 10, 2, sr);
    AudioMeter.feed(big, sr * 10, 2, sr);
    double ms = (System.nanoTime() - t0) / 1e6;
    ok(ms < 400, "10 s of audio measured in " + Math.round(ms) + " ms");
    System.out.println(fails == 0 ? "ALL PASSED" : "FAILED " + fails);
    System.exit(fails == 0 ? 0 : 1);
  }
}
