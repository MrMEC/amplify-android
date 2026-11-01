package com.markcoleman.amplify;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Automatic backups (build 373): the backup files in the folder the person chose (a document
 * tree they gave Amplify read and write access to). Files are named amplify-backup-<date>.json,
 * so name order is date order; only those are ever listed, replaced or removed.
 */
final class BackupFiles {
  private BackupFiles() {}

  static final Pattern NAME = Pattern.compile("^amplify-backup-[0-9A-Za-z_.\\-]+\\.json$");

  static final class Entry {
    final String name;
    final Uri uri;
    final long size;
    final long modified;

    Entry(String name, Uri uri, long size, long modified) {
      this.name = name;
      this.uri = uri;
      this.size = size;
      this.modified = modified;
    }
  }

  static Uri rootDoc(Uri tree) {
    return DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
  }

  /** The backup files directly in the folder, newest name first. */
  static List<Entry> list(ContentResolver cr, Uri tree) throws Exception {
    List<Entry> out = new ArrayList<>();
    Uri kids = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
    String[] cols = {
      DocumentsContract.Document.COLUMN_DOCUMENT_ID,
      DocumentsContract.Document.COLUMN_DISPLAY_NAME,
      DocumentsContract.Document.COLUMN_MIME_TYPE,
      DocumentsContract.Document.COLUMN_SIZE,
      DocumentsContract.Document.COLUMN_LAST_MODIFIED
    };
    try (Cursor c = cr.query(kids, cols, null, null, null)) {
      if (c == null) throw new Exception("The folder can't be read");
      while (c.moveToNext()) {
        String id = c.getString(0), name = c.getString(1), mime = c.getString(2);
        if (name == null || DocumentsContract.Document.MIME_TYPE_DIR.equals(mime) || !NAME.matcher(name).matches()) continue;
        out.add(new Entry(name, DocumentsContract.buildDocumentUriUsingTree(tree, id), c.isNull(3) ? 0 : c.getLong(3), c.isNull(4) ? 0 : c.getLong(4)));
      }
    }
    Collections.sort(out, (a, b) -> b.name.compareTo(a.name));
    return out;
  }

  /** Writes (or replaces) one backup file; then keeps only the newest `keep` of them. */
  static Entry write(ContentResolver cr, Uri tree, String name, String text, int keep, List<String> removed) throws Exception {
    if (!NAME.matcher(name).matches()) throw new Exception("Not a backup file name");
    Uri doc = null;
    for (Entry e : list(cr, tree)) if (e.name.equals(name)) doc = e.uri;
    if (doc == null) doc = DocumentsContract.createDocument(cr, rootDoc(tree), "application/json", name);
    if (doc == null) throw new Exception("The file couldn't be made");
    try (OutputStream os = cr.openOutputStream(doc, "wt")) {
      if (os == null) throw new Exception("The file couldn't be opened");
      os.write(text.getBytes(StandardCharsets.UTF_8));
    }
    if (keep > 0) {
      List<Entry> all = list(cr, tree);
      for (int i = keep; i < all.size(); i++) {
        try {
          if (DocumentsContract.deleteDocument(cr, all.get(i).uri)) removed.add(all.get(i).name);
        } catch (Exception ignored) {
          // An old backup that can't be removed stays; the new one is written either way.
        }
      }
    }
    for (Entry e : list(cr, tree)) if (e.name.equals(name)) return e;
    return new Entry(name, doc, text.length(), System.currentTimeMillis());
  }

  static String read(ContentResolver cr, Uri doc) throws Exception {
    try (InputStream in = cr.openInputStream(doc); ByteArrayOutputStream bo = new ByteArrayOutputStream()) {
      if (in == null) throw new Exception("The file couldn't be opened");
      byte[] buf = new byte[65536];
      int n;
      long total = 0;
      while ((n = in.read(buf)) > 0) {
        total += n;
        if (total > 64L * 1024 * 1024) throw new Exception("The file is too big to be a backup");
        bo.write(buf, 0, n);
      }
      return bo.toString("UTF-8");
    }
  }
}
