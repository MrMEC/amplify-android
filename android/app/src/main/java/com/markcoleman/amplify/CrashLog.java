package com.markcoleman.amplify;

import android.content.Context;
import android.os.Build;
import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Build 196: when the app closes because of an error, the error is written to a file, and the
 * page shows it the next time the app opens (so it can be reported). Errors that were caught and
 * survived (note) are kept too, for Check storage.
 */
final class CrashLog {
  private static volatile boolean installed;
  private static final String FILE = "last_crash.txt";
  private static final String NOTES = "caught_errors.txt";

  static synchronized void install(Context context) {
    if (installed) return;
    installed = true;
    final Context app = context.getApplicationContext();
    final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
    Thread.setDefaultUncaughtExceptionHandler(
        (t, e) -> {
          try {
            write(app, FILE, describe(t, e), false);
          } catch (Throwable ignored) {
          }
          if (prev != null) prev.uncaughtException(t, e);
        });
  }

  /** An error that was caught (the app carried on). */
  static void note(Context context, String where, Throwable e) {
    try {
      write(context.getApplicationContext(), NOTES, "[" + where + "] " + describe(Thread.currentThread(), e), true);
    } catch (Throwable ignored) {
    }
  }

  /** Build 198: one line of what happened (no stack trace), e.g. each cast attempt and its outcome. */
  static void info(Context context, String line) {
    try {
      String when = new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date());
      write(context.getApplicationContext(), NOTES, "[" + when + "] " + line, true);
    } catch (Throwable ignored) {
    }
  }

  private static String describe(Thread t, Throwable e) {
    StringWriter sw = new StringWriter();
    PrintWriter pw = new PrintWriter(sw);
    pw.println(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date())
        + " Android " + Build.VERSION.RELEASE + " (" + Build.VERSION.SDK_INT + ") " + Build.MODEL
        + " thread " + (t == null ? "?" : t.getName()));
    e.printStackTrace(pw);
    pw.flush();
    String s = sw.toString();
    return s.length() > 12000 ? s.substring(0, 12000) : s;
  }

  private static void write(Context app, String name, String text, boolean append) throws Exception {
    File f = new File(app.getFilesDir(), name);
    if (append && f.length() > 40000) append = false;
    try (FileOutputStream out = new FileOutputStream(f, append)) {
      out.write((text + "\n").getBytes(StandardCharsets.UTF_8));
    }
  }

  static String take(Context context, boolean notes) {
    File f = new File(context.getApplicationContext().getFilesDir(), notes ? NOTES : FILE);
    if (!f.exists()) return "";
    try {
      byte[] b = java.nio.file.Files.readAllBytes(f.toPath());
      if (!notes) f.delete();
      return new String(b, StandardCharsets.UTF_8);
    } catch (Throwable t) {
      return "";
    }
  }
}
