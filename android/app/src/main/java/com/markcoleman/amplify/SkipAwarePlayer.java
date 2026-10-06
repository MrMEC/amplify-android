package com.markcoleman.amplify;

import android.os.SystemClock;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.*;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.DeviceInfo;
import androidx.media3.common.FlagSet;
import androidx.media3.common.Format;
import androidx.media3.common.ForwardingPlayer;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.Metadata;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.PlaybackParameters;
import androidx.media3.common.Player;
import androidx.media3.common.Timeline;
import androidx.media3.common.TrackSelectionParameters;
import androidx.media3.common.Tracks;
import androidx.media3.common.VideoSize;
import androidx.media3.common.text.Cue;
import androidx.media3.common.text.CueGroup;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.extractor.metadata.icy.IcyHeaders;
import androidx.media3.extractor.metadata.icy.IcyInfo;
import androidx.media3.extractor.metadata.id3.TextInformationFrame;
import com.google.common.collect.UnmodifiableIterator;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * The player the MediaSession sees. It wraps the real ExoPlayer and does three things: - Transport
 * commands that come from outside the app (notification, lock screen, headset, Bluetooth, later
 * Android Auto) are handed to the web app, which owns the queue, instead of being applied to
 * ExoPlayer directly. If the web app is gone they fall back to ExoPlayer. - Next/Previous are
 * advertised whenever the web app says it has somewhere to go, even though ExoPlayer itself only
 * ever holds one item. - Title/artist/artwork come from the web app rather than from the stream's
 * own tags. The in-app plugin drives the ExoPlayer directly, so its calls never loop back through
 * here.
 *
 * <p>SkipListener below is adapted from androidx.media3 ForwardingPlayer (Apache License 2.0).
 */
@OptIn(markerClass = UnstableApi.class)
public final class SkipAwarePlayer extends ForwardingPlayer {
  private String buttonsShown;
  private String lastRaw;
  private String lastIcyBlock;
  private long lastRawAt;
  private String lastRawFor;
  private String lastVerdict;
  private boolean live;
  private int metaCalls;
  private final LinkedHashSet<String> metaKinds;
  private boolean nativeMode;
  private boolean nextEnabled;
  private StreamTitle onAir;
  private String onAirFor;
  private OnAirListener onAirListener;
  private Runnable onNativeModeStart;
  private Runnable onPodcastChanged;
  private MediaMetadata override;
  private List<MediaItem> pageQueue;
  private String pageQueueFor;
  private boolean podcastPage;
  private boolean prevEnabled;
  private int rawCount;
  private Remote remote;
  private boolean resumePending;
  private final Map<Player.Listener, SkipListener> wrapped;

  public interface OnAirListener {
    void onAirChanged(StreamTitle streamTitle);
  }

  public interface Remote {
    boolean onRemote(String str);
  }

  public SkipAwarePlayer(Player player) {
    super(player);
    this.wrapped = new HashMap();
    this.buttonsShown = "";
    this.lastVerdict = "nothing yet";
    this.metaKinds = new LinkedHashSet<>();
    player.addListener(
        new Player.Listener() { // from class: com.markcoleman.amplify.SkipAwarePlayer.1
          @Override // androidx.media3.common.Player.Listener
          public void onMetadata(Metadata metadata) {
            SkipAwarePlayer.this.handleStreamMetadata(metadata);
          }
        });
  }

  public void setOnAirListener(OnAirListener onAirListener) {
    this.onAirListener = onAirListener;
  }

  public StreamTitle getOnAir() {
    String str;
    MediaItem currentMediaItem = getCurrentMediaItem();
    if (this.onAir == null
        || currentMediaItem == null
        || (str = this.onAirFor) == null
        || !str.equals(currentMediaItem.mediaId)) {
      return null;
    }
    return this.onAir;
  }

  public void clearOnAir() {
    this.lastRaw = null;
    this.lastRawFor = null;
    if (this.onAir == null) {
      return;
    }
    this.onAir = null;
    this.onAirFor = null;
    announceOnAir();
  }

  public String streamDebug() {
    StringBuilder sb = new StringBuilder();
    Player wrappedPlayer = getWrappedPlayer();
    MediaItem currentMediaItem = wrappedPlayer.getCurrentMediaItem();
    String string =
        (currentMediaItem == null || currentMediaItem.localConfiguration == null)
            ? "none"
            : currentMediaItem.localConfiguration.uri.toString();
    if (string.length() > 90) {
      string = string.substring(0, 90) + "...";
    }
    sb.append("Playing URL: ").append(string);
    sb.append("\nPlayer: ")
        .append(wrappedPlayer.isPlaying() ? "playing" : "not playing")
        .append(", state ")
        .append(wrappedPlayer.getPlaybackState());
    Tracks currentTracks = wrappedPlayer.getCurrentTracks();
    sb.append("\nTracks: ").append(currentTracks.getGroups().size());
    UnmodifiableIterator<Tracks.Group> it = currentTracks.getGroups().iterator();
    while (it.hasNext()) {
      Tracks.Group next = it.next();
      for (int i = 0; i < next.length; i++) {
        Format trackFormat = next.getTrackFormat(i);
        sb.append("\n  ")
            .append(trackFormat.sampleMimeType)
            .append(next.isTrackSelected(i) ? " (on)" : " (off)");
        if (!next.isTrackSupported(i)) {
          sb.append(" unsupported");
        }
        if (trackFormat.metadata != null) {
          for (int i2 = 0; i2 < trackFormat.metadata.length(); i2++) {
            Metadata.Entry entry = trackFormat.metadata.get(i2);
            if (entry instanceof IcyHeaders) {
              sb.append(" icy-metaint=").append(((IcyHeaders) entry).metadataInterval);
            } else {
              sb.append(" ").append(entry.getClass().getSimpleName());
            }
          }
        }
      }
    }
    sb.append("\nMetadata batches: ")
        .append(this.metaCalls)
        .append(this.metaKinds.isEmpty() ? "" : " " + this.metaKinds);
    return sb.toString();
  }

  /** The raw ICY block as text for the diagnostics (NULs dropped, at most 240 characters). */
  private static String icyBlockText(byte[] bytes) {
    if (bytes == null) {
      return null;
    }
    String t = new String(bytes, java.nio.charset.StandardCharsets.ISO_8859_1).replace("\u0000", "").trim();
    return t.length() > 240 ? t.substring(0, 240) + "..." : t;
  }

  public String onAirDebug() {
    MediaItem currentMediaItem = getCurrentMediaItem();
    return "Stream titles: "
        + this.rawCount
        + " received, last "
        + (this.lastRawAt == 0
            ? "never"
            : ((SystemClock.elapsedRealtime() - this.lastRawAt) / 1000) + " s ago")
        + (this.lastRaw == null ? "" : " (\"" + this.lastRaw + "\")")
        + (this.lastIcyBlock == null ? "" : "; ICY block [" + this.lastIcyBlock + "]")
        + "; live "
        + (isLiveNow() ? "yes" : "no")
        + "; station \""
        + stationName()
        + "\"; item "
        + (currentMediaItem == null ? "none" : currentMediaItem.mediaId)
        + "; "
        + this.lastVerdict;
  }

  private boolean isLiveNow() {
    if (this.nativeMode) {
      MediaItem currentMediaItem = getCurrentMediaItem();
      return (currentMediaItem == null
              || currentMediaItem.mediaMetadata.extras == null
              || !currentMediaItem.mediaMetadata.extras.getBoolean("amplify.live", false))
          ? false
          : true;
    }
    return this.live;
  }

  private String stationName() {
    if (this.nativeMode) {
      MediaItem currentMediaItem = getCurrentMediaItem();
      if (currentMediaItem == null || currentMediaItem.mediaMetadata.title == null) {
        return null;
      }
      return currentMediaItem.mediaMetadata.title.toString();
    }
    MediaMetadata mediaMetadata = this.override;
    if (mediaMetadata == null || mediaMetadata.title == null) {
      return null;
    }
    return this.override.title.toString();
  }

  void handleStreamMetadata(Metadata metadata) {
    this.metaCalls++;
    for (int i = 0; i < metadata.length() && this.metaKinds.size() < 8; i++) {
      this.metaKinds.add(metadata.get(i).getClass().getSimpleName());
    }
    String str = null;
    String str2 = null;
    String str3 = null;
    for (int i2 = 0; i2 < metadata.length(); i2++) {
      Metadata.Entry entry = metadata.get(i2);
      if (entry instanceof IcyInfo) {
        IcyInfo icyInfo = (IcyInfo) entry;
        // Build 148: our own reading of the raw block, so an apostrophe can't cut the title off.
        String mine = null;
        try {
          mine = StreamTitle.icyTitle(icyInfo.rawMetadata);
          this.lastIcyBlock = icyBlockText(icyInfo.rawMetadata);
        } catch (RuntimeException e) {
          mine = null;
        }
        if (mine != null) {
          str = mine;
        } else if (icyInfo.title != null) {
          str = icyInfo.title;
        }
      } else if (entry instanceof TextInformationFrame) {
        TextInformationFrame textInformationFrame = (TextInformationFrame) entry;
        String str4 =
            textInformationFrame.values.isEmpty() ? null : textInformationFrame.values.get(0);
        if ("TIT2".equals(textInformationFrame.id)) {
          str2 = str4;
        } else if ("TPE1".equals(textInformationFrame.id)) {
          str3 = str4;
        }
      }
    }
    if (str == null && str2 != null) {
      str = (str3 == null || str3.trim().isEmpty()) ? str2 : str3 + " - " + str2;
    }
    if (str == null) {
      return;
    }
    MediaItem currentMediaItem = getCurrentMediaItem();
    this.rawCount++;
    this.lastRawAt = SystemClock.elapsedRealtime();
    this.lastRaw = str;
    this.lastRawFor = currentMediaItem != null ? currentMediaItem.mediaId : null;
    applyRaw();
  }

  private void applyRaw() {
    String str;
    String str2 = this.lastRaw;
    MediaItem currentMediaItem = getCurrentMediaItem();
    if (str2 == null
        || currentMediaItem == null
        || (str = this.lastRawFor) == null
        || !str.equals(currentMediaItem.mediaId)) {
      return;
    }
    if (!isLiveNow()) {
      this.lastVerdict = "held: not marked live yet";
      return;
    }
    StreamTitle streamTitle = StreamTitle.parse(str2, stationName());
    this.lastVerdict = streamTitle == null ? "not a song" : "shown: " + streamTitle.display();
    String str3 = this.onAirFor;
    boolean z = str3 != null && str3.equals(currentMediaItem.mediaId);
    if (z && streamTitle != null && streamTitle.sameSong(this.onAir)) {
      return;
    }
    if (z && streamTitle == null && this.onAir == null) {
      return;
    }
    if (!z && streamTitle == null) {
      this.onAir = null;
      this.onAirFor = currentMediaItem.mediaId;
    } else {
      this.onAir = streamTitle;
      this.onAirFor = currentMediaItem.mediaId;
      announceOnAir();
    }
  }

  private void announceOnAir() {
    MediaMetadata mediaMetadata = getMediaMetadata();
    Player.Events events = new Player.Events(new FlagSet.Builder().add(14).build());
    Iterator it = new ArrayList(this.wrapped.values()).iterator();
    while (it.hasNext()) {
      SkipListener skipListener = (SkipListener) it.next();
      skipListener.listener.onMediaMetadataChanged(mediaMetadata);
      skipListener.listener.onEvents(this, events);
    }
    OnAirListener onAirListener = this.onAirListener;
    if (onAirListener != null) {
      onAirListener.onAirChanged(getOnAir());
    }
  }

  private static boolean sameName(String str, String str2) {
    String strReplaceAll = str.toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+", "");
    return !strReplaceAll.isEmpty()
        && strReplaceAll.equals(str2.toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+", ""));
  }

  private static String str(CharSequence charSequence) {
    return charSequence == null ? "" : charSequence.toString().trim();
  }

  private static String joinDot(String... strArr) {
    StringBuilder sb = new StringBuilder();
    for (String str : strArr) {
      if (str != null && !str.isEmpty()) {
        if (sb.length() > 0) {
          sb.append(" · ");
        }
        sb.append(str);
      }
    }
    return sb.toString();
  }

  private MediaMetadata withCarLines(MediaMetadata mediaMetadata, String str) {
    if (isPodcastNow()) {
      return mediaMetadata;
    }
    if (isLiveNow()) {
      String str2 = str(mediaMetadata.title);
      StreamTitle onAir = getOnAir();
      String strJoinDot = "";
      String str3 =
          (onAir == null || onAir.artist.isEmpty() || sameName(onAir.artist, str2))
              ? ""
              : onAir.artist;
      if (onAir != null) {
        strJoinDot = joinDot(onAir.title, str3);
      }
      String strJoinDot2 = joinDot(strJoinDot, str(str));
      if (strJoinDot2.isEmpty()) {
        strJoinDot2 = str(mediaMetadata.artist);
      }
      MediaMetadata.Builder displayTitle =
          mediaMetadata.buildUpon().setDisplayTitle(str2.isEmpty() ? null : str2);
      if (strJoinDot2.isEmpty()) {
        strJoinDot2 = null;
      }
      MediaMetadata.Builder station =
          displayTitle.setSubtitle(strJoinDot2).setStation(str2.isEmpty() ? null : str2);
      if (!strJoinDot.isEmpty()) {
        station.setArtist(strJoinDot);
      }
      return station.build();
    }
    String str4 = str(mediaMetadata.title);
    String strJoinDot3 = joinDot(str(mediaMetadata.artist), str(mediaMetadata.albumTitle));
    MediaMetadata.Builder builderBuildUpon = mediaMetadata.buildUpon();
    if (str4.isEmpty()) {
      str4 = null;
    }
    return builderBuildUpon
        .setDisplayTitle(str4)
        .setSubtitle(strJoinDot3.isEmpty() ? null : strJoinDot3)
        .build();
  }

  private static String pagePlace(MediaMetadata mediaMetadata) {
    String str = str(mediaMetadata.artist);
    if (str.isEmpty() || "Internet radio".equals(str)) {
      return null;
    }
    return str;
  }

  public void setRemote(Remote remote) {
    this.remote = remote;
  }

  private boolean dispatch(String str) {
    Remote remote;
    return (this.nativeMode || (remote = this.remote) == null || !remote.onRemote(str))
        ? false
        : true;
  }

  public boolean isNativeMode() {
    return this.nativeMode;
  }

  public void setOnNativeModeStart(Runnable runnable) {
    this.onNativeModeStart = runnable;
  }

  public void exitNativeMode() {
    this.resumePending = false;
    if (this.nativeMode) {
      this.nativeMode = false;
      notifyCommandsChanged();
      refreshPodcast();
    }
  }

  public void setResumePending() {
    this.resumePending = true;
    Player.Events events = new Player.Events(new FlagSet.Builder().add(4).build());
    Iterator it = new ArrayList(this.wrapped.values()).iterator();
    while (it.hasNext()) {
      SkipListener skipListener = (SkipListener) it.next();
      skipListener.listener.onPlaybackStateChanged(3);
      skipListener.listener.onEvents(this, events);
    }
    notifyCommandsChanged();
  }

  public boolean isResumePending() {
    return this.resumePending && super.getPlaybackState() == 1 && getMediaItemCount() > 0;
  }

  private void wakeResume() {
    if (this.resumePending) {
      this.resumePending = false;
      if (super.getPlaybackState() != 1 || getMediaItemCount() <= 0) {
        return;
      }
      super.prepare();
    }
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public int getPlaybackState() {
    if (isResumePending()) {
      return 3;
    }
    return super.getPlaybackState();
  }

  public void setOnPodcastChanged(Runnable runnable) {
    this.onPodcastChanged = runnable;
  }

  public boolean isPodcastNow() {
    if (!this.nativeMode) {
      return this.podcastPage;
    }
    MediaItem currentMediaItem = getCurrentMediaItem();
    return (currentMediaItem == null
            || currentMediaItem.mediaMetadata.extras == null
            || currentMediaItem.mediaMetadata.extras.getString("amplify.guid") == null)
        ? false
        : true;
  }

  public boolean nextAvailable() {
    return this.nativeMode ? getWrappedPlayer().hasNextMediaItem() : this.nextEnabled;
  }

  public boolean prevAvailable() {
    if (this.nativeMode) {
      return getWrappedPlayer().getMediaItemCount() > 0;
    }
    return this.prevEnabled;
  }

  public void refreshPodcast() {
    String str = isPodcastNow() ? "podcast" : (prevAvailable() || nextAvailable()) ? "track" : "";
    if (str.equals(this.buttonsShown)) {
      return;
    }
    this.buttonsShown = str;
    Runnable runnable = this.onPodcastChanged;
    if (runnable != null) {
      runnable.run();
    }
    notifyCommandsChanged();
  }

  private void enterNativeMode() {
    this.resumePending = false;
    this.pageQueue = null;
    this.pageQueueFor = null;
    boolean z = this.nativeMode;
    this.nativeMode = true;
    this.override = null;
    this.live = false;
    if (!z) {
      Runnable runnable = this.onNativeModeStart;
      if (runnable != null) {
        runnable.run();
      }
      notifyCommandsChanged();
    }
    refreshPodcast();
  }

  private void notifyCommandsChanged() {
    Player.Commands availableCommands = getAvailableCommands();
    Player.Events events = new Player.Events(new FlagSet.Builder().add(13).build());
    Iterator it = new ArrayList(this.wrapped.values()).iterator();
    while (it.hasNext()) {
      SkipListener skipListener = (SkipListener) it.next();
      skipListener.listener.onAvailableCommandsChanged(availableCommands);
      skipListener.listener.onEvents(this, events);
    }
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setMediaItems(List<MediaItem> list, boolean z) {
    enterNativeMode();
    super.setMediaItems(list, z);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setMediaItems(List<MediaItem> list, int i, long j) {
    enterNativeMode();
    super.setMediaItems(list, i, j);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setMediaItems(List<MediaItem> list) {
    enterNativeMode();
    super.setMediaItems(list);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setMediaItem(MediaItem mediaItem) {
    enterNativeMode();
    super.setMediaItem(mediaItem);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setMediaItem(MediaItem mediaItem, long j) {
    enterNativeMode();
    super.setMediaItem(mediaItem, j);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setMediaItem(MediaItem mediaItem, boolean z) {
    enterNativeMode();
    super.setMediaItem(mediaItem, z);
  }

  public void setPageQueue(String str, List<MediaItem> list) {
    boolean zPageActive = pageActive();
    ArrayList arrayList = (list == null || list.isEmpty()) ? null : new ArrayList(list);
    this.pageQueue = arrayList;
    if (arrayList == null) {
      str = null;
    }
    this.pageQueueFor = str;
    if (zPageActive || pageActive()) {
      notifyTimelineChanged();
    }
  }

  boolean pageActive() {
    MediaItem currentMediaItem;
    if (!this.nativeMode && this.pageQueue != null && this.pageQueueFor != null) {
      Player wrappedPlayer = getWrappedPlayer();
      if (wrappedPlayer.getMediaItemCount() == 1
          && (currentMediaItem = wrappedPlayer.getCurrentMediaItem()) != null
          && this.pageQueueFor.equals(currentMediaItem.mediaId)) {
        return true;
      }
    }
    return false;
  }

  private void notifyTimelineChanged() {
    Timeline currentTimeline = getCurrentTimeline();
    Player.Events events = new Player.Events(new FlagSet.Builder().add(0).build());
    Iterator it = new ArrayList(this.wrapped.values()).iterator();
    while (it.hasNext()) {
      SkipListener skipListener = (SkipListener) it.next();
      skipListener.listener.onTimelineChanged(currentTimeline, 0);
      skipListener.listener.onEvents(this, events);
    }
  }

  static final class QueueTimeline extends Timeline {
    private final Timeline base;
    private final List<MediaItem> upcoming;

    QueueTimeline(Timeline timeline, List<MediaItem> list) {
      this.base = timeline;
      this.upcoming = list;
    }

    @Override // androidx.media3.common.Timeline
    public int getWindowCount() {
      return this.upcoming.size() + 1;
    }

    @Override // androidx.media3.common.Timeline
    public Timeline.Window getWindow(int i, Timeline.Window window, long j) {
      if (i == 0) {
        this.base.getWindow(0, window, j);
        window.firstPeriodIndex = 0;
        window.lastPeriodIndex = 0;
        return window;
      }
      MediaItem mediaItem = this.upcoming.get(i - 1);
      window.set(
          uid(i),
          mediaItem,
          null,
          -9223372036854775807L,
          -9223372036854775807L,
          -9223372036854775807L,
          true,
          false,
          null,
          0L,
          durationUs(mediaItem),
          i,
          i,
          0L);
      return window;
    }

    @Override // androidx.media3.common.Timeline
    public int getPeriodCount() {
      return this.upcoming.size() + 1;
    }

    @Override // androidx.media3.common.Timeline
    public Timeline.Period getPeriod(int i, Timeline.Period period, boolean z) {
      if (i == 0) {
        this.base.getPeriod(0, period, z);
        period.windowIndex = 0;
        return period;
      }
      Object objUid = uid(i);
      return period.set(objUid, objUid, i, durationUs(this.upcoming.get(i - 1)), 0L);
    }

    @Override // androidx.media3.common.Timeline
    public int getIndexOfPeriod(Object obj) {
      if (this.base.getPeriodCount() > 0 && this.base.getIndexOfPeriod(obj) == 0) {
        return 0;
      }
      for (int i = 1; i <= this.upcoming.size(); i++) {
        if (uid(i).equals(obj)) {
          return i;
        }
      }
      return -1;
    }

    @Override // androidx.media3.common.Timeline
    public Object getUidOfPeriod(int i) {
      return i == 0 ? this.base.getUidOfPeriod(0) : uid(i);
    }

    private Object uid(int i) {
      return "amplify-queue:" + i + ":" + this.upcoming.get(i - 1).mediaId;
    }

    private static long durationUs(MediaItem mediaItem) {
      Long l = mediaItem.mediaMetadata.durationMs;
      if (l == null || l.longValue() <= 0) {
        return -9223372036854775807L;
      }
      return l.longValue() * 1000;
    }
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public Timeline getCurrentTimeline() {
    Timeline currentTimeline = super.getCurrentTimeline();
    return (pageActive()
            && currentTimeline.getWindowCount() == 1
            && currentTimeline.getPeriodCount() == 1)
        ? new QueueTimeline(currentTimeline, this.pageQueue)
        : currentTimeline;
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public int getMediaItemCount() {
    return pageActive() ? this.pageQueue.size() + 1 : super.getMediaItemCount();
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public MediaItem getMediaItemAt(int i) {
    return (!pageActive() || i <= 0) ? super.getMediaItemAt(i) : this.pageQueue.get(i - 1);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public boolean hasNextMediaItem() {
    return pageActive() || super.hasNextMediaItem();
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public int getNextMediaItemIndex() {
    if (pageActive()) {
      return 1;
    }
    return super.getNextMediaItemIndex();
  }

  private boolean pickFromPageQueue(int i) {
    return pageActive() && i > 0 && dispatch(new StringBuilder("queue:").append(i).toString());
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void seekToDefaultPosition(int i) {
    if (pickFromPageQueue(i)) {
      return;
    }
    if (pageActive()) {
      i = 0;
    }
    super.seekToDefaultPosition(i);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void seekTo(int i, long j) {
    if (pickFromPageQueue(i)) {
      return;
    }
    if (pageActive()) {
      i = 0;
    }
    super.seekTo(i, j);
  }

  public void setSkipEnabled(boolean z, boolean z2, boolean z3) {
    this.podcastPage = z3;
    this.nextEnabled = z;
    this.prevEnabled = z2;
    refreshPodcast();
  }

  Player.Commands augment(Player.Commands commands) {
    return commands.buildUpon().removeAll(9, 8, 7, 6).build();
  }

  @Override
  public Commands getAvailableCommands() {
    return augment(super.getAvailableCommands());
  }

  @Override
  public boolean isCommandAvailable(@Command int command) {
    return getAvailableCommands().contains(command);
  }

  public void setOverrideMetadata(MediaMetadata mediaMetadata, boolean z) {
    this.override = mediaMetadata;
    this.live = z;
    if (this.lastRaw != null) {
      applyRaw();
    }
    MediaMetadata mediaMetadata2 = getMediaMetadata();
    Player.Events events = new Player.Events(new FlagSet.Builder().add(14).build());
    Iterator it = new ArrayList(this.wrapped.values()).iterator();
    while (it.hasNext()) {
      SkipListener skipListener = (SkipListener) it.next();
      skipListener.listener.onMediaMetadataChanged(mediaMetadata2);
      skipListener.listener.onEvents(this, events);
    }
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public MediaMetadata getMediaMetadata() {
    MediaMetadata mediaMetadata = super.getMediaMetadata();
    if (this.nativeMode) {
      MediaItem currentMediaItem = getCurrentMediaItem();
      if (currentMediaItem != null) {
        MediaMetadata mediaMetadata2 = currentMediaItem.mediaMetadata;
        return withCarLines(
            mediaMetadata2,
            mediaMetadata2.extras == null
                ? null
                : mediaMetadata2.extras.getString("amplify.place"));
      }
    } else {
      MediaMetadata mediaMetadata3 = this.override;
      if (mediaMetadata3 != null) {
        return withCarLines(mediaMetadata3, pagePlace(mediaMetadata3));
      }
    }
    return mediaMetadata;
  }

  @Override
  public void addListener(Listener listener) {
    SkipListener l = new SkipListener(this, listener);
    wrapped.put(listener, l);
    getWrappedPlayer().addListener(l);
  }

  @Override
  public void removeListener(Listener listener) {
    SkipListener l = wrapped.remove(listener);
    if (l != null) getWrappedPlayer().removeListener(l);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void play() {
    if (dispatch("play")) {
      return;
    }
    wakeResume();
    super.play();
  }

  @Override
  public void pause() {
    if (!dispatch("pause")) super.pause();
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void setPlayWhenReady(boolean z) {
    if (dispatch(z ? "play" : "pause")) {
      return;
    }
    if (z) {
      wakeResume();
    }
    super.setPlayWhenReady(z);
  }

  @Override // androidx.media3.common.ForwardingPlayer, androidx.media3.common.Player
  public void prepare() {
    this.resumePending = false;
    if (this.remote == null || this.nativeMode) {
      super.prepare();
    }
  }

  @Override
  public void stop() {
    if (!dispatch("stop")) super.stop();
  }

  @Override
  public void seekToNext() {
    if (nativeMode) super.seekToNext();
    else dispatch("next");
  }

  @Override
  public void seekToNextMediaItem() {
    if (nativeMode) super.seekToNextMediaItem();
    else dispatch("next");
  }

  @Override
  public void seekToPrevious() {
    if (nativeMode) super.seekToPrevious();
    else dispatch("previous");
  }

  @Override
  public void seekToPreviousMediaItem() {
    if (nativeMode) super.seekToPreviousMediaItem();
    else dispatch("previous");
  }

  private static final class SkipListener implements Player.Listener {
    private final SkipAwarePlayer forwardingPlayer;
    final Player.Listener listener;

    SkipListener(SkipAwarePlayer skipAwarePlayer, Player.Listener listener) {
      this.forwardingPlayer = skipAwarePlayer;
      this.listener = listener;
    }

    @Override
    public void onEvents(Player player, Events events) {
      // Replace player with forwarding player.
      listener.onEvents(forwardingPlayer, events);
    }

    @Override // androidx.media3.common.Player.Listener
    public void onTimelineChanged(Timeline timeline, int i) {
      this.listener.onTimelineChanged(this.forwardingPlayer.getCurrentTimeline(), i);
    }

    @Override
    public void onMediaItemTransition(
        @Nullable MediaItem mediaItem, @MediaItemTransitionReason int reason) {
      listener.onMediaItemTransition(mediaItem, reason);
    }

    @Override
    public void onTracksChanged(Tracks tracks) {
      listener.onTracksChanged(tracks);
    }

    @Override
    public void onMediaMetadataChanged(MediaMetadata mediaMetadata) {
      listener.onMediaMetadataChanged(forwardingPlayer.getMediaMetadata());
    }

    @Override
    public void onPlaylistMetadataChanged(MediaMetadata mediaMetadata) {
      listener.onPlaylistMetadataChanged(mediaMetadata);
    }

    @Override
    public void onIsLoadingChanged(boolean isLoading) {
      listener.onIsLoadingChanged(isLoading);
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onLoadingChanged(boolean isLoading) {
      listener.onIsLoadingChanged(isLoading);
    }

    @Override
    public void onAvailableCommandsChanged(Commands availableCommands) {
      listener.onAvailableCommandsChanged(forwardingPlayer.augment(availableCommands));
    }

    @Override
    public void onTrackSelectionParametersChanged(TrackSelectionParameters parameters) {
      listener.onTrackSelectionParametersChanged(parameters);
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onPlayerStateChanged(boolean playWhenReady, @State int playbackState) {
      listener.onPlayerStateChanged(playWhenReady, playbackState);
    }

    @Override
    public void onPlaybackStateChanged(@State int playbackState) {
      listener.onPlaybackStateChanged(playbackState);
    }

    @Override
    public void onPlayWhenReadyChanged(
        boolean playWhenReady, @PlayWhenReadyChangeReason int reason) {
      listener.onPlayWhenReadyChanged(playWhenReady, reason);
    }

    @Override
    public void onPlaybackSuppressionReasonChanged(
        @PlayWhenReadyChangeReason int playbackSuppressionReason) {
      listener.onPlaybackSuppressionReasonChanged(playbackSuppressionReason);
    }

    @Override
    public void onIsPlayingChanged(boolean isPlaying) {
      listener.onIsPlayingChanged(isPlaying);
    }

    @Override
    public void onRepeatModeChanged(@RepeatMode int repeatMode) {
      listener.onRepeatModeChanged(repeatMode);
    }

    @Override
    public void onShuffleModeEnabledChanged(boolean shuffleModeEnabled) {
      listener.onShuffleModeEnabledChanged(shuffleModeEnabled);
    }

    @Override
    public void onPlayerError(PlaybackException error) {
      listener.onPlayerError(error);
    }

    @Override
    public void onPlayerErrorChanged(@Nullable PlaybackException error) {
      listener.onPlayerErrorChanged(error);
    }

    @Override // androidx.media3.common.Player.Listener
    public void onPositionDiscontinuity(int i) {
      this.listener.onPositionDiscontinuity(i);
    }

    @Override // androidx.media3.common.Player.Listener
    public void onPositionDiscontinuity(
        Player.PositionInfo positionInfo, Player.PositionInfo positionInfo2, int i) {
      this.listener.onPositionDiscontinuity(positionInfo, positionInfo2, i);
    }

    @Override
    public void onPlaybackParametersChanged(PlaybackParameters playbackParameters) {
      listener.onPlaybackParametersChanged(playbackParameters);
    }

    @Override
    public void onSeekBackIncrementChanged(long seekBackIncrementMs) {
      listener.onSeekBackIncrementChanged(seekBackIncrementMs);
    }

    @Override
    public void onSeekForwardIncrementChanged(long seekForwardIncrementMs) {
      listener.onSeekForwardIncrementChanged(seekForwardIncrementMs);
    }

    @Override
    public void onMaxSeekToPreviousPositionChanged(long maxSeekToPreviousPositionMs) {
      listener.onMaxSeekToPreviousPositionChanged(maxSeekToPreviousPositionMs);
    }

    @Override
    public void onVideoSizeChanged(VideoSize videoSize) {
      listener.onVideoSizeChanged(videoSize);
    }

    @Override
    public void onSurfaceSizeChanged(int width, int height) {
      listener.onSurfaceSizeChanged(width, height);
    }

    @Override
    public void onRenderedFirstFrame() {
      listener.onRenderedFirstFrame();
    }

    @Override
    public void onAudioSessionIdChanged(int audioSessionId) {
      listener.onAudioSessionIdChanged(audioSessionId);
    }

    @Override
    public void onAudioAttributesChanged(AudioAttributes audioAttributes) {
      listener.onAudioAttributesChanged(audioAttributes);
    }

    @Override
    public void onVolumeChanged(float volume) {
      listener.onVolumeChanged(volume);
    }

    @Override
    public void onSkipSilenceEnabledChanged(boolean skipSilenceEnabled) {
      listener.onSkipSilenceEnabledChanged(skipSilenceEnabled);
    }

    @Override // androidx.media3.common.Player.Listener
    public void onCues(List<Cue> list) {
      this.listener.onCues(list);
    }

    @Override // androidx.media3.common.Player.Listener
    public void onCues(CueGroup cueGroup) {
      this.listener.onCues(cueGroup);
    }

    @Override
    public void onMetadata(Metadata metadata) {
      listener.onMetadata(metadata);
    }

    @Override
    public void onDeviceInfoChanged(DeviceInfo deviceInfo) {
      listener.onDeviceInfoChanged(deviceInfo);
    }

    @Override
    public void onDeviceVolumeChanged(int volume, boolean muted) {
      listener.onDeviceVolumeChanged(volume, muted);
    }

    public boolean equals(Object obj) {
      if (this == obj) {
        return true;
      }
      if (!(obj instanceof SkipListener)) {
        return false;
      }
      SkipListener skipListener = (SkipListener) obj;
      if (this.forwardingPlayer.equals(skipListener.forwardingPlayer)) {
        return this.listener.equals(skipListener.listener);
      }
      return false;
    }

    public int hashCode() {
      return (this.forwardingPlayer.hashCode() * 31) + this.listener.hashCode();
    }
  }
}
