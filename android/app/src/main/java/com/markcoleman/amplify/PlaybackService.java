package com.markcoleman.amplify;

import android.app.PendingIntent;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.Player;
import androidx.media3.common.Timeline;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.session.CommandButton;
import androidx.media3.session.LibraryResult;
import androidx.media3.session.MediaLibraryService;
import androidx.media3.session.MediaSession;
import androidx.media3.session.SessionCommand;
import androidx.media3.session.SessionResult;
import com.google.common.collect.ImmutableList;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.ListeningExecutorService;
import com.google.common.util.concurrent.MoreExecutors;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Date;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Hosts the ExoPlayer and the media session. Being a foreground media service is what keeps audio
 * going with the screen off or the app in the background, and gives the notification, lock-screen
 * and Bluetooth controls. It is also the media library Android Auto browses (see CarLibrary for the
 * menu itself).
 */
@OptIn(markerClass = UnstableApi.class)
public class PlaybackService extends MediaLibraryService {
  private static final SessionCommand NEXT;
  private static final ImmutableList<CommandButton> PODCAST_BUTTONS;
  private static final SessionCommand PREV;
  private static final SessionCommand SKIP_BACK;
  private static final SessionCommand SKIP_FORWARD;
  static PlaybackService instance;
  CarLibrary car;
  ExoPlayer exo;
  private String historyPending;
  // Play counts for items played from the car: time actually playing is added up in
  // HISTORY_STEP_MS steps; an item is recorded once it has had HISTORY_FIRST_MS, and a station
  // again for every further HISTORY_STATION_MS (about one song), like the phone does.
  private static final long HISTORY_STEP_MS = 5000L;
  private static final long HISTORY_FIRST_MS = 20000L;
  private static final long HISTORY_STATION_MS = 210000L;
  private long historyHeardMs;
  private long historyNeedMs = HISTORY_FIRST_MS;
  SkipAwarePlayer player;
  private MediaLibraryService.MediaLibrarySession session;
  private String widgetArtKey;
  private int widgetSeq;
  private final ListeningExecutorService io =
      MoreExecutors.listeningDecorator(Executors.newFixedThreadPool(3));
  private final Handler main = new Handler(Looper.getMainLooper());
  private final Runnable progressTick =
      () -> {
        this.saveCarProgress();
      };
  private final Set<String> browsed = ConcurrentHashMap.newKeySet();
  private final Runnable historyTick =
      () -> {
        this.recordCarHistory();
      };
  private final Runnable positionTick =
      new Runnable() { // from class: com.markcoleman.amplify.PlaybackService.1
        @Override // java.lang.Runnable
        public void run() {
          PlaybackService.this.main.removeCallbacks(this);
          PlaybackService.this.rememberPosition();
          if (PlaybackService.this.exo == null || !PlaybackService.this.exo.isPlaying()) {
            return;
          }
          PlaybackService.this.main.postDelayed(this, 5000L);
        }
      };
  private final ArrayDeque<String> carLog = new ArrayDeque<>();

  static {
    SessionCommand sessionCommand = new SessionCommand("amplify.SKIP_BACK", Bundle.EMPTY);
    SKIP_BACK = sessionCommand;
    SessionCommand sessionCommand2 = new SessionCommand("amplify.SKIP_FORWARD", Bundle.EMPTY);
    SKIP_FORWARD = sessionCommand2;
    PODCAST_BUTTONS =
        ImmutableList.of(
            new CommandButton.Builder(57410)
                .setDisplayName("Back 15 seconds")
                .setSessionCommand(sessionCommand)
                .setSlots(2)
                .build(),
            new CommandButton.Builder(63220)
                .setDisplayName("Forward 30 seconds")
                .setSessionCommand(sessionCommand2)
                .setSlots(3)
                .build());
    PREV = new SessionCommand("amplify.PREV", Bundle.EMPTY);
    NEXT = new SessionCommand("amplify.NEXT", Bundle.EMPTY);
  }

  private static CommandButton trackButton(boolean z, boolean z2) {
    return new CommandButton.Builder(z ? 57375 : 57376)
        .setCustomIconResId(z ? R.drawable.ic_amplify_next : R.drawable.ic_amplify_prev)
        .setDisplayName(z ? "Next" : "Previous")
        .setSessionCommand(z ? NEXT : PREV)
        .setSlots(z ? 3 : 2)
        .setEnabled(z2)
        .build();
  }

  @Override // androidx.media3.session.MediaSessionService, android.app.Service
  public void onCreate() {
    super.onCreate();
    this.exo =
        new ExoPlayer.Builder(this)
            .setMediaSourceFactory(
                new DefaultMediaSourceFactory(
                    new DefaultDataSource.Factory(
                        this,
                        new DefaultHttpDataSource.Factory()
                            .setAllowCrossProtocolRedirects(true)
                            .setUserAgent("Amplify/1.0 (Android) ExoPlayer")
                            .setConnectTimeoutMs(15000)
                            .setReadTimeoutMs(20000))))
            .setAudioAttributes(
                new AudioAttributes.Builder().setUsage(1).setContentType(2).build(), true)
            .setHandleAudioBecomingNoisy(true)
            .setWakeMode(2)
            .setSeekBackIncrementMs(15000L)
            .setSeekForwardIncrementMs(30000L)
            .build();
    SkipAwarePlayer skipAwarePlayer = new SkipAwarePlayer(this.exo);
    this.player = skipAwarePlayer;
    skipAwarePlayer.setOnPodcastChanged(
        () -> {
          this.updateButtons();
        });
    this.car = new CarLibrary(this);
    this.io.execute(
        () -> {
          this.car.reload();
          restoreNow(false);
        });
    this.exo.addListener(new CarListener());
    this.session =
        new MediaLibraryService.MediaLibrarySession.Builder(
                (MediaLibraryService) this,
                (Player) this.player,
                (MediaLibraryService.MediaLibrarySession.Callback) new LibraryCallback())
            .setSessionActivity(
                PendingIntent.getActivity(
                    this,
                    0,
                    new Intent(this, (Class<?>) MainActivity.class)
                        .setAction("android.intent.action.MAIN")
                        .addCategory("android.intent.category.LAUNCHER")
                        .addFlags(536870912),
                    201326592))
            .build();
    updateButtons();
    this.player.addListener(new WidgetListener());
    instance = this;
  }

  @Nullable
  @Override
  public MediaLibrarySession onGetSession(MediaSession.ControllerInfo controllerInfo) {
    return session;
  }

  private File resumeFile() {
    return new File(getFilesDir(), "car_resume.json");
  }

  private void tagResume(String str) {
    try {
      JSONObject resume = readResume();
      if (resume == null) {
        return;
      }
      resume.put("exoId", str);
      writeResume(resume);
    } catch (Exception unused) {
    }
  }

  private JSONObject readResume() {
    try {
      return new JSONObject(CarLibrary.readFile(resumeFile()));
    } catch (Exception unused) {
      return null;
    }
  }

  void rememberLastPlayed(String str, String str2, long j) {
    try {
      JSONObject resume = readResume();
      JSONObject jSONObject = new JSONObject();
      if (str != null) {
        jSONObject.put("mediaId", str);
      }
      if (str2 != null) {
        jSONObject.put("item", new JSONObject(str2));
      }
      jSONObject.put("pos", Math.max(0L, j));
      if (str != null
          && str.startsWith("resume|")
          && resume != null
          && resume.optJSONArray("list") != null) {
        String[] strArrSplit = str.split("\\|", 3);
        try {
          jSONObject.put("list", resume.getJSONArray("list"));
          jSONObject.put("at", Integer.parseInt(strArrSplit[1]));
        } catch (Exception unused) {
        }
      }
      writeResume(jSONObject);
    } catch (Exception unused2) {
    }
  }

  void rememberPageItem(String str, JSONArray jSONArray, long j, String str2) {
    try {
      JSONObject jSONObject = new JSONObject(str);
      JSONObject resume = readResume();
      boolean z =
          resume != null
              && CarLibrary.sameEntry(
                  resume == null ? null : resume.optJSONObject("item"), jSONObject);
      JSONObject jSONObject2 = new JSONObject();
      jSONObject2.put("item", jSONObject);
      if (j < 0) {
        j = z ? resume.optLong("pos", 0L) : 0L;
      }
      jSONObject2.put("pos", j);
      if (str2 != null && !str2.isEmpty()) {
        jSONObject2.put("exoId", str2);
      } else if (z && resume.has("exoId")) {
        jSONObject2.put("exoId", resume.optString("exoId"));
      }
      if (jSONArray != null) {
        JSONArray jSONArray2 = new JSONArray();
        jSONArray2.put(jSONObject);
        for (int i = 0; i < jSONArray.length(); i++) {
          jSONArray2.put(jSONArray.opt(i));
        }
        jSONObject2.put("list", jSONArray2);
        jSONObject2.put("at", 0);
      } else if (z && resume.optJSONArray("list") != null) {
        jSONObject2.put("list", resume.getJSONArray("list"));
        jSONObject2.put("at", resume.optInt("at", 0));
      }
      writeResume(jSONObject2);
    } catch (Exception unused) {
    }
  }

  private synchronized void writeResume(JSONObject o) throws Exception {
    File f = resumeFile();
    File part = new File(f.getPath() + ".part");
    try (FileOutputStream out = new FileOutputStream(part)) {
      out.write(o.toString().getBytes(StandardCharsets.UTF_8));
    }
    if (!part.renameTo(f)) part.delete();
  }

  void rememberPosition() {
    MediaItem currentMediaItem;
    ExoPlayer exoPlayer = this.exo;
    if (exoPlayer == null
        || exoPlayer.getMediaItemCount() == 0
        || (currentMediaItem = this.exo.getCurrentMediaItem()) == null
        || this.exo.getPlaybackState() == 1) {
      return;
    }
    try {
      JSONObject jSONObject = new JSONObject(CarLibrary.readFile(resumeFile()));
      String str = currentMediaItem.mediaId;
      if (str.equals(jSONObject.optString("mediaId", null))
          || str.equals(jSONObject.optString("exoId", null))) {
        jSONObject.put("pos", Math.max(0L, this.exo.getCurrentPosition()));
        writeResume(jSONObject);
      }
    } catch (Exception unused) {
    }
  }

  public CarLibrary.Queue lastPlayedQueue() {
    try {
      JSONObject jSONObject = new JSONObject(CarLibrary.readFile(resumeFile()));
      JSONArray jSONArrayOptJSONArray = jSONObject.optJSONArray("list");
      CarLibrary.Queue queueResumeList =
          (jSONArrayOptJSONArray == null || jSONArrayOptJSONArray.length() <= 0)
              ? null
              : this.car.resumeList(jSONArrayOptJSONArray, jSONObject.optInt("at", 0));
      if (queueResumeList == null) {
        queueResumeList =
            this.car.resumeQueue(
                jSONObject.optString("mediaId", null), jSONObject.optJSONObject("item"));
      }
      if (queueResumeList == null) {
        return null;
      }
      MediaItem mediaItem = queueResumeList.items.get(queueResumeList.startIndex);
      return new CarLibrary.Queue(
          queueResumeList.items,
          queueResumeList.startIndex,
          (mediaItem.mediaMetadata.extras == null
                  || !mediaItem.mediaMetadata.extras.getBoolean("amplify.live", false))
              ? jSONObject.optLong("pos", queueResumeList.startPositionMs)
              : 0L);
    } catch (Exception unused) {
      return null;
    }
  }

  private void restoreLastPlayed() {
    restoreLastPlayed(false);
  }

  void restoreLastPlayed(final boolean z) {
    this.io.execute(
        () -> {
          this.restoreNow(z);
        });
  }

  public void restoreNow(final boolean z) {
    final CarLibrary.Queue queueLastPlayedQueue = lastPlayedQueue();
    if (queueLastPlayedQueue == null) {
      return;
    }
    this.main.post(
        () -> {
          SkipAwarePlayer skipAwarePlayer;
          if (this.exo == null || (skipAwarePlayer = this.player) == null) {
            return;
          }
          boolean z2 = z && skipAwarePlayer.isNativeMode() && this.player.isResumePending();
          if (this.exo.getMediaItemCount() <= 0 || z2) {
            MediaItem currentMediaItem = this.exo.getCurrentMediaItem();
            MediaItem mediaItem = queueLastPlayedQueue.items.get(queueLastPlayedQueue.startIndex);
            if (z2
                && currentMediaItem != null
                && currentMediaItem.mediaId.equals(mediaItem.mediaId)
                && this.exo.getMediaItemCount() == queueLastPlayedQueue.items.size()
                && Math.abs(this.exo.getCurrentPosition() - queueLastPlayedQueue.startPositionMs)
                    < 2000) {
              return;
            }
            this.player.setMediaItems(
                queueLastPlayedQueue.items,
                queueLastPlayedQueue.startIndex,
                queueLastPlayedQueue.startPositionMs);
            this.exo.setPlayWhenReady(false);
            tagResume(mediaItem.mediaId);
            this.player.setResumePending();
          }
        });
  }

  ImmutableList<CommandButton> buttons() {
    SkipAwarePlayer skipAwarePlayer = this.player;
    return skipAwarePlayer == null
        ? ImmutableList.of()
        : skipAwarePlayer.isPodcastNow()
            ? PODCAST_BUTTONS
            : (this.player.prevAvailable() || this.player.nextAvailable())
                ? ImmutableList.of(trackButton(false, true), trackButton(true, true))
                : ImmutableList.of();
  }

  void updateButtons() {
    MediaLibraryService.MediaLibrarySession mediaLibrarySession = this.session;
    if (mediaLibrarySession == null || this.player == null) {
      return;
    }
    mediaLibrarySession.setMediaButtonPreferences(buttons());
  }

  void skip(boolean z) {
    ExoPlayer exoPlayer = this.exo;
    if (exoPlayer == null || exoPlayer.getMediaItemCount() == 0) {
      return;
    }
    long jMax = Math.max(0L, this.exo.getCurrentPosition());
    long duration = this.exo.getDuration();
    ExoPlayer exoPlayer2 = this.exo;
    long jMax2 =
        z
            ? Math.max(0L, jMax - exoPlayer2.getSeekBackIncrement())
            : jMax + exoPlayer2.getSeekForwardIncrement();
    if (!z && duration != -9223372036854775807L && duration > 0) {
      jMax2 = Math.min(jMax2, Math.max(0L, duration - 1000));
    }
    this.exo.seekTo(jMax2);
  }

  void logCar(String str) {
    String str2 = new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date());
    synchronized (this.carLog) {
      this.carLog.addFirst(str2 + " " + str);
      while (this.carLog.size() > 8) {
        this.carLog.removeLast();
      }
    }
  }

  void onPageQueue(String str, String str2, String str3, boolean z) {
    PlaybackService playbackService;
    String str4;
    String str5;
    if (this.player == null || this.exo == null) {
      return;
    }
    try {
      if (str2 == null || str2.isEmpty()) {
        str2 = "[]";
      }
      JSONArray jSONArray = new JSONArray(str2);
      boolean z2 = this.player.isNativeMode() && this.player.isResumePending();
      MediaItem currentMediaItem = this.exo.getCurrentMediaItem();
      boolean z3 =
          (this.player.isNativeMode()
                  || currentMediaItem == null
                  || str == null
                  || str.isEmpty()
                  || !str.equals(currentMediaItem.mediaId))
              ? false
              : true;
      StringBuilder sb =
          new StringBuilder(
              "queue "
                  + jSONArray.length()
                  + (z ? " follow" : "")
                  + (this.player.isNativeMode()
                      ? z2 ? " (car: restored)" : " (car playing)"
                      : z3 ? " (phone loaded)" : " (phone, not loaded)"));
      boolean z4 = (str3 == null || str3.isEmpty()) ? false : true;
      List<MediaItem> listPageQueueItems = null;
      if (!z4 || (this.player.isNativeMode() && !z2)) {
        playbackService = this;
        str4 = str3;
      } else {
        long currentPosition = z3 ? this.exo.getCurrentPosition() : -1L;
        if (z3) {
          str5 = currentMediaItem.mediaId;
          str4 = str3;
          playbackService = this;
        } else {
          str5 = null;
          playbackService = this;
          str4 = str3;
        }
        playbackService.rememberPageItem(str4, jSONArray, currentPosition, str5);
        sb.append(" saved");
        if (z2) {
          restoreLastPlayed(true);
          sb.append(", car reloads it");
        }
      }
      try {
        if (jSONArray.length() > 0 && str != null && !str.isEmpty()) {
          listPageQueueItems = playbackService.car.pageQueueItems(jSONArray);
        }
        playbackService.player.setPageQueue(str, listPageQueueItems);
        if (playbackService.player.pageActive()) {
          sb.append(", shown as car queue");
        }
      } catch (Exception e) {
        sb.append(", queue view failed: ").append(e.getClass().getSimpleName());
      }
      if (z && z4 && playbackService.player.isNativeMode() && !z2) {
        sb.append(extendCarQueue(str4, jSONArray));
      }
      logCar(sb.toString());
    } catch (Exception unused) {
      logCar("queue: bad list");
    }
  }

  private String extendCarQueue(String str, JSONArray jSONArray) {
    MediaItem currentMediaItem = this.exo.getCurrentMediaItem();
    if (currentMediaItem == null || currentMediaItem.mediaMetadata.extras == null) {
      return ", car item unknown";
    }
    if (this.exo.hasNextMediaItem()) {
      return ", car has its own queue";
    }
    try {
      JSONObject jSONObject = new JSONObject(str);
      String string = currentMediaItem.mediaMetadata.extras.getString("amplify.item");
      if (string != null && CarLibrary.sameEntry(new JSONObject(string), jSONObject)) {
        JSONArray jSONArray2 = new JSONArray();
        jSONArray2.put(jSONObject);
        for (int i = 0; i < jSONArray.length(); i++) {
          jSONArray2.put(jSONArray.opt(i));
        }
        CarLibrary.Queue queueResumeList = this.car.resumeList(jSONArray2, 0);
        if (queueResumeList == null) {
          return ", car can't play it";
        }
        ArrayList arrayList =
            new ArrayList(
                queueResumeList.items.subList(
                    queueResumeList.startIndex + 1, queueResumeList.items.size()));
        if (arrayList.isEmpty()) {
          return ", nothing playable to add";
        }
        this.exo.addMediaItems(arrayList);
        JSONObject resume = readResume();
        if (resume == null) {
          resume = new JSONObject();
        }
        resume.put("list", jSONArray2);
        resume.put("at", 0);
        writeResume(resume);
        return ", added " + arrayList.size() + " to the car's queue";
      }
      return ", car is on another item";
    } catch (Exception e) {
      return ", add failed: " + e.getClass().getSimpleName();
    }
  }

  String debugText() {
    ExoPlayer exoPlayer;
    StringBuilder sb = new StringBuilder();
    if (this.player == null || (exoPlayer = this.exo) == null) {
      return "no player";
    }
    MediaItem currentMediaItem = exoPlayer.getCurrentMediaItem();
    sb.append("Notifications: ")
        .append(
            NotificationManagerCompat.from(this).areNotificationsEnabled()
                ? "allowed"
                : "blocked (Settings > Apps > Amplify > Notifications)")
        .append("\nMode: ");
    sb.append(
            this.player.isNativeMode()
                ? this.player.isResumePending() ? "car, restored (not played yet)" : "car"
                : "phone")
        .append("\nLoaded: ")
        .append(this.exo.getMediaItemCount())
        .append(" item(s), at ")
        .append(this.exo.getCurrentMediaItemIndex())
        .append(
            currentMediaItem == null
                ? ""
                : " (" + ((Object) currentMediaItem.mediaMetadata.title) + ")")
        .append(", ")
        .append(this.exo.getCurrentPosition() / 1000)
        .append(" s\nCar queue shown: ")
        .append(this.player.getCurrentTimeline().getWindowCount())
        .append(" item(s)\nButtons: ")
        .append(buttons().size());
    StreamTitle onAir = this.player.getOnAir();
    sb.append("\nOn air: ")
        .append(
            onAir == null ? "no song named" : onAir.display() + " (sent as \"" + onAir.raw + "\")");
    sb.append("\n").append(this.player.onAirDebug());
    sb.append("\n").append(this.player.streamDebug());
    JSONObject resume = readResume();
    if (resume == null) {
      sb.append("\nSaved: nothing");
    } else {
      JSONObject jSONObjectOptJSONObject = resume.optJSONObject("item");
      JSONArray jSONArrayOptJSONArray = resume.optJSONArray("list");
      sb.append("\nSaved: ")
          .append(
              jSONObjectOptJSONObject == null
                  ? "?"
                  : jSONObjectOptJSONObject.optString(
                      "title",
                      jSONObjectOptJSONObject.optString(
                          "id", jSONObjectOptJSONObject.optString("k"))))
          .append(" at ")
          .append(resume.optLong("pos", 0L) / 1000)
          .append(" s")
          .append(
              jSONArrayOptJSONArray == null
                  ? ", no queue"
                  : ", queue of "
                      + jSONArrayOptJSONArray.length()
                      + " (at "
                      + resume.optInt("at", 0)
                      + ")");
    }
    synchronized (this.carLog) {
      Iterator<String> it = this.carLog.iterator();
      while (it.hasNext()) {
        sb.append("\n").append(it.next());
      }
    }
    return sb.toString();
  }

  void track(boolean z) {
    SkipAwarePlayer skipAwarePlayer = this.player;
    if (skipAwarePlayer == null) {
      return;
    }
    if (z) {
      skipAwarePlayer.seekToNext();
    } else {
      skipAwarePlayer.seekToPrevious();
    }
  }

  void trackKey(boolean z) {
    SkipAwarePlayer skipAwarePlayer = this.player;
    if (skipAwarePlayer == null) {
      return;
    }
    if (skipAwarePlayer.isPodcastNow()) {
      skip(!z);
    } else {
      track(z);
    }
  }

  void onCatalogChanged() {
    onSnapshotChanged(true, true);
  }

  void onSnapshotChanged(final boolean z, final boolean z2) {
    this.io.execute(
        () -> {
          if (z) {
            this.car.reloadCatalog();
          }
          if (z2) {
            this.car.reloadLibrary();
          }
          this.main.post(
              () -> {
                this.notifyListsChanged();
              });
        });
  }

  public void notifyListsChanged() {
    if (this.session == null) {
      return;
    }
    LinkedHashSet<String> linkedHashSet = new LinkedHashSet(CarLibrary.fixedNodeIds());
    linkedHashSet.addAll(this.browsed);
    for (String str : linkedHashSet) {
      if (!str.startsWith("search:") && !str.startsWith("voice:")) {
        this.session.notifyChildrenChanged(str, Integer.MAX_VALUE, null);
      }
    }
  }

  @Override // androidx.media3.session.MediaSessionService, android.app.Service
  public void onTaskRemoved(Intent intent) {
    ExoPlayer exoPlayer;
    rememberPosition();
    SkipAwarePlayer skipAwarePlayer = this.player;
    if (skipAwarePlayer == null
        || !skipAwarePlayer.isNativeMode()
        || (exoPlayer = this.exo) == null
        || !exoPlayer.getPlayWhenReady()) {
      SkipAwarePlayer skipAwarePlayer2 = this.player;
      if (skipAwarePlayer2 != null) {
        skipAwarePlayer2.setRemote(null);
      }
      pauseAllPlayersAndStopSelf();
    }
  }

  @Override // androidx.media3.session.MediaSessionService, android.app.Service
  public void onDestroy() {
    instance = null;
    this.main.removeCallbacks(this.progressTick);
    this.main.removeCallbacks(this.historyTick);
    this.main.removeCallbacks(this.positionTick);
    rememberPosition();
    try {
      NowPlayingWidget.showPlaying(this, false);
    } catch (Exception unused) {
    }
    saveCarProgress();
    MediaLibraryService.MediaLibrarySession mediaLibrarySession = this.session;
    if (mediaLibrarySession != null) {
      mediaLibrarySession.release();
      this.session = null;
    }
    ExoPlayer exoPlayer = this.exo;
    if (exoPlayer != null) {
      exoPlayer.release();
    }
    this.io.shutdown();
    super.onDestroy();
  }

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

  public void recordCarHistory() {
    SkipAwarePlayer skipAwarePlayer;
    MediaItem currentMediaItem;
    String string;
    String str = this.historyPending;
    if (str == null) {
      return;
    }
    if (this.exo == null
        || (skipAwarePlayer = this.player) == null
        || !skipAwarePlayer.isNativeMode()
        || (currentMediaItem = this.exo.getCurrentMediaItem()) == null
        || !str.equals(currentMediaItem.mediaId)
        || currentMediaItem.mediaMetadata.extras == null
        || (string = currentMediaItem.mediaMetadata.extras.getString("amplify.item")) == null
        || string.contains("\"t\":\"episode\"")) {
      this.historyPending = null;
      return;
    }
    if (this.exo.isPlaying()) {
      this.historyHeardMs += HISTORY_STEP_MS;
    }
    if (this.historyHeardMs >= this.historyNeedMs) {
      CarHistory.add(this, string);
      if (!string.contains("\"t\":\"station\"")) {
        this.historyPending = null;
        return;
      }
      this.historyHeardMs = 0;
      this.historyNeedMs = HISTORY_STATION_MS;
    }
    // Paused: look again less often (time is only added while playing).
    this.main.postDelayed(this.historyTick, this.exo.isPlaying() ? HISTORY_STEP_MS : 15000L);
  }

  private final class WidgetListener implements Player.Listener {
    private WidgetListener() {}

    @Override // androidx.media3.common.Player.Listener
    public void onEvents(Player player, Player.Events events) {
      if (events.containsAny(14, 1, 0)) {
        PlaybackService.this.updateWidget();
      } else if (events.containsAny(5, 7, 4)) {
        PlaybackService playbackService = PlaybackService.this;
        NowPlayingWidget.showPlaying(playbackService, playbackService.widgetPlaying());
      }
    }
  }

  public boolean widgetPlaying() {
    SkipAwarePlayer skipAwarePlayer = this.player;
    return (skipAwarePlayer == null
            || !skipAwarePlayer.getPlayWhenReady()
            || this.player.getPlaybackState() == 1
            || this.player.getPlaybackState() == 4)
        ? false
        : true;
  }

  void updateWidget() {
    String string;
    SkipAwarePlayer skipAwarePlayer = this.player;
    if (skipAwarePlayer == null || this.session == null) {
      return;
    }
    try {
      MediaMetadata mediaMetadata = skipAwarePlayer.getMediaMetadata();
      boolean zWidgetPlaying = widgetPlaying();
      NowPlayingWidget.showText(
          this,
          mediaMetadata.title != null ? mediaMetadata.title : mediaMetadata.displayTitle,
          mediaMetadata.artist,
          zWidgetPlaying);
      if (mediaMetadata.artworkUri != null) {
        string = mediaMetadata.artworkUri.toString();
      } else {
        string =
            mediaMetadata.artworkData != null
                ? "data:"
                    + mediaMetadata.artworkData.length
                    + ":"
                    + Arrays.hashCode(mediaMetadata.artworkData)
                : "";
      }
      if (string.equals(this.widgetArtKey)) {
        return;
      }
      this.widgetArtKey = string;
      final int i = this.widgetSeq + 1;
      this.widgetSeq = i;
      final ListenableFuture<Bitmap> listenableFutureLoadBitmapFromMetadata =
          string.isEmpty()
              ? null
              : this.session.getBitmapLoader().loadBitmapFromMetadata(mediaMetadata);
      if (listenableFutureLoadBitmapFromMetadata == null) {
        NowPlayingWidget.setArt(this, null, zWidgetPlaying);
      } else {
        listenableFutureLoadBitmapFromMetadata.addListener(
            () -> {
              Bitmap bitmap;
              if (i != this.widgetSeq) {
                return;
              }
              try {
                bitmap = (Bitmap) listenableFutureLoadBitmapFromMetadata.get();
              } catch (Exception unused) {
                bitmap = null;
              }
              NowPlayingWidget.setArt(this, bitmap, widgetPlaying());
            },
            ContextCompat.getMainExecutor(this));
      }
    } catch (Exception unused) {
    }
  }

  /* JADX WARN: Multi-variable type inference failed */

  private final class CarListener implements Player.Listener {
    private CarListener() {}

    @Override // androidx.media3.common.Player.Listener
    public void onIsPlayingChanged(boolean z) {
      PlaybackService.this.saveCarProgress();
      if (!z) {
        PlaybackService.this.rememberPosition();
      } else {
        PlaybackService.this.main.postDelayed(PlaybackService.this.positionTick, 5000L);
      }
    }

    @Override // androidx.media3.common.Player.Listener
    public void onTimelineChanged(Timeline timeline, int i) {
      if (PlaybackService.this.player != null) {
        PlaybackService.this.player.refreshPodcast();
      }
    }

    @Override // androidx.media3.common.Player.Listener
    public void onMediaItemTransition(MediaItem mediaItem, int i) {
      if (PlaybackService.this.player != null) {
        PlaybackService.this.player.refreshPodcast();
      }
      if (PlaybackService.this.player == null
          || !PlaybackService.this.player.isNativeMode()
          || mediaItem == null) {
        return;
      }
      Bundle bundle = mediaItem.mediaMetadata.extras;
      PlaybackService.this.exo.setPlaybackSpeed(
          bundle != null && bundle.getString("amplify.guid") != null
              ? (float) PlaybackService.this.car.podcastSpeed()
              : 1.0f);
      PlaybackService.this.main.removeCallbacks(PlaybackService.this.historyTick);
      PlaybackService.this.historyPending = null;
      String string = bundle != null ? bundle.getString("amplify.item") : null;
      if (string != null) {
        PlaybackService.this.rememberLastPlayed(
            mediaItem.mediaId, string, PlaybackService.this.exo.getCurrentPosition());
      }
      if (bundle == null || bundle.getString("amplify.item") == null) {
        return;
      }
      PlaybackService.this.historyPending = mediaItem.mediaId;
      PlaybackService.this.historyHeardMs = 0;
      PlaybackService.this.historyNeedMs = HISTORY_FIRST_MS;
      PlaybackService.this.main.postDelayed(PlaybackService.this.historyTick, HISTORY_STEP_MS);
    }
  }

  final class LibraryCallback implements MediaLibraryService.MediaLibrarySession.Callback {
    private LibraryCallback() {}

    @Override // androidx.media3.session.MediaSession.Callback
    public MediaSession.ConnectionResult onConnect(
        MediaSession mediaSession, MediaSession.ControllerInfo controllerInfo) {
      return new MediaSession.ConnectionResult.AcceptedResultBuilder(mediaSession)
          .setAvailableSessionCommands(
              MediaSession.ConnectionResult.DEFAULT_SESSION_AND_LIBRARY_COMMANDS
                  .buildUpon()
                  .add(PlaybackService.SKIP_BACK)
                  .add(PlaybackService.SKIP_FORWARD)
                  .add(PlaybackService.PREV)
                  .add(PlaybackService.NEXT)
                  .build())
          .setMediaButtonPreferences(PlaybackService.this.buttons())
          .build();
    }

    @Override // androidx.media3.session.MediaSession.Callback
    public boolean onMediaButtonEvent(
        MediaSession mediaSession, MediaSession.ControllerInfo controllerInfo, Intent intent) {
      KeyEvent keyEvent = (KeyEvent) intent.getParcelableExtra("android.intent.extra.KEY_EVENT");
      if (keyEvent == null || PlaybackService.this.player == null) {
        return false;
      }
      int keyCode = keyEvent.getKeyCode();
      boolean z = keyCode == 87;
      boolean z2 = keyCode == 88;
      if (!z && !z2) {
        return false;
      }
      if (keyEvent.getAction() == 0 && keyEvent.getRepeatCount() == 0) {
        PlaybackService.this.trackKey(z);
      }
      return true;
    }

    @Override // androidx.media3.session.MediaSession.Callback
    public ListenableFuture<MediaSession.MediaItemsWithStartPosition> onPlaybackResumption(
        MediaSession mediaSession, MediaSession.ControllerInfo controllerInfo) {
      return PlaybackService.this.io.submit(
          () -> {
            CarLibrary.Queue queueLastPlayedQueue = PlaybackService.this.lastPlayedQueue();
            if (queueLastPlayedQueue == null) {
              throw new IllegalStateException("Nothing played yet");
            }
            return new MediaSession.MediaItemsWithStartPosition(
                queueLastPlayedQueue.items,
                queueLastPlayedQueue.startIndex,
                queueLastPlayedQueue.startPositionMs);
          });
    }

    @Override // androidx.media3.session.MediaSession.Callback
    public ListenableFuture<SessionResult> onCustomCommand(
        MediaSession mediaSession,
        MediaSession.ControllerInfo controllerInfo,
        SessionCommand sessionCommand,
        Bundle bundle) {
      if (PlaybackService.SKIP_BACK.customAction.equals(sessionCommand.customAction)) {
        PlaybackService.this.skip(true);
        return Futures.immediateFuture(new SessionResult(0));
      }
      if (PlaybackService.SKIP_FORWARD.customAction.equals(sessionCommand.customAction)) {
        PlaybackService.this.skip(false);
        return Futures.immediateFuture(new SessionResult(0));
      }
      if (PlaybackService.PREV.customAction.equals(sessionCommand.customAction)
          || PlaybackService.NEXT.customAction.equals(sessionCommand.customAction)) {
        PlaybackService.this.track(
            PlaybackService.NEXT.customAction.equals(sessionCommand.customAction));
        return Futures.immediateFuture(new SessionResult(0));
      }
      return Futures.immediateFuture(new SessionResult(-6));
    }

    @Override // androidx.media3.session.MediaLibraryService.MediaLibrarySession.Callback
    public ListenableFuture<LibraryResult<MediaItem>> onGetLibraryRoot(
        MediaLibraryService.MediaLibrarySession mediaLibrarySession,
        MediaSession.ControllerInfo controllerInfo,
        MediaLibraryService.LibraryParams libraryParams) {
      if (libraryParams != null) {
        PlaybackService.this.car.setRootLimit(
            libraryParams.extras.getInt(
                "androidx.media.MediaBrowserCompat.Extras.KEY_ROOT_CHILDREN_LIMIT", 4));
      }
      return Futures.immediateFuture(
          LibraryResult.ofItem(
              PlaybackService.this.car.rootItem(),
              new MediaLibraryService.LibraryParams.Builder()
                  .setExtras(CarLibrary.rootExtras())
                  .build()));
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

    @Override // androidx.media3.session.MediaLibraryService.MediaLibrarySession.Callback
    public ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> onGetChildren(
        MediaLibraryService.MediaLibrarySession mediaLibrarySession,
        MediaSession.ControllerInfo controllerInfo,
        final String str,
        final int i,
        final int i2,
        final MediaLibraryService.LibraryParams libraryParams) {
      if (PlaybackService.this.browsed.size() < 300) {
        PlaybackService.this.browsed.add(str);
      }
      return PlaybackService.this.io.submit(
          () -> {
            return page(PlaybackService.this.car.children(str), i, i2, libraryParams);
          });
    }

    @Override // androidx.media3.session.MediaSession.Callback
    public ListenableFuture<MediaSession.MediaItemsWithStartPosition> onSetMediaItems(
        MediaSession mediaSession,
        MediaSession.ControllerInfo controllerInfo,
        final List<MediaItem> list,
        final int i,
        final long j) {
      return PlaybackService.this.io.submit(
          () -> {
            if (list.size() == 1) {
              MediaItem mediaItem = (MediaItem) list.get(0);
              CarLibrary.Queue queueQueueFor = PlaybackService.this.car.queueFor(mediaItem.mediaId);
              if (queueQueueFor == null
                  && isVoiceRequest(mediaItem)
                  && (queueQueueFor =
                          PlaybackService.this.car.voice(
                              mediaItem.requestMetadata.searchQuery,
                              mediaItem.requestMetadata.extras))
                      == null) {
                throw new IllegalArgumentException("Nothing found to play");
              }
              if (queueQueueFor != null) {
                return new MediaSession.MediaItemsWithStartPosition(
                    queueQueueFor.items, queueQueueFor.startIndex, queueQueueFor.startPositionMs);
              }
            }
            List<MediaItem> resolved = resolveEach(list);
            return new MediaSession.MediaItemsWithStartPosition(
                resolved, Math.max(0, Math.min(i, resolved.size() - 1)), j);
          });
    }

    @Override
    public ListenableFuture<List<MediaItem>> onAddMediaItems(
        MediaSession mediaSession,
        MediaSession.ControllerInfo controller,
        List<MediaItem> mediaItems) {
      return io.submit(() -> resolveEach(mediaItems));
    }

    private boolean isVoiceRequest(MediaItem mediaItem) {
      if (mediaItem.localConfiguration != null) {
        return false;
      }
      if (mediaItem.requestMetadata.searchQuery != null) {
        return true;
      }
      return mediaItem.mediaId.isEmpty() && mediaItem.requestMetadata.extras != null;
    }

    @Override // androidx.media3.session.MediaLibraryService.MediaLibrarySession.Callback
    public ListenableFuture<LibraryResult<Void>> onSearch(
        final MediaLibraryService.MediaLibrarySession mediaLibrarySession,
        final MediaSession.ControllerInfo controllerInfo,
        final String str,
        final MediaLibraryService.LibraryParams libraryParams) {
      PlaybackService.this.io.execute(
          () -> {
            int size;
            try {
              size = PlaybackService.this.car.searchItems(str).size();
            } catch (Exception unused) {
              size = 0;
            }
            final int i = size;
            PlaybackService.this.main.post(
                () -> {
                  mediaLibrarySession.notifySearchResultChanged(
                      controllerInfo, str, i, libraryParams);
                });
          });
      return Futures.immediateFuture(LibraryResult.ofVoid());
    }

    @Override // androidx.media3.session.MediaLibraryService.MediaLibrarySession.Callback
    public ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> onGetSearchResult(
        MediaLibraryService.MediaLibrarySession mediaLibrarySession,
        MediaSession.ControllerInfo controllerInfo,
        final String str,
        final int i,
        final int i2,
        final MediaLibraryService.LibraryParams libraryParams) {
      return PlaybackService.this.io.submit(
          () -> {
            return page(PlaybackService.this.car.searchItems(str), i, i2, libraryParams);
          });
    }

    private LibraryResult<ImmutableList<MediaItem>> page(
        List<MediaItem> list, int i, int i2, MediaLibraryService.LibraryParams libraryParams) {
      int i3 = 0;
      int iMax = Math.max(0, i) * Math.max(1, i2);
      if (i2 > 0 && i2 != Integer.MAX_VALUE) {
        i3 = iMax;
      }
      if (i3 >= list.size()) {
        return LibraryResult.ofItemList(ImmutableList.of(), libraryParams);
      }
      int size = list.size();
      if (i2 > 0) {
        size = (int) Math.min(size, i3 + i2);
      }
      return LibraryResult.ofItemList(
          ImmutableList.copyOf((Collection) list.subList(i3, size)), libraryParams);
    }

    public List<MediaItem> resolveEach(List<MediaItem> list) throws Exception {
      ArrayList arrayList = new ArrayList();
      if (list.size() == 1
          && isVoiceRequest(list.get(0))
          && PlaybackService.this.car.queueFor(list.get(0).mediaId) == null) {
        MediaItem mediaItem = list.get(0);
        CarLibrary.Queue queueVoice =
            PlaybackService.this.car.voice(
                mediaItem.requestMetadata.searchQuery, mediaItem.requestMetadata.extras);
        if (queueVoice != null) {
          arrayList.addAll(
              queueVoice.items.subList(queueVoice.startIndex, queueVoice.items.size()));
          return arrayList;
        }
      } else {
        for (MediaItem mediaItem2 : list) {
          if (mediaItem2.localConfiguration != null) {
            arrayList.add(mediaItem2);
          } else {
            CarLibrary.Queue queueQueueFor = PlaybackService.this.car.queueFor(mediaItem2.mediaId);
            if (queueQueueFor != null) {
              arrayList.add(queueQueueFor.items.get(queueQueueFor.startIndex));
            }
          }
        }
      }
      return arrayList;
    }
  }
}
