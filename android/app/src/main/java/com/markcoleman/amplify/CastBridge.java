package com.markcoleman.amplify;

import android.app.Activity;
import android.content.Context;
import android.net.Uri;
import androidx.annotation.Nullable;
import androidx.mediarouter.app.MediaRouteChooserDialog;
import androidx.mediarouter.app.MediaRouteControllerDialog;
import androidx.mediarouter.media.MediaRouteSelector;
import androidx.mediarouter.media.MediaRouter;
import com.google.android.gms.cast.MediaInfo;
import com.google.android.gms.cast.MediaLoadRequestData;
import com.google.android.gms.cast.MediaMetadata;
import com.google.android.gms.cast.MediaSeekOptions;
import com.google.android.gms.cast.MediaStatus;
import com.google.android.gms.cast.framework.CastContext;
import com.google.android.gms.cast.framework.CastSession;
import com.google.android.gms.cast.framework.CastState;
import com.google.android.gms.cast.framework.CastStateListener;
import com.google.android.gms.cast.framework.SessionManager;
import com.google.android.gms.cast.framework.SessionManagerListener;
import com.google.android.gms.cast.framework.media.RemoteMediaClient;
import com.google.android.gms.common.images.WebImage;
import java.util.Locale;

/**
 * Build 194: Google Cast for streams (radio, podcasts, TV channels, Plex). The phone hands the
 * stream's address to the Chromecast's own player (Google's Default Media Receiver) and drives it
 * from there; nothing plays on the phone meanwhile. Songs and videos kept on the phone stay on
 * the phone (a Chromecast can't reach them).
 *
 * <p>All calls are on the main thread.
 */
final class CastBridge {
  interface Listener {
    /** Devices found / a session started or ended. */
    void onCastChanged();
    /** A session just started (or was picked up again). */
    void onCastSessionStarted();
    /** The session ended; what the Chromecast was doing at the end. */
    void onCastSessionEnded(long positionMs, boolean wasPlaying);
    /** The Chromecast's player changed state or position. */
    void onCastStatus();
  }

  private final Context app;
  private final Listener listener;
  @Nullable private CastContext ctx;
  @Nullable private MediaRouter router;
  @Nullable private MediaRouteSelector selector;
  private boolean discovering;
  private int castState = CastState.NO_DEVICES_AVAILABLE;
  @Nullable private RemoteMediaClient client;
  // What the phone asked the Chromecast to do with the current item.
  boolean wantPlay;
  boolean loading;
  long lastPos;
  boolean lastPlaying;

  private final RemoteMediaClient.Callback clientCb =
      new RemoteMediaClient.Callback() {
        @Override
        public void onStatusUpdated() {
          safe("status", this::status);
        }
        @Override
        public void onMediaError(com.google.android.gms.cast.MediaError e) {
          safe("mediaError", () -> {
            Integer code = e == null ? null : e.getDetailedErrorCode();
            String reason = e == null ? null : e.getReason();
            fail("error " + (code == null ? "?" : code) + (reason != null ? " " + reason : "") + (e != null && e.getType() != null ? " (" + e.getType() + ")" : ""));
          });
        }
        private void status() {
          RemoteMediaClient c = client;
          if (c != null) {
            int ps = c.getPlayerState();
            if (ps == MediaStatus.PLAYER_STATE_PLAYING) {
              wantPlay = true;
              loading = false;
            } else if (ps == MediaStatus.PLAYER_STATE_PAUSED) {
              wantPlay = false;
              loading = false;
            } else if (ps == MediaStatus.PLAYER_STATE_IDLE && c.getIdleReason() != MediaStatus.IDLE_REASON_NONE) {
              loading = false;
            }
            lastPos = Math.max(0L, c.getApproximateStreamPosition());
            lastPlaying = ps == MediaStatus.PLAYER_STATE_PLAYING;
          }
          CastBridge.this.listener.onCastStatus();
        }
      };

  private final SessionManagerListener<CastSession> sessionCb =
      new SessionManagerListener<CastSession>() {
        @Override public void onSessionStarting(CastSession s) {}
        @Override public void onSessionStarted(CastSession s, String id) { safe("started", () -> { attach(s); CastBridge.this.listener.onCastSessionStarted(); CastBridge.this.listener.onCastChanged(); }); }
        @Override public void onSessionStartFailed(CastSession s, int error) { safe("startFailed", CastBridge.this.listener::onCastChanged); }
        @Override public void onSessionEnding(CastSession s) {
          try { ending(); } catch (Throwable t) { CrashLog.note(app, "cast ending", t); }
        }
        private void ending() {
          RemoteMediaClient c = client;
          if (c != null) {
            lastPos = Math.max(0L, c.getApproximateStreamPosition());
            lastPlaying = c.getPlayerState() == MediaStatus.PLAYER_STATE_PLAYING
                || c.getPlayerState() == MediaStatus.PLAYER_STATE_BUFFERING;
          }
        }
        @Override public void onSessionEnded(CastSession s, int error) { safe("ended", () -> { detach(); CastBridge.this.listener.onCastSessionEnded(lastPos, lastPlaying); CastBridge.this.listener.onCastChanged(); }); }
        @Override public void onSessionResuming(CastSession s, String id) {}
        @Override public void onSessionResumed(CastSession s, boolean wasSuspended) { safe("resumed", () -> { attach(s); CastBridge.this.listener.onCastSessionStarted(); CastBridge.this.listener.onCastChanged(); }); }
        @Override public void onSessionResumeFailed(CastSession s, int error) { safe("resumeFailed", CastBridge.this.listener::onCastChanged); }
        @Override public void onSessionSuspended(CastSession s, int reason) { safe("suspended", CastBridge.this.listener::onCastChanged); }
      };

  private final CastStateListener stateCb =
      new CastStateListener() {
        @Override
        public void onCastStateChanged(int state) {
          castState = state;
          safe("state", CastBridge.this.listener::onCastChanged);
        }
      };

  private final MediaRouter.Callback discoveryCb = new MediaRouter.Callback() {};

  CastBridge(Context context, Listener l) {
    app = context.getApplicationContext();
    listener = l;
    try {
      ctx = CastContext.getSharedInstance(app);
      ctx.addCastStateListener(stateCb);
      castState = ctx.getCastState();
      ctx.getSessionManager().addSessionManagerListener(sessionCb, CastSession.class);
      selector = ctx.getMergedSelector();
      router = MediaRouter.getInstance(app);
      CastSession s = ctx.getSessionManager().getCurrentCastSession();
      if (s != null && s.isConnected()) attach(s);
    } catch (Throwable t) {
      // No Google Play services (or Cast) on this phone: no Cast button.
      CrashLog.note(app, "cast init", t);
      ctx = null;
    }
  }

  boolean supported() { return ctx != null; }

  /** Build 196: an error in a Cast callback is recorded, never allowed to close the app. */
  private void safe(String where, Runnable r) {
    try {
      r.run();
    } catch (Throwable t) {
      CrashLog.note(app, "cast " + where, t);
    }
  }

  /** Looks for devices while the app is in front (the Cast button shows when there are some). */
  void setDiscovery(boolean on) {
    if (router == null || selector == null || on == discovering) return;
    discovering = on;
    try {
      if (on) router.addCallback(selector, discoveryCb, MediaRouter.CALLBACK_FLAG_REQUEST_DISCOVERY);
      else router.removeCallback(discoveryCb);
    } catch (Throwable ignored) {
    }
  }

  boolean devicesAvailable() {
    if (ctx == null) return false;
    if (castState != CastState.NO_DEVICES_AVAILABLE) return true;
    try {
      if (router != null && selector != null) {
        for (MediaRouter.RouteInfo r : router.getRoutes()) {
          if (!r.isDefaultOrBluetooth() && r.isEnabled() && r.matchesSelector(selector)) return true;
        }
      }
    } catch (Throwable ignored) {
    }
    return false;
  }

  boolean connecting() { return castState == CastState.CONNECTING; }

  boolean connected() {
    CastSession s = session();
    return s != null && s.isConnected() && client != null;
  }

  @Nullable String deviceName() {
    CastSession s = session();
    try {
      return s != null && s.getCastDevice() != null ? s.getCastDevice().getFriendlyName() : null;
    } catch (Throwable t) {
      return null;
    }
  }

  @Nullable private CastSession session() {
    if (ctx == null) return null;
    try {
      SessionManager sm = ctx.getSessionManager();
      return sm.getCurrentCastSession();
    } catch (Throwable t) {
      return null;
    }
  }

  private void attach(CastSession s) {
    RemoteMediaClient c = s.getRemoteMediaClient();
    if (c == client) return;
    detach();
    client = c;
    if (c != null) c.registerCallback(clientCb);
  }

  private void detach() {
    if (client != null) {
      try { client.unregisterCallback(clientCb); } catch (Throwable ignored) {}
    }
    client = null;
    loading = false;
  }

  /** The device picker, or (while casting) the device's own panel with Stop casting. */
  void showPicker(Activity activity) {
    if (ctx == null || selector == null) return;
    if (connected() || connecting()) {
      MediaRouteControllerDialog d = new MediaRouteControllerDialog(activity);
      d.show();
    } else {
      MediaRouteChooserDialog d = new MediaRouteChooserDialog(activity);
      d.setRouteSelector(selector);
      d.show();
    }
  }

  void endSession() {
    if (ctx == null) return;
    try { ctx.getSessionManager().endCurrentSession(true); } catch (Throwable ignored) {}
  }

  // ---- what can be cast ----

  /** A stream on the internet (not a file on the phone, not the phone's own cache). */
  static boolean castable(String url) {
    if (url == null) return false;
    String u = url.trim().toLowerCase(Locale.ROOT);
    if (!(u.startsWith("http://") || u.startsWith("https://"))) return false;
    try {
      String host = Uri.parse(url).getHost();
      if (host == null) return false;
      host = host.toLowerCase(Locale.ROOT);
      if (host.equals("localhost") || host.equals("127.0.0.1") || host.equals("::1") || host.endsWith(".localhost")) return false;
    } catch (Throwable t) {
      return false;
    }
    return true;
  }

  static String extOf(String url) {
    String path;
    try { path = Uri.parse(url).getPath(); } catch (Throwable t) { path = url; }
    if (path == null) return "";
    path = path.toLowerCase(Locale.ROOT);
    int dot = path.lastIndexOf('.');
    int slash = path.lastIndexOf('/');
    return dot > slash ? path.substring(dot + 1) : "";
  }

  static String mimeFor(String url) {
    String low = url.toLowerCase(Locale.ROOT);
    String ext = extOf(url);
    if (low.contains(".m3u8") || ext.equals("m3u8")) return "application/x-mpegURL";
    switch (ext) {
      case "mpd": return "application/dash+xml";
      case "mp4": case "m4v": case "mov": return "video/mp4";
      case "webm": return "video/webm";
      case "aac": return "audio/aac";
      case "m4a": return "audio/mp4";
      case "ogg": case "oga": case "opus": return "audio/ogg";
      case "flac": return "audio/flac";
      case "wav": return "audio/wav";
      default: return "audio/mpeg";
    }
  }

  /** A live stream: an HLS address, or one with no file name (a station's stream). */
  static boolean liveFor(String url, boolean pageSaysLive) {
    if (pageSaysLive) return true;
    String ext = extOf(url);
    if (ext.equals("m3u8")) return true;
    return ext.isEmpty() || ext.equals("pls") || ext.equals("m3u");
  }

  void load(String url, boolean live, String title, String artist, @Nullable String artUrl, long startMs, boolean play, boolean video) {
    RemoteMediaClient c = client;
    if (c == null) return;
    String mime = mimeFor(url);
    boolean isVideo = video || mime.startsWith("video/");
    MediaMetadata md = new MediaMetadata(isVideo ? MediaMetadata.MEDIA_TYPE_MOVIE : MediaMetadata.MEDIA_TYPE_MUSIC_TRACK);
    md.putString(MediaMetadata.KEY_TITLE, title == null ? "" : title);
    if (artist != null && !artist.isEmpty()) {
      md.putString(isVideo ? MediaMetadata.KEY_SUBTITLE : MediaMetadata.KEY_ARTIST, artist);
    }
    if (artUrl != null && artUrl.startsWith("http")) md.addImage(new WebImage(Uri.parse(artUrl)));
    MediaInfo info =
        new MediaInfo.Builder(url)
            .setStreamType(live ? MediaInfo.STREAM_TYPE_LIVE : MediaInfo.STREAM_TYPE_BUFFERED)
            .setContentType(mime)
            .setMetadata(md)
            .build();
    MediaLoadRequestData req =
        new MediaLoadRequestData.Builder()
            .setMediaInfo(info)
            .setAutoplay(play)
            .setCurrentTime(live ? 0L : Math.max(0L, startMs))
            .build();
    wantPlay = play;
    loading = true;
    lastPos = live ? 0L : Math.max(0L, startMs);
    failNote = null;
    lastUrl = url;
    try {
      c.load(req).setResultCallback(
          r -> safe("loadResult", () -> {
            if (r != null && r.getStatus() != null && !r.getStatus().isSuccess()) {
              fail("load refused (status " + r.getStatus().getStatusCode()
                  + (r.getStatus().getStatusMessage() != null ? " " + r.getStatus().getStatusMessage() : "") + ")");
            }
          }));
    } catch (Throwable t) {
      loading = false;
      fail("load threw " + t);
    }
  }

  // Build 197: why the Chromecast couldn't play the last item (its detailed error code), for
  // the page's error message and Check storage.
  @Nullable String failNote;
  @Nullable private String lastUrl;
  private void fail(String why) {
    loading = false;
    failNote = why;
    CrashLog.note(app, "cast media", new RuntimeException(why + " [" + mimeFor(lastUrl == null ? "" : lastUrl) + "] " + (lastUrl == null ? "" : lastUrl)));
    listener.onCastStatus();
  }
  @Nullable String takeFailNote() { String n = failNote; failNote = null; return n; }

  void play() { RemoteMediaClient c = client; if (c != null) { wantPlay = true; try { c.play(); } catch (Throwable ignored) {} } }
  void pause() { RemoteMediaClient c = client; if (c != null) { wantPlay = false; try { c.pause(); } catch (Throwable ignored) {} } }
  void stopMedia() { RemoteMediaClient c = client; if (c != null) { wantPlay = false; loading = false; try { c.stop(); } catch (Throwable ignored) {} } }
  void seek(long ms) {
    RemoteMediaClient c = client;
    if (c == null) return;
    try { c.seek(new MediaSeekOptions.Builder().setPosition(Math.max(0L, ms)).build()); } catch (Throwable ignored) {}
  }
  void setVolume(double v) {
    RemoteMediaClient c = client;
    if (c == null) return;
    try { c.setStreamVolume(Math.max(0d, Math.min(1d, v))); } catch (Throwable ignored) {}
  }

  // ---- what the Chromecast is doing ----
  long position() {
    RemoteMediaClient c = client;
    if (c == null) return lastPos;
    try { return Math.max(0L, c.getApproximateStreamPosition()); } catch (Throwable t) { return lastPos; }
  }
  long duration() {
    RemoteMediaClient c = client;
    if (c == null) return -1L;
    try { long d = c.getStreamDuration(); return d > 0 ? d : -1L; } catch (Throwable t) { return -1L; }
  }
  boolean live() {
    RemoteMediaClient c = client;
    if (c == null) return false;
    try {
      MediaInfo mi = c.getMediaInfo();
      return c.isLiveStream() || (mi != null && mi.getStreamType() == MediaInfo.STREAM_TYPE_LIVE);
    } catch (Throwable t) {
      return false;
    }
  }
  int playerState() {
    RemoteMediaClient c = client;
    if (c == null) return MediaStatus.PLAYER_STATE_UNKNOWN;
    try { return c.getPlayerState(); } catch (Throwable t) { return MediaStatus.PLAYER_STATE_UNKNOWN; }
  }
  int idleReason() {
    RemoteMediaClient c = client;
    if (c == null) return MediaStatus.IDLE_REASON_NONE;
    try { return c.getIdleReason(); } catch (Throwable t) { return MediaStatus.IDLE_REASON_NONE; }
  }
}
