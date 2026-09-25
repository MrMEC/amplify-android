package com.markcoleman.amplify;

import android.app.PendingIntent;
import android.content.Intent;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;

/**
 * Hosts the ExoPlayer and the MediaSession. Being a foreground media service is what keeps
 * audio going with the screen off or the app in the background, and gives the notification,
 * lock-screen and Bluetooth controls.
 */
@OptIn(markerClass = UnstableApi.class)
public class PlaybackService extends MediaSessionService {

  @Nullable static PlaybackService instance;

  ExoPlayer exo;
  SkipAwarePlayer player;
  private MediaSession session;

  @Override
  public void onCreate() {
    super.onCreate();
    DefaultHttpDataSource.Factory http =
        new DefaultHttpDataSource.Factory()
            .setAllowCrossProtocolRedirects(true)
            .setUserAgent("Amplify/1.0 (Android) ExoPlayer")
            .setConnectTimeoutMs(15_000)
            .setReadTimeoutMs(20_000);
    DefaultDataSource.Factory data = new DefaultDataSource.Factory(this, http);
    exo =
        new ExoPlayer.Builder(this)
            .setMediaSourceFactory(new DefaultMediaSourceFactory(data))
            .setAudioAttributes(
                new AudioAttributes.Builder()
                    .setUsage(C.USAGE_MEDIA)
                    .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                    .build(),
                /* handleAudioFocus= */ true)
            .setHandleAudioBecomingNoisy(true)
            .setWakeMode(C.WAKE_MODE_NETWORK)
            .setSeekBackIncrementMs(15_000)
            .setSeekForwardIncrementMs(30_000)
            .build();
    player = new SkipAwarePlayer(exo);

    Intent open =
        new Intent(this, MainActivity.class)
            .setAction(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
    PendingIntent pi =
        PendingIntent.getActivity(
            this, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    session = new MediaSession.Builder(this, player).setSessionActivity(pi).build();
    instance = this;
  }

  @Nullable
  @Override
  public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
    return session;
  }

  @Override
  public void onTaskRemoved(@Nullable Intent rootIntent) {
    // The queue lives in the app's page, which is gone once the app is swiped away, so stop
    // rather than leave a player that can't move on to the next track.
    if (player != null) player.setRemote(null);
    pauseAllPlayersAndStopSelf();
  }

  @Override
  public void onDestroy() {
    instance = null;
    if (session != null) {
      session.release();
      session = null;
    }
    if (exo != null) {
      exo.release();
    }
    super.onDestroy();
  }
}
