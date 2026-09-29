package com.markcoleman.amplify;

import android.content.Context;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** Items played from the car, kept until the page takes them (takeCarHistory) to update Recent. */
final class CarHistory {
  private static final int LIMIT = 100;

  private CarHistory() {}

  private static File file(Context context) {
    return new File(context.getFilesDir(), "car_history.json");
  }

  private static JSONArray readAll(Context context) {
    try {
      return new JSONArray(CarLibrary.readFile(file(context)));
    } catch (Exception unused) {
      return new JSONArray();
    }
  }

  /** Appends one played item (entry JSON); keeps the newest 100. */
  static synchronized void add(Context c, String itemJson) {
    try {
      JSONObject rec = new JSONObject();
      rec.put("item", new JSONObject(itemJson));
      rec.put("at", System.currentTimeMillis());
      JSONArray all = readAll(c);
      all.put(rec);
      JSONArray kept = new JSONArray();
      for (int i = Math.max(0, all.length() - 100); i < all.length(); i++) kept.put(all.get(i));
      File f = file(c);
      File part = new File(f.getPath() + ".part");
      try (FileOutputStream out = new FileOutputStream(part)) {
        out.write(kept.toString().getBytes(StandardCharsets.UTF_8));
      }
      if (!part.renameTo(f)) part.delete();
    } catch (Exception ignored) {
    }
  }

  static synchronized JSONArray takeAll(Context context) {
    JSONArray all;
    all = readAll(context);
    file(context).delete();
    return all;
  }
}
