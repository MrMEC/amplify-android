package com.markcoleman.amplify;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

/**
 * Writes a file (an Export backup) into the phone's Downloads folder. In the app a page download
 * link does nothing -- the WebView ignores it -- so Export goes through here and reports where the
 * file actually went. Android 10+ uses MediaStore (no permission needed); older phones get the
 * app's own Download folder.
 */
final class DownloadsSaver {

  static final class Result {
    final String name;
    final String folder;
    final String uri;
    final int bytes;

    Result(String name, String folder, String uri, int bytes) {
      this.name = name;
      this.folder = folder;
      this.uri = uri;
      this.bytes = bytes;
    }
  }

  private DownloadsSaver() {}

  static Result save(Context context, String name, byte[] data, String mime) throws IOException {
    if (Build.VERSION.SDK_INT >= 29) {
      ContentResolver cr = context.getContentResolver();
      ContentValues values = new ContentValues();
      values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
      values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
      values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
      values.put(MediaStore.MediaColumns.IS_PENDING, 1);
      Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
      if (uri == null) throw new IOException("Downloads is not available");
      try (OutputStream out = cr.openOutputStream(uri)) {
        if (out == null) throw new IOException("could not open the file");
        out.write(data);
      } catch (IOException e) {
        cr.delete(uri, null, null);
        throw e;
      }
      ContentValues done = new ContentValues();
      done.put(MediaStore.MediaColumns.IS_PENDING, 0);
      cr.update(uri, done, null, null);
      // Downloads may already hold a file by that name, in which case Android picks a new one.
      try (Cursor c =
          cr.query(uri, new String[] {MediaStore.MediaColumns.DISPLAY_NAME}, null, null, null)) {
        if (c != null && c.moveToFirst() && c.getString(0) != null) name = c.getString(0);
      }
      return new Result(name, "Downloads", uri.toString(), data.length);
    }
    File dir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
    if (dir == null) throw new IOException("storage is not available");
    if (!dir.exists() && !dir.mkdirs()) throw new IOException("could not create " + dir);
    File f = uniqueFile(dir, name);
    try (FileOutputStream out = new FileOutputStream(f)) {
      out.write(data);
    }
    return new Result(
        f.getName(),
        "Android/data/" + context.getPackageName() + "/files/Download",
        Uri.fromFile(f).toString(),
        data.length);
  }

  /** name, or "name (1).ext", "name (2).ext"… if taken. */
  static File uniqueFile(File dir, String name) {
    File f = new File(dir, name);
    if (!f.exists()) return f;
    int dot = name.lastIndexOf('.');
    String base = dot > 0 ? name.substring(0, dot) : name;
    String ext = dot > 0 ? name.substring(dot) : "";
    for (int i = 1; ; i++) {
      f = new File(dir, base + " (" + i + ")" + ext);
      if (!f.exists()) return f;
    }
  }
}
