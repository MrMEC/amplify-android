package com.markcoleman.amplify;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Build 656 (Mark): which followed podcasts publish chapter markers, and which of those mark
 * their ad breaks, so a "Skip ad" button would work for them.
 *
 * <p>Plain Java (no Android classes) so it can be tested with javac. Reads the top of each
 * show's feed (its newest items), looks for Podcasting 2.0 {@code <podcast:chapters url=...>}
 * or Podlove {@code <psc:chapters>}, and, when the newest episode's chapters live in a separate
 * JSON file, reads that file for the chapter titles. A chapter counts as an ad when its title
 * names one (ad, sponsor, promo, commercial, mid-roll...).
 */
public final class ChapterCheck {
  /** How many of a feed's newest items are looked at. */
  static final int ITEMS = 10;
  private static final int FEED_MAX = 1536 * 1024;
  private static final int JSON_MAX = 512 * 1024;

  private ChapterCheck() {}

  /** One show's outcome. status: "ads", "chapters", "none" or "error". */
  public static final class Result {
    public String status = "none";
    public int scanned;
    public int withChapters;
    public int adChapters;
    public String error = "";
  }

  private static final Pattern ITEM = Pattern.compile("(?is)<item[\\s>].*?</item>");
  private static final Pattern PC_URL =
      Pattern.compile("(?is)<podcast:chapters\\b[^>]*?\\burl\\s*=\\s*[\"']([^\"']+)[\"']");
  private static final Pattern PSC_BLOCK = Pattern.compile("(?is)<psc:chapters\\b.*?</psc:chapters>");
  private static final Pattern PSC_TITLE =
      Pattern.compile("(?is)<psc:chapter\\b[^>]*?\\btitle\\s*=\\s*[\"']([^\"']*)[\"']");
  private static final Pattern JSON_TITLE = Pattern.compile("\"title\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"");
  private static final Pattern AD =
      Pattern.compile(
          "(?i)(^|[^a-z])(ads?|adverts?|advertisements?|advertising|sponsors?|sponsored|sponsorship|promos?|"
              + "promotions?|commercials?|ad ?break|mid-?roll|pre-?roll|post-?roll|word from our sponsors?)($|[^a-z])");

  /** Whether a chapter title names an ad break. */
  public static boolean isAdTitle(String title) {
    if (title == null) return false;
    String t = title.replace("&amp;", "&").trim();
    return !t.isEmpty() && AD.matcher(t).find();
  }

  /** The chapter titles in a Podcasting 2.0 chapters JSON file. */
  public static List<String> titlesFromJson(String json) {
    List<String> out = new ArrayList<>();
    if (json == null) return out;
    Matcher m = JSON_TITLE.matcher(json);
    while (m.find()) out.add(m.group(1).replace("\\\"", "\"").replace("\\/", "/"));
    return out;
  }

  /**
   * What a feed's newest items say about chapters. Returns the result plus, in urlOut[0], the
   * newest item's chapters JSON address when its chapters aren't written inline.
   */
  public static Result scanFeed(String xml, String[] urlOut) {
    Result r = new Result();
    if (urlOut != null && urlOut.length > 0) urlOut[0] = "";
    if (xml == null) return r;
    Matcher items = ITEM.matcher(xml);
    boolean newestDone = false;
    while (r.scanned < ITEMS && items.find()) {
      String item = items.group();
      r.scanned++;
      Matcher pc = PC_URL.matcher(item);
      Matcher psc = PSC_BLOCK.matcher(item);
      boolean has = false;
      if (psc.find()) {
        has = true;
        if (!newestDone) {
          Matcher t = PSC_TITLE.matcher(psc.group());
          while (t.find()) if (isAdTitle(t.group(1))) r.adChapters++;
          newestDone = true;
        }
      }
      if (pc.find()) {
        has = true;
        if (!newestDone && urlOut != null && urlOut.length > 0) {
          urlOut[0] = pc.group(1).replace("&amp;", "&").trim();
          newestDone = true;
        }
      }
      if (has) r.withChapters++;
    }
    r.status = r.adChapters > 0 ? "ads" : r.withChapters > 0 ? "chapters" : "none";
    return r;
  }

  /** Reads one show's feed (and its newest chapters file) and says what it found. */
  public static Result check(String feedUrl) {
    Result r;
    try {
      if (feedUrl == null || feedUrl.trim().isEmpty()) throw new Exception("no feed address");
      String xml = fetch(feedUrl.trim(), FEED_MAX);
      String[] url = {""};
      r = scanFeed(xml, url);
      if (!url[0].isEmpty()) {
        try {
          for (String t : titlesFromJson(fetch(url[0], JSON_MAX))) if (isAdTitle(t)) r.adChapters++;
        } catch (Exception ignored) {
          // chapters exist even if their file can't be read
        }
        if (r.adChapters > 0) r.status = "ads";
      }
    } catch (Exception e) {
      r = new Result();
      r.status = "error";
      r.error = String.valueOf(e.getMessage());
    }
    return r;
  }

  /** GET with redirects followed by hand (http and https), reading at most max bytes. */
  static String fetch(String url, int max) throws Exception {
    String u = url;
    for (int hop = 0; hop < 6; hop++) {
      HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
      c.setInstanceFollowRedirects(false);
      c.setConnectTimeout(15000);
      c.setReadTimeout(20000);
      c.setRequestProperty("User-Agent", "Amplify/1.0 (Android) chapter check");
      c.setRequestProperty("Accept", "application/rss+xml, application/xml, application/json, text/xml, */*");
      int code = c.getResponseCode();
      if (code >= 300 && code < 400) {
        String loc = c.getHeaderField("Location");
        c.disconnect();
        if (loc == null) throw new Exception("redirect without Location");
        u = new URL(new URL(u), loc).toString();
        continue;
      }
      if (code < 200 || code >= 300) {
        c.disconnect();
        throw new Exception("HTTP " + code);
      }
      try (InputStream in = c.getInputStream()) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        int n;
        while ((n = in.read(buf)) > 0) {
          out.write(buf, 0, n);
          if (out.size() >= max) break;
        }
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
      } finally {
        c.disconnect();
      }
    }
    throw new Exception("too many redirects");
  }
}
