package com.markcoleman.amplify;

import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import androidx.annotation.OptIn;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.util.UnstableApi;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * The Android Auto menu. The page works out every list (Favorites, Recent Stations, For You, Top
 * Stations, podcasts...) and saves them here as one JSON snapshot -- the "catalog" -- so the car
 * can browse and play even when the page isn't running. Only a show's own episode list is fetched
 * here, live from Apple's podcast directory.
 *
 * <p>Node ids: fixed ones ("tab:home", "st:recent", ...), "fy:<id>" (a For You search), "cat:<id>"
 * (a podcast category), "show:<collectionId>". A playable item's id is "<node>|<index>|<key>",
 * which is what lets a tap queue up the rest of that list.
 */
@OptIn(markerClass = UnstableApi.class)
final class CarLibrary {
  private static final String COMPLETION_PCT =
      "androidx.media.MediaItem.Extras.COMPLETION_PERCENTAGE";
  static final String EXTRA_GUID = "amplify.guid";
  static final String EXTRA_ITEM = "amplify.item";
  static final String EXTRA_LIVE = "amplify.live";
  static final String EXTRA_PLACE = "amplify.place";
  static final String EXTRA_RECORD = "amplify.record";
  private static final Map<String, String[]> FIXED;
  private static final Map<String, String> ICONS;
  private static final Map<String, String> LIST_OF;
  private static final long NET_CACHE_MS = 1800000;
  private static final String NO_SONGS =
      "No songs yet. On your phone, open Amplify, tap Add folder and pick your music folder.";
  private static final String PLAYBACK_STATUS = "android.media.extra.PLAYBACK_STATUS";
  private static final int QUEUE_AFTER = 250;
  private static final int QUEUE_BEFORE = 50;
  private static final int RECENT_SEARCHES = 12;
  static final String ROOT = "root";
  private static final String SEARCH_SUPPORTED = "android.media.browse.SEARCH_SUPPORTED";
  private static final String STYLE_BROWSABLE = "android.media.browse.CONTENT_STYLE_BROWSABLE_HINT";
  private static final int STYLE_GRID = 2;
  private static final String STYLE_GROUP = "android.media.browse.CONTENT_STYLE_GROUP_TITLE_HINT";
  private static final int STYLE_LIST = 1;
  private static final String STYLE_PLAYABLE = "android.media.browse.CONTENT_STYLE_PLAYABLE_HINT";
  private static final String STYLE_SUPPORTED = "android.media.browse.CONTENT_STYLE_SUPPORTED";
  private static final Map<String, String> TITLES;
  private static int messageSeq;
  private final Context ctx;
  private JSONObject catalog = new JSONObject();
  private JSONObject library = new JSONObject();
  private JSONObject tracks = new JSONObject();
  private final Map<String, JSONObject> albumsByKey = new HashMap();
  private final Map<String, JSONObject> artistsByKey = new HashMap();
  private final Map<String, CachedList> netCache = new ConcurrentHashMap();
  private final Map<String, List<JSONObject>> adhoc =
      Collections.synchronizedMap(
          new LinkedHashMap<String, List<JSONObject>>(
              16, 0.75f, true) { // from class: com.markcoleman.amplify.CarLibrary.1
            @Override // java.util.LinkedHashMap
            protected boolean removeEldestEntry(Map.Entry<String, List<JSONObject>> entry) {
              return size() > 24;
            }
          });
  private final Map<String, JSONObject> extraShows = new ConcurrentHashMap();
  private volatile int rootLimit = 4;

  private static final class CachedList {
    final long at = System.currentTimeMillis();
    final List<JSONObject> items;

    CachedList(List<JSONObject> list) {
      this.items = list;
    }

    boolean fresh() {
      return System.currentTimeMillis() - this.at < 1800000;
    }
  }

  CarLibrary(Context context) {
    this.ctx = context.getApplicationContext();
  }

  static File catalogFile(Context context) {
    return new File(context.getFilesDir(), "car_catalog.json");
  }

  static File libraryFile(Context context) {
    return new File(context.getFilesDir(), "car_library.json");
  }

  static void saveCatalog(Context context, String str) throws Exception {
    saveJson(catalogFile(context), str);
  }

  static void saveLibrary(Context context, String str) throws Exception {
    saveJson(libraryFile(context), str);
  }

  private static void saveJson(File f, String json) throws Exception {
    String t = json.trim();
    if (!t.startsWith("{") || !t.endsWith("}")) throw new Exception("Not a car menu");
    File part = new File(f.getPath() + ".part");
    try (FileOutputStream out = new FileOutputStream(part)) {
      out.write(json.getBytes(StandardCharsets.UTF_8));
    }
    if (!part.renameTo(f)) throw new Exception("Could not save the car menu");
  }

  /**
   * The library snapshot can be large, so the page sends it in parts: the first part starts a new
   * file, the last one moves it into place.
   */
  static synchronized void appendLibraryPart(Context c, String part, boolean first, boolean last)
      throws Exception {
    File incoming = new File(libraryFile(c).getPath() + ".incoming");
    try (FileOutputStream out = new FileOutputStream(incoming, !first)) {
      out.write(part.getBytes(StandardCharsets.UTF_8));
    }
    if (last) {
      String json = readFile(incoming);
      incoming.delete();
      saveLibrary(c, json);
    }
  }

  void reload() {
    reloadCatalog();
    reloadLibrary();
  }

  void reloadCatalog() {
    JSONObject jSONObject;
    try {
      jSONObject = new JSONObject(readFile(catalogFile(this.ctx)));
    } catch (Exception unused) {
      jSONObject = new JSONObject();
    }
    synchronized (this) {
      this.catalog = jSONObject;
      this.adhoc.clear();
    }
  }

  void reloadLibrary() {
    JSONObject jSONObject;
    try {
      jSONObject = new JSONObject(readFile(libraryFile(this.ctx)));
    } catch (Exception unused) {
      jSONObject = new JSONObject();
    }
    JSONObject jSONObjectOptJSONObject = jSONObject.optJSONObject("tracks");
    HashMap map = new HashMap();
    HashMap map2 = new HashMap();
    for (JSONObject jSONObject2 : arrayOf(jSONObject, "albums")) {
      map.put(jSONObject2.optString("key"), jSONObject2);
    }
    for (JSONObject jSONObject3 : arrayOf(jSONObject, "artists")) {
      map2.put(jSONObject3.optString("key"), jSONObject3);
    }
    synchronized (this) {
      this.library = jSONObject;
      if (jSONObjectOptJSONObject == null) {
        jSONObjectOptJSONObject = new JSONObject();
      }
      this.tracks = jSONObjectOptJSONObject;
      this.albumsByKey.clear();
      this.albumsByKey.putAll(map);
      this.artistsByKey.clear();
      this.artistsByKey.putAll(map2);
      this.adhoc.clear();
    }
  }

  synchronized double podcastSpeed() {
    double d;
    d = 1.0d;
    double dOptDouble = this.catalog.optDouble("podcastSpeed", 1.0d);
    if (dOptDouble > 0.2d && dOptDouble < 4.0d) {
      d = dOptDouble;
    }
    return d;
  }

  static {
    LinkedHashMap linkedHashMap = new LinkedHashMap();
    TITLES = linkedHashMap;
    LinkedHashMap linkedHashMap2 = new LinkedHashMap();
    FIXED = linkedHashMap2;
    LinkedHashMap linkedHashMap3 = new LinkedHashMap();
    LIST_OF = linkedHashMap3;
    LinkedHashMap linkedHashMap4 = new LinkedHashMap();
    ICONS = linkedHashMap4;
    linkedHashMap.put("tab:home", "Home");
    linkedHashMap.put("tab:library", "Library");
    linkedHashMap.put("tab:stations", "Stations");
    linkedHashMap.put("tab:podcasts", "Podcasts");
    linkedHashMap.put("home:favorites", "Favorites");
    linkedHashMap.put("home:topartists", "Top Artists");
    linkedHashMap.put("home:continue", "Continue Listening");
    linkedHashMap.put("home:recentsongs", "Recent Songs");
    linkedHashMap.put("home:latest", "Latest Podcasts");
    linkedHashMap.put("home:topstations", "Top Stations");
    linkedHashMap.put("lib:artists", "Artists");
    linkedHashMap.put("lib:albums", "Albums");
    linkedHashMap.put("lib:songs", "Songs");
    linkedHashMap.put("lib:playlists", "Playlists");
    linkedHashMap.put("lib:genres", "Genres");
    linkedHashMap.put("st:foryou", "For You");
    linkedHashMap.put("st:recent", "Recent Stations");
    linkedHashMap.put("st:top", "Top Stations");
    linkedHashMap.put("pod:latest", "Latest");
    linkedHashMap.put("pod:az", "A-Z");
    linkedHashMap.put("pod:popular", "Popular");
    linkedHashMap2.put(
        "root", new String[] {"tab:home", "tab:library", "tab:stations", "tab:podcasts"});
    linkedHashMap2.put(
        "tab:home",
        new String[] {
          "home:favorites",
          "home:topartists",
          "home:continue",
          "home:recentsongs",
          "home:latest",
          "home:topstations"
        });
    linkedHashMap2.put(
        "tab:library",
        new String[] {"lib:artists", "lib:albums", "lib:songs", "lib:playlists", "lib:genres"});
    linkedHashMap2.put("tab:stations", new String[] {"st:foryou", "st:recent", "st:top"});
    linkedHashMap3.put("home:favorites", "favorites");
    linkedHashMap3.put("home:topartists", "topArtists");
    linkedHashMap3.put("home:continue", "continue");
    linkedHashMap3.put("home:recentsongs", "recentSongs");
    linkedHashMap3.put("home:latest", "podLatest");
    linkedHashMap3.put("home:topstations", "topStations");
    linkedHashMap3.put("st:recent", "recentStations");
    linkedHashMap3.put("st:top", "topStations");
    linkedHashMap3.put("pod:latest", "podLatest");
    linkedHashMap3.put("pod:az", "shows");
    linkedHashMap3.put("pod:popular", "popular");
    linkedHashMap4.put("tab:home", "ic_car_home");
    linkedHashMap4.put("tab:library", "ic_car_library");
    linkedHashMap4.put("tab:stations", "ic_car_stations");
    linkedHashMap4.put("tab:podcasts", "ic_car_podcasts");
    messageSeq = 0;
  }

  static List<String> fixedNodeIds() {
    ArrayList arrayList = new ArrayList(TITLES.keySet());
    arrayList.add("root");
    return arrayList;
  }

  static Bundle rootExtras() {
    Bundle bundle = new Bundle();
    bundle.putBoolean("android.media.browse.CONTENT_STYLE_SUPPORTED", true);
    bundle.putInt("android.media.browse.CONTENT_STYLE_BROWSABLE_HINT", 1);
    bundle.putInt("android.media.browse.CONTENT_STYLE_PLAYABLE_HINT", 1);
    bundle.putBoolean("android.media.browse.SEARCH_SUPPORTED", true);
    return bundle;
  }

  MediaItem rootItem() {
    return folder("root", "Amplify", null, null, null);
  }

  synchronized MediaItem node(String str) {
    if ("root".equals(str)) {
      return rootItem();
    }
    String str2 = TITLES.get(str);
    MediaItem mediaItemFolder = null;
    if (str2 != null) {
      return folder(str, str2, null, iconUri(str), null);
    }
    if (str.startsWith("fy:")) {
      JSONObject jSONObjectFindIn = findIn("forYou", str.substring(3));
      if (jSONObjectFindIn != null) {
        mediaItemFolder =
            folder(str, jSONObjectFindIn.optString("label", "Search"), null, null, null);
      }
      return mediaItemFolder;
    }
    if (str.startsWith("cat:")) {
      JSONObject jSONObjectFindIn2 = findIn("categories", str.substring(4));
      if (jSONObjectFindIn2 != null) {
        mediaItemFolder =
            folder(str, jSONObjectFindIn2.optString("name", "Category"), null, null, null);
      }
      return mediaItemFolder;
    }
    if (str.startsWith("show:")) {
      JSONObject jSONObjectFindShow = findShow(str.substring(5));
      if (jSONObjectFindShow != null) {
        return showFolder(jSONObjectFindShow, null);
      }
      return folder(str, "Podcast", null, null, null);
    }
    if (str.startsWith("artist:")) {
      String strDec = dec(str.substring(7));
      JSONObject jSONObject = this.artistsByKey.get(strDec);
      return artistFolder(
          strDec, jSONObject == null ? "Artist" : jSONObject.optString("name", "Artist"), null);
    }
    if (str.startsWith("album:")) {
      JSONObject jSONObject2 = this.albumsByKey.get(dec(str.substring(6)));
      if (jSONObject2 == null) {
        return null;
      }
      return albumFolder(jSONObject2.optString("key"), jSONObject2.optString("title"), null);
    }
    if (str.startsWith("pl:")) {
      JSONObject jSONObjectFindIn3 = findIn("playlists", dec(str.substring(3)));
      if (jSONObjectFindIn3 != null) {
        mediaItemFolder =
            folder(str, jSONObjectFindIn3.optString("label", "Playlist"), null, null, null);
      }
      return mediaItemFolder;
    }
    if (str.startsWith("genre:")) {
      return folder(str, dec(str.substring(6)), null, null, null);
    }
    if (str.startsWith("search:")) {
      return folder(str, dec(str.substring(7)), null, null, null);
    }
    if (str.startsWith("voice:")) {
      return folder(str, "Results", null, null, null);
    }
    return null;
  }

  void setRootLimit(int i) {
    if (i > 0) {
      this.rootLimit = i;
    }
  }

  boolean searchIsTab() {
    return this.rootLimit >= 5;
  }

  List<MediaItem> children(String str) throws JSONException {
    ArrayList arrayList = new ArrayList();
    String[] strArr = FIXED.get(str);
    int i = 0;
    if (strArr != null) {
      int length = strArr.length;
      while (i < length) {
        MediaItem mediaItemNode = node(strArr[i]);
        if (mediaItemNode != null) {
          arrayList.add(mediaItemNode);
        }
        i++;
      }
    } else {
      switch (str) {
        case "lib:playlists":
          synchronized (this) {
            for (JSONObject jSONObject : arrayOf(this.catalog, "playlists")) {
              arrayList.add(
                  folder(
                      "pl:" + enc(jSONObject.optString("id")),
                      jSONObject.optString("label", "Playlist"),
                      null,
                      null,
                      null));
            }
          }
          if (arrayList.isEmpty()) {
            arrayList.add(message("No playlists yet. Make one on your phone."));
            break;
          }
          break;
        case "tab:podcasts":
          arrayList.add(node("pod:latest"));
          synchronized (this) {
            for (JSONObject jSONObject2 : arrayOf(this.catalog, "categories")) {
              arrayList.add(
                  folder(
                      "cat:" + jSONObject2.optString("id"),
                      jSONObject2.optString("name"),
                      null,
                      null,
                      null));
            }
          }
          arrayList.add(node("pod:az"));
          arrayList.add(node("pod:popular"));
          return arrayList;
        case "lib:artists":
          synchronized (this) {
            for (JSONObject jSONObject3 : arrayOf(this.library, "artists")) {
              arrayList.add(
                  artistFolder(jSONObject3.optString("key"), jSONObject3.optString("name"), null));
            }
          }
          if (arrayList.isEmpty()) {
            arrayList.add(
                message(
                    "No songs yet. On your phone, open Amplify, tap Add folder and pick your music"
                        + " folder."));
            return arrayList;
          }
          break;
        case "lib:albums":
          synchronized (this) {
            for (JSONObject jSONObject4 : arrayOf(this.library, "albums")) {
              arrayList.add(
                  albumFolder(jSONObject4.optString("key"), jSONObject4.optString("title"), null));
            }
          }
          if (arrayList.isEmpty()) {
            arrayList.add(
                message(
                    "No songs yet. On your phone, open Amplify, tap Add folder and pick your music"
                        + " folder."));
            return arrayList;
          }
          break;
        case "lib:genres":
          synchronized (this) {
            JSONArray jSONArrayOptJSONArray = this.catalog.optJSONArray("genres");
            if (jSONArrayOptJSONArray != null) {
              while (i < jSONArrayOptJSONArray.length()) {
                String strOptString = jSONArrayOptJSONArray.optString(i, "");
                if (!strOptString.isEmpty()) {
                  arrayList.add(
                      folder("genre:" + enc(strOptString), strOptString, null, null, null));
                }
                i++;
              }
            }
          }
          if (arrayList.isEmpty()) {
            arrayList.add(message("Open Amplify on your phone to load the genres."));
            return arrayList;
          }
          break;
        case "st:foryou":
          synchronized (this) {
            for (JSONObject jSONObject5 : arrayOf(this.catalog, "forYou")) {
              arrayList.add(
                  folder(
                      "fy:" + jSONObject5.optString("id"),
                      jSONObject5.optString("label"),
                      null,
                      null,
                      null));
            }
          }
          if (arrayList.isEmpty()) {
            arrayList.add(message("No saved searches yet. Add one in Stations on your phone."));
            return arrayList;
          }
          break;
        default:
          List<JSONObject> listListItems = listItems(str);
          while (i < listListItems.size()) {
            MediaItem browseItem = toBrowseItem(str, i, listListItems.get(i));
            if (browseItem != null) {
              arrayList.add(browseItem);
            }
            i++;
          }
          if (arrayList.isEmpty()) {
            arrayList.add(message(emptyMessage(str)));
            return arrayList;
          }
          break;
      }
    }
    return arrayList;
  }

  private static File searchesFile(Context context) {
    return new File(context.getFilesDir(), "car_searches.json");
  }

  synchronized void rememberSearch(String query) throws Exception {
    String q = query == null ? "" : query.trim();
    if (q.isEmpty()) return;
    JSONArray old;
    try {
      old = new JSONArray(readFile(searchesFile(ctx)));
    } catch (Exception e) {
      old = new JSONArray();
    }
    // newest first, no duplicates (ignoring case), at most 12
    JSONArray next = new JSONArray().put(q);
    for (int i = 0; i < old.length() && next.length() < 12; i++) {
      String s = old.optString(i, "");
      if (!s.isEmpty() && !s.equalsIgnoreCase(q)) next.put(s);
    }
    saveJsonArray(searchesFile(ctx), next);
  }

  private static void saveJsonArray(File f, JSONArray a) throws Exception {
    File part = new File(f.getPath() + ".part");
    try (FileOutputStream out = new FileOutputStream(part)) {
      out.write(a.toString().getBytes(StandardCharsets.UTF_8));
    }
    if (!part.renameTo(f)) part.delete();
  }

  private static String emptyMessage(String str) {
    switch (str) {
      case "pod:az":
        return "You aren't following any podcasts yet.";
      case "lib:songs":
        return "No songs yet. On your phone, open Amplify, tap Add folder and pick your music"
            + " folder.";
      case "home:topartists":
        return "Artists you play most will show up here.";
      case "home:favorites":
        return "No favorites yet.";
      case "home:recentsongs":
        return "Songs you play will show up here.";
      case "pod:popular":
        return "Open Podcasts > Popular on your phone once to load this list.";
      case "st:recent":
        return "Stations you play will show up here.";
      case "home:continue":
        return "Nothing in progress.";
      default:
        return str.startsWith("show:")
            ? "Couldn't load this show's episodes."
            : str.startsWith("artist:")
                ? "No songs or stations for this artist on the phone yet."
                : str.startsWith("genre:")
                    ? "Nothing found for this genre right now."
                    : str.startsWith("search:")
                        ? "No results."
                        : str.startsWith("pl:")
                            ? "This playlist is empty."
                            : "Nothing here yet. Open Amplify on your phone to refresh.";
    }
  }

  List<JSONObject> listItems(String str) throws JSONException {
    if ("resume".equals(str)) {
      List<JSONObject> list = this.adhoc.get(str);
      return list != null ? list : Collections.emptyList();
    }
    if (str.startsWith("show:")) {
      return showEpisodes(str.substring(5));
    }
    if (str.startsWith("genre:")) {
      return genreItems(dec(str.substring(6)));
    }
    if (str.startsWith("search:")) {
      List<JSONObject> list2 = this.adhoc.get(str);
      return list2 != null ? list2 : search(dec(str.substring(7)));
    }
    if (str.startsWith("voice:")) {
      List<JSONObject> list3 = this.adhoc.get(str);
      return list3 != null ? list3 : Collections.emptyList();
    }
    synchronized (this) {
      if ("lib:songs".equals(str)) {
        ArrayList arrayList = new ArrayList();
        JSONArray jSONArrayOptJSONArray = this.library.optJSONArray("songs");
        if (jSONArrayOptJSONArray != null) {
          for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
            arrayList.add(songRef(jSONArrayOptJSONArray.optString(i), null));
          }
        }
        return arrayList;
      }
      if (str.startsWith("artist:")) {
        return artistItems(dec(str.substring(7)));
      }
      if (str.startsWith("album:")) {
        return albumItems(dec(str.substring(6)));
      }
      String str2 = LIST_OF.get(str);
      if (str2 == null && (str.startsWith("fy:") || str.startsWith("cat:"))) {
        str2 = str;
      }
      if (str2 == null && str.startsWith("pl:")) {
        str2 = "pl:" + dec(str.substring(3));
      }
      if (str2 == null) {
        return Collections.emptyList();
      }
      return arrayOf(this.catalog.optJSONObject("lists"), str2);
    }
  }

  private static JSONObject songRef(String str, String str2) {
    JSONObject jSONObject = new JSONObject();
    try {
      jSONObject.put("t", "song");
      jSONObject.put("id", str);
      if (str2 != null) {
        jSONObject.put("g", str2);
      }
    } catch (Exception unused) {
    }
    return jSONObject;
  }

  /** A library song that can play in the car (it has a content:// uri), or null. */
  private synchronized JSONObject track(String id) {
    JSONObject t = tracks.optJSONObject(id);
    if (t == null || t.optString("uri").isEmpty()) return null;
    return t;
  }

  private synchronized List<JSONObject> albumItems(String str) {
    ArrayList arrayList = new ArrayList();
    JSONObject jSONObject = this.albumsByKey.get(str);
    if (jSONObject == null) {
      return arrayList;
    }
    JSONArray jSONArrayOptJSONArray = jSONObject.optJSONArray("tracks");
    if (jSONArrayOptJSONArray != null) {
      for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
        arrayList.add(songRef(jSONArrayOptJSONArray.optString(i), null));
      }
    }
    return arrayList;
  }

  private synchronized List<JSONObject> artistItems(String str) {
    ArrayList arrayList = new ArrayList();
    JSONObject jSONObject = this.artistsByKey.get(str);
    if (jSONObject == null) {
      return arrayList;
    }
    // The artist's stations first, then their albums (build 48).
    Iterator<JSONObject> it = arrayOf(jSONObject, "stations").iterator();
    while (it.hasNext()) {
      arrayList.add(withGroup(it.next(), "Stations"));
    }
    JSONArray jSONArrayOptJSONArray = jSONObject.optJSONArray("albums");
    if (jSONArrayOptJSONArray != null) {
      for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
        JSONObject jSONObject2 = new JSONObject();
        try {
          jSONObject2.put("t", "album");
          jSONObject2.put("key", jSONArrayOptJSONArray.optString(i));
          jSONObject2.put("g", "Albums");
        } catch (Exception unused) {
        }
        arrayList.add(jSONObject2);
      }
    }
    return arrayList;
  }

  private synchronized List<JSONObject> artistSongs(String str) {
    ArrayList arrayList = new ArrayList();
    JSONObject jSONObject = this.artistsByKey.get(str);
    if (jSONObject == null) {
      return arrayList;
    }
    JSONArray jSONArrayOptJSONArray = jSONObject.optJSONArray("albums");
    if (jSONArrayOptJSONArray != null) {
      for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
        arrayList.addAll(albumItems(jSONArrayOptJSONArray.optString(i)));
      }
    }
    if (arrayList.isEmpty()) {
      arrayList.addAll(arrayOf(jSONObject, "stations"));
    }
    return arrayList;
  }

  private List<JSONObject> genreItems(String str) throws JSONException {
    ArrayList arrayList = new ArrayList();
    String str2 = " " + norm(str) + " ";
    synchronized (this) {
      JSONArray jSONArrayOptJSONArray = this.library.optJSONArray("songs");
      if (jSONArrayOptJSONArray != null) {
        for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
          String strOptString = jSONArrayOptJSONArray.optString(i);
          JSONObject jSONObjectOptJSONObject = this.tracks.optJSONObject(strOptString);
          if (jSONObjectOptJSONObject != null) {
            String strNorm = norm(jSONObjectOptJSONObject.optString("genre"));
            if (!strNorm.isEmpty() && (" " + strNorm + " ").contains(str2)) {
              arrayList.add(songRef(strOptString, "Songs"));
            }
          }
        }
      }
    }
    Iterator<JSONObject> it = stationSearch("tag", str.toLowerCase(Locale.ROOT), 60).iterator();
    while (it.hasNext()) {
      arrayList.add(withGroup(it.next(), "Stations"));
    }
    return arrayList;
  }

  private MediaItem toBrowseItem(String str, int i, JSONObject jSONObject) throws JSONException {
    String strEmptyToNull;
    JSONObject jSONObject2;
    String strOptString = jSONObject.optString("t");
    strEmptyToNull = emptyToNull(jSONObject.optString("g"));
    switch (strOptString) {
      case "artist":
        return artistFolder(
            jSONObject.optString("key"),
            jSONObject.optString("title", "Artist"),
            strEmptyToNull,
            jSONObject.optString("art"));
      case "show":
        return showFolder(jSONObject, strEmptyToNull);
      case "album":
        synchronized (this) {
          jSONObject2 = this.albumsByKey.get(jSONObject.optString("key"));
        }
        if (jSONObject2 == null) {
          return null;
        }
        return albumFolder(
            jSONObject2.optString("key"), jSONObject2.optString("title"), strEmptyToNull);
      default:
        if (isPlayable(jSONObject)) {
          return playable(str, i, jSONObject, null);
        }
        return null;
    }
  }

  private boolean isPlayable(JSONObject jSONObject) {
    String strOptString = jSONObject.optString("t");
    if ("song".equals(strOptString)) {
      return track(jSONObject.optString("id")) != null;
    }
    if ("station".equals(strOptString) || "episode".equals(strOptString)) {
      return !jSONObject.optString("url").isEmpty();
    }
    return false;
  }

  private static String keyOf(JSONObject jSONObject, int i) {
    return "song".equals(jSONObject.optString("t"))
        ? jSONObject.optString("id", String.valueOf(i))
        : jSONObject.optString("k", String.valueOf(i));
  }

  MediaItem playable(String str, int i, JSONObject jSONObject, JSONObject jSONObject2)
      throws JSONException {
    String strOptString = jSONObject.optString("t");
    String str2 = str + "|" + i + "|" + keyOf(jSONObject, i);
    if ("song".equals(strOptString)) {
      return songItem(str2, jSONObject);
    }
    boolean zEquals = "episode".equals(strOptString);
    String strOptString2 = jSONObject.optString("url");
    Bundle bundle = new Bundle();
    bundle.putBoolean("amplify.live", !zEquals);
    if (!zEquals && !jSONObject.optString("place").isEmpty()) {
      bundle.putString("amplify.place", jSONObject.optString("place"));
    }
    bundle.putString("amplify.item", historyEntry(jSONObject).toString());
    if (zEquals) {
      bundle.putString("amplify.guid", jSONObject.optString("guid"));
      JSONObject jSONObjectOptJSONObject = jSONObject.optJSONObject("rec");
      if (jSONObjectOptJSONObject != null) {
        bundle.putString("amplify.record", jSONObjectOptJSONObject.toString());
      }
      double dOptDouble = jSONObject.optDouble("pos", 0.0d);
      double dOptDouble2 = jSONObject.optDouble("dur", 0.0d);
      if (jSONObject2 != null) {
        dOptDouble = jSONObject2.optDouble("positionSec", dOptDouble);
        dOptDouble2 = jSONObject2.optDouble("durationSec", dOptDouble2);
      }
      if (jSONObject.optBoolean("done")) {
        bundle.putInt("android.media.extra.PLAYBACK_STATUS", 2);
      } else if (dOptDouble > 5.0d && dOptDouble2 > 0.0d) {
        bundle.putInt("android.media.extra.PLAYBACK_STATUS", 1);
        bundle.putDouble(
            "androidx.media.MediaItem.Extras.COMPLETION_PERCENTAGE",
            Math.min(1.0d, dOptDouble / dOptDouble2));
      } else {
        bundle.putInt("android.media.extra.PLAYBACK_STATUS", 0);
      }
    }
    String strOptString3 = jSONObject.optString("g");
    if (!strOptString3.isEmpty()) {
      bundle.putString("android.media.browse.CONTENT_STYLE_GROUP_TITLE_HINT", strOptString3);
    }
    MediaItem.Builder uri =
        new MediaItem.Builder()
            .setMediaId(str2)
            .setMediaMetadata(
                new MediaMetadata.Builder()
                    .setTitle(jSONObject.optString("title", zEquals ? "Episode" : "Station"))
                    .setArtist(emptyToNull(jSONObject.optString("sub")))
                    .setStation(zEquals ? null : jSONObject.optString("title"))
                    .setArtworkUri(ArtProvider.uriFor(jSONObject.optString("art")))
                    .setIsPlayable(true)
                    .setIsBrowsable(false)
                    .setMediaType(Integer.valueOf(zEquals ? 3 : 4))
                    .setExtras(bundle)
                    .build())
            .setUri(strOptString2);
    if (strOptString2.toLowerCase(Locale.ROOT).contains(".m3u8")) {
      uri.setMimeType("application/x-mpegURL");
    }
    return uri.build();
  }

  List<MediaItem> pageQueueItems(JSONArray jSONArray) throws JSONException {
    MediaItem mediaItemPlayable;
    ArrayList arrayList = new ArrayList();
    int i = 0;
    while (i < jSONArray.length()) {
      JSONObject jSONObjectOptJSONObject = jSONArray.optJSONObject(i);
      if (jSONObjectOptJSONObject == null) {
        jSONObjectOptJSONObject = new JSONObject();
      }
      String strOptString = jSONObjectOptJSONObject.optString("t");
      int i2 = i + 1;
      String str = "pageq|" + i2 + "|" + keyOf(jSONObjectOptJSONObject, i);
      if ("song".equals(strOptString) && track(jSONObjectOptJSONObject.optString("id")) != null) {
        mediaItemPlayable = songItem(str, jSONObjectOptJSONObject);
      } else if (("station".equals(strOptString) || "episode".equals(strOptString))
          && !jSONObjectOptJSONObject.optString("url").isEmpty()) {
        mediaItemPlayable = playable("pageq", i2, jSONObjectOptJSONObject, null);
      } else {
        mediaItemPlayable =
            new MediaItem.Builder()
                .setMediaId(str)
                .setMediaMetadata(
                    new MediaMetadata.Builder()
                        .setTitle(jSONObjectOptJSONObject.optString("title", ""))
                        .setArtist(emptyToNull(jSONObjectOptJSONObject.optString("sub")))
                        .setArtworkUri(ArtProvider.uriFor(jSONObjectOptJSONObject.optString("art")))
                        .setIsPlayable(true)
                        .setIsBrowsable(false)
                        .build())
                .build();
      }
      arrayList.add(mediaItemPlayable);
      i = i2;
    }
    return arrayList;
  }

  private MediaItem songItem(String str, JSONObject jSONObject) throws JSONException {
    JSONObject jSONObjectTrack = track(jSONObject.optString("id"));
    if (jSONObjectTrack == null) {
      jSONObjectTrack = new JSONObject();
    }
    Bundle bundle = new Bundle();
    bundle.putBoolean("amplify.live", false);
    bundle.putString("amplify.item", historyEntry(jSONObject).toString());
    String strOptString = jSONObject.optString("g");
    if (!strOptString.isEmpty()) {
      bundle.putString("android.media.browse.CONTENT_STYLE_GROUP_TITLE_HINT", strOptString);
    }
    MediaMetadata.Builder extras =
        new MediaMetadata.Builder()
            .setTitle(jSONObjectTrack.optString("title", "Song"))
            .setArtist(emptyToNull(jSONObjectTrack.optString("artist")))
            .setAlbumTitle(emptyToNull(jSONObjectTrack.optString("album")))
            .setGenre(emptyToNull(jSONObjectTrack.optString("genre")))
            .setArtworkUri(ArtProvider.uriFor(jSONObjectTrack.optString("art")))
            .setIsPlayable(true)
            .setIsBrowsable(false)
            .setMediaType(1)
            .setExtras(bundle);
    double dOptDouble = jSONObjectTrack.optDouble("dur", 0.0d);
    if (dOptDouble > 0.0d) {
      extras.setDurationMs(Long.valueOf((long) (dOptDouble * 1000.0d)));
    }
    return new MediaItem.Builder()
        .setMediaId(str)
        .setMediaMetadata(extras.build())
        .setUri(jSONObjectTrack.optString("uri"))
        .build();
  }

  private static JSONObject historyEntry(JSONObject jSONObject) throws JSONException {
    JSONObject jSONObject2 = new JSONObject();
    if ("song".equals(jSONObject.optString("t"))) {
      jSONObject2.put("t", "song");
      jSONObject2.put("id", jSONObject.optString("id"));
      return jSONObject2;
    }
    if ("episode".equals(jSONObject.optString("t"))) {
      jSONObject2.put("t", "episode");
      jSONObject2.put("guid", jSONObject.optString("guid"));
      jSONObject2.put("title", jSONObject.optString("title"));
      jSONObject2.put("sub", jSONObject.optString("sub"));
      jSONObject2.put("art", jSONObject.optString("art"));
      jSONObject2.put("url", jSONObject.optString("url"));
      JSONObject jSONObjectOptJSONObject = jSONObject.optJSONObject("rec");
      if (jSONObjectOptJSONObject != null) {
        jSONObject2.put("rec", jSONObjectOptJSONObject);
        return jSONObject2;
      }
    } else {
      jSONObject2.put("t", "station");
      jSONObject2.put("k", jSONObject.optString("k"));
      jSONObject2.put("title", jSONObject.optString("title"));
      jSONObject2.put("place", jSONObject.optString("place"));
      jSONObject2.put("url", jSONObject.optString("url"));
      jSONObject2.put("art", jSONObject.optString("art"));
    }
    return jSONObject2;
  }

  private MediaItem showFolder(JSONObject jSONObject, String str) {
    return folder(
        "show:" + jSONObject.optString("cid"),
        jSONObject.optString("title", "Podcast"),
        emptyToNull(jSONObject.optString("sub")),
        ArtProvider.uriFor(jSONObject.optString("art")),
        str);
  }

  private MediaItem artistFolder(String str, String str2, String str3) {
    return artistFolder(str, str2, str3, null);
  }

  private MediaItem artistFolder(String str, String str2, String str3, String str4) {
    JSONObject jSONObject;
    synchronized (this) {
      jSONObject = this.artistsByKey.get(str);
    }
    if (jSONObject != null) {
      str2 = jSONObject.optString("name", str2);
    }
    Uri uriUriFor = ArtProvider.uriFor(str4);
    if (uriUriFor == null && jSONObject != null) {
      uriUriFor = ArtProvider.uriFor(jSONObject.optString("art"));
    }
    String str5 = "artist:" + enc(str);
    if (str2.isEmpty()) {
      str2 = "Artist";
    }
    return folder(str5, str2, null, uriUriFor, str3);
  }

  private MediaItem albumFolder(String str, String str2, String str3) {
    JSONObject jSONObject;
    synchronized (this) {
      jSONObject = this.albumsByKey.get(str);
    }
    String strEmptyToNull = jSONObject == null ? null : emptyToNull(jSONObject.optString("artist"));
    Uri uriUriFor = jSONObject != null ? ArtProvider.uriFor(jSONObject.optString("art")) : null;
    String str4 = "album:" + enc(str);
    if (str2.isEmpty()) {
      str2 = "Album";
    }
    return folder(str4, str2, strEmptyToNull, uriUriFor, str3);
  }

  private static MediaItem folder(String str, String str2, String str3, Uri uri, String str4) {
    MediaMetadata.Builder mediaType =
        new MediaMetadata.Builder()
            .setTitle(str2)
            .setArtist(str3)
            .setArtworkUri(uri)
            .setIsBrowsable(true)
            .setIsPlayable(false)
            .setMediaType(20);
    if (str4 != null) {
      Bundle bundle = new Bundle();
      bundle.putString("android.media.browse.CONTENT_STYLE_GROUP_TITLE_HINT", str4);
      mediaType.setExtras(bundle);
    }
    return new MediaItem.Builder().setMediaId(str).setMediaMetadata(mediaType.build()).build();
  }

  private static MediaItem message(String str) {
    MediaMetadata mediaMetadataBuild =
        new MediaMetadata.Builder()
            .setTitle(str)
            .setIsBrowsable(false)
            .setIsPlayable(false)
            .build();
    MediaItem.Builder builder = new MediaItem.Builder();
    StringBuilder sb = new StringBuilder("msg:");
    int i = messageSeq;
    messageSeq = i + 1;
    return builder.setMediaId(sb.append(i).toString()).setMediaMetadata(mediaMetadataBuild).build();
  }

  private Uri iconUri(String str) {
    String str2 = ICONS.get(str);
    if (str2 == null) {
      return null;
    }
    return Uri.parse("android.resource://" + this.ctx.getPackageName() + "/drawable/" + str2);
  }

  static String[] parsePlayableId(String str) {
    if (str == null) {
      return null;
    }
    String[] strArrSplit = str.split("\\|", 3);
    if (strArrSplit.length == 3) {
      return strArrSplit;
    }
    return null;
  }

  Queue queueFor(String str) throws JSONException {
    int i;
    int i2;
    JSONObject jSONObjectOptJSONObject;
    List<JSONObject> list;
    JSONObject jSONObject;
    double dOptDouble;
    boolean z;
    boolean zOptBoolean;
    CarLibrary carLibrary = this;
    String[] playableId = parsePlayableId(str);
    if (playableId == null) {
      return null;
    }
    String str2 = playableId[0];
    try {
      i = Integer.parseInt(playableId[1]);
    } catch (NumberFormatException unused) {
      i = 0;
    }
    String str3 = playableId[2];
    List<JSONObject> listListItems = carLibrary.listItems(str2);
    String strOptString =
        (!str2.startsWith("search:") || i < 0 || i >= listListItems.size())
            ? null
            : listListItems.get(i).optString("t");
    ArrayList arrayList = new ArrayList();
    int size = -1;
    int size2 = -1;
    for (int i3 = 0; i3 < listListItems.size(); i3++) {
      JSONObject jSONObject2 = listListItems.get(i3);
      if (carLibrary.isPlayable(jSONObject2)
          && (strOptString == null || strOptString.equals(jSONObject2.optString("t")))) {
        if (i3 == i) {
          size = arrayList.size();
        }
        if (size2 < 0 && keyOf(jSONObject2, i3).equals(str3) && (i3 == i || size < 0)) {
          size2 = arrayList.size();
        }
        arrayList.add(Integer.valueOf(i3));
      }
    }
    if (arrayList.isEmpty()) {
      return null;
    }
    if (size >= 0
        && keyOf(
                listListItems.get(((Integer) arrayList.get(size)).intValue()),
                ((Integer) arrayList.get(size)).intValue())
            .equals(str3)) {
      size2 = size;
    }
    if (size2 < 0) {
      if (size < 0) {
        size = 0;
      }
      size2 = size;
    }
    int iMax = Math.max(0, size2 - 50);
    int iMin = Math.min(arrayList.size(), size2 + 251);
    JSONObject all = CarProgress.readAll(carLibrary.ctx);
    ArrayList arrayList2 = new ArrayList();
    ArrayList arrayList3 = new ArrayList();
    int i4 = iMax;
    while (i4 < iMin) {
      int iIntValue = ((Integer) arrayList.get(i4)).intValue();
      JSONObject jSONObject3 = listListItems.get(iIntValue);
      String strOptString2 = jSONObject3.optString("t");
      if ("episode".equals(strOptString2)) {
        i2 = iMax;
        jSONObjectOptJSONObject = all.optJSONObject(jSONObject3.optString("guid"));
      } else {
        i2 = iMax;
        jSONObjectOptJSONObject = null;
      }
      MediaItem mediaItemPlayable =
          carLibrary.playable(str2, iIntValue, jSONObject3, jSONObjectOptJSONObject);
      if ("station".equals(strOptString2)) {
        mediaItemPlayable = resolvePlaylist(mediaItemPlayable);
      }
      arrayList2.add(mediaItemPlayable);
      String str4 = str2;
      int i5 = iMin;
      if (jSONObjectOptJSONObject != null) {
        list = listListItems;
        jSONObject = all;
        dOptDouble =
            jSONObjectOptJSONObject.optDouble("positionSec", jSONObject3.optDouble("pos", 0.0d));
      } else {
        list = listListItems;
        jSONObject = all;
        dOptDouble = jSONObject3.optDouble("pos", 0.0d);
      }
      if (jSONObjectOptJSONObject != null) {
        z = false;
        zOptBoolean = jSONObjectOptJSONObject.optBoolean("completed", false);
      } else {
        z = false;
        zOptBoolean = jSONObject3.optBoolean("done", false);
      }
      arrayList3.add(
          Long.valueOf(
              (!"episode".equals(strOptString2) || dOptDouble <= 5.0d || zOptBoolean)
                  ? 0L
                  : (long) (dOptDouble * 1000.0d)));
      i4++;
      str2 = str4;
      iMin = i5;
      iMax = i2;
      listListItems = list;
      all = jSONObject;
      carLibrary = this;
    }
    int i6 = size2 - iMax;
    return new Queue(arrayList2, i6, ((Long) arrayList3.get(i6)).longValue());
  }

  Queue resumeQueue(String str, JSONObject jSONObject) throws JSONException {
    Queue queueQueueFor;
    if (str != null
        && !str.isEmpty()
        && !str.startsWith("voice:")
        && (queueQueueFor = queueFor(str)) != null) {
      return queueQueueFor;
    }
    if (jSONObject == null) {
      return null;
    }
    ArrayList arrayList = new ArrayList();
    arrayList.add(jSONObject);
    this.adhoc.put("resume", arrayList);
    if (isPlayable(jSONObject)) {
      return queueFor("resume|0|" + keyOf(jSONObject, 0));
    }
    return null;
  }

  Queue resumeList(JSONArray jSONArray, int i) throws JSONException {
    if (jSONArray == null || i < 0 || i >= jSONArray.length()) {
      return null;
    }
    ArrayList arrayList = new ArrayList();
    for (int i2 = 0; i2 < jSONArray.length(); i2++) {
      JSONObject jSONObjectOptJSONObject = jSONArray.optJSONObject(i2);
      if (jSONObjectOptJSONObject == null) {
        jSONObjectOptJSONObject = new JSONObject();
      }
      arrayList.add(jSONObjectOptJSONObject);
    }
    JSONObject jSONObject = (JSONObject) arrayList.get(i);
    if (!isPlayable(jSONObject)) {
      return null;
    }
    this.adhoc.put("resume", arrayList);
    return queueFor("resume|" + i + "|" + keyOf(jSONObject, i));
  }

  static boolean sameEntry(JSONObject jSONObject, JSONObject jSONObject2) {
    if (jSONObject == null || jSONObject2 == null) {
      return false;
    }
    String strOptString = jSONObject.optString("t");
    if (!strOptString.equals(jSONObject2.optString("t"))) {
      return false;
    }
    if ("song".equals(strOptString)) {
      return jSONObject.optString("id").equals(jSONObject2.optString("id"))
          && !jSONObject.optString("id").isEmpty();
    }
    if ("episode".equals(strOptString) && !jSONObject.optString("guid").isEmpty()) {
      return jSONObject.optString("guid").equals(jSONObject2.optString("guid"));
    }
    String strOptString2 = jSONObject.optString("k");
    String strOptString3 = jSONObject2.optString("k");
    if (strOptString2.isEmpty() && strOptString3.isEmpty()) {
      return jSONObject.optString("url").equals(jSONObject2.optString("url"))
          && !jSONObject.optString("url").isEmpty();
    }
    return strOptString2.equals(strOptString3);
  }

  private Queue playList(String str, List<JSONObject> list) throws JSONException {
    if (list != null && !list.isEmpty()) {
      this.adhoc.put(str, list);
      for (int i = 0; i < list.size(); i++) {
        JSONObject jSONObject = list.get(i);
        if (isPlayable(jSONObject)) {
          return queueFor(str + "|" + i + "|" + keyOf(jSONObject, i));
        }
      }
    }
    return null;
  }

  static final class Queue {
    final List<MediaItem> items;
    final int startIndex;
    final long startPositionMs;

    Queue(List<MediaItem> list, int i, long j) {
      this.items = list;
      this.startIndex = i;
      this.startPositionMs = j;
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

  static String searchNode(String str) {
    return "search:" + enc(str.trim());
  }

  List<JSONObject> search(String str) throws JSONException {
    int i;
    String strSearchNode = searchNode(str);
    List<JSONObject> list = this.adhoc.get(strSearchNode);
    if (list != null) {
      return list;
    }
    String[] strArrWords = words(str);
    ArrayList arrayList = new ArrayList();
    if (strArrWords.length == 0) {
      return arrayList;
    }
    synchronized (this) {
      JSONArray jSONArrayOptJSONArray = this.library.optJSONArray("songs");
      i = 0;
      if (jSONArrayOptJSONArray != null) {
        int i2 = 0;
        for (int i3 = 0; i3 < jSONArrayOptJSONArray.length() && i2 < 25; i3++) {
          JSONObject jSONObjectOptJSONObject =
              this.tracks.optJSONObject(jSONArrayOptJSONArray.optString(i3));
          if (jSONObjectOptJSONObject != null
              && matchesAll(
                  jSONObjectOptJSONObject.optString("title")
                      + " "
                      + jSONObjectOptJSONObject.optString("artist")
                      + " "
                      + jSONObjectOptJSONObject.optString("album"),
                  strArrWords)) {
            arrayList.add(songRef(jSONArrayOptJSONArray.optString(i3), "Songs"));
            i2++;
          }
        }
      }
      int i4 = 0;
      for (JSONObject jSONObject : arrayOf(this.library, "artists")) {
        if (i4 >= 10) {
          break;
        }
        if (matchesAll(jSONObject.optString("name"), strArrWords)) {
          arrayList.add(
              ref("artist", jSONObject.optString("key"), jSONObject.optString("name"), "Artists"));
          i4++;
        }
      }
      int i5 = 0;
      for (JSONObject jSONObject2 : arrayOf(this.library, "albums")) {
        if (i5 >= 10) {
          break;
        }
        if (matchesAll(
            jSONObject2.optString("title") + " " + jSONObject2.optString("artist"), strArrWords)) {
          arrayList.add(
              ref("album", jSONObject2.optString("key"), jSONObject2.optString("title"), "Albums"));
          i5++;
        }
      }
    }
    HashSet hashSet = new HashSet();
    int i6 = 0;
    for (JSONObject jSONObject3 : knownStations()) {
      if (i6 >= 15) {
        break;
      }
      if (matchesAll(
              jSONObject3.optString("title") + " " + jSONObject3.optString("sub"), strArrWords)
          && hashSet.add(stationId(jSONObject3))) {
        arrayList.add(withGroup(jSONObject3, "Stations"));
        i6++;
      }
    }
    if (i6 < 15) {
      for (JSONObject jSONObject4 : stationSearch("name", str.trim(), 20)) {
        if (i6 >= 15) {
          break;
        }
        if (hashSet.add(stationId(jSONObject4))) {
          arrayList.add(withGroup(jSONObject4, "Stations"));
          i6++;
        }
      }
    }
    synchronized (this) {
      JSONObject jSONObjectOptJSONObject2 = this.catalog.optJSONObject("lists");
      HashSet hashSet2 = new HashSet();
      String[] strArr = {"favorites", "continue", "podLatest"};
      int i7 = 0;
      for (int i8 = 0; i8 < 3; i8++) {
        for (JSONObject jSONObject5 : arrayOf(jSONObjectOptJSONObject2, strArr[i8])) {
          if (i7 >= 10) {
            break;
          }
          if ("episode".equals(jSONObject5.optString("t"))
              && matchesAll(
                  jSONObject5.optString("title") + " " + jSONObject5.optString("sub"), strArrWords)
              && hashSet2.add(jSONObject5.optString("guid"))) {
            arrayList.add(withGroup(jSONObject5, "Episodes"));
            i7++;
          }
        }
      }
    }
    HashSet hashSet3 = new HashSet();
    synchronized (this) {
      for (JSONObject jSONObject6 : arrayOf(this.catalog.optJSONObject("lists"), "shows")) {
        if (i >= 8) {
          break;
        }
        if (matchesAll(
                jSONObject6.optString("title") + " " + jSONObject6.optString("sub"), strArrWords)
            && hashSet3.add(jSONObject6.optString("cid"))) {
          arrayList.add(withGroup(jSONObject6, "Podcasts"));
          i++;
        }
      }
    }
    if (i < 8) {
      for (JSONObject jSONObject7 : podcastSearch(str.trim())) {
        if (i >= 8) {
          break;
        }
        if (hashSet3.add(jSONObject7.optString("cid"))) {
          arrayList.add(withGroup(jSONObject7, "Podcasts"));
          i++;
        }
      }
    }
    this.adhoc.put(strSearchNode, arrayList);
    return arrayList;
  }

  List<MediaItem> searchItems(String str) throws JSONException {
    String strSearchNode = searchNode(str);
    List<JSONObject> listSearch = search(str);
    ArrayList arrayList = new ArrayList();
    for (int i = 0; i < listSearch.size(); i++) {
      MediaItem browseItem = toBrowseItem(strSearchNode, i, listSearch.get(i));
      if (browseItem != null) {
        arrayList.add(browseItem);
      }
    }
    return arrayList;
  }

  private static JSONObject ref(String str, String str2, String str3, String str4) {
    JSONObject jSONObject = new JSONObject();
    try {
      jSONObject.put("t", str);
      jSONObject.put("key", str2);
      jSONObject.put("title", str3);
      jSONObject.put("g", str4);
    } catch (Exception unused) {
    }
    return jSONObject;
  }

  private static String stationId(JSONObject jSONObject) {
    String strOptString = jSONObject.optString("k");
    return strOptString.isEmpty() ? jSONObject.optString("url") : strOptString;
  }

  private synchronized List<JSONObject> knownStations() {
    ArrayList arrayList = new ArrayList();
    JSONObject jSONObjectOptJSONObject = this.catalog.optJSONObject("lists");
    if (jSONObjectOptJSONObject == null) {
      return arrayList;
    }
    ArrayList arrayList2 = new ArrayList();
    arrayList2.add("favorites");
    arrayList2.add("recentStations");
    Iterator<String> itKeys = jSONObjectOptJSONObject.keys();
    while (itKeys.hasNext()) {
      String next = itKeys.next();
      if (next.startsWith("pl:") || next.startsWith("fy:")) {
        arrayList2.add(next);
      }
    }
    arrayList2.add("topStations");
    Iterator it = arrayList2.iterator();
    while (it.hasNext()) {
      for (JSONObject jSONObject : arrayOf(jSONObjectOptJSONObject, (String) it.next())) {
        if ("station".equals(jSONObject.optString("t")) && !jSONObject.optString("url").isEmpty()) {
          arrayList.add(jSONObject);
        }
      }
    }
    return arrayList;
  }

  Queue voice(String str, Bundle bundle) throws Exception {
    Queue queuePlayList;
    String strTrim = str == null ? "" : str.trim();
    String string = bundle == null ? null : bundle.getString("android.intent.extra.focus");
    String strExtra = extra(bundle, "android.intent.extra.artist");
    String strExtra2 = extra(bundle, "android.intent.extra.album");
    String strExtra3 = extra(bundle, "android.intent.extra.title");
    String strExtra4 = extra(bundle, "android.intent.extra.genre");
    String strExtra5 = extra(bundle, "android.intent.extra.playlist");
    String str2 = "voice:" + enc(strTrim.isEmpty() ? "*" : strTrim);
    rememberSearch(
        strTrim.isEmpty()
            ? firstNonNull(strExtra3, strExtra2, strExtra, strExtra4, strExtra5, "")
            : strTrim);
    if (strTrim.isEmpty()
        && strExtra == null
        && strExtra2 == null
        && strExtra3 == null
        && strExtra4 == null) {
      Queue queuePlayList2 = playList(str2, listItems("home:favorites"));
      if (queuePlayList2 == null) {
        queuePlayList2 = playList(str2, listItems("st:recent"));
      }
      return queuePlayList2 == null ? playList(str2, listItems("lib:songs")) : queuePlayList2;
    }
    if (string == null) {
      string = "";
    }
    if (string.endsWith("/artist")
        || (strExtra != null && strExtra2 == null && strExtra3 == null)) {
      Queue queuePlayArtist = playArtist(str2, strExtra != null ? strExtra : strTrim);
      if (queuePlayArtist != null) {
        return queuePlayArtist;
      }
    }
    if (string.endsWith("/album") || (strExtra2 != null && strExtra3 == null)) {
      Queue queuePlayAlbum = playAlbum(str2, strExtra2 != null ? strExtra2 : strTrim, strExtra);
      if (queuePlayAlbum != null) {
        return queuePlayAlbum;
      }
    }
    if (string.endsWith("/genre") || strExtra4 != null) {
      Queue queuePlayList3 =
          playList(str2, genreItems(matchGenre(strExtra4 != null ? strExtra4 : strTrim)));
      if (queuePlayList3 != null) {
        return queuePlayList3;
      }
    }
    if (string.endsWith("/playlist") || strExtra5 != null) {
      Queue queuePlayPlaylist = playPlaylist(str2, strExtra5 != null ? strExtra5 : strTrim);
      if (queuePlayPlaylist != null) {
        return queuePlayPlaylist;
      }
    }
    if (string.endsWith("/audio") || strExtra3 != null) {
      Queue queuePlayList4 =
          playList(str2, songsTitled(strExtra3 != null ? strExtra3 : strTrim, strExtra));
      if (queuePlayList4 != null) {
        return queuePlayList4;
      }
    }
    if (strTrim.isEmpty()) {
      strTrim = firstNonNull(strExtra3, strExtra2, strExtra, strExtra4, strExtra5, "");
    }
    if (strTrim.isEmpty()) {
      return null;
    }
    String strStripSuffix = stripSuffix(strTrim);
    Queue queuePlayArtist2 = playArtist(str2, strTrim);
    if (queuePlayArtist2 != null) {
      return queuePlayArtist2;
    }
    Queue queuePlayAlbum2 = playAlbum(str2, strTrim, null);
    if (queuePlayAlbum2 != null) {
      return queuePlayAlbum2;
    }
    Queue queuePlayList5 = playList(str2, songsTitled(strTrim, null));
    if (queuePlayList5 != null) {
      return queuePlayList5;
    }
    String strMatchGenre = matchGenre(strStripSuffix);
    if (strMatchGenre != null
        && (queuePlayList = playList(str2, genreItems(strMatchGenre))) != null) {
      return queuePlayList;
    }
    Queue queuePlayPlaylist2 = playPlaylist(str2, strTrim);
    if (queuePlayPlaylist2 != null) {
      return queuePlayPlaylist2;
    }
    Queue queuePlayList6 = playList(str2, stationsNamed(strStripSuffix));
    if (queuePlayList6 != null) {
      return queuePlayList6;
    }
    Queue queuePlayShow = playShow(str2, strTrim);
    if (queuePlayShow != null) {
      return queuePlayShow;
    }
    String[] strArrWords = words(strTrim);
    ArrayList arrayList = new ArrayList();
    synchronized (this) {
      JSONArray jSONArrayOptJSONArray = this.library.optJSONArray("songs");
      if (jSONArrayOptJSONArray != null) {
        for (int i = 0; i < jSONArrayOptJSONArray.length() && arrayList.size() < 100; i++) {
          JSONObject jSONObjectOptJSONObject =
              this.tracks.optJSONObject(jSONArrayOptJSONArray.optString(i));
          if (jSONObjectOptJSONObject != null
              && matchesAll(
                  jSONObjectOptJSONObject.optString("title")
                      + " "
                      + jSONObjectOptJSONObject.optString("artist")
                      + " "
                      + jSONObjectOptJSONObject.optString("album"),
                  strArrWords)) {
            arrayList.add(songRef(jSONArrayOptJSONArray.optString(i), null));
          }
        }
      }
    }
    Queue queuePlayList7 = playList(str2, arrayList);
    return queuePlayList7 != null
        ? queuePlayList7
        : playList(str2, stationSearch("name", strStripSuffix, 20));
  }

  private Queue playArtist(String str, String str2) throws JSONException {
    String strReplace = norm(str2).replace(" ", "");
    String strReplace2 = norm(str2).replaceFirst("^the ", "").replace(" ", "");
    synchronized (this) {
      String[] strArr = {strReplace, strReplace2};
      for (int i = 0; i < 2; i++) {
        String str3 = strArr[i];
        if (!str3.isEmpty() && this.artistsByKey.containsKey(str3)) {
          return playList(str, artistSongs(str3));
        }
      }
      return null;
    }
  }

  private Queue playAlbum(String str, String str2, String str3) throws JSONException {
    JSONObject next;
    String strNorm = norm(str2);
    String strNorm2 = str3 == null ? null : norm(str3);
    synchronized (this) {
      Iterator<JSONObject> it = arrayOf(this.library, "albums").iterator();
      while (true) {
        if (!it.hasNext()) {
          next = null;
          break;
        }
        next = it.next();
        if (norm(next.optString("title")).equals(strNorm)
            && (strNorm2 == null || norm(next.optString("artist")).contains(strNorm2))) {
          break;
        }
      }
    }
    if (next == null) {
      return null;
    }
    return playList(str, albumItems(next.optString("key")));
  }

  private Queue playPlaylist(String str, String str2) throws JSONException {
    JSONObject next;
    String strNorm = norm(str2.replaceAll("(?i)\\s*playlist$", ""));
    synchronized (this) {
      Iterator<JSONObject> it = arrayOf(this.catalog, "playlists").iterator();
      while (true) {
        if (!it.hasNext()) {
          next = null;
          break;
        }
        next = it.next();
        if (norm(next.optString("label")).equals(strNorm)) {
          break;
        }
      }
    }
    if (next == null) {
      return null;
    }
    return playList(str, listItems("pl:" + enc(next.optString("id"))));
  }

  private Queue playShow(String str, String str2) throws JSONException {
    String strOptString;
    String[] strArrWords = words(str2.replaceAll("(?i)\\s*podcast$", ""));
    if (strArrWords.length == 0) {
      return null;
    }
    synchronized (this) {
      Iterator<JSONObject> it = arrayOf(this.catalog.optJSONObject("lists"), "shows").iterator();
      while (true) {
        if (!it.hasNext()) {
          strOptString = null;
          break;
        }
        JSONObject next = it.next();
        if (matchesAll(next.optString("title"), strArrWords)) {
          strOptString = next.optString("cid");
          break;
        }
      }
    }
    if (strOptString == null) {
      return null;
    }
    return playList(str, showEpisodes(strOptString));
  }

  private synchronized List<JSONObject> songsTitled(String str, String str2) {
    ArrayList arrayList = new ArrayList();
    String strNorm = norm(str);
    String strNorm2 = str2 == null ? null : norm(str2);
    if (strNorm.isEmpty()) {
      return arrayList;
    }
    JSONArray jSONArrayOptJSONArray = this.library.optJSONArray("songs");
    if (jSONArrayOptJSONArray == null) {
      return arrayList;
    }
    for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
      JSONObject jSONObjectOptJSONObject =
          this.tracks.optJSONObject(jSONArrayOptJSONArray.optString(i));
      if (jSONObjectOptJSONObject != null
          && norm(jSONObjectOptJSONObject.optString("title")).equals(strNorm)
          && (strNorm2 == null
              || norm(jSONObjectOptJSONObject.optString("artist")).contains(strNorm2))) {
        arrayList.add(songRef(jSONArrayOptJSONArray.optString(i), null));
      }
    }
    return arrayList;
  }

  private List<JSONObject> stationsNamed(String str) {
    String strNorm = norm(str);
    ArrayList arrayList = new ArrayList();
    ArrayList arrayList2 = new ArrayList();
    if (strNorm.isEmpty()) {
      return arrayList;
    }
    HashSet hashSet = new HashSet();
    String[] strArrWords = words(str);
    for (JSONObject jSONObject : knownStations()) {
      if (hashSet.add(stationId(jSONObject))) {
        if (norm(jSONObject.optString("title")).equals(strNorm)) {
          arrayList.add(jSONObject);
        } else if (matchesAll(jSONObject.optString("title"), strArrWords)) {
          arrayList2.add(jSONObject);
        }
      }
    }
    arrayList.addAll(arrayList2);
    return arrayList;
  }

  private synchronized String matchGenre(String str) {
    String strNorm = norm(str);
    if (strNorm.isEmpty()) {
      return null;
    }
    JSONArray jSONArrayOptJSONArray = this.catalog.optJSONArray("genres");
    if (jSONArrayOptJSONArray != null) {
      for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
        if (norm(jSONArrayOptJSONArray.optString(i)).equals(strNorm)) {
          return jSONArrayOptJSONArray.optString(i);
        }
      }
    }
    return null;
  }

  private static String stripSuffix(String str) {
    return str.replaceAll("(?i)\\s+(radio|station|stations|music|songs)$", "").trim();
  }

  private static String extra(Bundle bundle, String str) {
    if (bundle == null) {
      return null;
    }
    Object obj = bundle.get(str);
    String strTrim = obj == null ? null : String.valueOf(obj).trim();
    if (strTrim == null || strTrim.isEmpty()) {
      return null;
    }
    return strTrim;
  }

  private static String firstNonNull(String... strArr) {
    for (String str : strArr) {
      if (str != null) {
        return str;
      }
    }
    return "";
  }

  /**
   * Live radio-browser search, e.g. by="tag" (genres) or by="name". Tries each API host the page
   * uses, skips blacklisted stations and duplicate streams, caches results.
   */
  private List<JSONObject> stationSearch(String by, String term, int limit) throws JSONException {
    String cacheKey = by + ":" + term.toLowerCase(Locale.ROOT);
    CachedList cached = netCache.get(cacheKey);
    if (cached != null && cached.fresh()) return cached.items;
    List<String> hosts = new ArrayList<>();
    Set<String> blocked = new HashSet<>();
    synchronized (this) {
      JSONArray h = catalog.optJSONArray("apiHosts");
      if (h != null) for (int i = 0; i < h.length(); i++) hosts.add(h.optString(i));
      JSONArray b = catalog.optJSONArray("blacklist");
      if (b != null) for (int i = 0; i < b.length(); i++) blocked.add(b.optString(i));
    }
    if (hosts.isEmpty()) hosts.add("https://de1.api.radio-browser.info");
    for (String host : hosts) {
      try {
        String url =
            host
                + "/json/stations/search?"
                + by
                + "="
                + URLEncoder.encode(term, "UTF-8")
                + "&limit="
                + limit
                + "&hidebroken=true&order=clickcount&reverse=true";
        JSONArray res = new JSONArray(httpGet(url, 2 * 1024 * 1024));
        List<JSONObject> out = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < res.length(); i++) {
          JSONObject s = res.optJSONObject(i);
          if (s == null) continue;
          String stream = s.optString("url_resolved", "");
          if (stream.isEmpty()) stream = s.optString("url", "");
          String id = s.optString("stationuuid", stream);
          if (stream.isEmpty() || blocked.contains(id) || blocked.contains(stream)) continue;
          if (!seen.add(stream)) continue;
          String[] tags = s.optString("tags", "").split(",");
          StringBuilder sub = new StringBuilder();
          for (int t = 0; t < tags.length && t < 3; t++) {
            if (tags[t].trim().isEmpty()) continue;
            if (sub.length() > 0) sub.append(", ");
            sub.append(tags[t].trim());
          }
          if (sub.length() == 0) {
            String country = s.optString("country", "");
            if (country.trim().equalsIgnoreCase("The United Arab Emirates"))
              country = "Amplify Radio";
            sub.append(country);
          }
          JSONObject e = new JSONObject();
          e.put("t", "station");
          e.put("k", id);
          e.put("title", s.optString("name", "Station").trim());
          e.put("sub", sub.toString());
          e.put("art", s.optString("favicon", ""));
          e.put("url", stream);
          out.add(e);
        }
        netCache.put(cacheKey, new CachedList(out));
        return out;
      } catch (Exception ignored) {
        // try the next host
      }
    }
    return cached != null ? cached.items : Collections.<JSONObject>emptyList();
  }

  private List<JSONObject> podcastSearch(String str) {
    String str2 = "pod:" + str.toLowerCase(Locale.ROOT);
    CachedList cachedList = this.netCache.get(str2);
    if (cachedList != null && cachedList.fresh()) {
      return cachedList.items;
    }
    ArrayList arrayList = new ArrayList();
    try {
      JSONArray jSONArrayOptJSONArray =
          new JSONObject(
                  httpGet(
                      "https://itunes.apple.com/search?media=podcast&limit=8&term="
                          + URLEncoder.encode(str, "UTF-8"),
                      2097152))
              .optJSONArray("results");
      if (jSONArrayOptJSONArray != null) {
        for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
          JSONObject jSONObjectOptJSONObject = jSONArrayOptJSONArray.optJSONObject(i);
          if (jSONObjectOptJSONObject != null
              && jSONObjectOptJSONObject.opt("collectionId") != null) {
            JSONObject jSONObject = new JSONObject();
            jSONObject.put("t", "show");
            jSONObject.put("cid", String.valueOf(jSONObjectOptJSONObject.opt("collectionId")));
            jSONObject.put("title", jSONObjectOptJSONObject.optString("collectionName", "Podcast"));
            jSONObject.put("sub", jSONObjectOptJSONObject.optString("artistName", ""));
            jSONObject.put(
                "art",
                firstNonEmpty(
                    jSONObjectOptJSONObject, "artworkUrl600", "artworkUrl100", "artworkUrl60"));
            this.extraShows.put(jSONObject.optString("cid"), jSONObject);
            arrayList.add(jSONObject);
          }
        }
      }
      this.netCache.put(str2, new CachedList(arrayList));
      return arrayList;
    } catch (Exception unused) {
      return cachedList != null ? cachedList.items : arrayList;
    }
  }

  private synchronized JSONObject findShow(String str) {
    JSONObject jSONObjectOptJSONObject = this.catalog.optJSONObject("lists");
    if (jSONObjectOptJSONObject == null) {
      return null;
    }
    String[] strArr = {"shows", "popular"};
    for (int i = 0; i < 2; i++) {
      JSONArray jSONArrayOptJSONArray = jSONObjectOptJSONObject.optJSONArray(strArr[i]);
      if (jSONArrayOptJSONArray != null) {
        for (int i2 = 0; i2 < jSONArrayOptJSONArray.length(); i2++) {
          JSONObject jSONObjectOptJSONObject2 = jSONArrayOptJSONArray.optJSONObject(i2);
          if (jSONObjectOptJSONObject2 != null
              && str.equals(jSONObjectOptJSONObject2.optString("cid"))) {
            return jSONObjectOptJSONObject2;
          }
        }
      }
    }
    return this.extraShows.get(str);
  }

  private List<JSONObject> showEpisodes(String cid) {
    CachedList c = netCache.get("show:" + cid);
    if (c != null && c.fresh()) return c.items;
    List<JSONObject> out = new ArrayList<>();
    try {
      String url =
          "https://itunes.apple.com/lookup?id="
              + URLEncoder.encode(cid, "UTF-8")
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
          String art =
              firstNonEmpty(r, "artworkUrl600", "artworkUrl160", "artworkUrl100", "artworkUrl60");
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
      netCache.put("show:" + cid, new CachedList(out));
    } catch (Exception ignored) {
      if (c != null) return c.items; // an older list beats none
    }
    return out;
  }

  private static List<JSONObject> arrayOf(JSONObject jSONObject, String str) {
    ArrayList arrayList = new ArrayList();
    JSONArray jSONArrayOptJSONArray = jSONObject == null ? null : jSONObject.optJSONArray(str);
    if (jSONArrayOptJSONArray != null) {
      for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
        JSONObject jSONObjectOptJSONObject = jSONArrayOptJSONArray.optJSONObject(i);
        if (jSONObjectOptJSONObject != null) {
          arrayList.add(jSONObjectOptJSONObject);
        }
      }
    }
    return arrayList;
  }

  private static JSONObject withGroup(JSONObject jSONObject, String str) {
    JSONObject jSONObject2 = new JSONObject();
    try {
      Iterator<String> itKeys = jSONObject.keys();
      while (itKeys.hasNext()) {
        String next = itKeys.next();
        jSONObject2.put(next, jSONObject.opt(next));
      }
      jSONObject2.put("g", str);
    } catch (Exception unused) {
    }
    return jSONObject2;
  }

  static String enc(String str) {
    return Base64.encodeToString(str.getBytes(StandardCharsets.UTF_8), 11);
  }

  static String dec(String str) {
    try {
      return new String(Base64.decode(str, 10), StandardCharsets.UTF_8);
    } catch (Exception unused) {
      return "";
    }
  }

  static String norm(String str) {
    if (str == null) {
      return "";
    }
    return Normalizer.normalize(str, Normalizer.Form.NFD)
        .replaceAll("\\p{M}+", "")
        .toLowerCase(Locale.ROOT)
        .replace("&", " and ")
        .replaceAll("[^a-z0-9]+", " ")
        .trim();
  }

  private static String[] words(String str) {
    String strNorm = norm(str);
    return strNorm.isEmpty() ? new String[0] : strNorm.split(" ");
  }

  private static boolean matchesAll(String str, String[] strArr) {
    if (strArr.length == 0) {
      return false;
    }
    String str2 = " " + norm(str) + " ";
    for (String str3 : strArr) {
      if (!str2.contains(" " + str3)) {
        return false;
      }
    }
    return true;
  }

  private synchronized JSONObject findIn(String str, String str2) {
    JSONArray jSONArrayOptJSONArray = this.catalog.optJSONArray(str);
    if (jSONArrayOptJSONArray == null) {
      return null;
    }
    for (int i = 0; i < jSONArrayOptJSONArray.length(); i++) {
      JSONObject jSONObjectOptJSONObject = jSONArrayOptJSONArray.optJSONObject(i);
      if (jSONObjectOptJSONObject != null && str2.equals(jSONObjectOptJSONObject.optString("id"))) {
        return jSONObjectOptJSONObject;
      }
    }
    return null;
  }

  private static String firstNonEmpty(JSONObject jSONObject, String... strArr) {
    for (String str : strArr) {
      String strOptString = jSONObject.optString(str, "");
      if (!strOptString.isEmpty()) {
        return strOptString;
      }
    }
    return "";
  }

  private static String emptyToNull(String str) {
    if (str == null || str.isEmpty()) {
      return null;
    }
    return str;
  }

  static String readFile(File file) throws FileNotFoundException, IOException {
    FileInputStream fileInputStream = new FileInputStream(file);
    try {
      String all = readAll(fileInputStream, Integer.MAX_VALUE);
      fileInputStream.close();
      return all;
    } catch (Throwable th) {
      try {
        fileInputStream.close();
      } catch (Throwable th2) {
        th.addSuppressed(th2);
      }
      throw th;
    }
  }

  private static String readAll(InputStream inputStream, int i) throws IOException {
    StringBuilder sb = new StringBuilder();
    BufferedReader bufferedReader =
        new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8));
    try {
      char[] cArr = new char[8192];
      do {
        int i2 = bufferedReader.read(cArr);
        if (i2 <= 0) {
          break;
        }
        sb.append(cArr, 0, i2);
      } while (sb.length() <= i);
      bufferedReader.close();
      return sb.toString();
    } catch (Throwable th) {
      try {
        bufferedReader.close();
      } catch (Throwable th2) {
        th.addSuppressed(th2);
      }
      throw th;
    }
  }

  static String httpGet(String str, int i) throws Exception {
    HttpURLConnection httpURLConnection = (HttpURLConnection) new URL(str).openConnection();
    try {
      httpURLConnection.setConnectTimeout(8000);
      httpURLConnection.setReadTimeout(12000);
      httpURLConnection.setRequestProperty("User-Agent", "Amplify/1.0 (Android)");
      if (httpURLConnection.getResponseCode() != 200) {
        throw new Exception("HTTP " + httpURLConnection.getResponseCode());
      }
      return readAll(httpURLConnection.getInputStream(), i);
    } finally {
      httpURLConnection.disconnect();
    }
  }
}
