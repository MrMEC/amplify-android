package com.markcoleman.amplify;

import android.app.PendingIntent;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.session.LibraryResult;
import androidx.media3.session.MediaLibraryService;
import androidx.media3.session.MediaSession;
import com.google.common.collect.ImmutableList;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.ListeningExecutorService;
import com.google.common.util.concurrent.MoreExecutors;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import org.json.JSONObject;

/**
 * Hosts the ExoPlayer and the media session. Being a foreground media service is what keeps
 * audio going with the screen off or the app in the background, and gives the notification,
 * lock-screen and Bluetooth controls. It is also the media library Android Auto browses (see
 * CarLibrary for the menu itself).
 */
@OptIn(markerClass = UnstableApi.class)
public class PlaybackService extends MediaLibraryService {

  @Nullable static PlaybackService instance;

  ExoPlayer exo;
  SkipAwarePlayer player;
  CarLibrary car;
  private MediaLibrarySession session;
  private final ListeningExecutorService io =
      MoreExecutors.listeningDecorator(Executors.newFixedThreadPool(3));
  private final Handler main = new Handler(Looper.getMainLooper());
  private final Runnable progressTick = this::saveCarProgress;

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
    car = new CarLibrary(this);
    exo.addListener(new CarListener());

    Intent open =
        new Intent(this, MainActivity.class)
            .setAction(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
    PendingIntent pi =
        PendingIntent.getActivity(
            this, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    session =
        new MediaLibrarySession.Builder(this, player, new LibraryCallback())
            .setSessionActivity(pi)
            .build();
    instance = this;
  }

  @Nullable
  @Override
  public MediaLibrarySession onGetSession(MediaSession.ControllerInfo controllerInfo) {
    return session;
  }

  /** The page saved a new car menu: reload it and tell the car its lists changed. */
  void onCatalogChanged() {
    car.reload();
    if (session == null) return;
    for (String id :
        new String[] {
          "tab:home", "tab:stations", "tab:podcasts", "home:favorites", "home:continue",
          "home:latest", "home:topstations", "st:foryou", "st:recent", "st:top", "pod:latest",
          "pod:az", "pod:popular"
        }) {
      session.notifyChildrenChanged(id, Integer.MAX_VALUE, null);
    }
  }

  @Override
  public void onTaskRemoved(@Nullable Intent rootIntent) {
    // Something the car started keeps going without the page. Otherwise the queue lives in
    // the page, which is gone once the app is swiped away, so stop rather than leave a player
    // that can't move on to the next track.
    if (player != null && player.isNativeMode() && exo != null && exo.getPlayWhenReady()) return;
    if (player != null) player.setRemote(null);
    pauseAllPlayersAndStopSelf();
  }

  @Override
  public void onDestroy() {
    instance = null;
    main.removeCallbacks(progressTick);
    saveCarProgress();
    if (session != null) {
      session.release();
      session = null;
    }
    if (exo != null) {
      exo.release();
    }
    io.shutdown();
    super.onDestroy();
  }

  // ---------------- car playback bookkeeping ----------------

  private void saveCarProgress() {
    main.removeCallbacks(progressTick);
    if (exo == null || player == null || !player.isNativeMode()) return;
    MediaItem item = exo.getCurrentMediaItem();
    if (item != null && item.mediaMetadata.extras != null) {
      Bundle ex = item.mediaMetadata.extras;
      String guid = ex.getString(CarLibrary.EXTRA_GUID);
      if (guid != null && !guid.isEmpty()) {
        long pos = exo.getCurrentPosition();
        long dur = exo.getDuration();
        JSONObject rec;
        try {
          rec = new JSONObject(ex.getString(CarLibrary.EXTRA_RECORD, "{}"));
        } catch (Exception e) {
          rec = new JSONObject();
        }
        double durSec = dur == C.TIME_UNSET ? rec.optDouble("durationSec", 0) : dur / 1000.0;
        if (pos > 0) CarProgress.put(this, guid, pos / 1000.0, durSec, rec);
      }
    }
    if (exo.isPlaying()) main.postDelayed(progressTick, 10_000);
  }

  private final class CarListener implements Player.Listener {
    @Override
    public void onIsPlayingChanged(boolean isPlaying) {
      saveCarProgress();
    }

    @Override
    public void onMediaItemTransition(@Nullable MediaItem mediaItem, int reason) {
      if (player == null || !player.isNativeMode() || mediaItem == null) return;
      Bundle ex = mediaItem.mediaMetadata.extras;
      boolean episode = ex != null && ex.getString(CarLibrary.EXTRA_GUID) != null;
      exo.setPlaybackSpeed(episode ? (float) car.podcastSpeed() : 1f);
    }
  }

  // ---------------- the library Android Auto browses ----------------

  private final class LibraryCallback implements MediaLibrarySession.Callback {

    @Override
    public ListenableFuture<LibraryResult<MediaItem>> onGetLibraryRoot(
        MediaLibrarySession session,
        MediaSession.ControllerInfo browser,
        @Nullable LibraryParams params) {
      LibraryParams out = new LibraryParams.Builder().setExtras(CarLibrary.rootExtras()).build();
      return Futures.immediateFuture(LibraryResult.ofItem(car.rootItem(), out));
    }

    @Override
    public ListenableFuture<LibraryResult<MediaItem>> onGetItem(
        MediaLibrarySession session, MediaSession.ControllerInfo browser, String mediaId) {
      MediaItem n = car.node(mediaId);
      if (n != null) return Futures.immediateFuture(LibraryResult.ofItem(n, null));
      return io.submit(
          () -> {
            CarLibrary.Queue q = car.queueFor(mediaId);
            if (q == null) return LibraryResult.ofError(LibraryResult.RESULT_ERROR_BAD_VALUE);
            return LibraryResult.ofItem(q.items.get(q.startIndex), null);
          });
    }

    @Override
    public ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> onGetChildren(
        MediaLibrarySession session,
        MediaSession.ControllerInfo browser,
        String parentId,
        int page,
        int pageSize,
        @Nullable LibraryParams params) {
      return io.submit(
          () -> {
            List<MediaItem> all = car.children(parentId);
            int from = Math.max(0, page) * Math.max(1, pageSize);
            if (pageSize <= 0 || pageSize == Integer.MAX_VALUE) from = 0;
            if (from >= all.size()) return LibraryResult.ofItemList(ImmutableList.of(), params);
            int to = pageSize <= 0 ? all.size() : (int) Math.min(all.size(), (long) from + pageSize);
            return LibraryResult.ofItemList(ImmutableList.copyOf(all.subList(from, to)), params);
          });
    }

    @Override
    public ListenableFuture<MediaSession.MediaItemsWithStartPosition> onSetMediaItems(
        MediaSession mediaSession,
        MediaSession.ControllerInfo controller,
        List<MediaItem> mediaItems,
        int startIndex,
        long startPositionMs) {
      return io.submit(
          () -> {
            // A tap in the car arrives as one bare id: play the list it came from, from there.
            if (mediaItems.size() == 1) {
              CarLibrary.Queue q = car.queueFor(mediaItems.get(0).mediaId);
              if (q != null) {
                return new MediaSession.MediaItemsWithStartPosition(
                    q.items, q.startIndex, q.startPositionMs);
              }
            }
            List<MediaItem> resolved = resolveEach(mediaItems);
            return new MediaSession.MediaItemsWithStartPosition(
                resolved,
                Math.max(0, Math.min(startIndex, resolved.size() - 1)),
                startPositionMs);
          });
    }

    @Override
    public ListenableFuture<List<MediaItem>> onAddMediaItems(
        MediaSession mediaSession, MediaSession.ControllerInfo controller, List<MediaItem> mediaItems) {
      return io.submit(() -> resolveEach(mediaItems));
    }

    private List<MediaItem> resolveEach(List<MediaItem> mediaItems) {
      List<MediaItem> out = new ArrayList<>();
      for (MediaItem m : mediaItems) {
        if (m.localConfiguration != null) {
          out.add(m);
          continue;
        }
        CarLibrary.Queue q = car.queueFor(m.mediaId);
        if (q != null) out.add(q.items.get(q.startIndex));
      }
      return out;
    }
  }
}
