package com.markcoleman.amplify;

import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.util.UnstableApi;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * The Android Auto menu. The page works out every list (Favorites, Recent Stations, For You,
 * Top Stations, podcasts...) and saves them here as one JSON snapshot -- the "catalog" -- so
 * the car can browse and play even when the page isn't running. Only a show's own episode
 * list is fetched here, live from Apple's podcast directory.
 *
 * Node ids: fixed ones ("tab:home", "st:recent", ...), "fy:<id>" (a For You search),
 * "cat:<id>" (a podcast category), "show:<collectionId>". A playable item's id is
 * "<node>|<index>|<key>", which is what lets a tap queue up the rest of that list.
 */
@OptIn(markerClass = UnstableApi.class)
final class CarLibrary {

  static final String ROOT = "root";
  static final String EXTRA_GUID = "amplify.guid";
  static final String EXTRA_LIVE = "amplify.live";
  static final String EXTRA_RECORD = "amplify.record";

  // Keys Android Auto reads off browse items (the same values as androidx.media MediaConstants).
  private static final String STYLE_SUPPORTED = "android.media.browse.CONTENT_STYLE_SUPPORTED";
  private static final String STYLE_BROWSABLE = "android.media.browse.CONTENT_STYLE_BROWSABLE_HINT";
  private static final String STYLE_PLAYABLE = "android.media.browse.CONTENT_STYLE_PLAYABLE_HINT";
  private static final String STYLE_GROUP = "android.media.browse.CONTENT_STYLE_GROUP_TITLE_HINT";
  private static final String PLAYBACK_STATUS = "android.media.extra.PLAYBACK_STATUS";
  private static final String COMPLETION_PCT =
      "androidx.media.MediaItem.Extras.COMPLETION_PERCENTAGE";
  private static final int STYLE_LIST = 1;
  private static final int STYLE_GRID = 2;

  private static final String PLACEHOLDER = "Coming in the next update";
  private static final long SHOW_CACHE_MS = 30 * 60 * 1000L;

  private final Context ctx;
  private JSONObject catalog = new JSONObject();
  private final Map<String, CachedShow> showCache = new ConcurrentHashMap<>();

  private static final class CachedShow {
    final long at;
    final List<JSONObject> items;

    CachedShow(List<JSONObject> items) {
      this.at = System.currentTimeMillis();
      this.items = items;
    }
  }

  CarLibrary(Context c) {
    ctx = c.getApplicationContext();
    reload();
  }

  // ---------------- catalog file ----------------

  static File catalogFile(Context c) {
    return new File(c.getFilesDir(), "car_catalog.json");
  }

  static void saveCatalog(Context c, String json) throws Exception {
    new JSONObject(json); // refuse anything that isn't valid JSON
    File dest = catalogFile(c);
    File part = new File(dest.getPath() + ".part");
    try (FileOutputStream out = new FileOutputStream(part)) {
      out.write(json.getBytes(StandardCharsets.UTF_8));
    }
    if (!part.renameTo(dest)) throw new Exception("Could not save the car menu");
  }

  synchronized void reload() {
    try {
      catalog = new JSONObject(readFile(catalogFile(ctx)));
    } catch (Exception e) {
      catalog = new JSONObject();
    }
  }

  synchronized double podcastSpeed() {
    double s = catalog.optDouble("podcastSpeed", 1.0);
    return s > 0.2 && s < 4 ? s : 1.0;
  }

  // ---------------- tree ----------------

  private static final Map<String, String> TITLES = new LinkedHashMap<>();
  private static final Map<String, String[]> FIXED = new LinkedHashMap<>();
  private static final Map<String, String> LIST_OF = new LinkedHashMap<>();
  private static final Map<String, String> ICONS = new LinkedHashMap<>();

  static {
    TITLES.put("tab:home", "Home");
    TITLES.put("tab:library", "Library");
    TITLES.put("tab:stations", "Stations");
    TITLES.put("tab:podcasts", "Podcasts");
    TITLES.put("home:favorites", "Favorites");
    TITLES.put("home:topartists", "Top Artists");
    TITLES.put("home:continue", "Continue Listening");
    TITLES.put("home:recentsongs", "Recent Songs");
    TITLES.put("home:latest", "Latest Podcasts");
    TITLES.put("home:topstations", "Top Stations");
    TITLES.put("lib:artists", "Artists");
    TITLES.put("lib:albums", "Albums");
    TITLES.put("lib:songs", "Songs");
    TITLES.put("lib:playlists", "Playlists");
    TITLES.put("lib:genres", "Genres");
    TITLES.put("st:foryou", "For You");
    TITLES.put("st:recent", "Recent Stations");
    TITLES.put("st:top", "Top Stations");
    TITLES.put("pod:latest", "Latest");
    TITLES.put("pod:az", "A-Z");
    TITLES.put("pod:popular", "Popular");

    FIXED.put(ROOT, new String[] {"tab:home", "tab:library", "tab:stations", "tab:podcasts"});
    FIXED.put(
        "tab:home",
        new String[] {
          "home:favorites", "home:topartists", "home:continue", "home:recentsongs",
          "home:latest", "home:topstations"
        });
    FIXED.put(
        "tab:library",
        new String[] {"lib:artists", "lib:albums", "lib:songs", "lib:playlists", "lib:genres"});
    FIXED.put("tab:stations", new String[] {"st:foryou", "st:recent", "st:top"});

    LIST_OF.put("home:favorites", "favorites");
    LIST_OF.put("home:continue", "continue");
    LIST_OF.put("home:latest", "podLatest");
    LIST_OF.put("home:topstations", "topStations");
    LIST_OF.put("st:recent", "recentStations");
    LIST_OF.put("st:top", "topStations");
    LIST_OF.put("pod:latest", "podLatest");
    LIST_OF.put("pod:az", "shows");
    LIST_OF.put("pod:popular", "popular");

    ICONS.put("tab:home", "ic_car_home");
    ICONS.put("tab:library", "ic_car_library");
    ICONS.put("tab:stations", "ic_car_stations");
    ICONS.put("tab:podcasts", "ic_car_podcasts");
  }

  static Bundle rootExtras() {
    Bundle b = new Bundle();
    b.putBoolean(STYLE_SUPPORTED, true);
    b.putInt(STYLE_BROWSABLE, STYLE_LIST);
    b.putInt(STYLE_PLAYABLE, STYLE_LIST);
    return b;
  }

  MediaItem rootItem() {
    return folder(ROOT, "Amplify", null, null);
  }

  /** Browse item for a node id, or null if it doesn't exist (any more). */
  @Nullable
  synchronized MediaItem node(String id) {
    if (ROOT.equals(id)) return rootItem();
    String t = TITLES.get(id);
    if (t != null) return folder(id, t, null, iconUri(id));
    if (id.startsWith("fy:")) {
      JSONObject s = findIn("forYou", id.substring(3));
      return s == null ? null : folder(id, s.optString("label", "Search"), null, null);
    }
    if (id.startsWith("cat:")) {
      JSONObject c = findIn("categories", id.substring(4));
      return c == null ? null : folder(id, c.optString("name", "Category"), null, null);
    }
    if (id.startsWith("show:")) {
      JSONObject sh = findShow(id.substring(5));
      if (sh != null) return showFolder(sh);
      return folder(id, "Podcast", null, null);
    }
    return null;
  }

  /** Children of a browsable node. May go to the network (a show's episodes). */
  List<MediaItem> children(String id) {
    List<MediaItem> out = new ArrayList<>();
    String[] fixed = FIXED.get(id);
    if (fixed != null) {
      for (String c : fixed) {
        MediaItem n = node(c);
        if (n != null) out.add(n);
      }
      return out;
    }
    if ("tab:podcasts".equals(id)) {
      out.add(node("pod:latest"));
      synchronized (this) {
        JSONArray cats = catalog.optJSONArray("categories");
        if (cats != null) {
          for (int i = 0; i < cats.length(); i++) {
            JSONObject c = cats.optJSONObject(i);
            if (c != null) out.add(folder("cat:" + c.optString("id"), c.optString("name"), null, null));
          }
        }
      }
      out.add(node("pod:az"));
      out.add(node("pod:popular"));
      return out;
    }
    if ("st:foryou".equals(id)) {
      synchronized (this) {
        JSONArray fy = catalog.optJSONArray("forYou");
        if (fy != null) {
          for (int i = 0; i < fy.length(); i++) {
            JSONObject s = fy.optJSONObject(i);
            if (s != null) out.add(folder("fy:" + s.optString("id"), s.optString("label"), null, null));
          }
        }
      }
      if (out.isEmpty()) out.add(message("No saved searches yet. Add one in Stations on your phone."));
      return out;
    }
    if (id.startsWith("home:") || id.startsWith("lib:")) {
      if (!LIST_OF.containsKey(id)) {
        out.add(message(PLACEHOLDER));
        return out;
      }
    }
    List<JSONObject> items = listItems(id);
    for (int i = 0; i < items.size(); i++) {
      MediaItem m = toBrowseItem(id, i, items.get(i));
      if (m != null) out.add(m);
    }
    if (out.isEmpty()) out.add(message(emptyMessage(id)));
    return out;
  }

  private static String emptyMessage(String id) {
    switch (id) {
      case "home:favorites":
        return "No favorite stations or episodes yet.";
      case "home:continue":
        return "Nothing in progress.";
      case "st:recent":
        return "Stations you play will show up here.";
      case "pod:az":
        return "You aren't following any podcasts yet.";
      case "pod:popular":
        return "Open Podcasts > Popular on your phone once to load this list.";
      default:
        if (id.startsWith("show:")) return "Couldn't load this show's episodes.";
        return "Nothing here yet. Open Amplify on your phone to refresh.";
    }
  }

  /** The raw entries behind a list node (from the catalog, or fetched for a show). */
  List<JSONObject> listItems(String id) {
    if (id.startsWith("show:")) return showEpisodes(id.substring(5));
    String key = LIST_OF.get(id);
    if (key == null && (id.startsWith("fy:") || id.startsWith("cat:"))) key = id;
    if (key == null) return Collections.emptyList();
    synchronized (this) {
      JSONObject lists = catalog.optJSONObject("lists");
      JSONArray arr = lists == null ? null : lists.optJSONArray(key);
      List<JSONObject> out = new ArrayList<>();
      if (arr == null) return out;
      for (int i = 0; i < arr.length(); i++) {
        JSONObject o = arr.optJSONObject(i);
        if (o != null) out.add(o);
      }
      return out;
    }
  }

  // ---------------- items ----------------

  @Nullable
  private MediaItem toBrowseItem(String node, int index, JSONObject e) {
    String kind = e.optString("t");
    if ("show".equals(kind)) return showFolder(e);
    if (!"station".equals(kind) && !"episode".equals(kind)) return null;
    if (e.optString("url").isEmpty()) return null;
    return playable(node, index, e, null);
  }

  /** A playable item. With progress (car-side), a partly-played episode shows its bar. */
  MediaItem playable(String node, int index, JSONObject e, @Nullable JSONObject progress) {
    String kind = e.optString("t");
    boolean episode = "episode".equals(kind);
    String key = e.optString("k", String.valueOf(index));
    String url = e.optString("url");
    Bundle extras = new Bundle();
    extras.putBoolean(EXTRA_LIVE, !episode);
    if (episode) {
      extras.putString(EXTRA_GUID, e.optString("guid"));
      JSONObject rec = e.optJSONObject("rec");
      if (rec != null) extras.putString(EXTRA_RECORD, rec.toString());
      double pos = e.optDouble("pos", 0);
      double dur = e.optDouble("dur", 0);
      if (progress != null) {
        pos = progress.optDouble("positionSec", pos);
        dur = progress.optDouble("durationSec", dur);
      }
      if (e.optBoolean("done")) {
        extras.putInt(PLAYBACK_STATUS, 2);
      } else if (pos > 5 && dur > 0) {
        extras.putInt(PLAYBACK_STATUS, 1);
        extras.putDouble(COMPLETION_PCT, Math.min(1.0, pos / dur));
      } else {
        extras.putInt(PLAYBACK_STATUS, 0);
      }
    }
    String group = e.optString("g");
    if (!group.isEmpty()) extras.putString(STYLE_GROUP, group);
    MediaMetadata md =
        new MediaMetadata.Builder()
            .setTitle(e.optString("title", episode ? "Episode" : "Station"))
            .setArtist(emptyToNull(e.optString("sub")))
            .setStation(episode ? null : e.optString("title"))
            .setArtworkUri(ArtProvider.uriFor(e.optString("art")))
            .setIsPlayable(true)
            .setIsBrowsable(false)
            .setMediaType(
                episode ? MediaMetadata.MEDIA_TYPE_PODCAST_EPISODE : MediaMetadata.MEDIA_TYPE_RADIO_STATION)
            .setExtras(extras)
            .build();
    MediaItem.Builder b =
        new MediaItem.Builder().setMediaId(node + "|" + index + "|" + key).setMediaMetadata(md).setUri(url);
    if (url.toLowerCase(Locale.ROOT).contains(".m3u8")) b.setMimeType(MimeTypes.APPLICATION_M3U8);
    return b.build();
  }

  private MediaItem showFolder(JSONObject sh) {
    String cid = sh.optString("cid");
    return folder("show:" + cid, sh.optString("title", "Podcast"), emptyToNull(sh.optString("sub")),
        ArtProvider.uriFor(sh.optString("art")));
  }

  private static MediaItem folder(String id, String title, @Nullable String sub, @Nullable Uri art) {
    MediaMetadata md =
        new MediaMetadata.Builder()
            .setTitle(title)
            .setArtist(sub)
            .setArtworkUri(art)
            .setIsBrowsable(true)
            .setIsPlayable(false)
            .setMediaType(MediaMetadata.MEDIA_TYPE_FOLDER_MIXED)
            .build();
    return new MediaItem.Builder().setMediaId(id).setMediaMetadata(md).build();
  }

  private static int messageSeq = 0;

  private static MediaItem message(String text) {
    MediaMetadata md =
        new MediaMetadata.Builder().setTitle(text).setIsBrowsable(false).setIsPlayable(false).build();
    return new MediaItem.Builder().setMediaId("msg:" + (messageSeq++)).setMediaMetadata(md).build();
  }

  @Nullable
  private Uri iconUri(String id) {
    String name = ICONS.get(id);
    if (name == null) return null;
    return Uri.parse("android.resource://" + ctx.getPackageName() + "/drawable/" + name);
  }

  // ---------------- playing a tapped item ----------------

  /** The list a playable id belongs to and its position, or null for a non-playable id. */
  @Nullable
  static String[] parsePlayableId(@Nullable String mediaId) {
    if (mediaId == null) return null;
    String[] p = mediaId.split("\\|", 3);
    return p.length == 3 ? p : null;
  }

  /**
   * Everything playable in that item's list, ready for ExoPlayer, with the index to start at.
   * Runs on a background thread: it may fetch a show's episodes or resolve a .pls link.
   */
  @Nullable
  Queue queueFor(String mediaId) {
    String[] p = parsePlayableId(mediaId);
    if (p == null) return null;
    String node = p[0];
    int wantIndex;
    try {
      wantIndex = Integer.parseInt(p[1]);
    } catch (NumberFormatException e) {
      wantIndex = 0;
    }
    String wantKey = p[2];
    List<JSONObject> raw = listItems(node);
    JSONObject progress = CarProgress.readAll(ctx);
    List<MediaItem> items = new ArrayList<>();
    List<Long> starts = new ArrayList<>();
    int start = -1, byIndex = -1;
    for (int i = 0; i < raw.size(); i++) {
      JSONObject e = raw.get(i);
      String kind = e.optString("t");
      if (!"station".equals(kind) && !"episode".equals(kind)) continue;
      if (e.optString("url").isEmpty()) continue;
      JSONObject pr = "episode".equals(kind) ? progress.optJSONObject(e.optString("guid")) : null;
      String key = e.optString("k", String.valueOf(i));
      if (key.equals(wantKey) && start < 0) start = items.size();
      if (i == wantIndex) byIndex = items.size();
      MediaItem m = playable(node, i, e, pr);
      if ("station".equals(kind)) m = resolvePlaylist(m);
      items.add(m);
      double pos = pr != null ? pr.optDouble("positionSec", e.optDouble("pos", 0)) : e.optDouble("pos", 0);
      boolean done = pr != null ? pr.optBoolean("completed", false) : e.optBoolean("done", false);
      starts.add("episode".equals(kind) && pos > 5 && !done ? (long) (pos * 1000) : 0L);
    }
    if (items.isEmpty()) return null;
    if (start < 0) start = byIndex >= 0 ? byIndex : 0;
    return new Queue(items, start, starts.get(start));
  }

  static final class Queue {
    final List<MediaItem> items;
    final int startIndex;
    final long startPositionMs;

    Queue(List<MediaItem> items, int startIndex, long startPositionMs) {
      this.items = items;
      this.startIndex = startIndex;
      this.startPositionMs = startPositionMs;
    }
  }

  /** A .pls/.m3u station link is a small text file naming the real stream; ExoPlayer needs that. */
  private static MediaItem resolvePlaylist(MediaItem m) {
    if (m.localConfiguration == null) return m;
    String url = m.localConfiguration.uri.toString();
    String path = m.localConfiguration.uri.getPath();
    String lp = path == null ? "" : path.toLowerCase(Locale.ROOT);
    if (!lp.endsWith(".pls") && !lp.endsWith(".m3u")) return m;
    try {
      String body = httpGet(url, 64 * 1024);
      for (String line : body.split("\\r?\\n")) {
        String l = line.trim();
        int eq = l.indexOf('=');
        if (l.toLowerCase(Locale.ROOT).startsWith("file") && eq > 0) l = l.substring(eq + 1).trim();
        if (l.startsWith("http://") || l.startsWith("https://")) {
          return m.buildUpon().setUri(l).build();
        }
      }
    } catch (Exception ignored) {
      // Try the link as it is.
    }
    return m;
  }

  // ---------------- podcast shows (live from Apple's directory) ----------------

  @Nullable
  private synchronized JSONObject findShow(String cid) {
    JSONObject lists = catalog.optJSONObject("lists");
    if (lists == null) return null;
    for (String k : new String[] {"shows", "popular"}) {
      JSONArray arr = lists.optJSONArray(k);
      if (arr == null) continue;
      for (int i = 0; i < arr.length(); i++) {
        JSONObject o = arr.optJSONObject(i);
        if (o != null && cid.equals(o.optString("cid"))) return o;
      }
    }
    return null;
  }

  private List<JSONObject> showEpisodes(String cid) {
    CachedShow c = showCache.get(cid);
    if (c != null && System.currentTimeMillis() - c.at < SHOW_CACHE_MS) return c.items;
    List<JSONObject> out = new ArrayList<>();
    try {
      String url =
          "https://itunes.apple.com/lookup?id=" + URLEncoder.encode(cid, "UTF-8")
              + "&entity=podcastEpisode&limit=40";
      JSONObject data = new JSONObject(httpGet(url, 4 * 1024 * 1024));
      JSONArray res = data.optJSONArray("results");
      JSONObject progress = CarProgress.readAll(ctx);
      if (res != null) {
        for (int i = 0; i < res.length(); i++) {
          JSONObject r = res.optJSONObject(i);
          if (r == null || !"podcastEpisode".equals(r.optString("wrapperType"))) continue;
          if ("Video".equals(r.optString("episodeContentType"))) continue;
          String epUrl = r.optString("episodeUrl", r.optString("previewUrl", ""));
          if (epUrl.isEmpty()) continue;
          String guid = r.optString("episodeGuid", epUrl);
          String art = firstNonEmpty(r, "artworkUrl600", "artworkUrl160", "artworkUrl100", "artworkUrl60");
          double dur = r.optLong("trackTimeMillis", 0) / 1000.0;
          JSONObject rec = new JSONObject();
          rec.put("guid", guid);
          rec.put("collectionId", r.opt("collectionId"));
          rec.put("collectionName", r.optString("collectionName"));
          rec.put("artistName", r.optString("artistName"));
          rec.put("trackName", r.optString("trackName", "Untitled episode"));
          rec.put("artworkUrl", art);
          rec.put("releaseDate", r.optString("releaseDate"));
          rec.put("durationSec", dur);
          rec.put("episodeUrl", epUrl);
          rec.put("description", "");
          JSONObject e = new JSONObject();
          e.put("t", "episode");
          e.put("k", "podcast:" + guid);
          e.put("guid", guid);
          e.put("title", r.optString("trackName", "Untitled episode"));
          e.put("sub", r.optString("collectionName"));
          e.put("art", art);
          e.put("url", epUrl);
          e.put("dur", dur);
          JSONObject pr = progress.optJSONObject(guid);
          if (pr != null) {
            e.put("pos", pr.optDouble("positionSec", 0));
            e.put("done", pr.optBoolean("completed", false));
          }
          e.put("rec", rec);
          out.add(e);
        }
      }
      showCache.put(cid, new CachedShow(out));
    } catch (Exception ignored) {
      if (c != null) return c.items; // an older list beats none
    }
    return out;
  }

  // ---------------- helpers ----------------

  @Nullable
  private synchronized JSONObject findIn(String arrayKey, String id) {
    JSONArray arr = catalog.optJSONArray(arrayKey);
    if (arr == null) return null;
    for (int i = 0; i < arr.length(); i++) {
      JSONObject o = arr.optJSONObject(i);
      if (o != null && id.equals(o.optString("id"))) return o;
    }
    return null;
  }

  private static String firstNonEmpty(JSONObject o, String... keys) {
    for (String k : keys) {
      String v = o.optString(k, "");
      if (!v.isEmpty()) return v;
    }
    return "";
  }

  @Nullable
  private static String emptyToNull(@Nullable String s) {
    return s == null || s.isEmpty() ? null : s;
  }

  static String readFile(File f) throws Exception {
    try (InputStream in = new FileInputStream(f)) {
      return readAll(in, Integer.MAX_VALUE);
    }
  }

  private static String readAll(InputStream in, int max) throws Exception {
    StringBuilder b = new StringBuilder();
    try (BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
      char[] buf = new char[8192];
      int n;
      while ((n = r.read(buf)) > 0) {
        b.append(buf, 0, n);
        if (b.length() > max) break;
      }
    }
    return b.toString();
  }

  static String httpGet(String url, int max) throws Exception {
    HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
    try {
      c.setConnectTimeout(8000);
      c.setReadTimeout(12000);
      c.setRequestProperty("User-Agent", "Amplify/1.0 (Android)");
      if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
      return readAll(c.getInputStream(), max);
    } finally {
      c.disconnect();
    }
  }
}
