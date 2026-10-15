package com.markcoleman.amplify;

/**
 * The sleep timer (build 230). Lives in PlaybackService, so it keeps counting with the screen
 * locked, the page asleep or the phone in the car. Two kinds:
 *
 * <ul>
 *   <li>a time: the last FADE_MS fade the volume down, then playback pauses and the volume is put
 *       back for next time;
 *   <li>end of the current song or episode: the player pauses there instead of moving on.
 *       {@link #itemEnded()} is called when it gets there; {@link #endHold} then tells the page
 *       (and the page-queue takeover) not to start the next one.
 * </ul>
 *
 * Plain Java with no Android classes, so it can be tested with javac (tests/java).
 */
final class SleepTimer {
  interface Host {
    long now();

    void post(Runnable r, long delayMs);

    void cancel(Runnable r);

    float volume();

    void setVolume(float v);

    /** Stops whatever is playing (phone, VLC or Chromecast). */
    void pause();

    void setPauseAtEnd(boolean on);

    /** The timer changed: set, cancelled, or (fired) it has just stopped playback. */
    void changed(boolean fired);
  }

  static final long FADE_MS = 12000L;
  static final long STEP_MS = 250L;
  static final long RESTORE_MS = 400L;

  private final Host host;
  private long until; // when a timed sleep stops playback; 0 = none
  private boolean endOfItem;
  private boolean fading;
  private float fadeFrom = -1f;
  private float restoreTo = -1f;
  /** Playback was stopped at the end of an item; cleared when something plays again. */
  boolean endHold;

  private final Runnable tick = this::tick;
  private final Runnable restore = this::restoreVolume;

  SleepTimer(Host host) {
    this.host = host;
  }

  /** ms > 0: stop after that long. endOfItem: stop at the end of what is playing. Neither: off. */
  void set(long ms, boolean endOfItem) {
    clear();
    endHold = false;
    if (endOfItem) {
      this.endOfItem = true;
      host.setPauseAtEnd(true);
    } else if (ms > 0) {
      until = host.now() + ms;
      host.post(tick, Math.max(0L, ms - FADE_MS));
    }
    host.changed(false);
  }

  void cancel() {
    boolean was = active();
    clear();
    if (was) host.changed(false);
  }

  boolean active() {
    return until > 0 || endOfItem;
  }

  boolean isEndOfItem() {
    return endOfItem;
  }

  /** Epoch ms when a timed sleep stops playback, else 0. */
  long until() {
    return until;
  }

  long remainingMs() {
    return until > 0 ? Math.max(0L, until - host.now()) : 0L;
  }

  /** The player reached the end of an item. True when that was the sleep timer's stop. */
  boolean itemEnded() {
    if (!endOfItem) return false;
    endOfItem = false;
    host.setPauseAtEnd(false);
    endHold = true;
    host.pause();
    host.changed(true);
    return true;
  }

  /** Something is playing again: an earlier end-of-item stop no longer holds. */
  void playStarted() {
    endHold = false;
  }

  private void clear() {
    host.cancel(tick);
    if (fading && fadeFrom >= 0) host.setVolume(fadeFrom);
    fading = false;
    fadeFrom = -1f;
    until = 0;
    if (endOfItem) {
      endOfItem = false;
      host.setPauseAtEnd(false);
    }
  }

  private void tick() {
    if (until == 0) return;
    long left = until - host.now();
    if (left <= 0) {
      float v = fadeFrom;
      fading = false;
      fadeFrom = -1f;
      until = 0;
      host.pause();
      if (v >= 0) {
        // Put the volume back a moment after the pause has taken, so nothing is heard.
        restoreTo = v;
        host.post(restore, RESTORE_MS);
      }
      host.changed(true);
      return;
    }
    if (!fading) {
      fading = true;
      fadeFrom = host.volume();
    }
    float k = Math.min(1f, left / (float) FADE_MS);
    host.setVolume(fadeFrom * k * k); // squared, so it sounds like an even fade to the ear
    host.post(tick, Math.min(STEP_MS, left));
  }

  private void restoreVolume() {
    if (restoreTo >= 0) host.setVolume(restoreTo);
    restoreTo = -1f;
  }
}
