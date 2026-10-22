package android.content;
import java.io.File;
import java.util.HashMap;
import java.util.Map;
/** Test stand-in: only what PodcastFeeds uses. */
public class Context {
  public static final int MODE_PRIVATE = 0;
  private final File dir;
  public final Map<String, String> kv = new HashMap<>();
  public Context(File dir) { this.dir = dir; }
  public File getFilesDir() { return dir; }
  public Context getApplicationContext() { return this; }
  public SharedPreferences getSharedPreferences(String name, int mode) {
    return new SharedPreferences() {
      public String getString(String k, String def) { return kv.containsKey(k) ? kv.get(k) : def; }
    };
  }
}
