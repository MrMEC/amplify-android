package com.markcoleman.amplify;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.graphics.Color;
import android.view.Gravity;
import android.view.TextureView;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.annotation.OptIn;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.exoplayer.ExoPlayer;

/**
 * The picture for a stream that carries video (an IPTV channel pasted into search, say). The page
 * plays everything through the native player, which has no screen of its own, so this puts a native
 * video view over the WebView, exactly on top of the video box the Now Playing screen lays out. The
 * page reports where that box is (CSS pixels, relative to the WebView) and whether anything covers
 * it; this only draws. Tapping the picture toggles full screen (landscape for a wide picture,
 * system bars hidden); Back or another tap returns.
 */
@OptIn(markerClass = UnstableApi.class)
final class VideoOverlay {
  interface Listener {
    void onFullscreenChanged(boolean fullscreen);
  }

  private final Activity activity;
  private final View webView;
  private final Listener listener;
  private FrameLayout box;
  private TextureView texture;
  private ExoPlayer boundTo;
  private int videoW, videoH;
  private float pixelRatio = 1f;
  private boolean shown, fullscreen;
  // Where the page wants the box, in CSS pixels relative to the WebView (kept while full screen
  // so leaving full screen goes straight back to it).
  private float cssX, cssY, cssW, cssH;
  private int savedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED;
  private OnBackPressedCallback back;

  VideoOverlay(Activity activity, View webView, Listener listener) {
    this.activity = activity;
    this.webView = webView;
    this.listener = listener;
  }

  boolean isFullscreen() {
    return fullscreen;
  }

  /** Show the picture over the page's box (CSS px, relative to the WebView). */
  void show(ExoPlayer player, float x, float y, float w, float h) {
    cssX = x;
    cssY = y;
    cssW = w;
    cssH = h;
    if (player == null || w < 2 || h < 2) {
      hide();
      return;
    }
    if (!ensureBox()) return;
    if (boundTo != player) {
      if (boundTo != null) boundTo.clearVideoTextureView(texture);
      player.setVideoTextureView(texture);
      boundTo = player;
    }
    shown = true;
    if (!fullscreen) place();
    box.setVisibility(View.VISIBLE);
    box.bringToFront();
  }

  /** Nothing to show (no video, Now Playing closed, or something on the page covers the box). */
  void hide() {
    if (fullscreen) exitFullscreen();
    shown = false;
    if (box != null) box.setVisibility(View.GONE);
    // No surface while hidden: the sound carries on, the phone stops drawing frames nobody sees.
    if (boundTo != null && texture != null) boundTo.clearVideoTextureView(texture);
    boundTo = null;
  }

  void setVideoSize(int width, int height, float ratio) {
    videoW = width;
    videoH = height;
    pixelRatio = ratio > 0 ? ratio : 1f;
    fit();
  }

  void release() {
    hide();
    if (box != null && box.getParent() instanceof ViewGroup) {
      ((ViewGroup) box.getParent()).removeView(box);
    }
    box = null;
    texture = null;
  }

  private boolean ensureBox() {
    if (box != null) return true;
    if (!(webView.getParent() instanceof ViewGroup)) return false;
    ViewGroup parent = (ViewGroup) webView.getParent();
    box = new FrameLayout(activity);
    box.setBackgroundColor(Color.BLACK);
    box.setKeepScreenOn(true);
    box.setClickable(true);
    box.setContentDescription("Video. Tap for full screen.");
    box.setOnClickListener(v -> toggleFullscreen());
    box.setVisibility(View.GONE);
    texture = new TextureView(activity);
    box.addView(
        texture,
        new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
            Gravity.CENTER));
    box.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> fit());
    parent.addView(box, new ViewGroup.LayoutParams(1, 1));
    return true;
  }

  /** Size and position the box over the page's video box. */
  private void place() {
    if (box == null) return;
    ViewGroup parent = (ViewGroup) box.getParent();
    if (parent == null) return;
    float d = activity.getResources().getDisplayMetrics().density;
    int[] wl = new int[2];
    int[] pl = new int[2];
    webView.getLocationInWindow(wl);
    parent.getLocationInWindow(pl);
    int w = Math.max(1, Math.round(cssW * d));
    int h = Math.max(1, Math.round(cssH * d));
    setSize(w, h);
    // The box is laid out at the parent's padding corner; translation moves it onto the page box.
    box.setTranslationX(wl[0] - pl[0] - parent.getPaddingLeft() + cssX * d);
    box.setTranslationY(wl[1] - pl[1] - parent.getPaddingTop() + cssY * d);
  }

  private void setSize(int w, int h) {
    ViewGroup.LayoutParams lp = box.getLayoutParams();
    if (lp.width != w || lp.height != h) {
      lp.width = w;
      lp.height = h;
      box.setLayoutParams(lp);
    }
  }

  /** Letterbox the picture inside the box at its own shape. */
  private void fit() {
    if (box == null || texture == null) return;
    int bw = box.getWidth(), bh = box.getHeight();
    if (bw <= 0 || bh <= 0) return;
    int tw = bw, th = bh;
    if (videoW > 0 && videoH > 0) {
      float aspect = videoW * pixelRatio / videoH;
      if ((float) bw / bh > aspect) tw = Math.round(bh * aspect);
      else th = Math.round(bw / aspect);
    }
    FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) texture.getLayoutParams();
    if (lp.width != tw || lp.height != th) {
      lp.width = tw;
      lp.height = th;
      lp.gravity = Gravity.CENTER;
      texture.setLayoutParams(lp);
    }
  }

  private void toggleFullscreen() {
    if (fullscreen) exitFullscreen();
    else enterFullscreen();
  }

  private void enterFullscreen() {
    if (box == null || !shown || fullscreen) return;
    fullscreen = true;
    ViewGroup parent = (ViewGroup) box.getParent();
    setSize(parent.getWidth() + 2, parent.getHeight() + 2);
    box.setTranslationX(-parent.getPaddingLeft() - 1);
    box.setTranslationY(-parent.getPaddingTop() - 1);
    box.bringToFront();
    savedOrientation = activity.getRequestedOrientation();
    boolean wide = videoW <= 0 || videoH <= 0 || videoW * pixelRatio >= videoH;
    activity.setRequestedOrientation(
        wide
            ? ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            : ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT);
    WindowInsetsControllerCompat bars =
        WindowCompat.getInsetsController(activity.getWindow(), activity.getWindow().getDecorView());
    bars.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    bars.hide(WindowInsetsCompat.Type.systemBars());
    if (activity instanceof ComponentActivity) {
      back =
          new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
              exitFullscreen();
            }
          };
      ((ComponentActivity) activity).getOnBackPressedDispatcher().addCallback(back);
    }
    // The parent is resized by the rotation; keep covering it.
    parent.addOnLayoutChangeListener(followParent);
    listener.onFullscreenChanged(true);
  }

  private final View.OnLayoutChangeListener followParent =
      (v, l, t, r, b, ol, ot, or, ob) -> {
        if (!fullscreen || box == null) return;
        ViewGroup p = (ViewGroup) v;
        setSize(p.getWidth() + 2, p.getHeight() + 2);
        box.setTranslationX(-p.getPaddingLeft() - 1);
        box.setTranslationY(-p.getPaddingTop() - 1);
      };

  private void exitFullscreen() {
    if (!fullscreen) return;
    fullscreen = false;
    if (box != null && box.getParent() instanceof ViewGroup) {
      ((ViewGroup) box.getParent()).removeOnLayoutChangeListener(followParent);
    }
    if (back != null) {
      back.remove();
      back = null;
    }
    WindowCompat.getInsetsController(activity.getWindow(), activity.getWindow().getDecorView())
        .show(WindowInsetsCompat.Type.systemBars());
    activity.setRequestedOrientation(savedOrientation);
    if (shown) place();
    listener.onFullscreenChanged(false);
  }
}
