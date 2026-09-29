package com.markcoleman.amplify;

import android.app.Activity;
import android.graphics.Color;
import android.view.Gravity;
import android.view.TextureView;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import androidx.annotation.OptIn;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.exoplayer.ExoPlayer;

/**
 * The picture of a live stream that carries video (an IPTV channel pasted into search, say). The
 * page plays streams through the native player, which has no screen of its own, and the page's own
 * <video> can't play most IPTV formats -- so this puts a native video view over the WebView,
 * exactly on top of the Now Playing video box (the same box podcast video uses). The page reports
 * where that box is (CSS pixels, relative to the WebView), including when it is full screen, and
 * hides this whenever the box is covered or not showing; this only draws. A tap on the picture is
 * passed back to the page (which toggles full screen), since the page's own buttons can't sit on
 * top of a native view.
 */
@OptIn(markerClass = UnstableApi.class)
final class VideoOverlay {
  interface Listener {
    void onTap();
  }

  private final Activity activity;
  private final View webView;
  private final Listener listener;
  private FrameLayout box;
  private TextureView texture;
  private ExoPlayer boundTo;
  private int videoW, videoH;
  private float pixelRatio = 1f;

  VideoOverlay(Activity activity, View webView, Listener listener) {
    this.activity = activity;
    this.webView = webView;
    this.listener = listener;
  }

  /** Show the picture over the page's box (CSS px, relative to the WebView). */
  void show(ExoPlayer player, float x, float y, float w, float h) {
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
    place(x, y, w, h);
    box.setVisibility(View.VISIBLE);
    box.bringToFront();
  }

  /** Nothing to show (no video, Now Playing closed, or something on the page covers the box). */
  void hide() {
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
    box.setOnClickListener(v -> listener.onTap());
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
  private void place(float cssX, float cssY, float cssW, float cssH) {
    ViewGroup parent = (ViewGroup) box.getParent();
    if (parent == null) return;
    float d = activity.getResources().getDisplayMetrics().density;
    int[] wl = new int[2];
    int[] pl = new int[2];
    webView.getLocationInWindow(wl);
    parent.getLocationInWindow(pl);
    int w = Math.max(1, Math.round(cssW * d));
    int h = Math.max(1, Math.round(cssH * d));
    ViewGroup.LayoutParams lp = box.getLayoutParams();
    if (lp.width != w || lp.height != h) {
      lp.width = w;
      lp.height = h;
      box.setLayoutParams(lp);
    }
    // The box is laid out at the parent's padding corner; translation moves it onto the page box.
    box.setTranslationX(wl[0] - pl[0] - parent.getPaddingLeft() + cssX * d);
    box.setTranslationY(wl[1] - pl[1] - parent.getPaddingTop() + cssY * d);
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
}
