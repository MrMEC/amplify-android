package com.markcoleman.amplify;

import android.os.SystemClock;

/**
 * Listening time (build 369): how long the player has actually been playing, counted here
 * rather than in the page, because the page's timers stop while the screen is off and radio
 * mostly plays with the screen off. The page reads the total now and then and credits the
 * difference to whatever it has playing. Only goes up while playing; starts at 0 with the app.
 */
final class ListenClock {
  private ListenClock() {}

  private static long total;
  private static long since = -1;

  static synchronized void playing(boolean isPlaying) {
    long now = SystemClock.elapsedRealtime();
    if (isPlaying) {
      if (since < 0) since = now;
    } else if (since >= 0) {
      total += now - since;
      since = -1;
    }
  }

  static synchronized long ms() {
    return total + (since >= 0 ? SystemClock.elapsedRealtime() - since : 0);
  }

  static synchronized boolean isPlaying() {
    return since >= 0;
  }
}
