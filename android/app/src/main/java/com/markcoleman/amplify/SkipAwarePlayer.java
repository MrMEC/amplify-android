package com.markcoleman.amplify;

import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.*;
import androidx.media3.common.text.Cue;
import androidx.media3.common.text.CueGroup;
import androidx.media3.common.util.UnstableApi;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The player the MediaSession sees. It wraps the real ExoPlayer and does three things:
 * - Transport commands that come from outside the app (notification, lock screen, headset,
 *   Bluetooth, later Android Auto) are handed to the web app, which owns the queue, instead of
 *   being applied to ExoPlayer directly. If the web app is gone they fall back to ExoPlayer.
 * - Next/Previous are advertised whenever the web app says it has somewhere to go, even
 *   though ExoPlayer itself only ever holds one item.
 * - Title/artist/artwork come from the web app rather than from the stream's own tags.
 * The in-app plugin drives the ExoPlayer directly, so its calls never loop back through here.
 *
 * SkipListener below is adapted from androidx.media3 ForwardingPlayer (Apache License 2.0).
 */
@OptIn(markerClass = UnstableApi.class)
public final class SkipAwarePlayer extends ForwardingPlayer {

  public interface Remote {
    /** Returns true if the web app took the action. Called on the main thread. */
    boolean onRemote(String action);
  }

  private final Map<Listener, SkipListener> wrapped = new HashMap<>();
  @Nullable private Remote remote;
  private boolean nextEnabled;
  private boolean prevEnabled;
  @Nullable private MediaMetadata override;
  private boolean live;
  // Car mode: Android Auto picked something from its menu. The queue is then ExoPlayer's own
  // (the list the item came from), so transport controls act on ExoPlayer directly instead
  // of going to the page, and the title/art come from the item itself.
  private boolean nativeMode;
  @Nullable private Runnable onNativeModeStart;

  public SkipAwarePlayer(Player player) {
    super(player);
  }

  public void setRemote(@Nullable Remote remote) {
    this.remote = remote;
  }

  private boolean dispatch(String action) {
    if (nativeMode) return false;
    Remote r = remote;
    return r != null && r.onRemote(action);
  }

  // ---------- car mode ----------

  public boolean isNativeMode() {
    return nativeMode;
  }

  public void setOnNativeModeStart(@Nullable Runnable r) {
    onNativeModeStart = r;
  }

  /** The page took playback back (it loaded something itself). */
  public void exitNativeMode() {
    if (!nativeMode) return;
    nativeMode = false;
    notifyCommandsChanged();
  }

  private void enterNativeMode() {
    boolean was = nativeMode;
    nativeMode = true;
    override = null;
    live = false;
    if (!was) {
      Runnable r = onNativeModeStart;
      if (r != null) r.run();
      notifyCommandsChanged();
    }
  }

  private void notifyCommandsChanged() {
    Commands cmds = getAvailableCommands();
    Events ev = new Events(new FlagSet.Builder().add(EVENT_AVAILABLE_COMMANDS_CHANGED).build());
    for (SkipListener l : new ArrayList<>(wrapped.values())) {
      l.listener.onAvailableCommandsChanged(cmds);
      l.listener.onEvents(this, ev);
    }
  }

  @Override
  public void setMediaItems(List<MediaItem> mediaItems, boolean resetPosition) {
    enterNativeMode();
    super.setMediaItems(mediaItems, resetPosition);
  }

  @Override
  public void setMediaItems(List<MediaItem> mediaItems, int startIndex, long startPositionMs) {
    enterNativeMode();
    super.setMediaItems(mediaItems, startIndex, startPositionMs);
  }

  @Override
  public void setMediaItems(List<MediaItem> mediaItems) {
    enterNativeMode();
    super.setMediaItems(mediaItems);
  }

  @Override
  public void setMediaItem(MediaItem mediaItem) {
    enterNativeMode();
    super.setMediaItem(mediaItem);
  }

  @Override
  public void setMediaItem(MediaItem mediaItem, long startPositionMs) {
    enterNativeMode();
    super.setMediaItem(mediaItem, startPositionMs);
  }

  @Override
  public void setMediaItem(MediaItem mediaItem, boolean resetPosition) {
    enterNativeMode();
    super.setMediaItem(mediaItem, resetPosition);
  }

  // ---------- skip availability ----------

  public void setSkipEnabled(boolean next, boolean prev) {
    if (next == nextEnabled && prev == prevEnabled) return;
    nextEnabled = next;
    prevEnabled = prev;
    Commands cmds = getAvailableCommands();
    Events ev = new Events(new FlagSet.Builder().add(EVENT_AVAILABLE_COMMANDS_CHANGED).build());
    for (SkipListener l : new ArrayList<>(wrapped.values())) {
      l.listener.onAvailableCommandsChanged(cmds);
      l.listener.onEvents(this, ev);
    }
  }

  Commands augment(Commands c) {
    if (nativeMode) return c;
    Commands.Builder b = c.buildUpon();
    if (nextEnabled) b.addAll(COMMAND_SEEK_TO_NEXT, COMMAND_SEEK_TO_NEXT_MEDIA_ITEM);
    else b.removeAll(COMMAND_SEEK_TO_NEXT, COMMAND_SEEK_TO_NEXT_MEDIA_ITEM);
    if (prevEnabled) b.addAll(COMMAND_SEEK_TO_PREVIOUS, COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM);
    else b.removeAll(COMMAND_SEEK_TO_PREVIOUS, COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM);
    return b.build();
  }

  @Override
  public Commands getAvailableCommands() {
    return augment(super.getAvailableCommands());
  }

  @Override
  public boolean isCommandAvailable(@Command int command) {
    return getAvailableCommands().contains(command);
  }

  // ---------- metadata ----------

  public void setOverrideMetadata(@Nullable MediaMetadata md, boolean isLive) {
    override = md;
    live = isLive;
    MediaMetadata now = getMediaMetadata();
    Events ev = new Events(new FlagSet.Builder().add(EVENT_MEDIA_METADATA_CHANGED).build());
    for (SkipListener l : new ArrayList<>(wrapped.values())) {
      l.listener.onMediaMetadataChanged(now);
      l.listener.onEvents(this, ev);
    }
  }

  @Override
  public MediaMetadata getMediaMetadata() {
    MediaMetadata base = super.getMediaMetadata();
    if (nativeMode) {
      MediaItem item = getCurrentMediaItem();
      if (item == null) return base;
      MediaMetadata own = item.mediaMetadata;
      boolean isLive = own.extras != null && own.extras.getBoolean(CarLibrary.EXTRA_LIVE, false);
      if (isLive && base.title != null && own.title != null
          && !base.title.toString().trim().isEmpty()
          && !base.title.toString().equals(own.title.toString())) {
        return own.buildUpon().setArtist(base.title).build();
      }
      return own;
    }
    if (override == null) return base;
    if (live && base.title != null && override.title != null
        && !base.title.toString().trim().isEmpty()
        && !base.title.toString().equals(override.title.toString())) {
      // A station's stream tags usually carry the song on air: show it under the station name.
      return override.buildUpon().setArtist(base.title).build();
    }
    return override;
  }

  // ---------- listeners ----------

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

  // ---------- transport commands from outside the app ----------

  @Override
  public void play() {
    if (!dispatch("play")) super.play();
  }

  @Override
  public void pause() {
    if (!dispatch("pause")) super.pause();
  }

  @Override
  public void setPlayWhenReady(boolean playWhenReady) {
    if (!dispatch(playWhenReady ? "play" : "pause")) super.setPlayWhenReady(playWhenReady);
  }

  @Override
  public void prepare() {
    // With the web app present, it decides how to (re)start; otherwise prepare as usual.
    if (remote == null || nativeMode) super.prepare();
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

  private static final class SkipListener implements Listener {

    private final SkipAwarePlayer forwardingPlayer;
    final Listener listener;

    SkipListener(SkipAwarePlayer forwardingPlayer, Listener listener) {
      this.forwardingPlayer = forwardingPlayer;
      this.listener = listener;
    }

    @Override
    public void onEvents(Player player, Events events) {
      // Replace player with forwarding player.
      listener.onEvents(forwardingPlayer, events);
    }

    @Override
    public void onTimelineChanged(Timeline timeline, @TimelineChangeReason int reason) {
      listener.onTimelineChanged(timeline, reason);
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

    @Override
    @SuppressWarnings("deprecation")
    public void onPositionDiscontinuity(@DiscontinuityReason int reason) {
      listener.onPositionDiscontinuity(reason);
    }

    @Override
    public void onPositionDiscontinuity(
        PositionInfo oldPosition, PositionInfo newPosition, @DiscontinuityReason int reason) {
      listener.onPositionDiscontinuity(oldPosition, newPosition, reason);
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

    @SuppressWarnings("deprecation") // Intentionally forwarding deprecated method
    @Override
    public void onCues(List<Cue> cues) {
      listener.onCues(cues);
    }

    @Override
    public void onCues(CueGroup cueGroup) {
      listener.onCues(cueGroup);
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

    @Override
    public boolean equals(@Nullable Object o) {
      if (this == o) {
        return true;
      }
      if (!(o instanceof SkipListener)) {
        return false;
      }
      SkipListener that = (SkipListener) o;
      if (!forwardingPlayer.equals(that.forwardingPlayer)) {
        return false;
      }
      return listener.equals(that.listener);
    }

    @Override
    public int hashCode() {
      int result = forwardingPlayer.hashCode();
      result = 31 * result + listener.hashCode();
      return result;
    }
  }
}
