package com.markcoleman.amplify;

import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.provider.OpenableColumns;
import com.getcapacitor.JSObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Build 223: a music file opened from another app (Files, a download, a chat) with Amplify
 * chosen as the player. The file is copied into the app's cache (the other app's permission to
 * read it can end at any time), its tags and cover are read, and the page is told; it plays it
 * like a song, without adding it to the library.
 */
final class OpenedFile {
  private static final String TAKEN = "com.markcoleman.amplify.OPENED_TAKEN";
  private static JSObject pending;
  private static long seq;

  private OpenedFile() {}

  static boolean isAudio(String type) {
    if (type == null) return true; // unknown: let the player try
    type = type.toLowerCase();
    return type.startsWith("audio/") || type.equals("application/ogg") || type.equals("application/x-ogg")
        || type.equals("application/flac") || type.equals("application/x-flac");
  }

  /** Called by MainActivity for the intent it was started or resumed with. */
  static void handle(Context activity, Intent intent) {
    if (intent == null || !Intent.ACTION_VIEW.equals(intent.getAction())) return;
    final Uri uri = intent.getData();
    if (uri == null || intent.getBooleanExtra(TAKEN, false)) return;
    intent.putExtra(TAKEN, true);
    final Context ctx = activity.getApplicationContext();
    String t = intent.getType();
    if (t == null) {
      try { t = ctx.getContentResolver().getType(uri); } catch (Throwable ignored) { }
    }
    final String type = t;
    if (!isAudio(type)) return;
    final long id;
    synchronized (OpenedFile.class) { id = ++seq; }
    new Thread(() -> {
      JSObject o;
      try {
        o = prepare(ctx, uri, type);
      } catch (Throwable e) {
        CrashLog.note(ctx, "opened file", e);
        o = new JSObject();
        o.put("error", "Couldn't open that file.");
        o.put("name", displayName(ctx, uri));
      }
      o.put("seq", id);
      synchronized (OpenedFile.class) {
        if (id != seq) return; // a newer file was opened meanwhile
        pending = o;
      }
      AmplifyPlayerPlugin p = AmplifyPlayerPlugin.instance;
      if (p != null) p.openedFileReady();
    }, "amplify-open-file").start();
  }

  /** The file waiting for the page, once (null when there is none). */
  static synchronized JSObject take() {
    JSObject o = pending;
    pending = null;
    return o;
  }

  static String displayName(Context ctx, Uri uri) {
    String name = null;
    if (ContentResolver.SCHEME_CONTENT.equals(uri.getScheme())) {
      try (Cursor c = ctx.getContentResolver().query(uri, new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
        if (c != null && c.moveToFirst() && !c.isNull(0)) name = c.getString(0);
      } catch (Throwable ignored) { }
    }
    if (name == null || name.isEmpty()) name = uri.getLastPathSegment();
    if (name == null || name.isEmpty()) name = "Audio file";
    int slash = name.lastIndexOf('/');
    return slash >= 0 ? name.substring(slash + 1) : name;
  }

  private static JSObject prepare(Context ctx, Uri uri, String type) throws Exception {
    String name = displayName(ctx, uri);
    File dir = new File(ctx.getCacheDir(), "opened");
    if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("no cache dir");
    // Only the latest opened file is kept (an old one still playing keeps its open handle).
    File[] old = dir.listFiles();
    if (old != null) for (File f : old) f.delete();
    String ext = "";
    int dot = name.lastIndexOf('.');
    if (dot > 0 && name.length() - dot <= 6) ext = name.substring(dot).replaceAll("[^A-Za-z0-9.]", "");
    long stamp = System.currentTimeMillis();
    File out = new File(dir, "f" + stamp + ext);
    long size = 0;
    try (InputStream in = ctx.getContentResolver().openInputStream(uri);
         OutputStream os = new FileOutputStream(out)) {
      if (in == null) throw new IllegalStateException("unreadable");
      byte[] buf = new byte[64 * 1024];
      int n;
      while ((n = in.read(buf)) > 0) { os.write(buf, 0, n); size += n; }
    }
    JSObject o = new JSObject();
    o.put("url", Uri.fromFile(out).toString());
    o.put("path", out.getAbsolutePath());
    o.put("name", name);
    o.put("mime", type == null ? "" : type);
    o.put("size", size);
    MediaMetadataRetriever r = new MediaMetadataRetriever();
    try {
      r.setDataSource(out.getAbsolutePath());
      put(o, "title", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE));
      put(o, "artist", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST));
      put(o, "albumArtist", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUMARTIST));
      put(o, "album", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM));
      put(o, "genre", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_GENRE));
      String d = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
      if (d != null) {
        try { o.put("duration", (Object) Double.valueOf(Long.parseLong(d) / 1000.0)); } catch (NumberFormatException ignored) { }
      }
      byte[] pic = r.getEmbeddedPicture();
      if (pic != null && pic.length > 0) {
        File art = new File(dir, "a" + stamp + ".img");
        try (OutputStream os = new FileOutputStream(art)) { os.write(pic); }
        o.put("art", art.getAbsolutePath());
      }
    } catch (Throwable ignored) {
      // No tags it can read: the file name stands in for the title.
    } finally {
      try { r.release(); } catch (Throwable ignored) { }
    }
    return o;
  }

  private static void put(JSObject o, String k, String v) {
    if (v != null && !v.trim().isEmpty()) o.put(k, v.trim());
  }
}
