package com.markcoleman.amplify;

/** Build 240: the equalizer's presets. Run: tests/java/run_equalizer.sh */
public class EqualizerTest {
  static int fails = 0;
  static void ok(boolean c, String name) { System.out.println((c ? "PASS " : "FAIL ") + name); if (!c) fails++; }

  /** Level (dB) of a sine at `hz` after the preset, relative to the input, measured after it settles. */
  static double response(String preset, double hz, int rate, int channels) {
    Equalizer.setPreset(preset);
    Equalizer eq = new Equalizer();
    int frames = rate; // one second
    float[] buf = new float[frames * channels];
    for (int f = 0; f < frames; f++) for (int c = 0; c < channels; c++) buf[f * channels + c] = (float) (0.25 * Math.sin(2 * Math.PI * hz * f / rate));
    // in pieces, like the player hands it over
    for (int off = 0; off < frames; off += 4096) {
      int n = Math.min(4096, frames - off);
      float[] part = new float[n * channels];
      System.arraycopy(buf, off * channels, part, 0, n * channels);
      eq.process(part, n, channels, rate);
      System.arraycopy(part, 0, buf, off * channels, n * channels);
    }
    double sum = 0; int cnt = 0;
    for (int f = frames / 2; f < frames; f++) { double v = buf[f * channels]; sum += v * v; cnt++; }
    double rms = Math.sqrt(sum / cnt), inRms = 0.25 / Math.sqrt(2);
    return 20 * Math.log10(rms / inRms);
  }

  public static void main(String[] a) {
    int R = 48000;
    ok(Equalizer.PRESETS.size() >= 8 && Equalizer.PRESETS.containsKey("Off"), "presets " + Equalizer.PRESETS.keySet());
    // Off: untouched, bit for bit
    Equalizer.setPreset("Off");
    Equalizer e0 = new Equalizer();
    float[] x = new float[2000]; for (int i = 0; i < x.length; i++) x[i] = (float) Math.sin(i * 0.37) * 0.5f;
    float[] y = x.clone(); e0.process(y, 1000, 2, R);
    ok(java.util.Arrays.equals(x, y), "Off leaves the audio exactly as it was");
    // Bass Boost: lows up relative to highs; nothing over the input (headroom)
    double bLow = response("Bass Boost", 60, R, 2), bMid = response("Bass Boost", 1500, R, 2), bHigh = response("Bass Boost", 10000, R, 2);
    System.out.printf("  Bass Boost: 60 Hz %.1f dB, 1.5 kHz %.1f dB, 10 kHz %.1f dB%n", bLow, bMid, bHigh);
    ok(bLow - bHigh > 5 && bLow <= 0.5, "Bass Boost lifts the bass about 6 dB over the treble, no louder than before");
    double tLow = response("Treble Boost", 60, R, 2), tHigh = response("Treble Boost", 12000, R, 2);
    System.out.printf("  Treble Boost: 60 Hz %.1f dB, 12 kHz %.1f dB%n", tLow, tHigh);
    ok(tHigh - tLow > 5 && tHigh <= 0.5, "Treble Boost lifts the treble");
    double vLow = response("Vocal", 80, R, 1), vMid = response("Vocal", 2500, R, 1);
    System.out.printf("  Vocal: 80 Hz %.1f dB, 2.5 kHz %.1f dB%n", vLow, vMid);
    ok(vMid - vLow > 4, "Vocal brings the voice range forward (mono too)");
    double nLow = response("Late Night", 60, R, 2), nMid = response("Late Night", 1500, R, 2);
    ok(nMid - nLow > 3, "Late Night takes the boom out");
    // every preset: stable, no NaN, no clipping on a full-scale sweep, at 44.1 and 48 kHz
    boolean stable = true;
    for (String p : Equalizer.PRESETS.keySet()) for (int rate : new int[] {44100, 48000, 22050}) {
      Equalizer.setPreset(p); Equalizer e = new Equalizer();
      float[] s = new float[rate * 2];
      for (int i = 0; i < rate; i++) { double hz = 20 + 18000.0 * i / rate; s[2 * i] = s[2 * i + 1] = (float) (0.99 * Math.sin(2 * Math.PI * hz * i / rate)); }
      e.process(s, rate, 2, rate);
      for (float v : s) if (Float.isNaN(v) || Math.abs(v) > 1.0001f) { stable = false; System.out.println("  unstable " + p + " @" + rate + ": " + v); break; }
    }
    ok(stable, "every preset is stable and stays in range (sweeps at 22.05, 44.1, 48 kHz)");
    // switching presets while playing takes effect
    Equalizer.setPreset("Bass Boost"); Equalizer e1 = new Equalizer();
    float[] q = new float[4800]; e1.process(q, 2400, 2, R);
    Equalizer.setPreset("Off");
    float[] z2 = x.clone(); e1.process(z2, 1000, 2, R);
    ok(java.util.Arrays.equals(x, z2), "switching to Off takes effect at once");
    Equalizer.setPreset("Nonsense");
    ok(Equalizer.preset().equals("Off"), "an unknown preset name means Off");
    System.out.println(fails == 0 ? "ALL PASSED" : "FAILED " + fails);
    System.exit(fails == 0 ? 0 : 1);
  }
}
