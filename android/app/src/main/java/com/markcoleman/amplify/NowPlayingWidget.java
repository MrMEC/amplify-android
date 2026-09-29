package com.markcoleman.amplify;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.os.Handler;
import android.os.Looper;
import android.widget.RemoteViews;
import androidx.core.content.ContextCompat;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import com.google.common.util.concurrent.ListenableFuture;
import java.io.File;
import java.io.FileOutputStream;

public class NowPlayingWidget extends AppWidgetProvider {
  static final String ACTION_PREV = "com.markcoleman.amplify.widget.PREV";
  static final String ACTION_PLAY = "com.markcoleman.amplify.widget.PLAY";
  static final String ACTION_NEXT = "com.markcoleman.amplify.widget.NEXT";
  private static final String PREFS = "now_playing_widget";
  private static final int ART_SIZE = 192;

  @Override
  public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
    SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    render(
        context, p.getString("title", null), p.getString("artist", null), false, loadArt(context));
  }

  static void showText(Context context, CharSequence title, CharSequence artist, boolean playing) {
    String t = title == null ? null : title.toString();
    String a = artist == null ? null : artist.toString();
    context
        .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .edit()
        .putString("title", t)
        .putString("artist", a)
        .apply();
    render(context, t, a, playing, loadArt(context));
  }

  static void setArt(Context context, Bitmap art, boolean playing) {
    Bitmap r = art == null ? null : rounded(art);
    saveArt(context, r);
    SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    render(context, p.getString("title", null), p.getString("artist", null), playing, r);
  }

  static void showPlaying(Context context, boolean playing) {
    SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    render(
        context,
        p.getString("title", null),
        p.getString("artist", null),
        playing,
        loadArt(context));
  }

  private static void render(
      Context context, String title, String artist, boolean playing, Bitmap art) {
    AppWidgetManager manager = AppWidgetManager.getInstance(context);
    int[] ids = manager.getAppWidgetIds(new ComponentName(context, NowPlayingWidget.class));
    if (ids == null || ids.length == 0) return;
    RemoteViews v = new RemoteViews(context.getPackageName(), R.layout.widget_now_playing);
    boolean idle = title == null || title.trim().isEmpty();
    v.setTextViewText(R.id.widget_title, idle ? "Amplify" : title);
    String sub;
    if (idle) sub = "Tap to open";
    else if (artist == null || artist.trim().isEmpty()) sub = "Amplify";
    else sub = artist;
    v.setTextViewText(R.id.widget_artist, sub);
    if (art != null) v.setImageViewBitmap(R.id.widget_art, art);
    else v.setImageViewResource(R.id.widget_art, R.mipmap.ic_launcher_round);
    v.setImageViewResource(
        R.id.widget_play, playing ? R.drawable.ic_amplify_pause : R.drawable.ic_amplify_play);
    v.setContentDescription(R.id.widget_play, playing ? "Pause" : "Play");
    Intent launch =
        new Intent(context, MainActivity.class)
            .setAction(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
    PendingIntent open =
        PendingIntent.getActivity(
            context, 0, launch, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    v.setOnClickPendingIntent(R.id.widget_art, open);
    v.setOnClickPendingIntent(R.id.widget_text, open);
    v.setOnClickPendingIntent(R.id.widget_prev, button(context, ACTION_PREV, 1));
    v.setOnClickPendingIntent(R.id.widget_play, button(context, ACTION_PLAY, 2));
    v.setOnClickPendingIntent(R.id.widget_next, button(context, ACTION_NEXT, 3));
    manager.updateAppWidget(ids, v);
  }

  private static PendingIntent button(Context context, String action, int requestCode) {
    return PendingIntent.getBroadcast(
        context,
        requestCode,
        new Intent(action).setClass(context, NowPlayingWidget.class),
        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
  }

  @Override
  public void onReceive(Context context, Intent intent) {
    String action = intent.getAction();
    if (!ACTION_PREV.equals(action) && !ACTION_PLAY.equals(action) && !ACTION_NEXT.equals(action)) {
      super.onReceive(context, intent);
      return;
    }
    PlaybackService svc = PlaybackService.instance;
    if (svc != null && svc.player != null) {
      if (ACTION_PLAY.equals(action)) {
        if (svc.player.getPlayWhenReady()) svc.player.pause();
        else svc.player.play();
      } else {
        svc.trackKey(ACTION_NEXT.equals(action));
      }
      return;
    }
    if (!ACTION_PLAY.equals(action)) return;
    // Nothing running: start the service through a controller and resume the last item.
    PendingResult pending = goAsync();
    Context app = context.getApplicationContext();
    ListenableFuture<MediaController> future =
        new MediaController.Builder(
                app, new SessionToken(app, new ComponentName(app, PlaybackService.class)))
            .buildAsync();
    Handler handler = new Handler(Looper.getMainLooper());
    future.addListener(
        () -> {
          try {
            playWhenLoaded(future.get(), future, pending, handler);
          } catch (Exception e) {
            pending.finish();
          }
        },
        ContextCompat.getMainExecutor(app));
  }

  /** Waits (up to ~3 s) for playback resumption to load an item, then plays and lets go. */
  private static void playWhenLoaded(
      MediaController mc,
      ListenableFuture<MediaController> future,
      BroadcastReceiver.PendingResult pending,
      Handler handler) {
    int[] tries = {0};
    Runnable attempt =
        new Runnable() {
          @Override
          public void run() {
            if (mc.getMediaItemCount() == 0 && tries[0]++ < 20) {
              handler.postDelayed(this, 150);
              return;
            }
            mc.play();
            handler.postDelayed(
                () -> {
                  MediaController.releaseFuture(future);
                  pending.finish();
                },
                1500);
          }
        };
    attempt.run();
  }

  private static File artFile(Context context) {
    return new File(context.getFilesDir(), "widget_art.png");
  }

  private static void saveArt(Context context, Bitmap art) {
    File f = artFile(context);
    if (art == null) {
      f.delete();
      return;
    }
    try (FileOutputStream out = new FileOutputStream(f)) {
      art.compress(Bitmap.CompressFormat.PNG, 100, out);
    } catch (Exception ignored) {
    }
  }

  private static Bitmap loadArt(Context context) {
    File f = artFile(context);
    return f.exists() ? BitmapFactory.decodeFile(f.getPath()) : null;
  }

  /** Square cover with rounded corners (RemoteViews can't clip an ImageView on older Androids). */
  static Bitmap rounded(Bitmap src) {
    Bitmap scaled = Bitmap.createScaledBitmap(src, ART_SIZE, ART_SIZE, true);
    Bitmap out = Bitmap.createBitmap(ART_SIZE, ART_SIZE, Bitmap.Config.ARGB_8888);
    Canvas canvas = new Canvas(out);
    Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    paint.setShader(new BitmapShader(scaled, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP));
    canvas.drawRoundRect(new RectF(0, 0, ART_SIZE, ART_SIZE), 40, 40, paint);
    return out;
  }
}
