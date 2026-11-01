package com.markcoleman.amplify;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

/**
 * Downloads into a folder the person picked (build 379: archive.org items into the music or
 * video folder). Folders inside it are found by name or made; a file already there at the
 * expected size is left alone; a download that fails or is cancelled leaves no partial file.
 */
final class FolderDownloads {
  private FolderDownloads() {}

  interface Progress {
    /** Bytes of this file so far, and its size when the server says (else -1). */
    void on(long done, long total);
  }

  interface Cancelled {
    boolean now();
  }

  static final class CancelledException extends Exception {
    CancelledException() {
      super("Cancelled");
    }
  }

  private static final String[] COLS = {
    DocumentsContract.Document.COLUMN_DOCUMENT_ID,
    DocumentsContract.Document.COLUMN_DISPLAY_NAME,
    DocumentsContract.Document.COLUMN_MIME_TYPE,
    DocumentsContract.Document.COLUMN_SIZE,
    DocumentsContract.Document.COLUMN_LAST_MODIFIED
  };

  /** A name that every storage provider accepts. */
  static String safeName(String s) {
    if (s == null) s = "";
    s = s.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", " ").replaceAll("\\s+", " ").trim();
    while (s.startsWith(".")) s = s.substring(1).trim();
    while (s.endsWith(".")) s = s.substring(0, s.length() - 1).trim();
    if (s.length() > 120) s = s.substring(0, 120).trim();
    return s.isEmpty() ? "Untitled" : s;
  }

  static String mimeOf(String name) {
    int dot = name.lastIndexOf('.');
    String ext = dot >= 0 ? name.substring(dot + 1).toLowerCase(Locale.ROOT) : "";
    switch (ext) {
      case "mp3": return "audio/mpeg";
      case "ogg": case "oga": return "audio/ogg";
      case "flac": return "audio/flac";
      case "m4a": return "audio/mp4";
      case "wav": return "audio/wav";
      case "opus": return "audio/opus";
      case "mp4": case "m4v": return "video/mp4";
      case "mkv": return "video/x-matroska";
      case "webm": return "video/webm";
      case "avi": return "video/x-msvideo";
      case "mpg": case "mpeg": return "video/mpeg";
      case "jpg": case "jpeg": return "image/jpeg";
      case "png": return "image/png";
      default: return "application/octet-stream";
    }
  }

  /** {docId, size, modified} of a child with this name, or null. */
  static String[] child(ContentResolver cr, Uri tree, String parentId, String name, boolean dir) {
    Uri kids = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
    try (Cursor c = cr.query(kids, COLS, null, null, null)) {
      if (c == null) return null;
      while (c.moveToNext()) {
        String n = c.getString(1), m = c.getString(2);
        boolean isDir = DocumentsContract.Document.MIME_TYPE_DIR.equals(m);
        if (n != null && n.equalsIgnoreCase(name) && isDir == dir) {
          return new String[] {
            c.getString(0),
            String.valueOf(c.isNull(3) ? 0 : c.getLong(3)),
            String.valueOf(c.isNull(4) ? 0 : c.getLong(4))
          };
        }
      }
    }
    return null;
  }

  /** The folder at this path inside the tree (made where missing); its document id. */
  static String folder(ContentResolver cr, Uri tree, String[] path) throws Exception {
    String id = DocumentsContract.getTreeDocumentId(tree);
    for (String raw : path) {
      String name = safeName(raw);
      String[] got = child(cr, tree, id, name, true);
      if (got != null) {
        id = got[0];
        continue;
      }
      Uri parent = DocumentsContract.buildDocumentUriUsingTree(tree, id);
      Uri made = DocumentsContract.createDocument(cr, parent, DocumentsContract.Document.MIME_TYPE_DIR, name);
      if (made == null) throw new Exception("The folder " + name + " couldn't be made");
      id = DocumentsContract.getDocumentId(made);
    }
    return id;
  }

  static HttpURLConnection open(String url) throws Exception {
    String u = url;
    for (int hop = 0; hop < 6; hop++) {
      HttpURLConnection h = (HttpURLConnection) new URL(u).openConnection();
      h.setInstanceFollowRedirects(false);
      h.setConnectTimeout(20000);
      h.setReadTimeout(60000);
      h.setRequestProperty("User-Agent", "Amplify (Android)");
      int code = h.getResponseCode();
      if (code >= 300 && code < 400) {
        String loc = h.getHeaderField("Location");
        h.disconnect();
        if (loc == null) throw new Exception("The download went nowhere");
        u = new URL(new URL(u), loc).toString();
        continue;
      }
      if (code < 200 || code >= 300) {
        h.disconnect();
        throw new Exception("The server said " + code);
      }
      return h;
    }
    throw new Exception("Too many redirects");
  }

  /**
   * Downloads one file into the folder. Returns {docId, size, modified, skipped("1"/"0")}.
   * `expect` is the size the source lists (0 when unknown): a file already there at that size
   * is kept as it is.
   */
  static String[] download(
      ContentResolver cr, Uri tree, String folderId, String name, String url, long expect, Progress p, Cancelled cancel)
      throws Exception {
    name = safeName(name);
    String[] have = child(cr, tree, folderId, name, false);
    if (have != null && expect > 0 && Long.parseLong(have[1]) == expect) {
      return new String[] {have[0], have[1], have[2], "1"};
    }
    Uri doc;
    if (have != null) {
      doc = DocumentsContract.buildDocumentUriUsingTree(tree, have[0]);
    } else {
      Uri parent = DocumentsContract.buildDocumentUriUsingTree(tree, folderId);
      doc = DocumentsContract.createDocument(cr, parent, mimeOf(name), name);
      if (doc == null) throw new Exception("The file couldn't be made");
    }
    boolean ok = false;
    HttpURLConnection h = null;
    try {
      h = open(url);
      long total = h.getContentLengthLong();
      if (total <= 0 && expect > 0) total = expect;
      try (InputStream in = h.getInputStream(); OutputStream out = cr.openOutputStream(doc, "wt")) {
        if (out == null) throw new Exception("The file couldn't be opened");
        byte[] buf = new byte[64 * 1024];
        long done = 0, told = 0;
        int n;
        while ((n = in.read(buf)) > 0) {
          if (cancel.now()) throw new CancelledException();
          out.write(buf, 0, n);
          done += n;
          if (done - told >= 256 * 1024) {
            told = done;
            p.on(done, total);
          }
        }
        p.on(done, total);
      }
      ok = true;
    } finally {
      if (h != null) h.disconnect();
      if (!ok) {
        try {
          DocumentsContract.deleteDocument(cr, doc);
        } catch (Exception ignored) {
        }
      }
    }
    String id = DocumentsContract.getDocumentId(doc);
    String size = "0", mod = "0";
    try (Cursor c = cr.query(doc, COLS, null, null, null)) {
      if (c != null && c.moveToFirst()) {
        size = String.valueOf(c.isNull(3) ? 0 : c.getLong(3));
        mod = String.valueOf(c.isNull(4) ? 0 : c.getLong(4));
      }
    } catch (Exception ignored) {
    }
    return new String[] {id, size, mod, "0"};
  }
}
