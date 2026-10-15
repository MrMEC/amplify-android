package com.markcoleman.amplify;

import java.util.ArrayList;
import java.util.List;

/** Tests SleepTimer with a fake clock and player (build 230). Run with tests/java/run_sleep_timer.sh. */
public class SleepTimerTest {
  static final class Fake implements SleepTimer.Host {
    long t = 1_000_000L;
    final List<Object[]> jobs = new ArrayList<>(); // {Runnable, dueAt}
    float vol = 0.8f;
    int pauses;
    boolean pauseAtEnd;
    int changes, fires;
    final List<Float> vols = new ArrayList<>();

    public long now() { return t; }
    public void post(Runnable r, long d) { cancel(r); jobs.add(new Object[] {r, t + d}); }
    public void cancel(Runnable r) { jobs.removeIf(j -> j[0] == r); }
    public float volume() { return vol; }
    public void setVolume(float v) { vol = v; vols.add(v); }
    public void pause() { pauses++; }
    public void setPauseAtEnd(boolean on) { pauseAtEnd = on; }
    public void changed(boolean fired) { changes++; if (fired) fires++; }

    /** Moves the clock forward, running every job that comes due on the way. */
    void advance(long ms) {
      long end = t + ms;
      while (true) {
        Object[] next = null;
        for (Object[] j : jobs) if ((long) j[1] <= end && (next == null || (long) j[1] < (long) next[1])) next = j;
        if (next == null) break;
        jobs.remove(next);
        t = Math.max(t, (long) next[1]);
        ((Runnable) next[0]).run();
      }
      t = end;
    }
  }

  static int failures;

  static void check(boolean ok, String what) {
    System.out.println((ok ? "ok   " : "FAIL ") + what);
    if (!ok) failures++;
  }

  public static void main(String[] a) {
    // A timed sleep: nothing until the fade, a fade, then a pause and the volume put back.
    Fake f = new Fake();
    SleepTimer s = new SleepTimer(f);
    s.set(30 * 60_000L, false);
    check(s.active() && !s.isEndOfItem(), "30 minutes: active");
    check(s.remainingMs() == 30 * 60_000L, "30 minutes: remaining");
    f.advance(30 * 60_000L - SleepTimer.FADE_MS - 1);
    check(f.vols.isEmpty() && f.pauses == 0, "no change before the fade");
    f.advance(SleepTimer.FADE_MS / 2 + 1);
    check(f.vol < 0.8f * 0.3f && f.vol > 0.1f && f.pauses == 0, "half way through the fade: quieter, still playing (" + f.vol + ")");
    boolean falling = true;
    for (int i = 1; i < f.vols.size(); i++) if (f.vols.get(i) > f.vols.get(i - 1)) falling = false;
    check(falling, "the volume only goes down");
    f.advance(SleepTimer.FADE_MS / 2);
    check(f.pauses == 1 && f.fires == 1 && !s.active(), "at the time: paused, fired, off");
    check(f.vol < 0.01f, "silent at the pause");
    f.advance(SleepTimer.RESTORE_MS + 1);
    check(Math.abs(f.vol - 0.8f) < 1e-6, "volume put back after the pause");
    f.advance(60 * 60_000L);
    check(f.pauses == 1, "nothing more afterwards");

    // Cancelled during the fade: volume back at once, no pause.
    f = new Fake();
    s = new SleepTimer(f);
    s.set(20_000L, false);
    f.advance(15_000L);
    check(f.vol < 0.8f, "fading");
    s.cancel();
    check(Math.abs(f.vol - 0.8f) < 1e-6 && !s.active(), "cancel during the fade puts the volume back");
    f.advance(60_000L);
    check(f.pauses == 0, "cancelled: never pauses");

    // Changed to a longer time during the fade.
    f = new Fake();
    s = new SleepTimer(f);
    s.set(20_000L, false);
    f.advance(15_000L);
    s.set(15 * 60_000L, false);
    check(Math.abs(f.vol - 0.8f) < 1e-6, "a new time during the fade puts the volume back");
    f.advance(10 * 60_000L);
    check(f.pauses == 0, "new time not reached yet");
    f.advance(5 * 60_000L + 1);
    check(f.pauses == 1, "new time: paused");

    // End of the song.
    f = new Fake();
    s = new SleepTimer(f);
    s.set(0, true);
    check(s.active() && s.isEndOfItem() && f.pauseAtEnd, "end of song: active, pause at end on");
    f.advance(3 * 60 * 60_000L);
    check(f.pauses == 0, "end of song: no time limit");
    check(s.itemEnded() && f.pauses == 1 && f.fires == 1 && s.endHold, "item ended: paused, fired, held");
    check(!f.pauseAtEnd && !s.active(), "item ended: pause at end off, timer off");
    check(!s.itemEnded() && f.pauses == 1, "the next end is not the timer's");
    s.playStarted();
    check(!s.endHold, "playing again releases the hold");

    // Without a timer an end is ordinary; turning it off clears pause at end.
    f = new Fake();
    s = new SleepTimer(f);
    check(!s.itemEnded() && f.pauses == 0 && !s.endHold, "no timer: an end is ordinary");
    s.set(0, true);
    s.set(0, false);
    check(!s.active() && !f.pauseAtEnd, "turned off: pause at end off");
    s.set(0, true);
    s.set(45 * 60_000L, false);
    check(!f.pauseAtEnd && !s.isEndOfItem() && s.remainingMs() == 45 * 60_000L, "end of song switched to 45 minutes");

    System.out.println(failures == 0 ? "ALL PASSED" : failures + " FAILED");
    System.exit(failures == 0 ? 0 : 1);
  }
}
