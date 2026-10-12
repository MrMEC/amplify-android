package com.markcoleman.amplify;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

/**
 * Build 211: keeps Amplify running while a Top 100 song plays through Spotify.
 *
 * <p>With Spotify doing the playing, Amplify's own player is idle, and Android soon stops or
 * freezes an app in the background that isn't playing anything itself. Then nothing would put the
 * next chart song in Spotify's queue (SpotifyBridge), and the chart would stop after one song on a
 * locked phone. This service holds Amplify in the foreground with a quiet, minimised
 * notification for as long as the chart plays.
 */
public class SpotifyKeepAlive extends Service {
  private static final String CHANNEL = "spotify_keepalive";
  private static final int NOTE_ID = 4711;
  private static boolean running;

  static void start(Context c, String title) {
    Intent i = new Intent(c, SpotifyKeepAlive.class).putExtra("title", title == null ? "" : title);
    try {
      ContextCompat.startForegroundService(c, i);
      running = true;
    } catch (Throwable t) {
      // Not allowed from the background on newer Androids; it's started on the next tap.
      CrashLog.note(c, "spotify keepalive start", t);
    }
  }

  /** The song shown in the notification, changed in place (no new start from the background). */
  static void update(Context c, String title) {
    if (!running) {
      start(c, title);
      return;
    }
    try {
      NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
      if (nm != null) nm.notify(NOTE_ID, build(c, title));
    } catch (Throwable ignored) {
    }
  }

  static boolean isRunning() {
    return running;
  }

  static void stop(Context c) {
    if (!running) return;
    running = false;
    try {
      c.stopService(new Intent(c, SpotifyKeepAlive.class));
    } catch (Throwable ignored) {
    }
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int startId) {
    String title = intent == null ? "" : intent.getStringExtra("title");
    Notification n = build(this, title);
    try {
      if (Build.VERSION.SDK_INT >= 29) {
        startForeground(NOTE_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
      } else {
        startForeground(NOTE_ID, n);
      }
    } catch (Throwable t) {
      CrashLog.note(this, "spotify keepalive foreground", t);
      running = false;
      stopSelf();
    }
    return START_NOT_STICKY;
  }

  private static Notification build(Context c, String title) {
    NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
    if (Build.VERSION.SDK_INT >= 26 && nm != null && nm.getNotificationChannel(CHANNEL) == null) {
      NotificationChannel ch =
          new NotificationChannel(CHANNEL, "Top 100 on Spotify", NotificationManager.IMPORTANCE_MIN);
      ch.setDescription("Keeps Amplify playing the Top 100 through Spotify while the phone is locked");
      ch.setShowBadge(false);
      nm.createNotificationChannel(ch);
    }
    Intent open =
        new Intent(c, MainActivity.class)
            .setAction(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
    PendingIntent pi =
        PendingIntent.getActivity(
            c, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    return new NotificationCompat.Builder(c, CHANNEL)
        .setSmallIcon(R.drawable.ic_amplify_play)
        .setContentTitle("Top 100 \u00B7 Playing through Spotify")
        .setContentText(title == null || title.isEmpty() ? "Amplify" : title)
        .setContentIntent(pi)
        .setOngoing(true)
        .setSilent(true)
        .setPriority(NotificationCompat.PRIORITY_MIN)
        .setCategory(NotificationCompat.CATEGORY_SERVICE)
        .build();
  }

  @Override
  public void onDestroy() {
    running = false;
    super.onDestroy();
  }

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }
}
