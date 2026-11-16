package com.markcoleman.amplify;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;

public class ChapterCheckTest {
  static int fails = 0;

  static void check(boolean ok, String what) {
    System.out.println((ok ? "ok   " : "FAIL ") + what);
    if (!ok) fails++;
  }

  static String item(String extra) {
    return "<item><title>Ep</title><enclosure url=\"https://x/a.mp3\" type=\"audio/mpeg\"/>" + extra + "</item>";
  }

  public static void main(String[] a) throws Exception {
    // Titles
    check(ChapterCheck.isAdTitle("Ad break"), "Ad break is an ad");
    check(ChapterCheck.isAdTitle("Sponsor: Athletic Greens"), "Sponsor is an ad");
    check(ChapterCheck.isAdTitle("A word from our sponsors"), "word from our sponsors");
    check(ChapterCheck.isAdTitle("Mid-roll"), "Mid-roll");
    check(ChapterCheck.isAdTitle("ADS"), "ADS upper case");
    check(!ChapterCheck.isAdTitle("Adam's story"), "Adam is not an ad");
    check(!ChapterCheck.isAdTitle("Bad news headlines"), "Bad is not an ad");
    check(!ChapterCheck.isAdTitle("Intro"), "Intro is not an ad");
    check(!ChapterCheck.isAdTitle("Roadside promotional... no"), "promotional is not promo");

    // JSON titles
    List<String> t = ChapterCheck.titlesFromJson(
        "{\"version\":\"1.2.0\",\"chapters\":[{\"startTime\":0,\"title\":\"Intro\"},{\"startTime\":60,\"title\":\"Sponsor \\\"X\\\"\"}]}");
    check(t.size() == 2 && t.get(1).equals("Sponsor \"X\""), "titles from JSON: " + t);

    // Feeds
    String[] u = {""};
    ChapterCheck.Result r = ChapterCheck.scanFeed("<rss><channel>" + item("") + item("") + "</channel></rss>", u);
    check(r.status.equals("none") && r.scanned == 2 && r.withChapters == 0 && u[0].isEmpty(), "no chapters");

    r = ChapterCheck.scanFeed("<rss><channel>"
        + item("<podcast:chapters url=\"https://c/1.json?a=1&amp;b=2\" type=\"application/json+chapters\"/>")
        + item("<podcast:chapters url=\"https://c/0.json\"/>") + "</channel></rss>", u);
    check(r.status.equals("chapters") && r.withChapters == 2 && u[0].equals("https://c/1.json?a=1&b=2"), "podcast:chapters url, newest " + u[0]);

    r = ChapterCheck.scanFeed("<rss><channel>"
        + item("<psc:chapters version=\"1.2\"><psc:chapter start=\"00:00\" title=\"Intro\"/><psc:chapter start=\"05:00\" title=\"Ad Break\"/></psc:chapters>")
        + "</channel></rss>", u);
    check(r.status.equals("ads") && r.adChapters == 1, "psc inline ad chapter");

    r = ChapterCheck.scanFeed("<rss><channel>"
        + item("<psc:chapters><psc:chapter start=\"0\" title=\"Intro\"/></psc:chapters>") + "</channel></rss>", u);
    check(r.status.equals("chapters"), "psc inline, no ad");

    StringBuilder many = new StringBuilder("<rss><channel>");
    for (int i = 0; i < 30; i++) many.append(item(i == 20 ? "<podcast:chapters url=\"https://c/x.json\"/>" : ""));
    r = ChapterCheck.scanFeed(many.append("</channel></rss>").toString(), u);
    check(r.scanned == ChapterCheck.ITEMS && r.status.equals("none"), "only the newest " + ChapterCheck.ITEMS + " items");

    // Over the network: feed + chapters file, a redirect, and an error.
    HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    int port = s.getAddress().getPort();
    String base = "http://127.0.0.1:" + port;
    s.createContext("/feed", ex -> {
      byte[] b = ("<rss><channel>" + item("<podcast:chapters url=\"" + base + "/ch.json\"/>") + "</channel></rss>").getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); ex.close();
    });
    s.createContext("/feed2", ex -> {
      byte[] b = ("<rss><channel>" + item("<podcast:chapters url=\"" + base + "/plain.json\"/>") + "</channel></rss>").getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); ex.close();
    });
    s.createContext("/ch.json", ex -> {
      byte[] b = "{\"chapters\":[{\"startTime\":0,\"title\":\"Cold open\"},{\"startTime\":300,\"title\":\"Sponsored segment\"}]}".getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); ex.close();
    });
    s.createContext("/plain.json", ex -> {
      byte[] b = "{\"chapters\":[{\"startTime\":0,\"title\":\"Part one\"}]}".getBytes(StandardCharsets.UTF_8);
      ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); ex.close();
    });
    s.createContext("/moved", ex -> { ex.getResponseHeaders().add("Location", "/feed"); ex.sendResponseHeaders(301, -1); ex.close(); });
    s.createContext("/gone", ex -> { ex.sendResponseHeaders(404, -1); ex.close(); });
    s.start();
    try {
      r = ChapterCheck.check(base + "/moved");
      check(r.status.equals("ads") && r.adChapters == 1, "network: redirect, chapters file with a sponsor -> ads (" + r.status + ")");
      r = ChapterCheck.check(base + "/feed2");
      check(r.status.equals("chapters"), "network: chapters without ads (" + r.status + ")");
      r = ChapterCheck.check(base + "/gone");
      check(r.status.equals("error") && r.error.contains("404"), "network: 404 -> error (" + r.error + ")");
      r = ChapterCheck.check("");
      check(r.status.equals("error"), "empty address -> error");
    } finally {
      s.stop(0);
    }
    System.out.println(fails == 0 ? "ALL PASS" : fails + " FAILED");
    if (fails > 0) System.exit(1);
  }
}
