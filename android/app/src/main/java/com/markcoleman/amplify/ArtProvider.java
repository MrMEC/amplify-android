package com.markcoleman.amplify;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.util.Base64;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Android Auto only loads artwork through content:// uris, never straight from the web. This
 * provider stands in for a web image: content://com.markcoleman.amplify.art/<base64 url>
 * downloads the image once into the cache and serves the file from there.
 */
public final class ArtProvider extends ContentProvider {

  static final String AUTHORITY = "com.markcoleman.amplify.art";
  private static final long MAX_BYTES = 6L * 1024 * 1024;

  /** The content:// stand-in for a web image, or null when there is nothing to show. */
  @Nullable
  static Uri uriFor(@Nullable String url) {
    if (url == null) return null;
    String u = url.trim();
    if (u.isEmpty()) return null;
    if (u.startsWith("content:") || u.startsWith("android.resource:")) return Uri.parse(u);
    if (!u.startsWith("http://") && !u.startsWith("https://")) return null;
    String enc =
        Base64.encodeToString(
            u.getBytes(StandardCharsets.UTF_8), Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
    return new Uri.Builder().scheme("content").authority(AUTHORITY).appendPath(enc).build();
  }

  @Override
  public boolean onCreate() {
    return true;
  }

  @Nullable
  @Override
  public ParcelFileDescriptor openFile(@NonNull Uri uri, @NonNull String mode)
      throws FileNotFoundException {
    String seg = uri.getLastPathSegment();
    if (seg == null) throw new FileNotFoundException("No image");
    String url;
    try {
      url = new String(Base64.decode(seg, Base64.URL_SAFE), StandardCharsets.UTF_8);
    } catch (Exception e) {
      throw new FileNotFoundException("Bad image uri");
    }
    File dir = new File(getContext().getCacheDir(), "art");
    if (!dir.exists()) dir.mkdirs();
    File f = new File(dir, sha1(url));
    if (!f.exists() || f.length() == 0) download(url, f);
    if (!f.exists() || f.length() == 0) throw new FileNotFoundException("Image unavailable");
    f.setLastModified(System.currentTimeMillis());
    return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
  }

  private static void download(String url, File dest) {
    File part = new File(dest.getPath() + ".part");
    HttpURLConnection c = null;
    try {
      String current = url;
      for (int hop = 0; hop < 5; hop++) {
        c = (HttpURLConnection) new URL(current).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(10000);
        c.setInstanceFollowRedirects(false);
        c.setRequestProperty("User-Agent", "Amplify/1.0 (Android)");
        int code = c.getResponseCode();
        if (code >= 300 && code < 400 && c.getHeaderField("Location") != null) {
          current = new URL(new URL(current), c.getHeaderField("Location")).toString();
          c.disconnect();
          continue;
        }
        if (code != 200) return;
        try (InputStream in = c.getInputStream();
            FileOutputStream out = new FileOutputStream(part)) {
          byte[] buf = new byte[16384];
          long total = 0;
          int n;
          while ((n = in.read(buf)) > 0) {
            total += n;
            if (total > MAX_BYTES) return;
            out.write(buf, 0, n);
          }
        }
        if (!part.renameTo(dest)) part.delete();
        return;
      }
    } catch (Exception ignored) {
      part.delete();
    } finally {
      if (c != null) c.disconnect();
    }
  }

  private static String sha1(String s) {
    try {
      byte[] d = MessageDigest.getInstance("SHA-1").digest(s.getBytes(StandardCharsets.UTF_8));
      StringBuilder b = new StringBuilder();
      for (byte x : d) b.append(String.format("%02x", x));
      return b.toString();
    } catch (Exception e) {
      return String.valueOf(s.hashCode());
    }
  }

  @Nullable
  @Override
  public String getType(@NonNull Uri uri) {
    return "image/*";
  }

  @Nullable
  @Override
  public Cursor query(
      @NonNull Uri uri,
      @Nullable String[] projection,
      @Nullable String selection,
      @Nullable String[] selectionArgs,
      @Nullable String sortOrder) {
    return null;
  }

  @Nullable
  @Override
  public Uri insert(@NonNull Uri uri, @Nullable ContentValues values) {
    return null;
  }

  @Override
  public int delete(
      @NonNull Uri uri, @Nullable String selection, @Nullable String[] selectionArgs) {
    return 0;
  }

  @Override
  public int update(
      @NonNull Uri uri,
      @Nullable ContentValues values,
      @Nullable String selection,
      @Nullable String[] selectionArgs) {
    return 0;
  }
}
