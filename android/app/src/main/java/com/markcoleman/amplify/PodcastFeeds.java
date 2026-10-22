package com.markcoleman.amplify;

import android.content.Context;
import android.util.Xml;
import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;
import org.xmlpull.v1.XmlPullParser;

/**
 * Build 274: followed podcasts' newest episodes, read straight from each show's own RSS feed.
 *
 * <p>Mark had to open the app and wait for new episodes: the page asked Apple's directory one
 * show at a time (paced, so Apple wouldn't throttle it), only while the app was open, and Apple's
 * copy often trails the feed by hours. Here every feed is read natively (no CORS), several at
 * once, from PodcastRefreshWorker every hour in the background and from the page on demand. The
 * result is kept in files/podcast_feeds.json, which the page reads the moment it starts.
 *
 * <p>The followed shows come from the page's own copy of radioPlayerPodcastSubs in the amplify_kv
 * preferences (build 191's mirror). Episodes use the page's slim format (g, n, d, t, u, f, s, v);
 * g is the item's guid, which is what Apple reports as episodeGuid, so the two never double up.
 */
public final class PodcastFeeds {
  private static final String FILE = "podcast_feeds.json";
  private static final String KV_PREFS = "amplify_kv";
  private static final String SUBS_KEY = "radioPlayerPodcastSubs";
  private static final int MAX_EPISODES = 40;
  private static final long MAX_AGE_MS = 7L * 86400000L;
  private static final Object LOCK = new Object();

  private PodcastFeeds() {}

  /** The saved result, or an empty one. */
  public static JSONObject read(Context c) {
    synchronized (LOCK) {
      try {
        File f = new File(c.getFilesDir(), FILE);
        if (!f.exists()) return empty();
        byte[] b = readAll(new java.io.FileInputStream(f), 8 * 1024 * 1024);
        return new JSONObject(new String(b, StandardCharsets.UTF_8));
      } catch (Exception e) {
        return empty();
      }
    }
  }

  private static JSONObject empty() {
    JSONObject o = new JSONObject();
    try {
      o.put("at", 0);
      o.put("shows", new JSONObject());
    } catch (Exception ignored) {
      // cannot happen
    }
    return o;
  }

  private static void write(Context c, JSONObject o) {
    synchronized (LOCK) {
      try {
        File tmp = new File(c.getFilesDir(), FILE + ".tmp");
        try (FileOutputStream out = new FileOutputStream(tmp)) {
          out.write(o.toString().getBytes(StandardCharsets.UTF_8));
          out.getFD().sync();
        }
        File dst = new File(c.getFilesDir(), FILE);
        if (!tmp.renameTo(dst)) {
          dst.delete();
          tmp.renameTo(dst);
        }
      } catch (Exception e) {
        // keep the old file
      }
    }
  }

  private static final Object RUN_LOCK = new Object();

  /**
   * Reads every followed show's feed and saves the result. A feed that hasn't changed (ETag /
   * Last-Modified) or can't be reached keeps what was saved before. Only one run at a time; a
   * second caller waits for the running one and gets its result.
   */
  public static JSONObject refreshAll(Context c) {
    synchronized (RUN_LOCK) {
      JSONArray subs;
      try {
        String raw = c.getSharedPreferences(KV_PREFS, Context.MODE_PRIVATE).getString(SUBS_KEY, "[]");
        subs = new JSONArray(raw == null ? "[]" : raw);
      } catch (Exception e) {
        subs = new JSONArray();
      }
      JSONObject saved = read(c);
      JSONObject oldShows = saved.optJSONObject("shows");
      if (oldShows == null) oldShows = new JSONObject();
      final JSONObject shows = new JSONObject();
      ExecutorService pool = Executors.newFixedThreadPool(6);
      final JSONObject oldF = oldShows;
      final int[] ok = {0};
      for (int i = 0; i < subs.length(); i++) {
        final JSONObject sub = subs.optJSONObject(i);
        if (sub == null) continue;
        final String id = sub.optString("collectionId", "");
        if (id.isEmpty()) continue;
        pool.execute(
            () -> {
              JSONObject prev = oldF.optJSONObject(id);
              JSONObject res = refreshOne(sub, prev);
              synchronized (shows) {
                try {
                  shows.put(id, res);
                  if (res.optBoolean("ok")) ok[0]++;
                } catch (Exception ignored) {
                  // skip
                }
              }
            });
      }
      pool.shutdown();
      try {
        pool.awaitTermination(90, TimeUnit.SECONDS);
      } catch (InterruptedException ignored) {
        Thread.currentThread().interrupt();
      }
      JSONObject out = new JSONObject();
      try {
        out.put("at", System.currentTimeMillis());
        out.put("ok", ok[0]);
        out.put("total", subs.length());
        synchronized (shows) {
          out.put("shows", new JSONObject(shows.toString()));
        }
      } catch (Exception ignored) {
        // cannot happen
      }
      write(c, out);
      return out;
    }
  }

  private static JSONObject refreshOne(JSONObject sub, JSONObject prev) {
    JSONObject r = new JSONObject();
    try {
      String feed = sub.optString("feedUrl", "");
      if (feed.isEmpty() && prev != null) feed = prev.optString("feedUrl", "");
      if (feed.isEmpty()) feed = lookupFeedUrl(sub.optString("collectionId"));
      r.put("feedUrl", feed);
      if (feed.isEmpty()) throw new Exception("no feed");
      String etag = prev != null && feed.equals(prev.optString("feedUrl")) ? prev.optString("etag", "") : "";
      String lastMod = prev != null && feed.equals(prev.optString("feedUrl")) ? prev.optString("lastMod", "") : "";
      HttpURLConnection conn = open(feed, etag, lastMod);
      int code = conn.getResponseCode();
      if (code == 304 && prev != null && prev.has("eps")) {
        conn.disconnect();
        r.put("eps", prev.getJSONArray("eps"));
        r.put("etag", etag);
        r.put("lastMod", lastMod);
        r.put("ok", true);
        return r;
      }
      if (code < 200 || code >= 300) throw new Exception("HTTP " + code);
      String art = sub.optString("artworkUrl", "");
      JSONArray eps;
      try (InputStream in = new BufferedInputStream(conn.getInputStream())) {
        eps = parse(in, art, System.currentTimeMillis());
      } finally {
        r.put("etag", conn.getHeaderField("ETag") == null ? "" : conn.getHeaderField("ETag"));
        r.put("lastMod", conn.getHeaderField("Last-Modified") == null ? "" : conn.getHeaderField("Last-Modified"));
        conn.disconnect();
      }
      r.put("eps", eps);
      r.put("ok", true);
    } catch (Exception e) {
      try {
        r.put("ok", false);
        r.put("err", String.valueOf(e.getMessage()));
        if (prev != null && prev.has("eps")) r.put("eps", prev.getJSONArray("eps"));
        if (prev != null) {
          r.put("etag", prev.optString("etag", ""));
          r.put("lastMod", prev.optString("lastMod", ""));
        }
      } catch (Exception ignored) {
        // skip
      }
    }
    return r;
  }

  /** A subscription saved without its feed address: Apple's lookup has it. */
  private static String lookupFeedUrl(String id) {
    try {
      HttpURLConnection conn = open("https://itunes.apple.com/lookup?id=" + id, "", "");
      if (conn.getResponseCode() != 200) return "";
      String body = new String(readAll(conn.getInputStream(), 1024 * 1024), StandardCharsets.UTF_8);
      conn.disconnect();
      JSONArray res = new JSONObject(body).optJSONArray("results");
      if (res == null) return "";
      for (int i = 0; i < res.length(); i++) {
        String f = res.getJSONObject(i).optString("feedUrl", "");
        if (!f.isEmpty()) return f;
      }
    } catch (Exception ignored) {
      // none
    }
    return "";
  }

  /** Follows redirects itself, since HttpURLConnection won't between http and https. */
  private static HttpURLConnection open(String url, String etag, String lastMod) throws Exception {
    String u = url;
    for (int hop = 0; hop < 6; hop++) {
      HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
      c.setInstanceFollowRedirects(false);
      c.setConnectTimeout(15000);
      c.setReadTimeout(20000);
      c.setRequestProperty("User-Agent", "Amplify/1.0 (Android) podcast refresh");
      c.setRequestProperty("Accept", "application/rss+xml, application/xml, text/xml, */*");
      if (!etag.isEmpty()) c.setRequestProperty("If-None-Match", etag);
      if (!lastMod.isEmpty()) c.setRequestProperty("If-Modified-Since", lastMod);
      int code = c.getResponseCode();
      if (code >= 300 && code < 400 && code != 304) {
        String loc = c.getHeaderField("Location");
        c.disconnect();
        if (loc == null) throw new Exception("redirect without Location");
        u = new URL(new URL(u), loc).toString();
        continue;
      }
      return c;
    }
    throw new Exception("too many redirects");
  }

  private static byte[] readAll(InputStream in, int max) throws Exception {
    try (InputStream s = in) {
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      byte[] buf = new byte[16384];
      int n;
      while ((n = s.read(buf)) > 0) {
        out.write(buf, 0, n);
        if (out.size() > max) break;
      }
      return out.toByteArray();
    }
  }

  /**
   * The feed's newest items (at most MAX_EPISODES, none older than a week), newest first. Stops
   * reading after MAX_EPISODES items, so a feed with thousands of episodes costs only its top.
   */
  static JSONArray parse(InputStream in, String showArt, long now) throws Exception {
    XmlPullParser p = Xml.newPullParser();
    p.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, false);
    p.setInput(in, null);
    List<JSONObject> items = new ArrayList<>();
    String channelArt = "";
    JSONObject cur = null;
    String tag;
    int seen = 0;
    for (int ev = p.getEventType(); ev != XmlPullParser.END_DOCUMENT; ev = p.next()) {
      if (ev == XmlPullParser.START_TAG) {
        tag = p.getName();
        if ("item".equals(tag) || "entry".equals(tag)) {
          cur = new JSONObject();
          continue;
        }
        if (cur == null) {
          if ("itunes:image".equals(tag) && channelArt.isEmpty()) {
            String h = p.getAttributeValue(null, "href");
            if (h != null) channelArt = h;
          }
          continue;
        }
        switch (tag) {
          case "title":
            if (!cur.has("n")) cur.put("n", text(p).trim());
            break;
          case "guid":
          case "id":
            if (!cur.has("g")) cur.put("g", text(p).trim());
            break;
          case "pubDate":
          case "published":
          case "dc:date":
            if (!cur.has("d")) cur.put("d", isoDate(text(p).trim()));
            break;
          case "enclosure":
            {
              String u = p.getAttributeValue(null, "url");
              String t = p.getAttributeValue(null, "type");
              if (u != null && !cur.has("u")) {
                cur.put("u", u.trim());
                String ty = t == null ? "" : t.toLowerCase(Locale.US);
                boolean video = ty.startsWith("video/")
                    || (ty.isEmpty() && u.toLowerCase(Locale.US).matches(".*\\.(mp4|m4v|mov)(\\?.*)?$"));
                cur.put("v", video ? 1 : 0);
              }
              break;
            }
          case "itunes:duration":
            cur.put("t", duration(text(p).trim()));
            break;
          case "itunes:image":
            {
              String h = p.getAttributeValue(null, "href");
              if (h != null && !h.trim().isEmpty()) cur.put("f", h.trim());
              break;
            }
          case "description":
          case "itunes:summary":
          case "content:encoded":
          case "summary":
            if (!cur.has("s")) {
              String s = plain(text(p));
              if (!s.isEmpty()) cur.put("s", s.length() > 200 ? s.substring(0, 200) : s);
            }
            break;
          default:
            break;
        }
      } else if (ev == XmlPullParser.END_TAG) {
        tag = p.getName();
        if (cur != null && ("item".equals(tag) || "entry".equals(tag))) {
          seen++;
          if (cur.has("u")) {
            String u = cur.getString("u");
            // Same as the page's episodeFromItunes: a guid-less item is known by its address.
            String https = u.replaceFirst("(?i)^http://", "https://");
            cur.put("u", https);
            if (!cur.has("g") || cur.getString("g").isEmpty()) cur.put("g", https);
            items.add(cur);
          }
          cur = null;
          if (seen >= MAX_EPISODES) break;
        }
      }
    }
    String fallbackArt = showArt != null && !showArt.isEmpty() ? showArt : channelArt;
    JSONArray out = new JSONArray();
    items.sort((a, b) -> Long.compare(time(b.optString("d")), time(a.optString("d"))));
    for (JSONObject it : items) {
      long t = time(it.optString("d"));
      if (t == 0 || now - t > MAX_AGE_MS) continue;
      if (!it.has("f")) it.put("f", fallbackArt);
      if (!it.has("n") || it.getString("n").isEmpty()) it.put("n", "Untitled episode");
      if (!it.has("t")) it.put("t", 0);
      if (!it.has("s")) it.put("s", "");
      if (!it.has("v")) it.put("v", 0);
      out.put(it);
    }
    return out;
  }

  private static String text(XmlPullParser p) throws Exception {
    StringBuilder sb = new StringBuilder();
    int depth = 1;
    while (depth > 0) {
      int ev = p.next();
      if (ev == XmlPullParser.TEXT || ev == XmlPullParser.CDSECT) sb.append(p.getText());
      else if (ev == XmlPullParser.START_TAG) depth++;
      else if (ev == XmlPullParser.END_TAG) depth--;
      else if (ev == XmlPullParser.END_DOCUMENT) break;
    }
    return sb.toString();
  }

  static String plain(String html) {
    // Block tags become a space, inline ones (b, a, span...) nothing, so "<b>Ilja</b>." stays "Ilja.".
    String s = html.replaceAll("(?i)<\\s*(br|/?p|/?div|/?li|/?ul|/?ol|/?h[1-6]|/?tr|/?td)\\b[^>]*>", " ");
    s = s.replaceAll("(?s)<[^>]*>", "");
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", "\"").replace("&#39;", "'").replace("&apos;", "'");
    return s.replaceAll("\\s+", " ").replaceAll(" ([.,;:!?])", "$1").trim();
  }

  static int duration(String s) {
    try {
      if (s.isEmpty()) return 0;
      String[] parts = s.split(":");
      int total = 0;
      for (String part : parts) total = total * 60 + (int) Math.round(Double.parseDouble(part.trim()));
      return total;
    } catch (Exception e) {
      return 0;
    }
  }

  private static final String[] DATE_FORMATS = {
    "EEE, d MMM yyyy HH:mm:ss Z",
    "EEE, d MMM yyyy HH:mm:ss zzz",
    "EEE, d MMM yyyy HH:mm Z",
    "EEE, d MMM yyyy HH:mm zzz",
    "d MMM yyyy HH:mm:ss Z",
    "d MMM yyyy HH:mm:ss zzz",
    "EEE, d MMM yyyy",
    "yyyy-MM-dd'T'HH:mm:ssXXX",
    "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    "yyyy-MM-dd"
  };

  /** RSS dates (RFC 822, with or without the day name) as ISO 8601 UTC, like Apple sends. */
  static String isoDate(String s) {
    if (s.isEmpty()) return "";
    String in = s.replaceAll("\\s+", " ");
    for (String f : DATE_FORMATS) {
      try {
        SimpleDateFormat df = new SimpleDateFormat(f, Locale.US);
        df.setLenient(true);
        if (f.endsWith("'Z'")) df.setTimeZone(TimeZone.getTimeZone("UTC"));
        Date d = df.parse(in);
        if (d == null) continue;
        SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        iso.setTimeZone(TimeZone.getTimeZone("UTC"));
        return iso.format(d);
      } catch (Exception ignored) {
        // next format
      }
    }
    return "";
  }

  static long time(String iso) {
    if (iso == null || iso.isEmpty()) return 0;
    try {
      SimpleDateFormat df = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
      df.setTimeZone(TimeZone.getTimeZone("UTC"));
      Date d = df.parse(iso);
      return d == null ? 0 : d.getTime();
    } catch (Exception e) {
      return 0;
    }
  }
}
