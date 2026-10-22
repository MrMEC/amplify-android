package com.markcoleman.amplify;

import android.content.Context;
import com.sun.net.httpserver.HttpServer;
import java.io.File;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONArray;
import org.json.JSONObject;

/** Build 274: PodcastFeeds against a local feed server. Run: tests/java/run_podcast_feeds.sh */
public class PodcastFeedsTest {
  static int fails = 0;
  static void check(boolean ok, String what) {
    System.out.println((ok ? "PASS " : "FAIL ") + what);
    if (!ok) fails++;
  }
  static String rfc(long t, String pattern, String tz) {
    SimpleDateFormat f = new SimpleDateFormat(pattern, Locale.US);
    f.setTimeZone(TimeZone.getTimeZone(tz));
    return f.format(new Date(t));
  }
  static final long NOW = System.currentTimeMillis();
  static final long H = 3600000L;

  static String feedA() {
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        + "<rss version=\"2.0\" xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\" xmlns:content=\"http://purl.org/rss/1.0/modules/content/\">"
        + "<channel><title>WhatCulture Wrestling</title><itunes:image href=\"https://a.example/show.jpg\"/>"
        + "<image><title>ignored</title><url>https://a.example/x.jpg</url></image>"
        // newest: GMT, CDATA description with HTML, h:m:s duration
        + "<item><title>NEWS - Ilja Dragunov Injury Update</title><guid isPermaLink=\"false\">wcw-1</guid>"
        + "<pubDate>" + rfc(NOW - 1 * H, "EEE, dd MMM yyyy HH:mm:ss 'GMT'", "GMT") + "</pubDate>"
        + "<description><![CDATA[<p>Today's wrestling news &amp; more, including <b>Ilja</b>.</p>]]></description>"
        + "<enclosure url=\"http://cdn.example/wcw-1.mp3\" type=\"audio/mpeg\" length=\"1\"/><itunes:duration>1:02:03</itunes:duration>"
        + "<itunes:image href=\"https://a.example/ep1.jpg\"/></item>"
        // numeric offset, seconds duration, no guid (known by its address)
        + "<item><title>Raw Review</title>"
        + "<pubDate>" + rfc(NOW - 5 * H, "EEE, d MMM yyyy HH:mm:ss Z", "America/New_York") + "</pubDate>"
        + "<enclosure url=\"https://cdn.example/raw.mp3\" type=\"audio/mpeg\"/><itunes:duration>1800</itunes:duration></item>"
        // video, named zone, no day name
        + "<item><title>Video Show</title><guid>wcw-v</guid>"
        + "<pubDate>" + rfc(NOW - 30 * H, "d MMM yyyy HH:mm:ss zzz", "America/New_York") + "</pubDate>"
        + "<enclosure url=\"https://cdn.example/v.mp4\" type=\"video/mp4\"/></item>"
        // no enclosure: skipped
        + "<item><title>Text only</title><guid>wcw-t</guid><pubDate>" + rfc(NOW - 2 * H, "EEE, d MMM yyyy HH:mm:ss Z", "UTC") + "</pubDate></item>"
        // older than a week: dropped
        + "<item><title>Old</title><guid>wcw-old</guid><pubDate>" + rfc(NOW - 10 * 24 * H, "EEE, d MMM yyyy HH:mm:ss Z", "UTC") + "</pubDate>"
        + "<enclosure url=\"https://cdn.example/old.mp3\" type=\"audio/mpeg\"/></item>"
        + "</channel></rss>";
  }

  static String bigFeed() {
    StringBuilder sb = new StringBuilder("<rss xmlns:itunes=\"x\"><channel><title>Big</title>");
    for (int i = 0; i < 3000; i++) {
      sb.append("<item><title>Ep ").append(i).append("</title><guid>big-").append(i).append("</guid><pubDate>")
          .append(rfc(NOW - (i + 1) * 60000L, "EEE, d MMM yyyy HH:mm:ss Z", "UTC"))
          .append("</pubDate><enclosure url=\"https://cdn.example/big").append(i).append(".mp3\" type=\"audio/mpeg\"/>")
          .append("<description>").append("lorem ipsum ".repeat(200)).append("</description></item>");
    }
    return sb.append("</channel></rss>").toString();
  }

  public static void main(String[] args) throws Exception {
    final AtomicInteger aHits = new AtomicInteger(), a304 = new AtomicInteger();
    final boolean[] dDown = {false};
    final String big = bigFeed();
    HttpServer srv = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    srv.createContext("/a", ex -> {
      aHits.incrementAndGet();
      if ("\"v1\"".equals(ex.getRequestHeaders().getFirst("If-None-Match"))) {
        a304.incrementAndGet();
        ex.sendResponseHeaders(304, -1);
        ex.close();
        return;
      }
      byte[] b = feedA().getBytes(StandardCharsets.UTF_8);
      ex.getResponseHeaders().add("ETag", "\"v1\"");
      ex.getResponseHeaders().add("Content-Type", "application/rss+xml");
      ex.sendResponseHeaders(200, b.length);
      try (OutputStream o = ex.getResponseBody()) { o.write(b); }
    });
    srv.createContext("/moved", ex -> {
      ex.getResponseHeaders().add("Location", "/a2");
      ex.sendResponseHeaders(301, -1);
      ex.close();
    });
    srv.createContext("/a2", ex -> {
      byte[] b = feedA().replace("wcw-", "moved-").getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length);
      try (OutputStream o = ex.getResponseBody()) { o.write(b); }
    });
    srv.createContext("/big", ex -> {
      byte[] b = big.getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length);
      try (OutputStream o = ex.getResponseBody()) { o.write(b); }
    });
    srv.createContext("/d", ex -> {
      if (dDown[0]) { ex.sendResponseHeaders(500, -1); ex.close(); return; }
      byte[] b = feedA().replace("wcw-", "d-").getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length);
      try (OutputStream o = ex.getResponseBody()) { o.write(b); }
    });
    srv.start();
    String base = "http://127.0.0.1:" + srv.getAddress().getPort();

    File dir = Files.createTempDirectory("pf").toFile();
    Context c = new Context(dir);
    JSONArray subs = new JSONArray();
    subs.put(new JSONObject().put("collectionId", 111).put("collectionName", "WhatCulture Wrestling").put("feedUrl", base + "/a").put("artworkUrl", "https://art.example/111.jpg"));
    subs.put(new JSONObject().put("collectionId", 222).put("feedUrl", base + "/moved"));
    subs.put(new JSONObject().put("collectionId", 333).put("feedUrl", base + "/big"));
    subs.put(new JSONObject().put("collectionId", 444).put("feedUrl", base + "/d"));
    c.kv.put("radioPlayerPodcastSubs", subs.toString());

    check(PodcastFeeds.read(c).getLong("at") == 0, "nothing saved yet reads as empty");

    long t0 = System.currentTimeMillis();
    JSONObject r = PodcastFeeds.refreshAll(c);
    long took = System.currentTimeMillis() - t0;
    System.out.println("first refresh took " + took + " ms");
    JSONObject shows = r.getJSONObject("shows");
    check(r.getInt("ok") == 4 && r.getInt("total") == 4, "all four feeds read " + r.getInt("ok") + "/" + r.getInt("total"));

    JSONObject a = shows.getJSONObject("111");
    JSONArray ae = a.getJSONArray("eps");
    System.out.println(ae.toString(1));
    check(ae.length() == 3, "feed A: 3 episodes (no enclosure and over a week old left out): " + ae.length());
    JSONObject e0 = ae.getJSONObject(0);
    check("wcw-1".equals(e0.getString("g")) && e0.getString("n").startsWith("NEWS - Ilja"), "newest first, guid and title");
    check(e0.getString("u").equals("https://cdn.example/wcw-1.mp3"), "http enclosure upgraded to https like the page does");
    check(e0.getInt("t") == 3723, "h:m:s duration " + e0.getInt("t"));
    check(e0.getString("s").startsWith("Today's wrestling news & more, including Ilja."), "description as plain text: " + e0.getString("s"));
    check(e0.getString("f").equals("https://a.example/ep1.jpg"), "episode's own picture");
    check(Math.abs(PodcastFeeds.time(e0.getString("d")) - (NOW - H)) < 2000, "GMT date to ISO " + e0.getString("d"));
    JSONObject e1 = ae.getJSONObject(1);
    check(e1.getString("g").equals("https://cdn.example/raw.mp3") && e1.getInt("t") == 1800, "guid-less item known by its address; seconds duration");
    check(e1.getString("f").equals("https://art.example/111.jpg"), "no episode picture: the show's artwork");
    check(Math.abs(PodcastFeeds.time(e1.getString("d")) - (NOW - 5 * H)) < 2000, "numeric offset date " + e1.getString("d"));
    JSONObject e2 = ae.getJSONObject(2);
    check(e2.getInt("v") == 1 && e1.getInt("v") == 0, "video enclosure marked video");
    check(Math.abs(PodcastFeeds.time(e2.getString("d")) - (NOW - 30 * H)) < 2000, "named zone, no day name " + e2.getString("d"));

    JSONArray me = shows.getJSONObject("222").getJSONArray("eps");
    check(me.length() == 3 && me.getJSONObject(0).getString("g").equals("moved-1"), "redirected feed followed");
    JSONObject showB = shows.getJSONObject("222");
    check(showB.getJSONArray("eps").getJSONObject(0).getString("f").equals("https://a.example/ep1.jpg"), "redirected feed episode art");
    JSONArray be = shows.getJSONObject("333").getJSONArray("eps");
    check(be.length() == 40 && be.getJSONObject(0).getString("g").equals("big-0"), "3000-episode feed: only the newest 40 read (" + be.length() + ")");
    check(be.getJSONObject(0).getString("s").length() <= 200, "notes kept short");

    JSONObject saved = PodcastFeeds.read(c);
    check(saved.getLong("at") == r.getLong("at") && saved.getJSONObject("shows").length() == 4, "result saved for the next start");

    // second run: A unchanged (304) keeps its episodes; D down keeps its old ones
    dDown[0] = true;
    JSONObject r2 = PodcastFeeds.refreshAll(c);
    JSONObject s2 = r2.getJSONObject("shows");
    check(a304.get() == 1 && s2.getJSONObject("111").getJSONArray("eps").length() == 3 && s2.getJSONObject("111").getBoolean("ok"), "unchanged feed (304) keeps its episodes");
    check(!s2.getJSONObject("444").getBoolean("ok") && s2.getJSONObject("444").getJSONArray("eps").length() == 3, "unreachable feed keeps the episodes it had");
    check(r2.getInt("ok") == 3, "ok count " + r2.getInt("ok"));

    // a show saved without its feed address and unknown to Apple: reported, no crash
    subs.put(new JSONObject().put("collectionId", 1));
    c.kv.put("radioPlayerPodcastSubs", subs.toString());
    JSONObject r3 = PodcastFeeds.refreshAll(c);
    check(r3.getJSONObject("shows").has("1") && !r3.getJSONObject("shows").getJSONObject("1").getBoolean("ok"), "show without a feed address it can find: not ok, nothing else affected");
    check(r3.getInt("total") == 5, "total " + r3.getInt("total"));

    srv.stop(0);
    System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED");
    System.exit(fails == 0 ? 0 : 1);
  }
}
