package com.markcoleman.amplify;

import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.Metadata;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.exoplayer.hls.HlsManifest;
import androidx.media3.exoplayer.hls.playlist.HlsMediaPlaylist;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.Date;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/**
 * What a stream says about itself while it plays, for the "Stream Details" view: timed metadata
 * inside the stream (ID3 tags, ICY titles, emsg boxes) and the tags in its HLS playlist that can
 * carry programme information (EXT-X-DATERANGE, cue markers, titled segments). Kept in a small
 * list, newest last, cleared when something new loads; repeats are left out.
 */
@OptIn(markerClass = UnstableApi.class)
final class StreamProbe {
  private static final int MAX = 80;
  private final ArrayDeque<String[]> entries = new ArrayDeque<>(); // {time, kind, text}
  private final Set<String> seen = new HashSet<>();
  private final SimpleDateFormat clock = new SimpleDateFormat("HH:mm:ss", Locale.US);
  private int playlistTags;
  private int playlistSegments;

  synchronized void clear() {
    entries.clear();
    seen.clear();
    playlistTags = 0;
    playlistSegments = 0;
  }

  private void add(String kind, String text) {
    if (text == null) return;
    text = text.trim();
    if (text.isEmpty()) return;
    if (text.length() > 600) text = text.substring(0, 600) + "…";
    if (!seen.add(kind + "|" + text)) return;
    entries.addLast(new String[] {clock.format(new Date()), kind, text});
    while (entries.size() > MAX) entries.removeFirst();
  }

  synchronized void noteMetadata(Metadata metadata) {
    if (metadata == null) return;
    for (int i = 0; i < metadata.length(); i++) {
      Metadata.Entry e = metadata.get(i);
      add("In the stream", String.valueOf(e));
    }
  }

  synchronized void noteManifest(@Nullable Object manifest) {
    if (!(manifest instanceof HlsManifest)) return;
    HlsMediaPlaylist p = ((HlsManifest) manifest).mediaPlaylist;
    if (p == null) return;
    playlistTags = p.tags == null ? 0 : p.tags.size();
    playlistSegments = p.segments == null ? 0 : p.segments.size();
    if (p.tags != null) {
      for (String t : p.tags) {
        String u = t.toUpperCase(Locale.ROOT);
        if (u.contains("DATERANGE")
            || u.contains("TITLE")
            || u.contains("PROGRAM")
            || u.contains("CUE")
            || u.contains("SCTE")
            || u.contains("ASSET")
            || u.contains("X-EVENT")
            || u.contains("X-DISCONTINUITY-SEQUENCE")) {
          add("Playlist", t);
        }
      }
    }
    if (p.segments != null) {
      for (HlsMediaPlaylist.Segment s : p.segments) {
        if (s.title != null && !s.title.trim().isEmpty()) add("Segment title", s.title);
      }
    }
  }

  synchronized JSObject toJson() {
    JSArray list = new JSArray();
    for (String[] e : entries) {
      JSObject o = new JSObject();
      o.put("time", e[0]);
      o.put("kind", e[1]);
      o.put("text", e[2]);
      list.put(o);
    }
    JSObject o = new JSObject();
    o.put("entries", list);
    o.put("playlistTags", playlistTags);
    o.put("playlistSegments", playlistSegments);
    return o;
  }
}
