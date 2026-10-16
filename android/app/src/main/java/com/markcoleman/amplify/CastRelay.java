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
  // Build 238: songs, videos and cover pictures on the phone, served to the Chromecast.
  private final Map<String, String> files = new ConcurrentHashMap<>();
  private final Map<String, byte[]> blobs = new ConcurrentHashMap<>();

  /**
   * Build 238: reads a file on the phone. The plain-Java default reads file:// addresses (and
   * plain paths); the app installs one that also reads content:// (Android's documents).
   */
  interface FileSource {
    /** The file's size in bytes, or -1 if unknown. */
    long size(String uri) throws Exception;
    /** The file, from byte `offset` on. */
    InputStream open(String uri, long offset) throws Exception;
  }

  static volatile FileSource fileSource = new FileSource() {
    @Override public long size(String uri) throws Exception { return toFile(uri).length(); }
    @Override public InputStream open(String uri, long offset) throws Exception {
      java.io.FileInputStream in = new java.io.FileInputStream(toFile(uri));
      if (offset > 0) in.getChannel().position(offset);
      return in;
    }
  };

  static java.io.File toFile(String uri) throws Exception {
    if (uri.startsWith("file:")) return new java.io.File(new java.net.URI(uri));
    return new java.io.File(uri);
  }

  /** Build 238: a song or video on the phone (not on the internet). */
  static boolean isLocal(String url) {
    if (url == null) return false;
    String u = url.trim().toLowerCase(Locale.ROOT);
    return u.startsWith("file:") || u.startsWith("content:") || u.startsWith("/");
  }
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
    files.clear();
    blobs.clear();
  }

  private String token() {
    return Integer.toString(seq.incrementAndGet(), 36) + Long.toString(System.nanoTime() & 0xffffff, 36);
  }

  /** Build 238: the relay address for a file on the phone; `ext` names its kind (mp3, mp4...). */
  String wrapFile(String uri, String ext) {
    String tok = token();
    files.put(tok, uri);
    if (files.size() > 200) {
      int n = 0;
      for (String k : files.keySet()) { if (n++ > 100) break; if (!k.equals(tok)) files.remove(k); }
    }
    String e = ext == null ? "" : ext.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    return base + "/f/" + tok + (e.isEmpty() ? "" : "." + e);
  }

  /** Build 238: the relay address for a few bytes (a song's cover picture). */
  String wrapBytes(byte[] data, String ext) {
    String tok = token();
    blobs.put(tok, data);
    if (blobs.size() > 20) {
      for (String k : blobs.keySet()) { if (!k.equals(tok)) { blobs.remove(k); if (blobs.size() <= 10) break; } }
    }
    return base + "/b/" + tok + "." + ext;
  }

  /** What a file is, from its extension (the Chromecast is told this). */
  static String mimeForExt(String ext) {
    switch (ext == null ? "" : ext.toLowerCase(Locale.ROOT)) {
      case "mp3": return "audio/mpeg";
      case "m4a": case "m4b": case "mp4a": return "audio/mp4";
      case "aac": return "audio/aac";
      case "flac": return "audio/flac";
      case "wav": return "audio/wav";
      case "ogg": case "oga": case "opus": return "audio/ogg";
      case "weba": return "audio/webm";
      case "mp4": case "m4v": case "mov": return "video/mp4";
      case "webm": return "video/webm";
      case "mkv": return "video/x-matroska";
      case "ts": case "m2ts": return "video/mp2t";
      case "jpg": case "jpeg": return "image/jpeg";
      case "png": return "image/png";
      case "webp": return "image/webp";
      case "gif": return "image/gif";
      default: return "application/octet-stream";
    }
  }

  /**
   * Build 238: what a file is from its first bytes, as an extension (a song the page copied
   * into the app's cache is "<key>.bin", and a document's name may not say). `video`: the page
   * says it's a video (decides MP4 vs M4A).
   */
  static String sniffExt(byte[] h, int n, boolean video) {
    if (n >= 3 && h[0] == 'I' && h[1] == 'D' && h[2] == '3') {
      // ID3 tags come before MP3 (and sometimes AAC/FLAC); skip them and look again.
      if (n >= 10) {
        int size = ((h[6] & 0x7f) << 21) | ((h[7] & 0x7f) << 14) | ((h[8] & 0x7f) << 7) | (h[9] & 0x7f);
        int at = 10 + size;
        if (at + 4 <= n) {
          if (h[at] == 'f' && h[at + 1] == 'L' && h[at + 2] == 'a' && h[at + 3] == 'C') return "flac";
          if ((h[at] & 0xff) == 0xff && ((h[at + 1] & 0xf6) == 0xf0)) return "aac";
        }
      }
      return "mp3";
    }
    if (n >= 4 && h[0] == 'f' && h[1] == 'L' && h[2] == 'a' && h[3] == 'C') return "flac";
    if (n >= 4 && h[0] == 'O' && h[1] == 'g' && h[2] == 'g' && h[3] == 'S') return "ogg";
    if (n >= 12 && h[0] == 'R' && h[1] == 'I' && h[2] == 'F' && h[3] == 'F' && h[8] == 'W' && h[9] == 'A' && h[10] == 'V' && h[11] == 'E') return "wav";
    if (n >= 12 && h[4] == 'f' && h[5] == 't' && h[6] == 'y' && h[7] == 'p') {
      String brand = new String(h, 8, 4, StandardCharsets.ISO_8859_1);
      if (brand.startsWith("M4A") || brand.startsWith("M4B") || brand.startsWith("M4P")) return "m4a";
      if (brand.startsWith("qt")) return "mov";
      return video ? "mp4" : "m4a";
    }
    if (n >= 4 && (h[0] & 0xff) == 0x1a && (h[1] & 0xff) == 0x45 && (h[2] & 0xff) == 0xdf && (h[3] & 0xff) == 0xa3) {
      String head = new String(h, 0, n, StandardCharsets.ISO_8859_1);
      return head.contains("webm") ? "webm" : "mkv";
    }
    if (n > 188 && (h[0] & 0xff) == 0x47 && (h[188] & 0xff) == 0x47) return "ts";
    if (n >= 2 && (h[0] & 0xff) == 0xff && (h[1] & 0xf6) == 0xf0) return "aac";
    if (n >= 2 && (h[0] & 0xff) == 0xff && (h[1] & 0xe0) == 0xe0) return "mp3";
    if (n >= 3 && (h[0] & 0xff) == 0xff && (h[1] & 0xff) == 0xd8) return "jpg";
    if (n >= 4 && (h[0] & 0xff) == 0x89 && h[1] == 'P' && h[2] == 'N' && h[3] == 'G') return "png";
    return video ? "mp4" : "mp3";
  }

  /** The extension of a file name or address ("" if none). */
  static String extOfName(String name) {
    if (name == null) return "";
    String p = name;
    int q = p.indexOf('?');
    if (q >= 0) p = p.substring(0, q);
    int dot = p.lastIndexOf('.'), slash = Math.max(p.lastIndexOf('/'), p.lastIndexOf("%2F"));
    return dot > slash && dot < p.length() - 1 ? p.substring(dot + 1).toLowerCase(Locale.ROOT) : "";
  }

  /**
   * Build 238: the kind of a file on the phone: its name's extension when the Chromecast knows
   * it, otherwise its first bytes.
   */
  static String extFor(String uri, String name, boolean video) {
    String ext = extOfName(name != null && !name.isEmpty() ? name : uri);
    if (!ext.isEmpty() && !mimeForExt(ext).equals("application/octet-stream")) return ext;
    byte[] h = new byte[4096];
    int n = 0;
    try (InputStream in = fileSource.open(uri, 0)) {
      int r;
      while (n < h.length && (r = in.read(h, n, h.length - n)) > 0) n += r;
    } catch (Exception e) {
      return video ? "mp4" : "mp3";
    }
    return sniffExt(h, n, video);
  }

  static boolean isVideoExt(String ext) {
    return mimeForExt(ext).startsWith("video/");
  }

  /** The relay address for an upstream playlist. */
  String wrap(String upstream) {
    String tok = token();
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
      // Build 238: a file on the phone, or a cover picture.
      Matcher fm = Pattern.compile("^/([fb])/([0-9a-z]+)(?:\\.([0-9a-z]+))?(?:[?#].*)?$").matcher(path);
      if (fm.find()) {
        String ext = fm.group(3) == null ? "" : fm.group(3);
        if (fm.group(1).equals("b")) {
          byte[] data = blobs.get(fm.group(2));
          if (data == null) { respond(out, 404, "text/plain", "not found".getBytes(StandardCharsets.UTF_8)); return; }
          served.incrementAndGet();
          respond(out, 200, mimeForExt(ext), method.equals("HEAD") ? new byte[0] : data);
          return;
        }
        String uri = files.get(fm.group(2));
        if (uri == null) { respond(out, 404, "text/plain", "not found".getBytes(StandardCharsets.UTF_8)); return; }
        serveFile(out, method, uri, mimeForExt(ext), rangeOf(head));
        return;
      }
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

  /** The Range header's value ("bytes=0-"), or null. */
  static String rangeOf(String head) {
    for (String line : head.split("\r\n")) {
      int c = line.indexOf(':');
      if (c > 0 && line.substring(0, c).trim().equalsIgnoreCase("range")) return line.substring(c + 1).trim();
    }
    return null;
  }

  /**
   * Build 238: {start, end} (inclusive) for a Range header and a file size; null for the whole
   * file; {-1, -1} when the range can't be met (416).
   */
  static long[] parseRange(String range, long size) {
    if (range == null || size < 0) return null;
    String r = range.trim().toLowerCase(Locale.ROOT);
    if (!r.startsWith("bytes=") || r.contains(",")) return null;
    String spec = r.substring(6).trim();
    int dash = spec.indexOf('-');
    if (dash < 0) return null;
    try {
      String a = spec.substring(0, dash).trim(), b = spec.substring(dash + 1).trim();
      long start, end;
      if (a.isEmpty()) {
        long n = Long.parseLong(b);
        if (n <= 0) return new long[] {-1, -1};
        start = Math.max(0, size - n);
        end = size - 1;
      } else {
        start = Long.parseLong(a);
        end = b.isEmpty() ? size - 1 : Math.min(Long.parseLong(b), size - 1);
      }
      if (start >= size || start > end) return new long[] {-1, -1};
      return new long[] {start, end};
    } catch (NumberFormatException e) {
      return null;
    }
  }

  private void serveFile(OutputStream out, String method, String uri, String type, String range) throws Exception {
    long size = fileSource.size(uri);
    long[] r = parseRange(range, size);
    if (r != null && r[0] < 0) {
      String h = "HTTP/1.1 416 Range Not Satisfiable\r\n" + corsHeaders()
          + "Content-Range: bytes */" + size + "\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
      out.write(h.getBytes(StandardCharsets.ISO_8859_1));
      out.flush();
      return;
    }
    long start = r == null ? 0 : r[0];
    long end = r == null ? size - 1 : r[1];
    long len = size < 0 ? -1 : end - start + 1;
    StringBuilder h = new StringBuilder();
    h.append(r == null ? "HTTP/1.1 200 OK\r\n" : "HTTP/1.1 206 Partial Content\r\n");
    h.append("Content-Type: ").append(type).append("\r\n").append(corsHeaders());
    h.append("Accept-Ranges: bytes\r\n");
    if (r != null) h.append("Content-Range: bytes ").append(start).append('-').append(end).append('/').append(size).append("\r\n");
    if (len >= 0) h.append("Content-Length: ").append(len).append("\r\n");
    h.append("Cache-Control: no-cache\r\nConnection: close\r\n\r\n");
    out.write(h.toString().getBytes(StandardCharsets.ISO_8859_1));
    served.incrementAndGet();
    if (method.equals("HEAD")) { out.flush(); return; }
    try (InputStream in = fileSource.open(uri, start)) {
      byte[] buf = new byte[64 * 1024];
      long left = len;
      while (left != 0) {
        int want = left < 0 ? buf.length : (int) Math.min(buf.length, left);
        int n = in.read(buf, 0, want);
        if (n <= 0) break;
        out.write(buf, 0, n);
        if (left > 0) left -= n;
      }
      out.flush();
    } catch (java.net.SocketException e) {
      // The Chromecast hung up mid-file (it seeks by asking again): nothing to report.
    }
  }

  private static String corsHeaders() {
    return "Access-Control-Allow-Origin: *\r\n"
        + "Access-Control-Allow-Headers: *\r\n"
        + "Access-Control-Allow-Methods: GET, HEAD, OPTIONS\r\n"
        + "Access-Control-Expose-Headers: Content-Length, Content-Range, Accept-Ranges\r\n";
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
    String reason = code == 200 ? "OK" : code == 204 ? "No Content" : code == 404 ? "Not Found" : code == 400 ? "Bad Request" : code == 500 ? "Server Error" : "Bad Gateway";
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
