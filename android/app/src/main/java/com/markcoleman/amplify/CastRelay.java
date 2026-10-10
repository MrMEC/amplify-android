package com.markcoleman.amplify;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Build 199: hands HLS playlists to the Chromecast from the phone.
 *
 * <p>Pluto's stream server only lets its own web pages read its playlists (CORS), and the
 * Chromecast's player is a web page on another site, so it can't load a Pluto channel. Its
 * video pieces and keys are open to anyone. So while a Pluto channel is cast, the phone serves
 * the playlists (fetched by the phone, which isn't held to CORS) on the home network with an
 * open CORS header, and the Chromecast takes the video pieces straight from Pluto.
 *
 * <p>Plain Java (no Android classes), so it is tested with javac/java (tests/java/CastRelayTest).
 */
final class CastRelay {
  private static CastRelay instance;

  static synchronized CastRelay get() {
    if (instance == null) instance = new CastRelay();
    return instance;
  }

  private ServerSocket server;
  private String base; // http://<phone ip>:<port>
  private final Map<String, String> playlists = new ConcurrentHashMap<>();
  private final AtomicInteger seq = new AtomicInteger();
  private final ExecutorService pool = Executors.newCachedThreadPool();
  volatile String lastError;
  final AtomicInteger served = new AtomicInteger();

  /** Whether an address needs the relay (a Pluto channel from its stream server). */
  static boolean needed(String url) {
    if (url == null) return false;
    try {
      URL u = new URL(url);
      String h = u.getHost().toLowerCase(Locale.ROOT);
      return (h.endsWith(".pluto.tv") || h.endsWith(".plutotv.net")) && u.getPath().contains("/stitch/");
    } catch (Exception e) {
      return false;
    }
  }

  /** Starts the server if needed; the address the Chromecast can reach it on. */
  synchronized String start() throws Exception {
    if (server != null && !server.isClosed() && base != null) return base;
    String ip = lanAddress();
    if (ip == null) throw new IllegalStateException("No Wi-Fi address for the phone");
    server = new ServerSocket(0, 50);
    base = "http://" + ip + ":" + server.getLocalPort();
    final ServerSocket ss = server;
    Thread t = new Thread(() -> {
      while (!ss.isClosed()) {
        try {
          Socket s = ss.accept();
          pool.execute(() -> handle(s));
        } catch (Exception e) {
          if (ss.isClosed()) return;
        }
      }
    }, "cast-relay");
    t.setDaemon(true);
    t.start();
    return base;
  }

  /** For tests: serve on a given host name (127.0.0.1) instead of the Wi-Fi address. */
  synchronized String startOn(String host) throws Exception {
    if (server == null || server.isClosed()) {
      server = new ServerSocket(0, 50);
      final ServerSocket ss = server;
      Thread t = new Thread(() -> {
        while (!ss.isClosed()) {
          try { Socket s = ss.accept(); pool.execute(() -> handle(s)); } catch (Exception e) { if (ss.isClosed()) return; }
        }
      }, "cast-relay");
      t.setDaemon(true);
      t.start();
    }
    base = "http://" + host + ":" + server.getLocalPort();
    return base;
  }

  synchronized void stop() {
    try { if (server != null) server.close(); } catch (Exception ignored) {}
    server = null;
    base = null;
    playlists.clear();
  }

  /** The relay address for an upstream playlist. */
  String wrap(String upstream) {
    String tok = Integer.toString(seq.incrementAndGet(), 36) + Long.toString(System.nanoTime() & 0xffffff, 36);
    playlists.put(tok, upstream);
    if (playlists.size() > 400) {
      // Old playlists of earlier channels: drop some (keeps the map small on long sessions).
      int n = 0;
      for (String k : playlists.keySet()) { if (n++ > 200) break; if (!k.equals(tok)) playlists.remove(k); }
    }
    return base + "/p/" + tok + ".m3u8";
  }

  static String lanAddress() {
    try {
      String fallback = null;
      for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
        if (!ni.isUp() || ni.isLoopback()) continue;
        String name = ni.getName() == null ? "" : ni.getName().toLowerCase(Locale.ROOT);
        for (InetAddress a : Collections.list(ni.getInetAddresses())) {
          if (!(a instanceof Inet4Address) || a.isLoopbackAddress() || !a.isSiteLocalAddress()) continue;
          if (name.startsWith("wlan") || name.startsWith("eth") || name.startsWith("en")) return a.getHostAddress();
          if (fallback == null && !name.startsWith("rmnet") && !name.startsWith("tun")) fallback = a.getHostAddress();
        }
      }
      return fallback;
    } catch (Exception e) {
      return null;
    }
  }

  // ---- serving ----

  private void handle(Socket sock) {
    OutputStream out = null;
    try {
      sock.setSoTimeout(15000);
      InputStream in = sock.getInputStream();
      String head = readHead(in);
      out = sock.getOutputStream();
      if (head == null) return;
      String first = head.split("\r\n", 2)[0];
      String[] parts = first.split(" ");
      if (parts.length < 2) { respond(out, 400, "text/plain", new byte[0]); return; }
      String method = parts[0], path = parts[1];
      if (method.equals("OPTIONS")) { respond(out, 204, "text/plain", new byte[0]); return; }
      Matcher m = Pattern.compile("^/p/([0-9a-z]+)\\.m3u8").matcher(path);
      String upstream = m.find() ? playlists.get(m.group(1)) : null;
      if (upstream == null) { respond(out, 404, "text/plain", "not found".getBytes(StandardCharsets.UTF_8)); return; }
      String[] fetched = fetchText(upstream);
      String body = rewrite(fetched[0], fetched[1], this::wrap);
      served.incrementAndGet();
      respond(out, 200, "application/vnd.apple.mpegurl", method.equals("HEAD") ? new byte[0] : body.getBytes(StandardCharsets.UTF_8));
    } catch (Exception e) {
      lastError = String.valueOf(e);
      try { if (out != null) respond(out, 502, "text/plain", String.valueOf(e).getBytes(StandardCharsets.UTF_8)); } catch (Exception ignored) {}
    } finally {
      try { sock.close(); } catch (Exception ignored) {}
    }
  }

  private static String readHead(InputStream in) throws Exception {
    ByteArrayOutputStream b = new ByteArrayOutputStream();
    int c, n = 0;
    while ((c = in.read()) != -1) {
      b.write(c);
      if (++n > 16384) return null;
      byte[] a = b.toByteArray();
      int l = a.length;
      if (l >= 4 && a[l - 4] == '\r' && a[l - 3] == '\n' && a[l - 2] == '\r' && a[l - 1] == '\n') break;
    }
    return n == 0 ? null : b.toString("ISO-8859-1");
  }

  private static void respond(OutputStream out, int code, String type, byte[] body) throws Exception {
    String reason = code == 200 ? "OK" : code == 204 ? "No Content" : code == 404 ? "Not Found" : code == 400 ? "Bad Request" : "Bad Gateway";
    String h = "HTTP/1.1 " + code + " " + reason + "\r\n"
        + "Content-Type: " + type + "\r\n"
        + "Access-Control-Allow-Origin: *\r\n"
        + "Access-Control-Allow-Headers: *\r\n"
        + "Access-Control-Allow-Methods: GET, HEAD, OPTIONS\r\n"
        + "Cache-Control: no-cache, no-store\r\n"
        + "Content-Length: " + body.length + "\r\n"
        + "Connection: close\r\n\r\n";
    out.write(h.getBytes(StandardCharsets.ISO_8859_1));
    out.write(body);
    out.flush();
  }

  /** {text, final address after redirects}. */
  static String[] fetchText(String url) throws Exception {
    String u = url;
    for (int hop = 0; hop < 6; hop++) {
      HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
      c.setInstanceFollowRedirects(false);
      c.setConnectTimeout(8000);
      c.setReadTimeout(10000);
      c.setRequestProperty("Accept", "*/*");
      int code = c.getResponseCode();
      if (code >= 300 && code < 400 && c.getHeaderField("Location") != null) {
        u = new URL(new URL(u), c.getHeaderField("Location")).toString();
        c.disconnect();
        continue;
      }
      if (code != 200) { c.disconnect(); throw new IllegalStateException("upstream " + code); }
      try (InputStream in = c.getInputStream()) {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int r;
        while ((r = in.read(buf)) > 0) {
          b.write(buf, 0, r);
          if (b.size() > 4 * 1024 * 1024) throw new IllegalStateException("playlist too large");
        }
        return new String[] {b.toString("UTF-8"), u};
      } finally {
        c.disconnect();
      }
    }
    throw new IllegalStateException("too many redirects");
  }

  private static final Pattern URI_ATTR = Pattern.compile("URI=\"([^\"]*)\"");

  /**
   * Makes every address in a playlist absolute; playlists (variants, audio and subtitle
   * renditions) are pointed at the relay through wrap, everything else (video pieces, keys,
   * init sections) at its own server.
   */
  static String rewrite(String text, String baseUrl, Function<String, String> wrap) throws Exception {
    URL base = new URL(baseUrl);
    StringBuilder out = new StringBuilder(text.length() + 256);
    boolean nextIsPlaylist = false;
    for (String raw : text.split("\r?\n", -1)) {
      String line = raw.trim();
      if (line.isEmpty()) { out.append(raw).append('\n'); continue; }
      if (line.startsWith("#")) {
        String upper = line.toUpperCase(Locale.ROOT);
        if (upper.startsWith("#EXT-X-STREAM-INF")) nextIsPlaylist = true;
        boolean attrIsPlaylist = upper.startsWith("#EXT-X-MEDIA") || upper.startsWith("#EXT-X-I-FRAME-STREAM-INF");
        Matcher m = URI_ATTR.matcher(line);
        StringBuffer sb = new StringBuffer();
        while (m.find()) {
          String abs = new URL(base, m.group(1)).toString();
          String rep = attrIsPlaylist ? wrap.apply(abs) : abs;
          m.appendReplacement(sb, Matcher.quoteReplacement("URI=\"" + rep + "\""));
        }
        m.appendTail(sb);
        out.append(sb).append('\n');
        continue;
      }
      String abs = new URL(base, line).toString();
      boolean playlist = nextIsPlaylist || abs.toLowerCase(Locale.ROOT).split("\\?")[0].endsWith(".m3u8");
      out.append(playlist ? wrap.apply(abs) : abs).append('\n');
      nextIsPlaylist = false;
    }
    // split(-1) keeps a trailing empty piece; don't add an extra newline for it.
    if (out.length() > 0 && !text.endsWith("\n")) out.setLength(out.length() - 1);
    return out.toString();
  }
}
