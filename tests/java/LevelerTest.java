package com.markcoleman.amplify;

/** Tests Leveler with generated tones (build 231). Run with tests/java/run_leveler.sh. */
public class LevelerTest {
  static int failures;

  static void check(boolean ok, String what) {
    System.out.println((ok ? "ok   " : "FAIL ") + what);
    if (!ok) failures++;
  }

  static final int SR = 44100, CH = 2;

  /** Plays seconds of a sine at amplitude amp through lv in 20ms buffers; returns the output RMS of the last second. */
  static double play(Leveler lv, double amp, double seconds, double[] peak) {
    int frames = SR / 50;
    float[] buf = new float[frames * CH];
    long total = (long) (seconds * SR), done = 0;
    double sum = 0; long n = 0;
    double phase = 0;
    while (done < total) {
      for (int f = 0; f < frames; f++) {
        float v = (float) (amp * Math.sin(phase));
        phase += 2 * Math.PI * 440 / SR;
        for (int c = 0; c < CH; c++) buf[f * CH + c] = v;
      }
      lv.process(buf, frames, CH, SR);
      for (int i = 0; i < buf.length; i++) {
        if (peak != null) peak[0] = Math.max(peak[0], Math.abs(buf[i]));
        if (done >= total - SR) { sum += buf[i] * (double) buf[i]; n++; }
      }
      done += frames;
    }
    return Math.sqrt(sum / Math.max(1, n));
  }

  static double db(double r) { return 20 * Math.log10(r); }

  public static void main(String[] a) {
    Leveler.enabled = true;
    // A quiet source comes up, a loud one goes down, so they end up much closer.
    Leveler lv = new Leveler();
    double quiet = play(lv, 0.05, 12, null); // -29 dBFS RMS in
    lv.reset();
    double[] pk = {0};
    double loud = play(lv, 0.9, 12, pk); // -4 dBFS RMS in
    double inGap = db(0.9) - db(0.05), outGap = db(loud) - db(quiet);
    check(quiet > 0.05 / Math.sqrt(2) * 2.5, "quiet audio raised (" + String.format("%.1f", db(quiet) - db(0.05 / Math.sqrt(2))) + " dB)");
    check(loud < 0.9 / Math.sqrt(2) * 0.6, "loud audio lowered (" + String.format("%.1f", db(loud) - db(0.9 / Math.sqrt(2))) + " dB)");
    check(outGap < inGap - 12, "difference cut from " + String.format("%.1f", inGap) + " dB to " + String.format("%.1f", outGap) + " dB");
    check(pk[0] <= 1.0, "never past full scale (peak " + pk[0] + ")");

    // Silence doesn't pump the gain up.
    lv = new Leveler();
    play(lv, 0.3, 6, null);
    double g = lv.gain();
    play(lv, 0.0, 10, null);
    check(Math.abs(lv.gain() - g) < 1e-9, "silence holds the gain (" + g + " -> " + lv.gain() + ")");

    // A sudden loud part comes down quickly; the gain moves smoothly.
    lv = new Leveler();
    play(lv, 0.05, 10, null);
    double gHigh = lv.gain();
    play(lv, 0.9, 1.0, null);
    check(lv.gain() < gHigh * 0.45, "a sudden loud part is turned down within a second (" + gHigh + " -> " + lv.gain() + ")");

    // Within the limits.
    lv = new Leveler();
    play(lv, 0.002, 20, null);
    check(lv.gain() <= Leveler.MAX_GAIN + 1e-9, "never more than +9 dB (" + lv.gain() + ")");
    lv = new Leveler();
    play(lv, 1.0, 20, null);
    check(lv.gain() >= Leveler.MIN_GAIN - 1e-9, "never less than -6 dB (" + lv.gain() + ")");

    // Off: eases back to 1, then leaves the audio exactly as it was.
    lv = new Leveler();
    play(lv, 0.05, 10, null);
    Leveler.enabled = false;
    play(lv, 0.05, 10, null);
    check(Math.abs(lv.gain() - 1) < 1e-3, "off: back to 1 (" + lv.gain() + ")");
    float[] b = {0.95f, -0.95f, 0.5f, -0.5f};
    float[] c = b.clone();
    lv.process(c, 2, 2, SR);
    check(java.util.Arrays.equals(b, c), "off: audio untouched");
    Leveler.enabled = true;

    // The soft limiter.
    check(Leveler.soft(0.5f) == 0.5f && Leveler.soft(-0.7f) == -0.7f, "limiter leaves normal levels alone");
    check(Leveler.soft(3f) <= 1f && Leveler.soft(3f) > 0.95f && Leveler.soft(-3f) >= -1f && Leveler.soft(1.2f) < 1f, "limiter keeps peaks within full scale");
    check(Leveler.soft(0.81f) > Leveler.soft(0.8f) && Leveler.soft(0.9f) > Leveler.soft(0.85f), "limiter is smooth and rising");

    System.out.println(failures == 0 ? "ALL PASSED" : failures + " FAILED");
    System.exit(failures == 0 ? 0 : 1);
  }
}
