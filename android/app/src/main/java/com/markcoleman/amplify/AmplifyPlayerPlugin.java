package com.markcoleman.amplify;

import android.content.ComponentName;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.core.content.ContextCompat;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.common.util.concurrent.ListenableFuture;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Bridge between the web app and the native player. The page keeps its whole playback logic
 * (queue, reconnects, podcast resume); a small shim in the page stands in for its <audio>
 * element and turns element calls into these methods, and these events back into element
 * events.
 */
@OptIn(markerClass = UnstableApi.class)
@CapacitorPlugin(name = "AmplifyPlayer")
public class AmplifyPlayerPlugin extends Plugin implements SkipAwarePlayer.Remote {

  private static final long CACHE_LIMIT_BYTES = 600L * 1024 * 1024;

  private final Handler main = new Handler(Looper.getMainLooper());
  private final List<Runnable> pending = new ArrayList<>();
  @Nullable private ListenableFuture<MediaController> controllerFuture;
  private boolean attached;
  @Nullable private String currentId;
  @Nullable private MediaMetadata lastMeta;
  private boolean lastLive;
  private final Player.Listener exoListener = new ExoListener();
  private final Runnable progressTick = this::progressTick;

  // ---------------- lifecycle ----------------

  @Override
  public void load() {
    main.post(this::connect);
  }

  private void connect() {
    SessionToken token =
        new SessionToken(getContext(), new ComponentName(getContext(), PlaybackService.class));
    controllerFuture = new MediaController.Builder(getContext(), token).buildAsync();
    controllerFuture.addListener(this::attach, ContextCompat.getMainExecutor(getContext()));
  }

  private void attach() {
    PlaybackService svc = PlaybackService.instance;
    if (svc == null) {
      main.postDelayed(this::attach, 100);
      return;
    }
    svc.player.setRemote(this);
    svc.exo.addListener(exoListener);
    attached = true;
    List<Runnable> todo = new ArrayList<>(pending);
    pending.clear();
    for (Runnable r : todo) r.run();
  }

  @Override
  protected void handleOnDestroy() {
    main.post(
        () -> {
          PlaybackService svc = PlaybackService.instance;
          if (svc != null) {
            svc.player.setRemote(null);
            svc.exo.removeListener(exoListener);
          }
          attached = false;
          main.removeCallbacks(progressTick);
          if (controllerFuture != null) MediaController.releaseFuture(controllerFuture);
        });
  }

  @Nullable
  private ExoPlayer exo() {
    PlaybackService svc = PlaybackService.instance;
    return svc == null ? null : svc.exo;
  }

  @Nullable
  private SkipAwarePlayer sessionPlayer() {
    PlaybackService svc = PlaybackService.instance;
    return svc == null ? null : svc.player;
  }

  /** Runs on the main thread once the player service is up. */
  private void run(PluginCall call, Runnable r) {
    main.post(
        () -> {
          Runnable guarded =
              () -> {
                try {
                  r.run();
                } catch (Exception e) {
                  call.reject(String.valueOf(e.getMessage()));
                }
              };
          if (attached && exo() != null) guarded.run();
          else pending.add(guarded);
        });
  }

  // ---------------- remote control (notification, headset, car) ----------------

  @Override
  public boolean onRemote(String action) {
    if (!hasListeners("remote")) return false;
    JSObject o = new JSObject();
    o.put("action", action);
    notifyListeners("remote", o);
    return true;
  }

  // ---------------- playback ----------------

  @PluginMethod
  public void load(PluginCall call) {
    String url = call.getString("url");
    String id = call.getString("id", "");
    boolean play = Boolean.TRUE.equals(call.getBoolean("play", false));
    double start = call.getDouble("start", 0.0);
    Double rate = call.getDouble("rate", 1.0);
    Double volume = call.getDouble("volume", 1.0);
    if (url == null || url.isEmpty()) {
      call.reject("No url");
      return;
    }
    run(
        call,
        () -> {
          ExoPlayer p = exo();
          MediaItem.Builder b = new MediaItem.Builder().setUri(url).setMediaId(id);
          String lower = url.toLowerCase();
          if (lower.contains(".m3u8")) b.setMimeType(MimeTypes.APPLICATION_M3U8);
          currentId = id;
          p.setMediaItem(b.build(), (long) (start * 1000));
          p.setPlaybackSpeed(rate.floatValue());
          p.setVolume(volume.floatValue());
          p.prepare();
          p.setPlayWhenReady(play);
          call.resolve();
        });
  }

  @PluginMethod
  public void play(PluginCall call) {
    run(
        call,
        () -> {
          ExoPlayer p = exo();
          if (p.getMediaItemCount() == 0) {
            call.reject("Nothing loaded");
            return;
          }
          if (p.getPlaybackState() == Player.STATE_IDLE) p.prepare();
          if (p.getPlaybackState() == Player.STATE_ENDED) p.seekToDefaultPosition();
          p.setPlayWhenReady(true);
          call.resolve();
        });
  }

  @PluginMethod
  public void pause(PluginCall call) {
    run(
        call,
        () -> {
          exo().setPlayWhenReady(false);
          call.resolve();
        });
  }

  @PluginMethod
  public void stop(PluginCall call) {
    run(
        call,
        () -> {
          ExoPlayer p = exo();
          currentId = null;
          p.stop();
          p.clearMediaItems();
          SkipAwarePlayer sp = sessionPlayer();
          if (sp != null) sp.setOverrideMetadata(null, false);
          lastMeta = null;
          call.resolve();
        });
  }

  @PluginMethod
  public void seek(PluginCall call) {
    double pos = call.getDouble("position", 0.0);
    run(
        call,
        () -> {
          exo().seekTo((long) (pos * 1000));
          call.resolve();
        });
  }

  @PluginMethod
  public void setVolume(PluginCall call) {
    Double v = call.getDouble("volume", 1.0);
    run(
        call,
        () -> {
          exo().setVolume(v.floatValue());
          call.resolve();
        });
  }

  @PluginMethod
  public void setRate(PluginCall call) {
    Double r = call.getDouble("rate", 1.0);
    run(
        call,
        () -> {
          exo().setPlaybackSpeed(Math.max(0.25f, r.floatValue()));
          call.resolve();
        });
  }

  @PluginMethod
  public void setSkip(PluginCall call) {
    boolean next = Boolean.TRUE.equals(call.getBoolean("next", false));
    boolean prev = Boolean.TRUE.equals(call.getBoolean("prev", false));
    run(
        call,
        () -> {
          sessionPlayer().setSkipEnabled(next, prev);
          call.resolve();
        });
  }

  @PluginMethod
  public void setMetadata(PluginCall call) {
    MediaMetadata.Builder b =
        new MediaMetadata.Builder()
            .setTitle(call.getString("title", ""))
            .setArtist(call.getString("artist", ""))
            .setAlbumTitle(call.getString("album", ""))
            .setIsPlayable(true);
    boolean live = Boolean.TRUE.equals(call.getBoolean("live", false));
    String artUrl = call.getString("artUrl");
    String artData = call.getString("artData");
    if (artData != null && !artData.isEmpty()) {
      byte[] jpeg = shrinkArt(artData);
      if (jpeg != null) b.setArtworkData(jpeg, MediaMetadata.PICTURE_TYPE_FRONT_COVER);
    } else if (artUrl != null && artUrl.startsWith("http")) {
      b.setArtworkUri(Uri.parse(artUrl));
    }
    MediaMetadata md = b.build();
    run(
        call,
        () -> {
          lastMeta = md;
          lastLive = live;
          sessionPlayer().setOverrideMetadata(md, live);
          call.resolve();
        });
  }

  /** Decodes a base64 image, scales it to at most 512px and re-encodes it as a small JPEG. */
  @Nullable
  private static byte[] shrinkArt(String b64) {
    try {
      byte[] raw = Base64.decode(b64, Base64.DEFAULT);
      Bitmap bmp = BitmapFactory.decodeByteArray(raw, 0, raw.length);
      if (bmp == null) return null;
      int max = Math.max(bmp.getWidth(), bmp.getHeight());
      if (max > 512) {
        float s = 512f / max;
        bmp =
            Bitmap.createScaledBitmap(
                bmp,
                Math.max(1, Math.round(bmp.getWidth() * s)),
                Math.max(1, Math.round(bmp.getHeight() * s)),
                true);
      }
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      bmp.compress(Bitmap.CompressFormat.JPEG, 85, out);
      return out.toByteArray();
    } catch (Exception e) {
      return null;
    }
  }

  // ---------------- local file cache (library songs live in the page's IndexedDB) ----------------

  private File cacheDir() {
    File d = new File(getContext().getCacheDir(), "audio");
    if (!d.exists()) d.mkdirs();
    return d;
  }

  private static String safeKey(String k) {
    return k == null ? "" : k.replaceAll("[^A-Za-z0-9_-]", "");
  }

  @PluginMethod
  public void cacheCheck(PluginCall call) {
    String key = safeKey(call.getString("key"));
    JSObject o = new JSObject();
    File f = new File(cacheDir(), key + ".bin");
    if (!key.isEmpty() && f.exists() && f.length() > 0) {
      f.setLastModified(System.currentTimeMillis());
      o.put("url", Uri.fromFile(f).toString());
    }
    call.resolve(o);
  }

  @PluginMethod
  public void cacheWrite(PluginCall call) {
    String key = safeKey(call.getString("key"));
    String data = call.getString("data", "");
    boolean first = Boolean.TRUE.equals(call.getBoolean("first", false));
    if (key.isEmpty()) {
      call.reject("Bad key");
      return;
    }
    try (FileOutputStream out = new FileOutputStream(new File(cacheDir(), key + ".part"), !first)) {
      out.write(Base64.decode(data, Base64.DEFAULT));
      call.resolve();
    } catch (Exception e) {
      call.reject("Write failed: " + e.getMessage());
    }
  }

  @PluginMethod
  public void cacheFinish(PluginCall call) {
    String key = safeKey(call.getString("key"));
    File part = new File(cacheDir(), key + ".part");
    File done = new File(cacheDir(), key + ".bin");
    if (key.isEmpty() || !part.exists()) {
      call.reject("Nothing written");
      return;
    }
    done.delete();
    if (!part.renameTo(done)) {
      call.reject("Rename failed");
      return;
    }
    trimCache(done);
    JSObject o = new JSObject();
    o.put("url", Uri.fromFile(done).toString());
    call.resolve(o);
  }

  private void trimCache(File keep) {
    File[] files = cacheDir().listFiles();
    if (files == null) return;
    Arrays.sort(files, (a, b) -> Long.compare(a.lastModified(), b.lastModified()));
    long total = 0;
    for (File f : files) total += f.length();
    for (File f : files) {
      if (total <= CACHE_LIMIT_BYTES) break;
      if (f.equals(keep)) continue;
      total -= f.length();
      f.delete();
    }
  }

  // ---------------- events to the page ----------------

  private JSObject snapshot() {
    ExoPlayer p = exo();
    JSObject o = new JSObject();
    o.put("id", currentId);
    if (p == null) return o;
    long dur = p.getDuration();
    o.put("position", Math.max(0, p.getCurrentPosition()) / 1000.0);
    o.put("duration", dur == C.TIME_UNSET ? -1 : dur / 1000.0);
    o.put("live", p.isCurrentMediaItemLive() || (dur == C.TIME_UNSET && !p.isCurrentMediaItemSeekable()));
    o.put("isPlaying", p.isPlaying());
    o.put("playWhenReady", p.getPlayWhenReady());
    String st;
    switch (p.getPlaybackState()) {
      case Player.STATE_BUFFERING:
        st = "buffering";
        break;
      case Player.STATE_READY:
        st = "ready";
        break;
      case Player.STATE_ENDED:
        st = "ended";
        break;
      default:
        st = "idle";
    }
    o.put("state", st);
    return o;
  }

  private void emitState(boolean external) {
    if (currentId == null) return;
    JSObject o = snapshot();
    o.put("external", external);
    notifyListeners("state", o);
  }

  private void progressTick() {
    ExoPlayer p = exo();
    if (p == null || !p.isPlaying() || currentId == null) return;
    notifyListeners("progress", snapshot());
    main.postDelayed(progressTick, 500);
  }

  private final class ExoListener implements Player.Listener {
    @Override
    public void onPlaybackStateChanged(int state) {
      emitState(false);
    }

    @Override
    public void onIsPlayingChanged(boolean isPlaying) {
      emitState(false);
      main.removeCallbacks(progressTick);
      if (isPlaying) main.postDelayed(progressTick, 500);
    }

    @Override
    public void onPlayWhenReadyChanged(boolean playWhenReady, int reason) {
      // Anything other than a request (ours or the app's) is the system acting on its own:
      // a call taking audio focus, headphones unplugged.
      emitState(reason != Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST
          && reason != Player.PLAY_WHEN_READY_CHANGE_REASON_END_OF_MEDIA_ITEM);
    }

    @Override
    public void onPositionDiscontinuity(
        Player.PositionInfo oldPosition, Player.PositionInfo newPosition, int reason) {
      if (currentId != null) notifyListeners("progress", snapshot());
    }

    @Override
    public void onPlayerError(PlaybackException error) {
      if (currentId == null) return;
      JSObject o = new JSObject();
      o.put("id", currentId);
      o.put("code", error.errorCode);
      o.put("name", error.getErrorCodeName());
      o.put("message", String.valueOf(error.getMessage()));
      notifyListeners("error", o);
    }
  }
}
