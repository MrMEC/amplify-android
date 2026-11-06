package com.markcoleman.amplify;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.os.Handler;
import android.os.Looper;
import androidx.annotation.Nullable;
import com.google.android.gms.cast.MediaStatus;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Build 495 (Mark): casting to a Roku. A Roku on the same Wi-Fi is found with SSDP (it answers
 * "roku:ecp") and driven over its External Control Protocol on port 8060: the address is handed to
 * Roku's own "Play on Roku" player (app 15985, the way Home Assistant does it), and its state is
 * read back from /query/media-player about once a second. There is no "session" on a Roku: picking
 * one in the Cast menu starts ours, Stop casting (or another pick) ends it.
 *
 * <p>Network calls run on one background thread; everything reported to CastBridge is on the main
 * thread. ECP can't seek or set the volume, so those do nothing while a Roku plays.
 */
final class RokuCast {
  static final String PLAY_ON_ROKU = "15985";

  interface Owner {
    void onRokuDevices();
    void onRokuSessionStarted();
    void onRokuSessionEnded(long positionMs, boolean wasPlaying);
    void onRokuStatus();
  }

  static final class Device {
    final String base; // http://192.168.1.20:8060
    final String name;
    volatile long seenAt;

    Device(String base, String name) {
      this.base = base;
      this.name = name;
      this.seenAt = System.currentTimeMillis();
    }
  }

  private final Context app;
  private final Owner owner;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final ScheduledExecutorService io = Executors.newSingleThreadScheduledExecutor(r -> {
    Thread t = new Thread(r, "roku-cast");
    t.setDaemon(true);
    return t;
  });
  private final Map<String, Device> devices = new ConcurrentHashMap<>();
  @Nullable private ScheduledFuture<?> searchTask;
  @Nullable private ScheduledFuture<?> pollTask;

  // ---- the session (main thread) ----
  @Nullable private volatile Device current;
  private int ps = MediaStatus.PLAYER_STATE_UNKNOWN;
  private int idle = MediaStatus.IDLE_REASON_NONE;
  private long pos;
  private long posAt;
  private long dur = -1L;
  private boolean live;
  private boolean sawMedia;
  /** When the last item was handed over (0: nothing pending). */
  private long loadAt;
  private int loadGen;
  /** The item was asked to start paused: pause it once it plays. */
  private boolean pauseWhenPlaying;
  @Nullable private String failNote;

  RokuCast(Context context, Owner o) {
    app = context.getApplicationContext();
    owner = o;
  }

  // ---- finding Rokus ----

  void setDiscovery(boolean on) {
    if (on) {
      if (searchTask == null) {
        searchTask = io.scheduleWithFixedDelay(() -> {
          try { searchOnce(); } catch (Throwable t) { CrashLog.note(app, "roku search", t); }
        }, 0L, 20L, TimeUnit.SECONDS);
      }
    } else if (searchTask != null) {
      searchTask.cancel(false);
      searchTask = null;
    }
  }

  boolean hasDevices() {
    return !devices.isEmpty();
  }

  List<Device> devices() {
    List<Device> out = new ArrayList<>(devices.values());
    java.util.Collections.sort(out, (a, b) -> a.name.compareToIgnoreCase(b.name));
    return out;
  }

  private void searchOnce() {
    WifiManager.MulticastLock lock = null;
    try {
      WifiManager wm = (WifiManager) app.getSystemService(Context.WIFI_SERVICE);
      if (wm != null) {
        lock = wm.createMulticastLock("amplify-roku");
        lock.setReferenceCounted(false);
        lock.acquire();
      }
    } catch (Throwable ignored) {
      lock = null;
    }
    boolean changed = false;
    try (DatagramSocket sock = new DatagramSocket()) {
      sock.setSoTimeout(800);
      byte[] msg =
          ("M-SEARCH * HTTP/1.1\r\n"
                  + "HOST: 239.255.255.250:1900\r\n"
                  + "MAN: \"ssdp:discover\"\r\n"
                  + "ST: roku:ecp\r\n"
                  + "MX: 2\r\n\r\n")
              .getBytes(StandardCharsets.US_ASCII);
      InetAddress group = InetAddress.getByName("239.255.255.250");
      sock.send(new DatagramPacket(msg, msg.length, group, 1900));
      sock.send(new DatagramPacket(msg, msg.length, group, 1900));
      long end = System.currentTimeMillis() + 3000L;
      byte[] buf = new byte[2048];
      while (System.currentTimeMillis() < end) {
        try {
          DatagramPacket p = new DatagramPacket(buf, buf.length);
          sock.receive(p);
          String reply = new String(p.getData(), 0, p.getLength(), StandardCharsets.ISO_8859_1);
          if (!reply.toLowerCase(Locale.ROOT).contains("roku")) continue;
          String loc = header(reply, "LOCATION");
          if (loc == null) continue;
          if (found(loc)) changed = true;
        } catch (SocketTimeoutException ignored) {
          // keep listening until the window closes
        }
      }
    } catch (Throwable t) {
      // no Wi-Fi: nothing found this time
    } finally {
      if (lock != null) try { lock.release(); } catch (Throwable ignored) {}
    }
    // A Roku not heard from for a minute is gone (unless it's the one playing).
    long cutoff = System.currentTimeMillis() - 65000L;
    for (Iterator<Device> it = devices.values().iterator(); it.hasNext(); ) {
      Device d = it.next();
      if (d.seenAt < cutoff && d != current) {
        it.remove();
        changed = true;
      }
    }
    if (changed) main.post(owner::onRokuDevices);
  }

  /** A Roku answered: true when it's new. */
  private boolean found(String location) {
    String base = location.trim();
    while (base.endsWith("/")) base = base.substring(0, base.length() - 1);
    if (!base.startsWith("http://")) return false;
    Device known = devices.get(base);
    if (known != null) {
      known.seenAt = System.currentTimeMillis();
      return false;
    }
    String name = "Roku";
    try {
      String info = get(base + "/query/device-info");
      String n = tag(info, "user-device-name");
      if (n == null || n.isEmpty()) n = tag(info, "friendly-device-name");
      if (n == null || n.isEmpty()) n = tag(info, "model-name");
      if (n != null && !n.isEmpty()) name = n;
    } catch (Throwable ignored) {
      // still a Roku; its name just couldn't be read
    }
    devices.put(base, new Device(base, name));
    CrashLog.info(app, "roku found: " + name + " at " + base);
    return true;
  }

  // ---- the session ----

  boolean connected() {
    return current != null;
  }

  @Nullable String deviceName() {
    Device d = current;
    return d == null ? null : d.name;
  }

  /** Picked in the Cast menu. */
  void connect(Device d) {
    if (current == d) return;
    if (current != null) end(false);
    current = d;
    ps = MediaStatus.PLAYER_STATE_IDLE;
    idle = MediaStatus.IDLE_REASON_NONE;
    pos = 0L;
    posAt = System.currentTimeMillis();
    dur = -1L;
    live = false;
    sawMedia = false;
    loadAt = 0L;
    failNote = null;
    CrashLog.info(app, "roku session on " + d.name);
    startPolling();
    owner.onRokuSessionStarted();
  }

  /** Stop casting: the Roku leaves its player (back to its home screen) and the item comes back. */
  void end(boolean stopTheRoku) {
    Device d = current;
    if (d == null) return;
    long at = position();
    boolean wasPlaying = ps == MediaStatus.PLAYER_STATE_PLAYING;
    current = null;
    loadAt = 0L;
    stopPolling();
    if (stopTheRoku) io.execute(() -> post(d.base + "/keypress/Home"));
    owner.onRokuSessionEnded(at, wasPlaying);
  }

  /**
   * Hands an address to Play on Roku. The kind of stream decides audio (t=a, with song and artist)
   * or video (t=v); the format names are the ones Roku's player takes.
   */
  void load(String url, boolean isLive, String title, String artist, @Nullable String artUrl, boolean play, boolean video, @Nullable String mime) {
    Device d = current;
    if (d == null) return;
    String[] kind = formatFor(url, video, mime);
    if (kind == null) {
      fail("a Roku can't play " + describe(mime) + " streams");
      return;
    }
    StringBuilder q = new StringBuilder();
    q.append("t=").append(kind[0]).append("&u=").append(enc(url));
    String name = title == null || title.isEmpty() ? "Amplify" : title;
    if ("a".equals(kind[0])) {
      q.append("&songName=").append(enc(name));
      q.append("&artistName=").append(enc(artist == null || artist.isEmpty() ? "Amplify" : artist));
      if (kind[1] != null) q.append("&songFormat=").append(enc(kind[1]));
      if (artUrl != null && artUrl.startsWith("http")) q.append("&albumArtUrl=").append(enc(artUrl));
    } else {
      q.append("&videoName=").append(enc(name));
      if (kind[1] != null) q.append("&videoFormat=").append(enc(kind[1]));
      if (artUrl != null && artUrl.startsWith("http")) q.append("&k=").append(enc(artUrl));
    }
    final int gen = ++loadGen;
    loadAt = System.currentTimeMillis();
    pauseWhenPlaying = !play;
    failNote = null;
    ps = MediaStatus.PLAYER_STATE_BUFFERING;
    idle = MediaStatus.IDLE_REASON_NONE;
    pos = 0L;
    posAt = loadAt;
    dur = -1L;
    live = isLive;
    sawMedia = false;
    final String launch = d.base + "/launch/" + PLAY_ON_ROKU + "?" + q;
    CrashLog.info(app, "roku load " + kind[0] + "/" + kind[1] + (isLive ? " live" : "") + " " + url);
    io.execute(() -> {
      int code = post(launch);
      if (code >= 400 || code < 0) {
        main.post(() -> {
          if (gen != loadGen || current != d) return;
          fail(code == 403
              ? "the Roku turned it away: on the Roku, set Settings > System > Advanced system settings > Control by mobile apps to Enabled"
              : "the Roku didn't answer (" + (code < 0 ? "no connection" : "error " + code) + ")");
        });
      }
    });
    // Nothing playing 25 s after the hand-over: say so.
    main.postDelayed(() -> {
      if (gen != loadGen || current != d || loadAt == 0L) return;
      fail("the Roku didn't start playing it");
    }, 25000L);
  }

  void play() {
    Device d = current;
    if (d == null) return;
    pauseWhenPlaying = false;
    if (ps == MediaStatus.PLAYER_STATE_PAUSED) {
      ps = MediaStatus.PLAYER_STATE_PLAYING;
      posAt = System.currentTimeMillis();
      io.execute(() -> post(d.base + "/keypress/Play"));
    }
  }

  void pause() {
    Device d = current;
    if (d == null) return;
    if (ps == MediaStatus.PLAYER_STATE_PLAYING) {
      pos = position();
      posAt = System.currentTimeMillis();
      ps = MediaStatus.PLAYER_STATE_PAUSED;
      io.execute(() -> post(d.base + "/keypress/Play"));
    } else if (loadAt != 0L) {
      pauseWhenPlaying = true;
    }
  }

  /** The page stopped the item: the Roku leaves its player (the session stays). */
  void stopMedia() {
    Device d = current;
    if (d == null) return;
    loadAt = 0L;
    loadGen++;
    ps = MediaStatus.PLAYER_STATE_IDLE;
    idle = MediaStatus.IDLE_REASON_NONE;
    io.execute(() -> post(d.base + "/keypress/Back"));
  }

  long position() {
    if (ps == MediaStatus.PLAYER_STATE_PLAYING && !live) {
      return pos + Math.max(0L, System.currentTimeMillis() - posAt);
    }
    return pos;
  }

  long duration() {
    return dur > 0 ? dur : -1L;
  }

  boolean live() {
    return live;
  }

  int playerState() {
    return ps;
  }

  int idleReason() {
    return idle;
  }

  @Nullable String takeFailNote() {
    String n = failNote;
    failNote = null;
    return n;
  }

  private void fail(String why) {
    loadAt = 0L;
    failNote = why;
    ps = MediaStatus.PLAYER_STATE_IDLE;
    idle = MediaStatus.IDLE_REASON_ERROR;
    CrashLog.note(app, "roku media", new RuntimeException(why));
    owner.onRokuStatus();
  }

  // ---- watching the Roku's player ----

  private void startPolling() {
    stopPolling();
    pollTask = io.scheduleWithFixedDelay(() -> {
      Device d = current;
      if (d == null) return;
      try {
        String xml = get(d.base + "/query/media-player");
        main.post(() -> onPlayer(d, xml));
      } catch (Throwable t) {
        // the Roku went quiet for a moment; ask again next time
      }
    }, 600L, 1000L, TimeUnit.MILLISECONDS);
  }

  private void stopPolling() {
    if (pollTask != null) {
      pollTask.cancel(false);
      pollTask = null;
    }
  }

  private static final Pattern PLAYER = Pattern.compile("<player\\b([^>]*)>", Pattern.CASE_INSENSITIVE);

  private void onPlayer(Device d, String xml) {
    if (current != d || xml == null) return;
    Matcher m = PLAYER.matcher(xml);
    if (!m.find()) return;
    String attrs = m.group(1);
    String state = attr(attrs, "state");
    boolean error = "true".equalsIgnoreCase(attr(attrs, "error"));
    long p = ms(tag(xml, "position"));
    long du = ms(tag(xml, "duration"));
    String isLive = tag(xml, "is_live");
    int before = ps;
    long now = System.currentTimeMillis();
    // Until the Roku shows the new item, what it reports is the one before (or nothing yet).
    boolean waiting = loadAt != 0L && now - loadAt < 1500L;
    if (error && loadAt != 0L && !waiting) {
      fail("the Roku couldn't play it");
      return;
    }
    if (state == null || waiting) return;
    switch (state) {
      case "play":
        ps = MediaStatus.PLAYER_STATE_PLAYING;
        break;
      case "pause":
        ps = MediaStatus.PLAYER_STATE_PAUSED;
        break;
      case "buffer":
      case "open":
      case "startup":
        ps = MediaStatus.PLAYER_STATE_BUFFERING;
        break;
      default: // stop, close, none
        if (loadAt != 0L) {
          ps = MediaStatus.PLAYER_STATE_BUFFERING; // still starting
        } else if (sawMedia) {
          boolean atEnd = !live && dur > 0 && pos >= dur - 4000L;
          ps = MediaStatus.PLAYER_STATE_IDLE;
          idle = atEnd ? MediaStatus.IDLE_REASON_FINISHED : MediaStatus.IDLE_REASON_NONE;
        }
        break;
    }
    if (ps == MediaStatus.PLAYER_STATE_PLAYING || ps == MediaStatus.PLAYER_STATE_PAUSED) {
      if (loadAt != 0L) {
        CrashLog.info(app, "roku playing after " + ((now - loadAt) / 100) / 10.0 + " s");
        loadAt = 0L;
      }
      sawMedia = true;
      idle = MediaStatus.IDLE_REASON_NONE;
      if (p >= 0) {
        pos = p;
        posAt = now;
      }
      if (du > 0) dur = du;
      if (isLive != null) live = "true".equalsIgnoreCase(isLive.trim()) || live;
      if (pauseWhenPlaying && ps == MediaStatus.PLAYER_STATE_PLAYING) {
        pauseWhenPlaying = false;
        pause();
      }
    }
    // Progress is worked out on the phone between reads; the page hears of changes.
    if (ps != before || ps == MediaStatus.PLAYER_STATE_PLAYING) owner.onRokuStatus();
  }

  // ---- what a Roku can play ----

  /** {t, format} for Play on Roku, or null when a Roku can't play it. */
  @Nullable
  static String[] formatFor(String url, boolean video, @Nullable String mimeIn) {
    String mime = (mimeIn == null ? CastBridge.mimeFor(url) : mimeIn).toLowerCase(Locale.ROOT);
    String ext = CastBridge.extOf(url);
    if (mime.contains("mpegurl") || url.toLowerCase(Locale.ROOT).contains(".m3u8")) return new String[] {"v", "hls"};
    if (mime.contains("dash")) return new String[] {"v", "dash"};
    if (mime.startsWith("video/")) {
      if (mime.contains("mp4") || mime.contains("quicktime") || ext.equals("mov") || ext.equals("m4v")) return new String[] {"v", "mp4"};
      if (mime.contains("matroska") || mime.contains("webm") || ext.equals("mkv") || ext.equals("webm")) return new String[] {"v", "mkv"};
      return new String[] {"v", null}; // let the Roku work it out
    }
    if (video) return new String[] {"v", ext.equals("mkv") ? "mkv" : "mp4"};
    if (mime.contains("ogg") || mime.contains("opus")) return null;
    if (mime.contains("flac")) return new String[] {"a", "flac"};
    if (mime.contains("mp4") || mime.contains("m4a")) return new String[] {"a", "m4a"};
    if (mime.contains("aac")) return new String[] {"a", "es.aac-adts"};
    if (mime.contains("wav")) return new String[] {"a", "wav"};
    if (mime.contains("matroska")) return new String[] {"a", "mka"};
    return new String[] {"a", "mp3"};
  }

  private static String describe(@Nullable String mime) {
    if (mime == null) return "these";
    String m = mime.toLowerCase(Locale.ROOT);
    if (m.contains("ogg") || m.contains("opus")) return "Ogg/Opus";
    return mime;
  }

  // ---- HTTP ----

  private static String enc(String s) {
    try {
      return URLEncoder.encode(s, "UTF-8");
    } catch (Exception e) {
      return "";
    }
  }

  private static String get(String url) throws Exception {
    HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
    c.setConnectTimeout(2500);
    c.setReadTimeout(2500);
    try (InputStream in = c.getInputStream()) {
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      byte[] b = new byte[4096];
      int n;
      while ((n = in.read(b)) > 0 && out.size() < 256 * 1024) out.write(b, 0, n);
      return out.toString("UTF-8");
    } finally {
      c.disconnect();
    }
  }

  /** POST with an empty body; the HTTP code, or -1 when the Roku can't be reached. */
  private int post(String url) {
    HttpURLConnection c = null;
    try {
      c = (HttpURLConnection) new URL(url).openConnection();
      c.setConnectTimeout(3000);
      c.setReadTimeout(5000);
      c.setRequestMethod("POST");
      c.setDoOutput(true);
      c.setFixedLengthStreamingMode(0);
      c.getOutputStream().close();
      return c.getResponseCode();
    } catch (Throwable t) {
      CrashLog.info(app, "roku post failed: " + t);
      return -1;
    } finally {
      if (c != null) c.disconnect();
    }
  }

  // ---- tiny parsers ----

  @Nullable
  private static String header(String reply, String name) {
    for (String line : reply.split("\r?\n")) {
      int colon = line.indexOf(':');
      if (colon > 0 && line.substring(0, colon).trim().equalsIgnoreCase(name)) return line.substring(colon + 1).trim();
    }
    return null;
  }

  @Nullable
  static String tag(@Nullable String xml, String name) {
    if (xml == null) return null;
    Matcher m = Pattern.compile("<" + Pattern.quote(name) + "\\b[^>]*>([^<]*)</" + Pattern.quote(name) + ">", Pattern.CASE_INSENSITIVE).matcher(xml);
    return m.find() ? unescape(m.group(1).trim()) : null;
  }

  @Nullable
  private static String attr(String attrs, String name) {
    Matcher m = Pattern.compile("\\b" + Pattern.quote(name) + "\\s*=\\s*\"([^\"]*)\"", Pattern.CASE_INSENSITIVE).matcher(attrs);
    return m.find() ? m.group(1).trim().toLowerCase(Locale.ROOT) : null;
  }

  /** "12345 ms" -> 12345; -1 when missing. */
  static long ms(@Nullable String s) {
    if (s == null) return -1L;
    Matcher m = Pattern.compile("(\\d+)").matcher(s);
    return m.find() ? Long.parseLong(m.group(1)) : -1L;
  }

  private static String unescape(String s) {
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&apos;", "'").replace("&amp;", "&");
  }
}
