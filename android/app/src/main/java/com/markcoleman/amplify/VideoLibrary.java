package com.markcoleman.amplify;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.Build;
import android.provider.DocumentsContract;
import androidx.annotation.Nullable;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import java.io.File;
import java.io.FileOutputStream;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * Movies and TV shows kept on the phone. The files are never copied: a folder is picked once (its
 * read permission kept), its video files are listed with their content:// addresses, and the native
 * player plays them from where they are. Alongside each video the listing carries the pictures
 * (posters), subtitle files (.srt / .vtt) and .nfo files in the same folders, so the page can match
 * them up. videoInfo() reads a file's length and picture size and grabs a still from it for a
 * poster when the folder has none; the still is kept in the app's own files, so it is only made
 * once.
 */
final class VideoLibrary {
  static final List<String> VIDEO_EXTS =
      Arrays.asList(
          "mp4", "m4v", "mkv", "webm", "mov", "avi", "wmv", "flv", "mpg", "mpeg", "ts", "m2ts",
          "3gp", "ogv");
  static final List<String> SIDE_EXTS =
      Arrays.asList("jpg", "jpeg", "png", "webp", "srt", "vtt", "ass", "ssa", "nfo");
  private static final int MAX_DEPTH = 12;
  private static final int MAX_FILES = 30000;

  private VideoLibrary() {}

  private static String ext(String name) {
    int dot = name.lastIndexOf('.');
    return dot >= 0 ? name.substring(dot + 1).toLowerCase(Locale.ROOT) : "";
  }

  /** Every video (and poster / subtitle / .nfo) under a picked folder. */
  static JSObject walk(ContentResolver cr, Uri tree) {
    String rootId = DocumentsContract.getTreeDocumentId(tree);
    String rootName = displayName(cr, DocumentsContract.buildDocumentUriUsingTree(tree, rootId));
    if (rootName == null || rootName.isEmpty()) {
      int c = rootId.lastIndexOf(':');
      rootName = c >= 0 ? rootId.substring(c + 1) : rootId;
      int s = rootName.lastIndexOf('/');
      if (s >= 0) rootName = rootName.substring(s + 1);
      if (rootName.isEmpty()) rootName = "Videos";
    }
    JSArray files = new JSArray();
    int count = 0;
    boolean truncated = false;
    String[] cols = {
      DocumentsContract.Document.COLUMN_DOCUMENT_ID,
      DocumentsContract.Document.COLUMN_DISPLAY_NAME,
      DocumentsContract.Document.COLUMN_MIME_TYPE,
      DocumentsContract.Document.COLUMN_SIZE,
      DocumentsContract.Document.COLUMN_LAST_MODIFIED
    };
    ArrayDeque<String[]> queue = new ArrayDeque<>(); // {docId, relDir, depth}
    queue.add(new String[] {rootId, rootName, "0"});
    while (!queue.isEmpty() && !truncated) {
      String[] dir = queue.poll();
      int depth = Integer.parseInt(dir[2]);
      Uri kids = DocumentsContract.buildChildDocumentsUriUsingTree(tree, dir[0]);
      try (Cursor c = cr.query(kids, cols, null, null, null)) {
        if (c == null) continue;
        while (c.moveToNext()) {
          String id = c.getString(0);
          String name = c.getString(1);
          String mime = c.getString(2);
          if (id == null || name == null || name.startsWith(".")) continue;
          if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
            if (depth < MAX_DEPTH) {
              queue.add(new String[] {id, dir[1] + "/" + name, String.valueOf(depth + 1)});
            }
            continue;
          }
          String m = mime == null ? "" : mime;
          String e = ext(name);
          boolean video = m.startsWith("video/") || VIDEO_EXTS.contains(e);
          if (!video && !SIDE_EXTS.contains(e)) continue;
          JSObject f = new JSObject();
          f.put("uri", DocumentsContract.buildDocumentUriUsingTree(tree, id).toString());
          f.put("name", name);
          f.put("relPath", dir[1] + "/" + name);
          f.put("type", m);
          f.put("video", video);
          f.put("size", c.isNull(3) ? 0 : c.getLong(3));
          f.put("lastModified", c.isNull(4) ? 0 : c.getLong(4));
          files.put(f);
          if (++count >= MAX_FILES) {
            truncated = true;
            break;
          }
        }
      } catch (Exception ignored) {
        // An unreadable subfolder is skipped rather than failing the whole scan.
      }
    }
    JSObject o = new JSObject();
    o.put("folder", rootName);
    o.put("treeUri", tree.toString());
    o.put("files", files);
    o.put("truncated", truncated);
    return o;
  }

  @Nullable
  private static String displayName(ContentResolver cr, Uri doc) {
    try (Cursor c =
        cr.query(
            doc, new String[] {DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
      if (c != null && c.moveToFirst()) return c.getString(0);
    } catch (Exception ignored) {
    }
    return null;
  }

  private static String hash(String s) {
    try {
      MessageDigest md = MessageDigest.getInstance("SHA-1");
      byte[] b = md.digest(s.getBytes("UTF-8"));
      StringBuilder sb = new StringBuilder();
      for (int i = 0; i < 12; i++) sb.append(String.format(Locale.ROOT, "%02x", b[i]));
      return sb.toString();
    } catch (Exception e) {
      return Integer.toHexString(s.hashCode());
    }
  }

  /**
   * A video's length (ms), picture size, and a still from it saved as a JPEG in the app's files
   * (made once; the file's address is returned). A still from about a sixth of the way in, not the
   * first frame, which is usually black or a studio logo.
   */
  static JSObject info(Context context, String uriString, boolean wantThumb) {
    JSObject o = new JSObject();
    Uri uri = Uri.parse(uriString);
    File dir = new File(context.getFilesDir(), "vthumbs");
    File thumb = new File(dir, hash(uriString) + ".jpg");
    MediaMetadataRetriever r = new MediaMetadataRetriever();
    try {
      r.setDataSource(context, uri);
      long dur = parseLong(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
      int w = (int) parseLong(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH));
      int h = (int) parseLong(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT));
      int rot =
          (int) parseLong(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION));
      if (rot == 90 || rot == 270) {
        int t = w;
        w = h;
        h = t;
      }
      o.put("duration", dur);
      o.put("width", w);
      o.put("height", h);
      String title = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE);
      if (title != null && !title.trim().isEmpty()) o.put("title", title.trim());
      if (wantThumb) {
        if (!thumb.exists()) {
          long at = dur > 0 ? Math.min(dur / 6, 8 * 60 * 1000L) * 1000L : 5_000_000L;
          Bitmap frame;
          if (Build.VERSION.SDK_INT >= 27 && w > 0 && h > 0) {
            int tw = Math.min(640, w);
            int th = Math.max(1, Math.round(tw * (float) h / w));
            frame = r.getScaledFrameAtTime(at, MediaMetadataRetriever.OPTION_CLOSEST_SYNC, tw, th);
          } else {
            frame = r.getFrameAtTime(at, MediaMetadataRetriever.OPTION_CLOSEST_SYNC);
            if (frame != null && frame.getWidth() > 640) {
              int th = Math.max(1, Math.round(640f * frame.getHeight() / frame.getWidth()));
              Bitmap s = Bitmap.createScaledBitmap(frame, 640, th, true);
              if (s != frame) frame.recycle();
              frame = s;
            }
          }
          if (frame != null) {
            if (!dir.exists()) dir.mkdirs();
            try (FileOutputStream out = new FileOutputStream(thumb)) {
              frame.compress(Bitmap.CompressFormat.JPEG, 82, out);
            }
            frame.recycle();
          }
        }
        if (thumb.exists()) o.put("thumb", Uri.fromFile(thumb).toString());
      }
    } catch (Exception e) {
      o.put("error", e.getMessage() == null ? "unreadable" : e.getMessage());
    } finally {
      try {
        r.release();
      } catch (Exception ignored) {
      }
    }
    return o;
  }

  private static long parseLong(@Nullable String s) {
    if (s == null) return 0;
    try {
      return Long.parseLong(s.trim());
    } catch (Exception e) {
      return 0;
    }
  }
}
