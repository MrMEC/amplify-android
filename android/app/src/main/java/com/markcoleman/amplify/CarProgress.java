package com.markcoleman.amplify;

import android.content.Context;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/**
 * Where podcast episodes played from the car got to. The page keeps its own progress in its
 * database, which the car can't reach, so the car writes here (guid -> position, duration,
 * the episode record) and the page folds these in the next time it opens.
 */
final class CarProgress {

  private CarProgress() {}

  private static File file(Context c) {
    return new File(c.getFilesDir(), "car_progress.json");
  }

  static synchronized JSONObject readAll(Context c) {
    try {
      return new JSONObject(CarLibrary.readFile(file(c)));
    } catch (Exception e) {
      return new JSONObject();
    }
  }

  static synchronized void put(
      Context c, String guid, double positionSec, double durationSec, JSONObject record) {
    if (guid == null || guid.isEmpty()) return;
    try {
      JSONObject all = readAll(c);
      JSONObject o = new JSONObject();
      o.put("positionSec", positionSec);
      o.put("durationSec", durationSec);
      o.put("lastPlayedAt", System.currentTimeMillis());
      o.put("completed", durationSec > 0 && positionSec > durationSec - 15);
      o.put("record", record);
      all.put(guid, o);
      write(c, all);
    } catch (Exception ignored) {
      // Progress is a convenience; never let it break playback.
    }
  }

  /** Hands everything to the page and forgets it. */
  static synchronized JSONObject takeAll(Context c) {
    JSONObject all = readAll(c);
    file(c).delete();
    return all;
  }

  private static void write(Context c, JSONObject all) throws Exception {
    File dest = file(c);
    File part = new File(dest.getPath() + ".part");
    try (FileOutputStream out = new FileOutputStream(part)) {
      out.write(all.toString().getBytes(StandardCharsets.UTF_8));
    }
    if (!part.renameTo(dest)) part.delete();
  }
}
