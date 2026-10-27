package com.markcoleman.amplify;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Build;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Build 337: the tour's welcome voice. A plain Android MediaPlayer, separate from the app's music
 * player and from the web view: no media session, no notification, no Now Playing. Other audio is
 * ducked while it speaks. The sound file is one of the app's own assets (public/tour-welcome.wav).
 */
final class WelcomeVoice {
  private static MediaPlayer player;
  private static AudioManager audioManager;
  private static AudioFocusRequest focus;

  private WelcomeVoice() {}

  /** Starts the voice (replacing any already playing); answers "playing" or "error: ...". */
  static synchronized String play(Context ctx, String asset) {
    stop();
    try {
      File f = new File(ctx.getCacheDir(), "welcome-voice.wav");
      try (InputStream in = ctx.getAssets().open(asset);
          OutputStream out = new FileOutputStream(f)) {
        byte[] buf = new byte[16 * 1024];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
      }
      AudioAttributes attrs =
          new AudioAttributes.Builder()
              .setUsage(AudioAttributes.USAGE_MEDIA)
              .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
              .build();
      audioManager = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
      if (audioManager != null && Build.VERSION.SDK_INT >= 26) {
        focus =
            new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(attrs)
                .build();
        audioManager.requestAudioFocus(focus);
      }
      MediaPlayer mp = new MediaPlayer();
      player = mp;
      mp.setAudioAttributes(attrs);
      mp.setDataSource(f.getAbsolutePath());
      mp.setOnCompletionListener(
          m -> {
            if (player == m) stop();
          });
      mp.setOnErrorListener(
          (m, what, extra) -> {
            if (player == m) stop();
            return true;
          });
      mp.prepare();
      mp.start();
      return "playing";
    } catch (Exception e) {
      stop();
      return "error: " + e;
    }
  }

  /** Stops the voice if it is playing and gives the audio focus back. */
  static synchronized void stop() {
    MediaPlayer mp = player;
    player = null;
    if (mp != null) {
      try {
        mp.stop();
      } catch (Exception ignored) {
        // Never started.
      }
      try {
        mp.release();
      } catch (Exception ignored) {
        // Already released.
      }
    }
    if (audioManager != null && focus != null && Build.VERSION.SDK_INT >= 26) {
      try {
        audioManager.abandonAudioFocusRequest(focus);
      } catch (Exception ignored) {
        // Nothing to give back.
      }
    }
    focus = null;
  }
}
