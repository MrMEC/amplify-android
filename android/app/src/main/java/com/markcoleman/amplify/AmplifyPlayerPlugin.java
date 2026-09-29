package com.markcoleman.amplify;

import android.app.Activity;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.provider.DocumentsContract;
import android.util.Base64;
import androidx.activity.result.ActivityResult;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.core.content.ContextCompat;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.Tracks;
import androidx.media3.common.VideoSize;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.common.util.concurrent.ListenableFuture;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;

/**
 * Bridge between the web app and the native player. The page keeps its whole playback logic (queue,
 * reconnects, podcast resume); a small shim in the page stands in for its <audio> element and turns
 * element calls into these methods, and these events back into element events.
 */
@OptIn(markerClass = UnstableApi.class)
@CapacitorPlugin(name = "AmplifyPlayer")
public class AmplifyPlayerPlugin extends Plugin implements SkipAwarePlayer.Remote {
  private static final long CACHE_LIMIT_BYTES = 629145600;
  private static final List<String> FOLDER_EXTS =
      Arrays.asList(
          "mp3", "m4a", "m4b", "mp4", "aac", "flac", "ogg", "oga", "opus", "wav", "wma", "aiff",
          "aif", "jpg", "jpeg", "png", "webp", "gif");
  private static final int FOLDER_MAX_DEPTH = 12;
  private static final int FOLDER_MAX_FILES = 20000;
  private boolean attached;
  private int carSeq;
  private ListenableFuture<MediaController> controllerFuture;
  private String currentId;
  private boolean lastLive;
  private MediaMetadata lastMeta;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final List<Runnable> pending = new ArrayList();
  private final Player.Listener exoListener = new ExoListener();
  // Video: whether what is loaded carries a picture, its size, and the view that shows it.
  private boolean hasVideo;
  private int videoW, videoH;
  private float videoRatio = 1f;
  private VideoOverlay video;
  private final Runnable progressTick =
      () -> {
        this.progressTick();
      };

  @Override // com.getcapacitor.Plugin
  public void load() {
    this.main.post(
        () -> {
          this.connect();
        });
  }

  public void connect() {
    ListenableFuture<MediaController> listenableFutureBuildAsync =
        new MediaController.Builder(
                getContext(),
                new SessionToken(
                    getContext(),
                    new ComponentName(getContext(), (Class<?>) PlaybackService.class)))
            .buildAsync();
    this.controllerFuture = listenableFutureBuildAsync;
    listenableFutureBuildAsync.addListener(
        this::attach, ContextCompat.getMainExecutor(getContext()));
  }

  public void attach() {
    PlaybackService playbackService = PlaybackService.instance;
    if (playbackService == null) {
      this.main.postDelayed(this::attach, 100L);
      return;
    }
    playbackService.player.setRemote(this);
    playbackService.player.setOnNativeModeStart(
        () -> {
          this.onCarTookOver();
        });
    playbackService.player.setOnAirListener(
        (StreamTitle streamTitle) -> {
          this.emitOnAir(streamTitle);
        });
    playbackService.exo.addListener(this.exoListener);
    this.attached = true;
    ArrayList arrayList = new ArrayList(this.pending);
    this.pending.clear();
    Iterator it = arrayList.iterator();
    while (it.hasNext()) {
      ((Runnable) it.next()).run();
    }
  }

  @Override // com.getcapacitor.Plugin
  protected void handleOnDestroy() {
    this.main.post(
        () -> {
          PlaybackService playbackService = PlaybackService.instance;
          if (playbackService != null) {
            playbackService.player.setRemote(null);
            playbackService.player.setOnNativeModeStart(null);
            playbackService.player.setOnAirListener(null);
            playbackService.exo.removeListener(this.exoListener);
          }
          this.attached = false;
          this.main.removeCallbacks(this.progressTick);
          if (this.video != null) {
            this.video.release();
            this.video = null;
          }
          ListenableFuture<MediaController> listenableFuture = this.controllerFuture;
          if (listenableFuture != null) {
            MediaController.releaseFuture(listenableFuture);
          }
        });
  }

  private ExoPlayer exo() {
    PlaybackService playbackService = PlaybackService.instance;
    if (playbackService == null) {
      return null;
    }
    return playbackService.exo;
  }

  public SkipAwarePlayer sessionPlayer() {
    PlaybackService playbackService = PlaybackService.instance;
    if (playbackService == null) {
      return null;
    }
    return playbackService.player;
  }

  private void run(final PluginCall pluginCall, final Runnable runnable) {
    this.main.post(
        () -> {
          Runnable runnable2 =
              () -> {
                try {
                  runnable.run();
                } catch (Exception e) {
                  pluginCall.reject(String.valueOf(e.getMessage()));
                }
              };
          if (!this.attached || exo() == null) {
            this.pending.add(runnable2);
          } else {
            runnable2.run();
          }
        });
  }

  @Override
  public boolean onRemote(String action) {
    if (!hasListeners("remote")) return false;
    JSObject o = new JSObject();
    o.put("action", action);
    notifyListeners("remote", o);
    return true;
  }

  @PluginMethod
  public void load(final PluginCall pluginCall) {
    final String string = pluginCall.getString("url");
    final String string2 = pluginCall.getString("id", "");
    final boolean zEquals = Boolean.TRUE.equals(pluginCall.getBoolean("play", false));
    final double dDoubleValue = pluginCall.getDouble("start", Double.valueOf(0.0d)).doubleValue();
    Double dValueOf = Double.valueOf(1.0d);
    final Double d = pluginCall.getDouble("rate", dValueOf);
    final Double d2 = pluginCall.getDouble("volume", dValueOf);
    if (string == null || string.isEmpty()) {
      pluginCall.reject("No url");
    } else {
      run(
          pluginCall,
          () -> {
            ExoPlayer exoPlayerExo = exo();
            SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
            if (skipAwarePlayerSessionPlayer != null) {
              skipAwarePlayerSessionPlayer.exitNativeMode();
              skipAwarePlayerSessionPlayer.clearOnAir();
            }
            MediaItem.Builder mediaId = new MediaItem.Builder().setUri(string).setMediaId(string2);
            if (string.toLowerCase().contains(".m3u8")) {
              mediaId.setMimeType("application/x-mpegURL");
            }
            this.currentId = string2;
            exoPlayerExo.setMediaItem(mediaId.build(), (long) (dDoubleValue * 1000.0d));
            exoPlayerExo.setPlaybackSpeed(d.floatValue());
            exoPlayerExo.setVolume(d2.floatValue());
            exoPlayerExo.prepare();
            exoPlayerExo.setPlayWhenReady(zEquals);
            pluginCall.resolve();
          });
    }
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
  public void stop(final PluginCall pluginCall) {
    run(
        pluginCall,
        () -> {
          ExoPlayer exoPlayerExo = exo();
          this.currentId = null;
          exoPlayerExo.stop();
          exoPlayerExo.clearMediaItems();
          SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
          if (skipAwarePlayerSessionPlayer != null) {
            skipAwarePlayerSessionPlayer.setOverrideMetadata(null, false);
            skipAwarePlayerSessionPlayer.setSkipEnabled(false, false, false);
            skipAwarePlayerSessionPlayer.setPageQueue(null, null);
          }
          this.lastMeta = null;
          pluginCall.resolve();
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
  public void setSkip(final PluginCall pluginCall) {
    final boolean zEquals = Boolean.TRUE.equals(pluginCall.getBoolean("next", false));
    final boolean zEquals2 = Boolean.TRUE.equals(pluginCall.getBoolean("prev", false));
    final boolean zEquals3 = Boolean.TRUE.equals(pluginCall.getBoolean("podcast", false));
    run(
        pluginCall,
        () -> {
          sessionPlayer().setSkipEnabled(zEquals, zEquals2, zEquals3);
          pluginCall.resolve();
        });
  }

  private JSObject onAirJson(StreamTitle streamTitle) {
    String str;
    JSObject jSObject = new JSObject();
    jSObject.put("id", this.currentId);
    String str2 = "";
    jSObject.put("title", streamTitle == null ? "" : streamTitle.title);
    if (streamTitle == null) {
      str = "";
    } else {
      str = streamTitle.artist;
    }
    jSObject.put("artist", str);
    if (streamTitle != null) {
      str2 = streamTitle.raw;
    }
    jSObject.put("raw", str2);
    return jSObject;
  }

  public void emitOnAir(StreamTitle streamTitle) {
    if (this.currentId == null) {
      return;
    }
    notifyListeners("onair", onAirJson(streamTitle));
  }

  @PluginMethod
  public void onAirNow(final PluginCall pluginCall) {
    run(
        pluginCall,
        () -> {
          SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
          pluginCall.resolve(
              onAirJson(
                  skipAwarePlayerSessionPlayer == null
                      ? null
                      : skipAwarePlayerSessionPlayer.getOnAir()));
        });
  }

  @PluginMethod
  public void setMetadata(final PluginCall pluginCall) {
    MediaMetadata.Builder isPlayable =
        new MediaMetadata.Builder()
            .setTitle(pluginCall.getString("title", ""))
            .setArtist(pluginCall.getString("artist", ""))
            .setAlbumTitle(pluginCall.getString("album", ""))
            .setIsPlayable(true);
    final boolean zEquals = Boolean.TRUE.equals(pluginCall.getBoolean("live", false));
    String string = pluginCall.getString("artUrl");
    String string2 = pluginCall.getString("artData");
    if (string2 != null && !string2.isEmpty()) {
      byte[] bArrShrinkArt = shrinkArt(string2);
      if (bArrShrinkArt != null) {
        isPlayable.setArtworkData(bArrShrinkArt, 3);
      }
    } else if (string != null && string.startsWith("http")) {
      isPlayable.setArtworkUri(Uri.parse(string));
    }
    final MediaMetadata mediaMetadataBuild = isPlayable.build();
    run(
        pluginCall,
        () -> {
          String str;
          this.lastMeta = mediaMetadataBuild;
          this.lastLive = zEquals;
          sessionPlayer().setOverrideMetadata(mediaMetadataBuild, zEquals);
          ExoPlayer exoPlayerExo = exo();
          SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
          MediaItem currentMediaItem =
              exoPlayerExo == null ? null : exoPlayerExo.getCurrentMediaItem();
          if (currentMediaItem != null
              && skipAwarePlayerSessionPlayer != null
              && !skipAwarePlayerSessionPlayer.isNativeMode()
              && (str = this.currentId) != null
              && str.equals(currentMediaItem.mediaId)) {
            try {
              exoPlayerExo.replaceMediaItem(
                  exoPlayerExo.getCurrentMediaItemIndex(),
                  currentMediaItem.buildUpon().setMediaMetadata(mediaMetadataBuild).build());
            } catch (Exception unused) {
            }
          }
          pluginCall.resolve();
        });
  }

  private static byte[] shrinkArt(String str) {
    try {
      byte[] bArrDecode = Base64.decode(str, 0);
      Bitmap bitmapDecodeByteArray =
          BitmapFactory.decodeByteArray(bArrDecode, 0, bArrDecode.length);
      if (bitmapDecodeByteArray == null) {
        return null;
      }
      int iMax = Math.max(bitmapDecodeByteArray.getWidth(), bitmapDecodeByteArray.getHeight());
      if (iMax > 512) {
        float f = 512.0f / iMax;
        bitmapDecodeByteArray =
            Bitmap.createScaledBitmap(
                bitmapDecodeByteArray,
                Math.max(1, Math.round(bitmapDecodeByteArray.getWidth() * f)),
                Math.max(1, Math.round(bitmapDecodeByteArray.getHeight() * f)),
                true);
      }
      ByteArrayOutputStream byteArrayOutputStream = new ByteArrayOutputStream();
      bitmapDecodeByteArray.compress(Bitmap.CompressFormat.JPEG, 85, byteArrayOutputStream);
      return byteArrayOutputStream.toByteArray();
    } catch (Exception unused) {
      return null;
    }
  }

  private File cacheDir() {
    File file = new File(getContext().getCacheDir(), "audio");
    if (!file.exists()) {
      file.mkdirs();
    }
    return file;
  }

  private static String safeKey(String str) {
    return str == null ? "" : str.replaceAll("[^A-Za-z0-9_-]", "");
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

  private void trimCache(File file) {
    File[] fileArrListFiles = cacheDir().listFiles();
    if (fileArrListFiles == null) {
      return;
    }
    Arrays.sort(
        fileArrListFiles,
        (Object obj, Object obj2) -> {
          return Long.compare(((File) obj).lastModified(), ((File) obj2).lastModified());
        });
    long length = 0;
    for (File file2 : fileArrListFiles) {
      length += file2.length();
    }
    for (File file3 : fileArrListFiles) {
      if (length <= 629145600) {
        return;
      }
      if (!file3.equals(file)) {
        length -= file3.length();
        file3.delete();
      }
    }
  }

  @PluginMethod
  public void pickMusicFolder(PluginCall call) {
    Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
    i.addFlags(
        Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
    startActivityForResult(call, i, "onMusicFolderPicked");
  }

  @ActivityCallback
  private void onMusicFolderPicked(PluginCall call, ActivityResult result) {
    if (call == null) return;
    Intent data = result.getData();
    if (result.getResultCode() != Activity.RESULT_OK || data == null || data.getData() == null) {
      JSObject o = new JSObject();
      o.put("cancelled", true);
      call.resolve(o);
      return;
    }
    Uri tree = data.getData();
    ContentResolver cr = getContext().getContentResolver();
    try {
      cr.takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION);
    } catch (Exception ignored) {
      // A one-off grant is still enough to import from.
    }
    new Thread(
            () -> {
              try {
                call.resolve(walkTree(cr, tree));
              } catch (Exception e) {
                call.reject("Could not read that folder: " + e.getMessage());
              }
            })
        .start();
  }

  private static JSObject walkTree(ContentResolver cr, Uri tree) {
    String rootId = DocumentsContract.getTreeDocumentId(tree);
    String rootName = displayName(cr, DocumentsContract.buildDocumentUriUsingTree(tree, rootId));
    if (rootName == null || rootName.isEmpty()) {
      int c = rootId.lastIndexOf(':');
      rootName = c >= 0 ? rootId.substring(c + 1) : rootId;
      int s = rootName.lastIndexOf('/');
      if (s >= 0) rootName = rootName.substring(s + 1);
      if (rootName.isEmpty()) rootName = "Music";
    }
    JSArray files = new JSArray();
    int count = 0;
    boolean truncated = false;
    String[] cols = {
      DocumentsContract.Document.COLUMN_DOCUMENT_ID,
      DocumentsContract.Document.COLUMN_DISPLAY_NAME,
      DocumentsContract.Document.COLUMN_MIME_TYPE,
      DocumentsContract.Document.COLUMN_SIZE,
      DocumentsContract.Document.COLUMN_LAST_MODIFIED
    };
    ArrayDeque<String[]> queue = new ArrayDeque<>(); // {docId, relDir, depth}
    queue.add(new String[] {rootId, rootName, "0"});
    while (!queue.isEmpty() && !truncated) {
      String[] dir = queue.poll();
      int depth = Integer.parseInt(dir[2]);
      Uri kids = DocumentsContract.buildChildDocumentsUriUsingTree(tree, dir[0]);
      try (Cursor c = cr.query(kids, cols, null, null, null)) {
        if (c == null) continue;
        while (c.moveToNext()) {
          String id = c.getString(0);
          String name = c.getString(1);
          String mime = c.getString(2);
          if (id == null || name == null || name.startsWith(".")) continue;
          if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
            if (depth < FOLDER_MAX_DEPTH) {
              queue.add(new String[] {id, dir[1] + "/" + name, String.valueOf(depth + 1)});
            }
            continue;
          }
          String m = mime == null ? "" : mime;
          int dot = name.lastIndexOf('.');
          String ext = dot >= 0 ? name.substring(dot + 1).toLowerCase(Locale.ROOT) : "";
          if (!m.startsWith("audio/") && !m.startsWith("image/") && !FOLDER_EXTS.contains(ext)) {
            continue;
          }
          JSObject f = new JSObject();
          f.put("uri", DocumentsContract.buildDocumentUriUsingTree(tree, id).toString());
          f.put("name", name);
          f.put("relPath", dir[1] + "/" + name);
          f.put("type", m);
          f.put("size", c.isNull(3) ? 0 : c.getLong(3));
          f.put("lastModified", c.isNull(4) ? 0 : c.getLong(4));
          files.put(f);
          if (++count >= FOLDER_MAX_FILES) {
            truncated = true;
            break;
          }
        }
      } catch (Exception ignored) {
        // An unreadable subfolder is skipped rather than failing the whole import.
      }
    }
    JSObject o = new JSObject();
    o.put("folder", rootName);
    o.put("files", files);
    o.put("truncated", truncated);
    return o;
  }

  @Nullable
  private static String displayName(ContentResolver cr, Uri doc) {
    try (Cursor c =
        cr.query(
            doc, new String[] {DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
      if (c != null && c.moveToFirst()) return c.getString(0);
    } catch (Exception ignored) {
    }
    return null;
  }

  public void onCarTookOver() {
    if (this.currentId == null) {
      return;
    }
    JSObject jSObjectSnapshot = snapshot();
    jSObjectSnapshot.put("isPlaying", false);
    jSObjectSnapshot.put("playWhenReady", false);
    jSObjectSnapshot.put("external", true);
    jSObjectSnapshot.put("car", true);
    notifyListeners("state", jSObjectSnapshot);
    this.currentId = null;
    this.lastMeta = null;
    this.main.removeCallbacks(this.progressTick);
  }

  public void announceCar() {
    MediaItem currentMediaItem;
    String string;
    SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
    ExoPlayer exoPlayerExo = exo();
    if (skipAwarePlayerSessionPlayer == null
        || exoPlayerExo == null
        || !skipAwarePlayerSessionPlayer.isNativeMode()
        || skipAwarePlayerSessionPlayer.isResumePending()
        || (currentMediaItem = exoPlayerExo.getCurrentMediaItem()) == null
        || currentMediaItem.mediaMetadata.extras == null
        || (string = currentMediaItem.mediaMetadata.extras.getString("amplify.item")) == null) {
      return;
    }
    StringBuilder sb = new StringBuilder("car:");
    int i = this.carSeq + 1;
    this.carSeq = i;
    this.currentId = sb.append(i).toString();
    this.lastMeta = null;
    notifyListeners("car", carSnapshot(string));
    this.main.removeCallbacks(this.progressTick);
    if (exoPlayerExo.isPlaying()) {
      this.main.postDelayed(this.progressTick, 500L);
    }
  }

  private JSObject carSnapshot(String str) {
    ExoPlayer exoPlayerExo = exo();
    JSObject jSObjectSnapshot = snapshot();
    try {
      jSObjectSnapshot.put("item", (Object) new JSObject(str));
    } catch (Exception unused) {
      jSObjectSnapshot.put("item", (Object) new JSObject());
    }
    jSObjectSnapshot.put("hasNext", exoPlayerExo != null && exoPlayerExo.hasNextMediaItem());
    jSObjectSnapshot.put("hasPrev", exoPlayerExo != null && exoPlayerExo.hasPreviousMediaItem());
    return jSObjectSnapshot;
  }

  @PluginMethod
  public void carNowPlaying(final PluginCall pluginCall) {
    run(
        pluginCall,
        () -> {
          SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
          ExoPlayer exoPlayerExo = exo();
          String string = null;
          MediaItem currentMediaItem =
              exoPlayerExo == null ? null : exoPlayerExo.getCurrentMediaItem();
          if (currentMediaItem != null && currentMediaItem.mediaMetadata.extras != null) {
            string = currentMediaItem.mediaMetadata.extras.getString("amplify.item");
          }
          if (skipAwarePlayerSessionPlayer == null
              || !skipAwarePlayerSessionPlayer.isNativeMode()
              || string == null
              || skipAwarePlayerSessionPlayer.isResumePending()) {
            pluginCall.resolve(new JSObject());
            return;
          }
          String str = this.currentId;
          if (str == null || !str.startsWith("car:")) {
            StringBuilder sb = new StringBuilder("car:");
            int i = this.carSeq + 1;
            this.carSeq = i;
            this.currentId = sb.append(i).toString();
          }
          pluginCall.resolve(carSnapshot(string));
          this.main.removeCallbacks(this.progressTick);
          if (exoPlayerExo.isPlaying()) {
            this.main.postDelayed(this.progressTick, 500L);
          }
        });
  }

  @PluginMethod
  public void carSkip(final PluginCall pluginCall) {
    final boolean zEquals = Boolean.TRUE.equals(pluginCall.getBoolean("next", true));
    run(
        pluginCall,
        () -> {
          ExoPlayer exoPlayerExo = exo();
          SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
          if (skipAwarePlayerSessionPlayer == null
              || !skipAwarePlayerSessionPlayer.isNativeMode()) {
            pluginCall.reject("Not playing from the car");
            return;
          }
          if (zEquals) {
            if (exoPlayerExo.hasNextMediaItem()) {
              exoPlayerExo.seekToNextMediaItem();
            }
          } else if (exoPlayerExo.getCurrentPosition() > 3000
              || !exoPlayerExo.hasPreviousMediaItem()) {
            exoPlayerExo.seekTo(0L);
          } else {
            exoPlayerExo.seekToPreviousMediaItem();
          }
          pluginCall.resolve();
        });
  }

  @PluginMethod
  public void setCarCatalog(final PluginCall pluginCall) {
    final String string = pluginCall.getString("json");
    if (string == null || string.isEmpty()) {
      pluginCall.reject("No catalog");
    } else {
      new Thread(
              () -> {
                try {
                  CarLibrary.saveCatalog(getContext(), string);
                  this.main.post(
                      () -> {
                        PlaybackService playbackService = PlaybackService.instance;
                        if (playbackService != null) {
                          playbackService.onSnapshotChanged(true, false);
                        }
                      });
                  pluginCall.resolve();
                } catch (Exception e) {
                  pluginCall.reject(String.valueOf(e.getMessage()));
                }
              })
          .start();
    }
  }

  @PluginMethod
  public void setCarLibrary(final PluginCall pluginCall) {
    final String string = pluginCall.getString("json");
    if (string == null || string.isEmpty()) {
      pluginCall.reject("No library");
    } else {
      new Thread(
              () -> {
                try {
                  CarLibrary.saveLibrary(getContext(), string);
                  this.main.post(
                      () -> {
                        PlaybackService playbackService = PlaybackService.instance;
                        if (playbackService != null) {
                          playbackService.onSnapshotChanged(false, true);
                        }
                      });
                  pluginCall.resolve();
                } catch (Exception e) {
                  pluginCall.reject(String.valueOf(e.getMessage()));
                }
              })
          .start();
    }
  }

  @PluginMethod
  public void setCarQueue(final PluginCall pluginCall) {
    final String string = pluginCall.getString("forId", "");
    final String string2 = pluginCall.getString("json", "[]");
    run(
        pluginCall,
        () -> {
          PlaybackService playbackService = PlaybackService.instance;
          SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
          if (playbackService == null || skipAwarePlayerSessionPlayer == null) {
            pluginCall.resolve();
          } else {
            playbackService.onPageQueue(
                string,
                string2,
                pluginCall.getString("current"),
                Boolean.TRUE.equals(pluginCall.getBoolean("follow", false)));
            pluginCall.resolve();
          }
        });
  }

  @PluginMethod
  public void carDebug(final PluginCall pluginCall) {
    run(
        pluginCall,
        () -> {
          PlaybackService playbackService = PlaybackService.instance;
          JSObject jSObject = new JSObject();
          jSObject.put(
              "text",
              playbackService == null ? "service not running" : playbackService.debugText());
          pluginCall.resolve(jSObject);
        });
  }

  @PluginMethod
  public void setCarResume(final PluginCall pluginCall) {
    final String string = pluginCall.getString("json");
    if (string == null || string.isEmpty()) {
      pluginCall.reject("No item");
    } else {
      run(
          pluginCall,
          () -> {
            String str2;
            PlaybackService playbackService = PlaybackService.instance;
            SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
            boolean z = false;
            boolean z2 =
                skipAwarePlayerSessionPlayer != null
                    && skipAwarePlayerSessionPlayer.isNativeMode()
                    && skipAwarePlayerSessionPlayer.isResumePending();
            if (playbackService != null
                && (skipAwarePlayerSessionPlayer == null
                    || !skipAwarePlayerSessionPlayer.isNativeMode()
                    || z2)) {
              ExoPlayer exoPlayerExo = exo();
              MediaItem currentMediaItem =
                  exoPlayerExo == null ? null : exoPlayerExo.getCurrentMediaItem();
              if (!z2
                  && currentMediaItem != null
                  && (str2 = this.currentId) != null
                  && str2.equals(currentMediaItem.mediaId)) {
                z = true;
              }
              playbackService.rememberPageItem(
                  string,
                  null,
                  z ? exoPlayerExo.getCurrentPosition() : -1L,
                  z ? currentMediaItem.mediaId : null);
              if (z2) {
                playbackService.restoreLastPlayed(true);
              }
            }
            pluginCall.resolve();
          });
    }
  }

  @PluginMethod
  public void setCarLibraryPart(PluginCall pluginCall) {
    String str = "";
    String string = pluginCall.getString("data", "");
    boolean zEquals = Boolean.TRUE.equals(pluginCall.getBoolean("first", false));
    boolean zEquals2 = Boolean.TRUE.equals(pluginCall.getBoolean("last", false));
    try {
      Context context = getContext();
      if (string != null) {
        str = string;
      }
      CarLibrary.appendLibraryPart(context, str, zEquals, zEquals2);
      if (zEquals2) {
        this.main.post(
            () -> {
              PlaybackService playbackService = PlaybackService.instance;
              if (playbackService != null) {
                playbackService.onSnapshotChanged(false, true);
              }
            });
      }
      pluginCall.resolve();
    } catch (Exception e) {
      pluginCall.reject(String.valueOf(e.getMessage()));
    }
  }

  @PluginMethod
  public void carArtKeys(PluginCall pluginCall) {
    JSArray jSArray = new JSArray();
    File[] fileArrListFiles = ArtProvider.localArtDir(getContext()).listFiles();
    if (fileArrListFiles != null) {
      for (File file : fileArrListFiles) {
        String name = file.getName();
        if (name.endsWith(".jpg") && file.length() > 0) {
          jSArray.put(name.substring(0, name.length() - 4));
        }
      }
    }
    JSObject jSObject = new JSObject();
    jSObject.put("keys", (Object) jSArray);
    pluginCall.resolve(jSObject);
  }

  /** Album art for the car, uploaded by the page as base64 JPEG (see carArtKeys). */
  @PluginMethod
  public void putCarArt(PluginCall call) {
    String key = ArtProvider.safeKey(call.getString("key"));
    String data = call.getString("data", "");
    if (key.isEmpty() || data == null || data.isEmpty()) {
      call.reject("Bad art");
      return;
    }
    File dest = ArtProvider.localArt(getContext(), key);
    File part = new File(dest.getPath() + ".part");
    try {
      try (FileOutputStream out = new FileOutputStream(part)) {
        out.write(Base64.decode(data, Base64.DEFAULT));
      }
      if (!part.renameTo(dest)) {
        part.delete();
        call.reject("Rename failed");
      } else {
        call.resolve();
      }
    } catch (Exception e) {
      part.delete();
      call.reject("Write failed: " + e.getMessage());
    }
  }

  @PluginMethod
  public void takeCarHistory(PluginCall pluginCall) {
    JSObject jSObject = new JSObject();
    try {
      jSObject.put("history", (Object) new JSArray(CarHistory.takeAll(getContext()).toString()));
    } catch (Exception unused) {
      jSObject.put("history", (Object) new JSArray());
    }
    pluginCall.resolve(jSObject);
  }

  @PluginMethod
  public void takeCarProgress(PluginCall call) {
    JSObject o = new JSObject();
    try {
      o.put("progress", new JSObject(CarProgress.takeAll(getContext()).toString()));
    } catch (Exception e) {
      o.put("progress", new JSObject());
    }
    call.resolve(o);
  }

  public JSObject snapshot() {
    String str;
    ExoPlayer exoPlayerExo = exo();
    JSObject jSObject = new JSObject();
    jSObject.put("id", this.currentId);
    if (exoPlayerExo == null) {
      return jSObject;
    }
    SkipAwarePlayer skipAwarePlayerSessionPlayer = sessionPlayer();
    StreamTitle onAir =
        skipAwarePlayerSessionPlayer == null ? null : skipAwarePlayerSessionPlayer.getOnAir();
    String str2 = "";
    jSObject.put("onAirTitle", onAir == null ? "" : onAir.title);
    if (onAir != null) {
      str2 = onAir.artist;
    }
    jSObject.put("onAirArtist", str2);
    long duration = exoPlayerExo.getDuration();
    jSObject.put("position", Math.max(0L, exoPlayerExo.getCurrentPosition()) / 1000.0d);
    jSObject.put("duration", duration == -9223372036854775807L ? -1.0d : duration / 1000.0d);
    jSObject.put(
        "live",
        exoPlayerExo.isCurrentMediaItemLive()
            || (duration == -9223372036854775807L && !exoPlayerExo.isCurrentMediaItemSeekable()));
    jSObject.put("isPlaying", exoPlayerExo.isPlaying());
    jSObject.put("playWhenReady", exoPlayerExo.getPlayWhenReady());
    int playbackState = exoPlayerExo.getPlaybackState();
    if (playbackState == 2) {
      str = "buffering";
    } else if (playbackState == 3) {
      str = "ready";
    } else if (playbackState == 4) {
      str = "ended";
    } else {
      str = "idle";
    }
    jSObject.put("state", str);
    return jSObject;
  }

  public void emitState(boolean z) {
    if (this.currentId == null) {
      return;
    }
    JSObject jSObjectSnapshot = snapshot();
    jSObjectSnapshot.put("external", z);
    notifyListeners("state", jSObjectSnapshot);
  }

  public void progressTick() {
    ExoPlayer exoPlayerExo = exo();
    if (exoPlayerExo == null || !exoPlayerExo.isPlaying() || this.currentId == null) {
      return;
    }
    notifyListeners("progress", snapshot());
    this.main.postDelayed(this.progressTick, 500L);
  }

  // ---------------- video ----------------

  private JSObject videoJson() {
    JSObject o = new JSObject();
    o.put("id", currentId);
    o.put("hasVideo", hasVideo);
    o.put("width", Math.round(videoW * videoRatio));
    o.put("height", videoH);
    o.put("fullscreen", video != null && video.isFullscreen());
    return o;
  }

  private void emitVideo() {
    if (currentId != null) notifyListeners("video", videoJson());
  }

  /**
   * Whether the current stream has a picture (the page asks on start; changes arrive as events).
   */
  @PluginMethod
  public void videoState(PluginCall call) {
    main.post(() -> call.resolve(videoJson()));
  }

  /**
   * Where the page's video box is: {show, x, y, width, height} in CSS pixels relative to the
   * WebView. show=false whenever there is nothing to show or the box is covered.
   */
  @PluginMethod
  public void setVideoView(PluginCall call) {
    boolean show = Boolean.TRUE.equals(call.getBoolean("show", false));
    float x = call.getFloat("x", 0f), y = call.getFloat("y", 0f);
    float w = call.getFloat("width", 0f), h = call.getFloat("height", 0f);
    main.post(
        () -> {
          if (getActivity() == null || getBridge() == null) {
            call.resolve();
            return;
          }
          if (video == null) {
            if (!show) {
              call.resolve();
              return;
            }
            video = new VideoOverlay(getActivity(), getBridge().getWebView(), fs -> emitVideo());
            video.setVideoSize(videoW, videoH, videoRatio);
          }
          if (show && hasVideo) video.show(exo(), x, y, w, h);
          else video.hide();
          call.resolve();
        });
  }

  private void onTracks(Tracks tracks) {
    boolean v = tracks.containsType(C.TRACK_TYPE_VIDEO);
    if (v == hasVideo) return;
    hasVideo = v;
    if (!v) {
      videoW = videoH = 0;
      videoRatio = 1f;
      if (video != null) video.hide();
    }
    emitVideo();
  }

  private void onVideoSize(VideoSize size) {
    if (size.width == videoW && size.height == videoH && size.pixelWidthHeightRatio == videoRatio) {
      return;
    }
    videoW = size.width;
    videoH = size.height;
    videoRatio = size.pixelWidthHeightRatio > 0 ? size.pixelWidthHeightRatio : 1f;
    if (video != null) video.setVideoSize(videoW, videoH, videoRatio);
    if (hasVideo) emitVideo();
  }

  private final class ExoListener implements Player.Listener {
    @Override
    public void onTracksChanged(Tracks tracks) {
      onTracks(tracks);
    }

    @Override
    public void onVideoSizeChanged(VideoSize videoSize) {
      onVideoSize(videoSize);
    }

    private ExoListener() {}

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

    @Override // androidx.media3.common.Player.Listener
    public void onPlayWhenReadyChanged(boolean z, int i) {
      SkipAwarePlayer skipAwarePlayerSessionPlayer = AmplifyPlayerPlugin.this.sessionPlayer();
      if (z
          && skipAwarePlayerSessionPlayer != null
          && skipAwarePlayerSessionPlayer.isNativeMode()
          && (AmplifyPlayerPlugin.this.currentId == null
              || !AmplifyPlayerPlugin.this.currentId.startsWith("car:"))) {
        AmplifyPlayerPlugin.this.announceCar();
      }
      AmplifyPlayerPlugin.this.emitState((i == 1 || i == 5) ? false : true);
    }

    @Override // androidx.media3.common.Player.Listener
    public void onMediaItemTransition(MediaItem mediaItem, int i) {
      AmplifyPlayerPlugin.this.announceCar();
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
