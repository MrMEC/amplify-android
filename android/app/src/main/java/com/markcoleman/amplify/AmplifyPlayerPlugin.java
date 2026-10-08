package com.markcoleman.amplify;

import android.app.Activity;
import android.app.PictureInPictureParams;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.database.Cursor;
import android.media.MediaCodecList;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.DocumentsContract;
import android.util.Base64;
import android.util.Rational;
import android.view.Window;
import android.view.WindowManager;
import androidx.activity.result.ActivityResult;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.markcoleman.amplify.vlc.VlcPlayerActivity;
import androidx.media3.common.C;
import androidx.media3.common.Format;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.TrackSelectionOverride;
import androidx.media3.common.TrackSelectionParameters;
import androidx.media3.common.Tracks;
import androidx.media3.common.VideoSize;
import androidx.media3.common.text.Cue;
import androidx.media3.common.text.CueGroup;
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
import java.nio.charset.StandardCharsets;
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
          "aif", "jpg", "jpeg", "png", "webp", "gif",
          // Music videos beside the songs (build 152): listed on their artist's page.
          "m4v", "avi", "mkv", "mov", "wmv", "mpg", "mpeg", "3gp", "flv", "webm");
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
    // A video of your own can bring subtitle files from beside it, and says whether subtitles
    // should show.
    final JSArray subs = pluginCall.getArray("subs");
    final Boolean textOff = pluginCall.getBoolean("textOff", null);
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
            List<MediaItem.SubtitleConfiguration> side = subtitleConfigs(subs);
            if (!side.isEmpty()) mediaId.setSubtitleConfigurations(side);
            // Each item starts from its own tracks: no track picked by hand for the last one.
            TrackSelectionParameters.Builder tp =
                exoPlayerExo
                    .getTrackSelectionParameters()
                    .buildUpon()
                    .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                    .clearOverridesOfType(C.TRACK_TYPE_AUDIO);
            if (textOff != null) tp.setTrackTypeDisabled(C.TRACK_TYPE_TEXT, textOff);
            exoPlayerExo.setTrackSelectionParameters(tp.build());
            if (this.video != null) this.video.setCues(null);
            this.currentId = string2;
            // A new item: whether it has a picture is for its own tracks to say.
            this.hasVideo = false;
            this.videoW = this.videoH = 0;
            this.videoRatio = 1f;
            if (this.video != null) this.video.hide();
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
        Intent.FLAG_GRANT_READ_URI_PERMISSION
            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
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
      // Write too, when given, so Info & Tags can save edited tags into the songs.
      int keep =
          Intent.FLAG_GRANT_READ_URI_PERMISSION
              | (data.getFlags() & Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
      cr.takePersistableUriPermission(tree, keep);
    } catch (Exception ignored) {
      try {
        cr.takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION);
      } catch (Exception ignored2) {
        // A one-off grant is still enough to import from.
      }
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

  // ---- Movies and TV shows on the phone (see VideoLibrary) ----
  @PluginMethod
  public void pickVideoFolder(PluginCall call) {
    Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
    i.addFlags(
        Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
    startActivityForResult(call, i, "onVideoFolderPicked");
  }

  @ActivityCallback
  private void onVideoFolderPicked(PluginCall call, ActivityResult result) {
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
      // Kept, so the videos still play (and the folder can be scanned again) after a restart.
      cr.takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION);
    } catch (Exception ignored) {
    }
    new Thread(
            () -> {
              try {
                call.resolve(VideoLibrary.walk(cr, tree));
              } catch (Exception e) {
                call.reject("Could not read that folder: " + e.getMessage());
              }
            })
        .start();
  }

  /** Lists a folder picked earlier again (new or removed videos). */
  @PluginMethod
  public void rescanVideoFolder(PluginCall call) {
    String t = call.getString("treeUri");
    if (t == null || t.isEmpty()) {
      call.reject("No folder");
      return;
    }
    ContentResolver cr = getContext().getContentResolver();
    new Thread(
            () -> {
              try {
                call.resolve(VideoLibrary.walk(cr, Uri.parse(t)));
              } catch (Exception e) {
                call.reject("That folder can't be read any more: " + e.getMessage());
              }
            })
        .start();
  }

  /** A folder taken out of the library gives its read permission back. */
  @PluginMethod
  public void forgetVideoFolder(PluginCall call) {
    String t = call.getString("treeUri");
    if (t != null && !t.isEmpty()) {
      try {
        getContext()
            .getContentResolver()
            .releasePersistableUriPermission(Uri.parse(t), Intent.FLAG_GRANT_READ_URI_PERMISSION);
      } catch (Exception ignored) {
      }
    }
    call.resolve();
  }

  /** Length, picture size and a poster still for one video (off the main thread). */
  @PluginMethod
  public void videoInfo(PluginCall call) {
    String u = call.getString("uri");
    boolean thumb = !Boolean.FALSE.equals(call.getBoolean("thumb", true));
    if (u == null || u.isEmpty()) {
      call.reject("No uri");
      return;
    }
    Context ctx = getContext();
    new Thread(() -> call.resolve(VideoLibrary.info(ctx, u, thumb))).start();
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
          if (!m.startsWith("audio/")
              && !m.startsWith("image/")
              && !m.startsWith("video/")
              && !FOLDER_EXTS.contains(ext)) {
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
    o.put("treeUri", tree.toString());
    o.put("files", files);
    o.put("truncated", truncated);
    return o;
  }

  // ---- VLC, for videos the phone's own decoders can't play (build 153) ----

  /**
   * Whether the phone's own player can show this video: the container opens and every audio and
   * video track has a decoder on this phone. {ok, why}. AVI, WMV and FLV don't open here (the
   * phone's extractor doesn't read them), so they come back not ok and go to VLC.
   */
  @PluginMethod
  public void videoDecodable(PluginCall call) {
    String u = call.getString("uri");
    if (u == null || u.isEmpty()) {
      call.reject("No uri");
      return;
    }
    Context ctx = getContext();
    new Thread(
            () -> {
              JSObject o = new JSObject();
              MediaExtractor ex = new MediaExtractor();
              try {
                ex.setDataSource(ctx, Uri.parse(u), null);
                MediaCodecList codecs = new MediaCodecList(MediaCodecList.REGULAR_CODECS);
                boolean video = false;
                StringBuilder missing = new StringBuilder();
                for (int i = 0; i < ex.getTrackCount(); i++) {
                  MediaFormat f = ex.getTrackFormat(i);
                  String mime = f.getString(MediaFormat.KEY_MIME);
                  if (mime == null || !(mime.startsWith("video/") || mime.startsWith("audio/"))) continue;
                  if (mime.startsWith("video/")) video = true;
                  String dec = null;
                  try {
                    dec = codecs.findDecoderForFormat(f);
                  } catch (Exception ignored) {
                    // An odd format description: treated as no decoder.
                  }
                  if (dec == null) missing.append(missing.length() > 0 ? ", " : "").append(mime);
                }
                o.put("ok", video && missing.length() == 0);
                o.put("why", !video ? "no video track found" : missing.length() > 0 ? "no decoder for " + missing : "");
              } catch (Exception e) {
                o.put("ok", false);
                o.put("why", "the phone can't open this kind of file");
              } finally {
                try {
                  ex.release();
                } catch (Exception ignored) {
                }
              }
              call.resolve(o);
            })
        .start();
  }

  /**
   * Opens a video in the VLC player screen. {uri, title, startMs, hw} -> when it closes:
   * {position, duration (ms), ended, error}. The app's own player is paused first.
   */
  @PluginMethod
  public void playWithVlc(PluginCall call) {
    String u = call.getString("uri");
    if (u == null || u.isEmpty()) {
      call.reject("No uri");
      return;
    }
    main.post(
        () -> {
          try {
            ExoPlayer p = exo();
            if (p != null) p.setPlayWhenReady(false);
          } catch (Exception ignored) {
          }
        });
    Double startD = call.getDouble("startMs", 0.0);
    long start = startD == null ? 0L : (long) startD.doubleValue();
    Intent i =
        VlcPlayerActivity.intent(
            getContext(),
            Uri.parse(u),
            call.getString("title", ""),
            start,
            !Boolean.FALSE.equals(call.getBoolean("hw", true)));
    startActivityForResult(call, i, "onVlcDone");
  }

  @ActivityCallback
  private void onVlcDone(PluginCall call, ActivityResult result) {
    if (call == null) return;
    Intent d = result.getData();
    JSObject o = new JSObject();
    o.put("position", d == null ? 0L : d.getLongExtra(VlcPlayerActivity.RESULT_POSITION, 0L));
    o.put("duration", d == null ? 0L : d.getLongExtra(VlcPlayerActivity.RESULT_DURATION, 0L));
    o.put("ended", d != null && d.getBooleanExtra(VlcPlayerActivity.RESULT_ENDED, false));
    String err = d == null ? null : d.getStringExtra(VlcPlayerActivity.RESULT_ERROR);
    if (err != null) o.put("error", err);
    call.resolve(o);
  }

  /** Lists a music folder picked earlier again, to pick up songs added or removed since. */
  @PluginMethod
  public void rescanMusicFolder(PluginCall call) {
    String t = call.getString("treeUri");
    if (t == null || t.isEmpty()) {
      call.reject("No folder");
      return;
    }
    ContentResolver cr = getContext().getContentResolver();
    new Thread(
            () -> {
              try {
                call.resolve(walkTree(cr, Uri.parse(t)));
              } catch (Exception e) {
                call.reject("That folder can't be read any more: " + e.getMessage());
              }
            })
        .start();
  }

  // ---- Info & Tags: saving a song's edited tags into its file (see TagWriter) ----

  /** Same folder: the same storage provider and the same folder within it. */
  private static boolean sameTree(Uri a, Uri b) {
    try {
      return a.getAuthority() != null
          && a.getAuthority().equals(b.getAuthority())
          && DocumentsContract.getTreeDocumentId(a).equals(DocumentsContract.getTreeDocumentId(b));
    } catch (Exception e) {
      return false;
    }
  }

  /** Whether the folder a song came from was granted with permission to change its files. */
  private boolean canWrite(Uri doc) {
    for (android.content.UriPermission p :
        getContext().getContentResolver().getPersistedUriPermissions()) {
      if (p.isWritePermission() && sameTree(p.getUri(), doc)) return true;
    }
    return false;
  }

  /** {uri, data (base64 new tag), replace (bytes of the old tag), crc, size} -> {size, lastModified}. */
  @PluginMethod
  public void writeFileHead(PluginCall call) {
    final String u = call.getString("uri");
    final String b64 = call.getString("data");
    final Integer replace = call.getInt("replace");
    final long crc = call.getData().optLong("crc", -1);
    final long expect = call.getData().optLong("size", -1);
    if (u == null || b64 == null || replace == null || crc < 0) {
      call.reject("Missing details");
      return;
    }
    final Uri doc = Uri.parse(u);
    if (!canWrite(doc)) {
      call.reject("Amplify can't change files in this folder yet", "NO_WRITE");
      return;
    }
    final ContentResolver cr = getContext().getContentResolver();
    final File tmpDir = getContext().getCacheDir();
    new Thread(
            () -> {
              try {
                byte[] head = Base64.decode(b64, Base64.DEFAULT);
                TagWriter.replaceHead(
                    new TagWriter.Io() {
                      @Override
                      public long size() {
                        try (android.os.ParcelFileDescriptor pfd = cr.openFileDescriptor(doc, "r")) {
                          return pfd == null ? -1 : pfd.getStatSize();
                        } catch (Exception e) {
                          return -1;
                        }
                      }

                      @Override
                      public java.io.InputStream read() throws java.io.IOException {
                        java.io.InputStream in = cr.openInputStream(doc);
                        if (in == null) throw new java.io.IOException("The file can't be opened");
                        return in;
                      }

                      @Override
                      public java.io.OutputStream rewrite() throws java.io.IOException {
                        java.io.OutputStream out = cr.openOutputStream(doc, "wt");
                        if (out == null) throw new java.io.IOException("The file can't be written");
                        return out;
                      }

                      @Override
                      public void writeInPlace(byte[] data) throws java.io.IOException {
                        try (android.os.ParcelFileDescriptor pfd = cr.openFileDescriptor(doc, "rw")) {
                          if (pfd == null) throw new java.io.IOException("The file can't be written");
                          try (FileOutputStream fos = new FileOutputStream(pfd.getFileDescriptor())) {
                            java.nio.channels.FileChannel ch = fos.getChannel();
                            java.nio.ByteBuffer buf = java.nio.ByteBuffer.wrap(data);
                            long pos = 0;
                            while (buf.hasRemaining()) pos += ch.write(buf, pos);
                            fos.getFD().sync();
                          }
                        }
                      }
                    },
                    head,
                    replace,
                    crc,
                    expect,
                    tmpDir);
                JSObject o = new JSObject();
                String[] cols = {
                  DocumentsContract.Document.COLUMN_SIZE, DocumentsContract.Document.COLUMN_LAST_MODIFIED
                };
                try (Cursor c = cr.query(doc, cols, null, null, null)) {
                  if (c != null && c.moveToFirst()) {
                    o.put("size", c.isNull(0) ? 0 : c.getLong(0));
                    o.put("lastModified", c.isNull(1) ? 0 : c.getLong(1));
                  }
                } catch (Exception ignored) {
                }
                call.resolve(o);
              } catch (TagWriter.Changed e) {
                call.reject(e.getMessage(), "CHANGED");
              } catch (SecurityException e) {
                call.reject("Amplify can't change files in this folder yet", "NO_WRITE");
              } catch (Exception e) {
                call.reject(e.getMessage() == null ? "Write failed" : e.getMessage());
              }
            })
        .start();
  }

  /** Asks again for a music folder, this time with permission to change its files. */
  @PluginMethod
  public void grantFolderWrite(PluginCall call) {
    Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
    i.addFlags(
        Intent.FLAG_GRANT_READ_URI_PERMISSION
            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
    String t = call.getString("treeUri");
    if (t != null && Build.VERSION.SDK_INT >= 26) {
      try {
        Uri tree = Uri.parse(t);
        i.putExtra(
            DocumentsContract.EXTRA_INITIAL_URI,
            DocumentsContract.buildDocumentUriUsingTree(
                tree, DocumentsContract.getTreeDocumentId(tree)));
      } catch (Exception ignored) {
      }
    }
    startActivityForResult(call, i, "onFolderWriteGranted");
  }

  @ActivityCallback
  private void onFolderWriteGranted(PluginCall call, ActivityResult result) {
    if (call == null) return;
    Intent data = result.getData();
    JSObject o = new JSObject();
    if (result.getResultCode() != Activity.RESULT_OK || data == null || data.getData() == null) {
      o.put("cancelled", true);
      call.resolve(o);
      return;
    }
    Uri picked = data.getData();
    int flags =
        data.getFlags()
            & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
    try {
      getContext().getContentResolver().takePersistableUriPermission(picked, flags);
    } catch (Exception e) {
      call.reject("Permission wasn't kept: " + e.getMessage());
      return;
    }
    String want = call.getString("treeUri");
    o.put("treeUri", picked.toString());
    o.put("matches", want == null || sameTree(Uri.parse(want), picked));
    o.put("canWrite", (flags & Intent.FLAG_GRANT_WRITE_URI_PERMISSION) != 0);
    call.resolve(o);
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
    // Build 151: when it was sent, and whether the phone will carry on with its queue by
    // itself if the page doesn't answer (so a page that was asleep doesn't skip a song).
    jSObject.put("at", System.currentTimeMillis());
    if (playbackState == 4) {
      jSObject.put("takeover", willTakeOverPageQueue());
    }
    return jSObject;
  }

  // ---- the phone carries on by itself (build 151) ----
  // A song the page started ends while the page is asleep (screen off, or in the car with the
  // phone in a pocket): nothing would start the next one until the app was opened again. So
  // if the page hasn't loaded anything two seconds after a song ends, the player takes the
  // queue the page last handed it (the one the car shows) and plays on from it, as if the car
  // had started it. The page follows it when it wakes, and ignores the late "ended".
  private static final long PAGE_TAKEOVER_MS = 2000L;
  private String pageEndedFor;
  private final Runnable pageTakeover = this::takeOverPageQueue;

  private boolean willTakeOverPageQueue() {
    SkipAwarePlayer sp = sessionPlayer();
    if (sp == null || sp.isNativeMode()) return false;
    List<MediaItem> q = sp.pageQueueNow();
    return q != null && !q.isEmpty();
  }

  private void schedulePageTakeover() {
    main.removeCallbacks(pageTakeover);
    ExoPlayer p = exo();
    if (p == null || !willTakeOverPageQueue()) return;
    MediaItem cur = p.getCurrentMediaItem();
    pageEndedFor = cur == null ? null : cur.mediaId;
    main.postDelayed(pageTakeover, PAGE_TAKEOVER_MS);
  }

  private void takeOverPageQueue() {
    SkipAwarePlayer sp = sessionPlayer();
    ExoPlayer p = exo();
    if (sp == null || p == null || sp.isNativeMode() || p.getPlaybackState() != Player.STATE_ENDED) return;
    MediaItem cur = p.getCurrentMediaItem();
    if (cur == null || pageEndedFor == null || !pageEndedFor.equals(cur.mediaId)) return;
    List<MediaItem> q = sp.pageQueueNow();
    if (q == null || q.isEmpty()) return;
    try {
      sp.setMediaItems(new ArrayList<>(q), 0, 0L);
      sp.prepare();
      sp.play();
    } catch (RuntimeException e) {
      // Left as it was: the page picks up when it wakes.
    }
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

  // ---------------- network ----------------

  /**
   * Fetches a text file (a channel playlist or directory) for the page. A page can only read other
   * sites that allow it (CORS), and most IPTV playlist hosts don't, so the Video section's "Add
   * Channels" goes through here: {url, max} -> {text, url (after redirects)}. Follows up to five
   * redirects, including http <-> https, which plain Java does not.
   */
  @PluginMethod
  public void fetchText(PluginCall call) {
    String url = call.getString("url");
    int max = call.getInt("max", 48 * 1024 * 1024);
    if (url == null || !(url.startsWith("http://") || url.startsWith("https://"))) {
      call.reject("Not a web address");
      return;
    }
    new Thread(
            () -> {
              java.net.HttpURLConnection c = null;
              try {
                String current = url;
                for (int hop = 0; hop < 6; hop++) {
                  c = (java.net.HttpURLConnection) new java.net.URL(current).openConnection();
                  c.setConnectTimeout(10000);
                  c.setReadTimeout(20000);
                  c.setInstanceFollowRedirects(false);
                  c.setRequestProperty("User-Agent", "Amplify/1.0 (Android)");
                  int code = c.getResponseCode();
                  String loc = c.getHeaderField("Location");
                  if (code >= 300 && code < 400 && loc != null) {
                    current = new java.net.URL(new java.net.URL(current), loc).toString();
                    c.disconnect();
                    c = null;
                    continue;
                  }
                  if (code != 200) throw new Exception("HTTP " + code);
                  StringBuilder sb = new StringBuilder();
                  try (java.io.Reader r =
                      new java.io.InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8)) {
                    char[] buf = new char[16384];
                    int n;
                    while ((n = r.read(buf)) > 0) {
                      sb.append(buf, 0, n);
                      if (sb.length() > max) throw new Exception("File is too large");
                    }
                  }
                  JSObject o = new JSObject();
                  o.put("text", sb.toString());
                  o.put("url", current);
                  call.resolve(o);
                  return;
                }
                throw new Exception("Too many redirects");
              } catch (Exception e) {
                call.reject(String.valueOf(e.getMessage()));
              } finally {
                if (c != null) c.disconnect();
              }
            },
            "amplify-fetch")
        .start();
  }

  // ---------------- files ----------------

  /** Export: writes {name, text, mime} into Downloads and says where it went (build 48). */
  @PluginMethod
  public void saveToDownloads(PluginCall call) {
    String name = call.getString("name", "amplify-backup.json");
    try {
      DownloadsSaver.Result r =
          DownloadsSaver.save(
              getContext(),
              name,
              call.getString("text", "").getBytes(StandardCharsets.UTF_8),
              call.getString("mime", "application/json"));
      JSObject o = new JSObject();
      o.put("name", r.name);
      o.put("folder", r.folder);
      o.put("uri", r.uri);
      o.put("bytes", r.bytes);
      call.resolve(o);
    } catch (Exception e) {
      call.reject("Could not save " + name + ": " + e.getMessage());
    }
  }

  /**
   * Podcast video, which plays in the page (build 45): full screen hides the system bars (and holds
   * landscape when asked), and the screen stays on while a video shows.
   */
  // ---- Picture-in-picture ----
  // The page says when leaving the app should shrink the video into a floating window: while a
  // video is playing (a channel, a stream with a picture, or a podcast episode's video). Android
  // 12+ does it by itself on the home gesture (auto-enter); older versions are asked from
  // MainActivity.onUserLeaveHint. The page is told when the window opens and closes ("pip"), and
  // shows the picture full screen while it is open.
  private volatile boolean pipAllowed = false;

  private int pipW = 16, pipH = 9;

  boolean pipAllowed() {
    return pipAllowed;
  }

  @Nullable
  PictureInPictureParams pipParams() {
    if (Build.VERSION.SDK_INT < 26) return null;
    // Android refuses shapes wider than 2.39:1 or taller than 1:2.39.
    float r = (float) pipW / Math.max(1, pipH);
    int w = pipW, h = Math.max(1, pipH);
    if (r > 2.39f) {
      w = 239;
      h = 100;
    } else if (r < 1 / 2.39f) {
      w = 100;
      h = 239;
    }
    PictureInPictureParams.Builder b =
        new PictureInPictureParams.Builder().setAspectRatio(new Rational(w, h));
    if (Build.VERSION.SDK_INT >= 31) {
      b.setAutoEnterEnabled(pipAllowed);
      b.setSeamlessResizeEnabled(true);
    }
    return b.build();
  }

  @PluginMethod
  public void setPip(PluginCall call) {
    pipAllowed = Boolean.TRUE.equals(call.getBoolean("allowed", false));
    Integer w = call.getInt("width"), h = call.getInt("height");
    if (w != null && h != null && w > 0 && h > 0) {
      pipW = w;
      pipH = h;
    }
    Activity activity = getActivity();
    if (activity == null || Build.VERSION.SDK_INT < 26) {
      call.resolve();
      return;
    }
    activity.runOnUiThread(
        () -> {
          try {
            PictureInPictureParams params = pipParams();
            if (params != null) activity.setPictureInPictureParams(params);
          } catch (Exception ignored) {
            // A phone that has picture-in-picture turned off for the app refuses; nothing to do.
          }
          call.resolve();
        });
  }

  void onPipChanged(boolean active) {
    JSObject o = new JSObject();
    o.put("active", active);
    notifyListeners("pip", o);
  }

  @PluginMethod
  public void setVideoUi(PluginCall call) {
    boolean fullscreen = Boolean.TRUE.equals(call.getBoolean("fullscreen", false));
    boolean landscape = Boolean.TRUE.equals(call.getBoolean("landscape", false));
    boolean awake = Boolean.TRUE.equals(call.getBoolean("awake", false));
    Activity activity = getActivity();
    if (activity == null) {
      call.resolve();
      return;
    }
    activity.runOnUiThread(
        () -> {
          Window window = activity.getWindow();
          WindowInsetsControllerCompat bars =
              WindowCompat.getInsetsController(window, window.getDecorView());
          if (fullscreen) {
            bars.setSystemBarsBehavior(
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            bars.hide(WindowInsetsCompat.Type.systemBars());
          } else {
            bars.show(WindowInsetsCompat.Type.systemBars());
          }
          if (awake || fullscreen) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
          else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
          activity.setRequestedOrientation(
              fullscreen && landscape
                  ? ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                  : ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
          call.resolve();
        });
  }

  // ---------------- video ----------------

  private JSObject videoJson() {
    JSObject o = new JSObject();
    o.put("id", currentId);
    o.put("hasVideo", hasVideo);
    o.put("width", Math.round(videoW * videoRatio));
    o.put("height", videoH);
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
            video =
                new VideoOverlay(
                    getActivity(),
                    getBridge().getWebView(),
                    () -> {
                      JSObject o = new JSObject();
                      o.put("id", currentId);
                      notifyListeners("videotap", o);
                    });
            video.setVideoSize(videoW, videoH, videoRatio);
          }
          if (show && hasVideo) video.show(exo(), x, y, w, h);
          else video.hide();
          // What was drawn, for Diagnostics (build 156).
          JSObject r = video.state();
          r.put("hasVideo", hasVideo);
          call.resolve(r);
        });
  }

  private static List<MediaItem.SubtitleConfiguration> subtitleConfigs(@Nullable JSArray subs) {
    List<MediaItem.SubtitleConfiguration> out = new ArrayList<>();
    if (subs == null) return out;
    for (int i = 0; i < subs.length(); i++) {
      try {
        org.json.JSONObject o = subs.getJSONObject(i);
        String uri = o.optString("uri", "");
        String name = o.optString("name", "");
        if (uri.isEmpty()) continue;
        String lower = name.toLowerCase(Locale.ROOT);
        String mime =
            lower.endsWith(".vtt")
                ? MimeTypes.TEXT_VTT
                : (lower.endsWith(".ass") || lower.endsWith(".ssa"))
                    ? MimeTypes.TEXT_SSA
                    : MimeTypes.APPLICATION_SUBRIP;
        MediaItem.SubtitleConfiguration.Builder b =
            new MediaItem.SubtitleConfiguration.Builder(Uri.parse(uri))
                .setMimeType(mime)
                .setId("side" + i)
                .setLabel(o.optString("label", "Subtitles"))
                .setSelectionFlags(i == 0 ? C.SELECTION_FLAG_DEFAULT : 0);
        String lang = o.optString("language", "");
        if (!lang.isEmpty()) b.setLanguage(lang);
        out.add(b.build());
      } catch (Exception ignored) {
        // A subtitle entry that can't be read is left out; the video still plays.
      }
    }
    return out;
  }

  private static String trackLabel(Format f, int n, boolean audio) {
    String lang = f.language;
    String name = null;
    if (lang != null && !lang.isEmpty() && !"und".equals(lang)) {
      try {
        name = Locale.forLanguageTag(lang).getDisplayLanguage();
      } catch (Exception ignored) {
      }
      if (name == null || name.isEmpty()) name = lang;
    }
    String label = f.label;
    if (label != null && !label.isEmpty()) {
      if (name == null || label.toLowerCase(Locale.ROOT).contains(name.toLowerCase(Locale.ROOT))) {
        name = label;
      } else {
        name = name + " (" + label + ")";
      }
    }
    if (name == null || name.isEmpty()) name = (audio ? "Audio " : "Subtitles ") + n;
    if (audio && f.channelCount >= 6) name += " 5.1";
    return name;
  }

  /** The audio and subtitle tracks of what's playing, and which are on. */
  @PluginMethod
  public void videoTracks(PluginCall call) {
    run(
        call,
        () -> {
          ExoPlayer p = exo();
          JSArray audio = new JSArray(), text = new JSArray();
          int na = 0, nt = 0;
          java.util.List<Tracks.Group> groups = p.getCurrentTracks().getGroups();
          for (int gi = 0; gi < groups.size(); gi++) {
            Tracks.Group g = groups.get(gi);
            int type = g.getType();
            if (type != C.TRACK_TYPE_AUDIO && type != C.TRACK_TYPE_TEXT) continue;
            for (int ti = 0; ti < g.length; ti++) {
              if (!g.isTrackSupported(ti)) continue;
              boolean isAudio = type == C.TRACK_TYPE_AUDIO;
              JSObject t = new JSObject();
              t.put("group", gi);
              t.put("track", ti);
              t.put("label", trackLabel(g.getTrackFormat(ti), isAudio ? ++na : ++nt, isAudio));
              t.put("selected", g.isTrackSelected(ti));
              (isAudio ? audio : text).put(t);
            }
          }
          JSObject o = new JSObject();
          o.put("audio", audio);
          o.put("text", text);
          o.put(
              "textOff",
              p.getTrackSelectionParameters().disabledTrackTypes.contains(C.TRACK_TYPE_TEXT));
          call.resolve(o);
        });
  }

  /** Picks an audio or subtitle track ({type, group, track}), or turns subtitles off. */
  @PluginMethod
  public void selectVideoTrack(PluginCall call) {
    String type = call.getString("type", "text");
    boolean off = Boolean.TRUE.equals(call.getBoolean("off", false));
    int group = call.getInt("group", -1);
    int track = call.getInt("track", 0);
    run(
        call,
        () -> {
          ExoPlayer p = exo();
          int t = "audio".equals(type) ? C.TRACK_TYPE_AUDIO : C.TRACK_TYPE_TEXT;
          TrackSelectionParameters.Builder b = p.getTrackSelectionParameters().buildUpon();
          if (off) {
            b.setTrackTypeDisabled(t, true);
          } else {
            java.util.List<Tracks.Group> groups = p.getCurrentTracks().getGroups();
            if (group < 0 || group >= groups.size()) {
              call.reject("No such track");
              return;
            }
            b.setTrackTypeDisabled(t, false)
                .setOverrideForType(
                    new TrackSelectionOverride(groups.get(group).getMediaTrackGroup(), track));
          }
          p.setTrackSelectionParameters(b.build());
          if (off && t == C.TRACK_TYPE_TEXT && video != null) video.setCues(null);
          call.resolve();
        });
  }

  private void onCues(CueGroup cues) {
    if (video == null) return;
    StringBuilder sb = new StringBuilder();
    for (Cue c : cues.cues) {
      if (c.text == null) continue;
      if (sb.length() > 0) sb.append('\n');
      sb.append(c.text);
    }
    video.setCues(sb.length() == 0 ? null : sb.toString());
  }

  private String icyNameFor;

  /** A stream's own name (the icy-name header), so a pasted link can be titled properly. */
  private void emitStreamName(Tracks tracks) {
    if (currentId == null || currentId.equals(icyNameFor)) return;
    for (Tracks.Group g : tracks.getGroups()) {
      for (int i = 0; i < g.length; i++) {
        Format f = g.getTrackFormat(i);
        if (f.metadata == null) continue;
        for (int j = 0; j < f.metadata.length(); j++) {
          androidx.media3.common.Metadata.Entry e = f.metadata.get(j);
          if (e instanceof androidx.media3.extractor.metadata.icy.IcyHeaders) {
            String name = ((androidx.media3.extractor.metadata.icy.IcyHeaders) e).name;
            if (name != null && !name.trim().isEmpty()) {
              icyNameFor = currentId;
              JSObject o = new JSObject();
              o.put("id", currentId);
              o.put("name", name.trim());
              notifyListeners("streamname", o);
              return;
            }
          }
        }
      }
    }
  }

  private void onTracks(Tracks tracks) {
    emitStreamName(tracks);
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

    @Override
    public void onCues(CueGroup cueGroup) {
      AmplifyPlayerPlugin.this.onCues(cueGroup);
    }

    private ExoListener() {}

    @Override
    public void onPlaybackStateChanged(int state) {
      if (state == Player.STATE_ENDED) schedulePageTakeover();
      else main.removeCallbacks(pageTakeover);
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
