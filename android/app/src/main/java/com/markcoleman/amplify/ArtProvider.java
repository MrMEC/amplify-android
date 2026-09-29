package com.markcoleman.amplify;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
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
import java.util.List;

/**
 * Android Auto only loads artwork through content:// uris, never straight from the web. This
 * provider stands in for a web image: content://com.markcoleman.amplify.art/<base64 url> downloads
 * the image once into the cache and serves the file from there.
 */
public final class ArtProvider extends ContentProvider {
  static final String AUTHORITY = "com.markcoleman.amplify.art";
  private static final long MAX_BYTES = 6291456;

  @Override
  public int delete(
      @NonNull Uri uri, @Nullable String selection, @Nullable String[] selectionArgs) {
    return 0;
  }

  @Nullable
  @Override
  public Uri insert(@NonNull Uri uri, @Nullable ContentValues values) {
    return null;
  }

  @Override
  public boolean onCreate() {
    return true;
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

  @Override
  public int update(
      @NonNull Uri uri,
      @Nullable ContentValues values,
      @Nullable String selection,
      @Nullable String[] selectionArgs) {
    return 0;
  }

  static Uri uriFor(String str) {
    if (str == null) {
      return null;
    }
    String strTrim = str.trim();
    if (strTrim.isEmpty()) {
      return null;
    }
    if (strTrim.startsWith("content:") || strTrim.startsWith("android.resource:")) {
      return Uri.parse(strTrim);
    }
    if (strTrim.startsWith("local:")) {
      String strSafeKey = safeKey(strTrim.substring(6));
      if (strSafeKey.isEmpty()) {
        return null;
      }
      return new Uri.Builder()
          .scheme("content")
          .authority("com.markcoleman.amplify.art")
          .appendPath("local")
          .appendPath(strSafeKey)
          .build();
    }
    if (!strTrim.startsWith("http://") && !strTrim.startsWith("https://")) {
      return null;
    }
    return new Uri.Builder()
        .scheme("content")
        .authority("com.markcoleman.amplify.art")
        .appendPath(Base64.encodeToString(strTrim.getBytes(StandardCharsets.UTF_8), 11))
        .build();
  }

  @Override // android.content.ContentProvider
  public ParcelFileDescriptor openFile(@NonNull Uri uri, @NonNull String mode)
      throws FileNotFoundException {
    String seg = uri.getLastPathSegment();
    if (seg == null) throw new FileNotFoundException("No image");
    // content://…art/local/<key>: album art the page uploaded (see putCarArt)
    List<String> path = uri.getPathSegments();
    if (path.size() == 2 && "local".equals(path.get(0))) {
      File f = localArt(getContext(), seg);
      if (!f.exists() || f.length() == 0) throw new FileNotFoundException("Image unavailable");
      return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }
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

  static String safeKey(String str) {
    return str == null ? "" : str.replaceAll("[^A-Za-z0-9_-]", "");
  }

  static File localArtDir(Context context) {
    File file = new File(context.getFilesDir(), "carart");
    if (!file.exists()) {
      file.mkdirs();
    }
    return file;
  }

  static File localArt(Context context, String str) {
    return new File(localArtDir(context), safeKey(str) + ".jpg");
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

  private static String sha1(String str) {
    try {
      byte[] bArrDigest =
          MessageDigest.getInstance("SHA-1").digest(str.getBytes(StandardCharsets.UTF_8));
      StringBuilder sb = new StringBuilder();
      for (byte b : bArrDigest) {
        sb.append(String.format("%02x", Byte.valueOf(b)));
      }
      return sb.toString();
    } catch (Exception unused) {
      return String.valueOf(str.hashCode());
    }
  }

  @Nullable
  @Override
  public String getType(@NonNull Uri uri) {
    return "image/*";
  }
}
