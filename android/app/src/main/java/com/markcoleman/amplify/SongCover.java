package com.markcoleman.amplify;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.Locale;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Finds the cover of a song by artist and title (Deezer, then iTunes). Blocking: call it off the
 * main thread. Returns an https image address, or null when nothing fits.
 */
final class SongCover {
  private static final Pattern ALT =
      Pattern.compile("\\b(live|remix|acoustic|sped\\s*up|slowed|karaoke|instrumental|demo)\\b", Pattern.CASE_INSENSITIVE);

  private SongCover() {}

  static String find(String artist, String title) {
    String url = null;
    try {
      url = deezer(artist, title);
    } catch (Exception ignored) {
    }
    if (url == null) {
      try {
        url = itunes(artist, title);
      } catch (Exception ignored) {
      }
    }
    return url;
  }

  private static String norm(String s) {
    return s == null ? "" : s.toLowerCase(Locale.ROOT).replace("&", "and").replaceAll("[^a-z0-9]+", "");
  }

  private static boolean sameArtist(String want, String got) {
    String a = norm(want), b = norm(got);
    return !a.isEmpty() && !b.isEmpty() && (a.equals(b) || a.startsWith(b) || b.startsWith(a) || a.contains(b) || b.contains(a));
  }

  private static boolean sameTitle(String want, String got) {
    String a = norm(want.replaceAll("\\s*[\\(\\[].*?[\\)\\]]", "")), b = norm(got.replaceAll("\\s*[\\(\\[].*?[\\)\\]]", ""));
    return !a.isEmpty() && !b.isEmpty() && (a.equals(b) || b.startsWith(a) || a.startsWith(b));
  }

  private static String get(String address) throws Exception {
    HttpURLConnection c = (HttpURLConnection) new URL(address).openConnection();
    try {
      c.setConnectTimeout(6000);
      c.setReadTimeout(8000);
      c.setRequestProperty("User-Agent", "Amplify/1.0 (Android)");
      if (c.getResponseCode() != 200) {
        return null;
      }
      StringBuilder sb = new StringBuilder();
      try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"))) {
        String line;
        while ((line = r.readLine()) != null) {
          sb.append(line);
          if (sb.length() > 400000) {
            break;
          }
        }
      }
      return sb.toString();
    } finally {
      c.disconnect();
    }
  }

  private static String deezer(String artist, String title) throws Exception {
    String q = URLEncoder.encode("artist:\"" + artist + "\" track:\"" + title + "\"", "UTF-8");
    String body = get("https://api.deezer.com/search?limit=10&q=" + q);
    if (body == null) {
      return null;
    }
    JSONArray data = new JSONObject(body).optJSONArray("data");
    if (data == null) {
      return null;
    }
    String fallback = null;
    for (int i = 0; i < data.length(); i++) {
      JSONObject o = data.getJSONObject(i);
      JSONObject album = o.optJSONObject("album");
      JSONObject who = o.optJSONObject("artist");
      if (album == null || who == null || !sameArtist(artist, who.optString("name"))) {
        continue;
      }
      String cover = album.optString("cover_big", album.optString("cover_medium", ""));
      if (cover.isEmpty() || cover.contains("/images/cover//")) {
        continue;
      }
      String t = o.optString("title");
      if (!sameTitle(title, t)) {
        continue;
      }
      if (ALT.matcher(t + " " + album.optString("title")).find()) {
        if (fallback == null) {
          fallback = cover;
        }
        continue;
      }
      return cover;
    }
    return fallback;
  }

  private static String itunes(String artist, String title) throws Exception {
    String q = URLEncoder.encode(artist + " " + title, "UTF-8");
    String body = get("https://itunes.apple.com/search?media=music&entity=song&limit=10&term=" + q);
    if (body == null) {
      return null;
    }
    JSONArray results = new JSONObject(body).optJSONArray("results");
    if (results == null) {
      return null;
    }
    for (int i = 0; i < results.length(); i++) {
      JSONObject o = results.getJSONObject(i);
      String art = o.optString("artworkUrl100", "");
      if (art.isEmpty() || !sameArtist(artist, o.optString("artistName")) || !sameTitle(title, o.optString("trackName"))) {
        continue;
      }
      if (ALT.matcher(o.optString("trackName") + " " + o.optString("collectionName")).find()) {
        continue;
      }
      return art.replace("100x100bb", "600x600bb");
    }
    return null;
  }
}
