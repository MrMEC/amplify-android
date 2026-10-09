package com.markcoleman.amplify;

import android.app.Activity;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.TextureView;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;
import androidx.annotation.Nullable;
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
public final class VideoOverlay {
  interface Listener {
    void onTap();

    /** A finger dragging the picture (build 161): phase start / move / end, distance in px. */
    void onDrag(String phase, float dxPx, float dyPx);

    /** Two fingers pinching the picture (build 175): phase start / move / end, and the
     *  distance between the fingers now divided by the distance when the pinch began. */
    void onPinch(String phase, float scale);
  }

  /**
   * Whatever draws the picture into the box's TextureView: the phone's own player, or VLC (build
   * 159). Only one is connected at a time.
   */
  public interface Target {
    void bind(TextureView view);

    void unbind(TextureView view);

    /** The size the picture is drawn at, in screen pixels. */
    default void onWindowSize(int width, int height) {}
  }

  /** The phone's own player as a target. Equal when it is the same player. */
  static final class ExoTarget implements Target {
    final ExoPlayer player;

    ExoTarget(ExoPlayer player) {
      this.player = player;
    }

    @Override
    public void bind(TextureView view) {
      player.setVideoTextureView(view);
    }

    @Override
    public void unbind(TextureView view) {
      player.clearVideoTextureView(view);
    }

    @Override
    public boolean equals(Object o) {
      return o instanceof ExoTarget && ((ExoTarget) o).player == player;
    }

    @Override
    public int hashCode() {
      return System.identityHashCode(player);
    }
  }

  private final Activity activity;
  private final View webView;
  private final Listener listener;
  private FrameLayout box;
  private TextureView texture;
  private TextView captions;
  @Nullable private CharSequence cueText;
  private Target boundTo;
  private int videoW, videoH;
  private float pixelRatio = 1f;
  // Build 156: a hide that is followed by a show soon after (Now Playing closing into the
  // floating window, a menu passing over the box) keeps the picture connected, so the decoder is
  // not torn down and restarted (which showed as a black box). The surface is let go only once
  // the picture has stayed hidden for a while.
  private final Handler main = new Handler(Looper.getMainLooper());
  private final Runnable unbind =
      () -> {
        if (box != null && box.getVisibility() == View.VISIBLE) return;
        if (boundTo != null && texture != null) boundTo.unbind(texture);
        boundTo = null;
      };
  private static final long UNBIND_DELAY_MS = 2500;

  VideoOverlay(Activity activity, View webView, Listener listener) {
    this.activity = activity;
    this.webView = webView;
    this.listener = listener;
  }

  /** Show the picture over the page's box (CSS px, relative to the WebView). */
  void show(ExoPlayer player, float x, float y, float w, float h) {
    show(player == null ? null : new ExoTarget(player), x, y, w, h);
  }

  void show(Target target, float x, float y, float w, float h) {
    if (target == null || w < 2 || h < 2) {
      hide();
      return;
    }
    if (!ensureBox()) return;
    main.removeCallbacks(unbind);
    if (!target.equals(boundTo)) {
      if (boundTo != null) boundTo.unbind(texture);
      target.bind(texture);
      boundTo = target;
      int tw = texture.getLayoutParams().width, th = texture.getLayoutParams().height;
      if (tw > 0 && th > 0) target.onWindowSize(tw, th);
    }
    place(x, y, w, h);
    box.setVisibility(View.VISIBLE);
    box.bringToFront();
    box.post(this::fit);
  }

  /** Nothing to show (no video, Now Playing closed, or something on the page covers the box). */
  void hide() {
    // INVISIBLE rather than GONE keeps the box laid out, so coming back needs no new layout pass.
    if (box != null) box.setVisibility(View.INVISIBLE);
    // No surface while hidden for long: the sound carries on, the phone stops drawing frames
    // nobody sees.
    main.removeCallbacks(unbind);
    if (boundTo != null) main.postDelayed(unbind, UNBIND_DELAY_MS);
  }

  private void unbindNow() {
    main.removeCallbacks(unbind);
    if (box != null) box.setVisibility(View.GONE);
    if (boundTo != null && texture != null) boundTo.unbind(texture);
    boundTo = null;
  }

  /** Where the box is and whether a picture is connected (Diagnostics). */
  com.getcapacitor.JSObject state() {
    com.getcapacitor.JSObject o = new com.getcapacitor.JSObject();
    o.put("visible", box != null && box.getVisibility() == View.VISIBLE);
    o.put("bound", boundTo != null);
    o.put("textureReady", texture != null && texture.isAvailable());
    if (box != null) {
      o.put("w", box.getLayoutParams().width);
      o.put("h", box.getLayoutParams().height);
      o.put("x", Math.round(box.getTranslationX()));
      o.put("y", Math.round(box.getTranslationY()));
    }
    if (texture != null) {
      o.put("tw", texture.getWidth());
      o.put("th", texture.getHeight());
    }
    o.put("d", activity.getResources().getDisplayMetrics().density);
    o.put("wv", webView.getWidth() + "x" + webView.getHeight() + "/" + webView.getScaleX());
    if (box != null) {
      o.put("shown", box.isShown());
      android.graphics.Rect g = new android.graphics.Rect();
      o.put("onScreen", box.getGlobalVisibleRect(g) ? g.toShortString() : "no");
      if (box.getParent() instanceof ViewGroup) {
        ViewGroup p = (ViewGroup) box.getParent();
        o.put("parent", p.getClass().getSimpleName() + " " + p.getWidth() + "x" + p.getHeight()
            + " i" + p.indexOfChild(box) + "/" + p.getChildCount());
      }
    }
    return o;
  }

  void setVideoSize(int width, int height, float ratio) {
    videoW = width;
    videoH = height;
    pixelRatio = ratio > 0 ? ratio : 1f;
    fit();
  }

  /** The subtitle line(s) showing now, or null for none. */
  void setCues(@Nullable CharSequence text) {
    cueText = text;
    if (captions == null) return;
    if (text == null || text.length() == 0) {
      captions.setVisibility(View.GONE);
      return;
    }
    captions.setText(text);
    captions.setVisibility(View.VISIBLE);
  }

  void release() {
    unbindNow();
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
    // A tap is a tap; a finger that moves drags the picture instead (the page decides what a
    // drag does: it moves the floating window). Screen coordinates, so the box moving under
    // the finger doesn't change the distance.
    final int slop = android.view.ViewConfiguration.get(activity).getScaledTouchSlop();
    box.setOnTouchListener(
        new View.OnTouchListener() {
          float x0, y0, span0;
          boolean dragging, pinching, spent;

          float span(android.view.MotionEvent e) {
            if (e.getPointerCount() < 2) return 0f;
            return (float) Math.hypot(e.getX(1) - e.getX(0), e.getY(1) - e.getY(0));
          }

          @Override
          public boolean onTouch(View v, android.view.MotionEvent e) {
            switch (e.getActionMasked()) {
              case android.view.MotionEvent.ACTION_DOWN:
                x0 = e.getRawX();
                y0 = e.getRawY();
                dragging = false;
                pinching = false;
                spent = false;
                return false; // the click still sees it
              case android.view.MotionEvent.ACTION_POINTER_DOWN:
                // A second finger: a pinch resizes the floating window (the page decides how).
                if (!pinching && e.getPointerCount() == 2) {
                  if (dragging) {
                    dragging = false;
                    listener.onDrag("end", e.getRawX() - x0, e.getRawY() - y0);
                  }
                  span0 = Math.max(1f, span(e));
                  pinching = true;
                  v.setPressed(false);
                  v.cancelLongPress();
                  listener.onPinch("start", 1f);
                }
                return true;
              case android.view.MotionEvent.ACTION_POINTER_UP:
                if (pinching) {
                  pinching = false;
                  spent = true; // the finger left behind doesn't drag or tap
                  listener.onPinch("end", 1f);
                }
                return true;
              case android.view.MotionEvent.ACTION_MOVE:
                if (pinching) {
                  if (e.getPointerCount() >= 2) listener.onPinch("move", span(e) / span0);
                  return true;
                }
                if (spent) return true;
                float dx = e.getRawX() - x0, dy = e.getRawY() - y0;
                if (!dragging && Math.hypot(dx, dy) > slop) {
                  dragging = true;
                  v.setPressed(false);
                  v.cancelLongPress();
                  listener.onDrag("start", 0f, 0f);
                }
                if (dragging) {
                  listener.onDrag("move", dx, dy);
                  return true;
                }
                return false;
              case android.view.MotionEvent.ACTION_UP:
              case android.view.MotionEvent.ACTION_CANCEL:
                if (pinching || spent) {
                  if (pinching) listener.onPinch("end", 1f);
                  pinching = false;
                  spent = false;
                  v.setPressed(false);
                  return true; // not a click
                }
                if (dragging) {
                  dragging = false;
                  listener.onDrag("end", e.getRawX() - x0, e.getRawY() - y0);
                  v.setPressed(false);
                  return true; // not a click
                }
                return false;
              default:
                return false;
            }
          }
        });
    box.setVisibility(View.GONE);
    texture = new TextureView(activity);
    box.addView(
        texture,
        new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
            Gravity.CENTER));
    // Subtitles: drawn here, over the picture, since nothing of the page can sit on top of it.
    captions = new TextView(activity);
    captions.setTextColor(Color.WHITE);
    captions.setGravity(Gravity.CENTER);
    captions.setShadowLayer(6f, 0f, 1f, Color.BLACK);
    captions.setBackgroundColor(0x88000000);
    int pad = Math.round(6 * activity.getResources().getDisplayMetrics().density);
    captions.setPadding(pad, pad / 3, pad, pad / 3);
    captions.setVisibility(View.GONE);
    FrameLayout.LayoutParams cp =
        new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
    cp.bottomMargin = pad * 2;
    box.addView(captions, cp);
    // Posted: resizing the picture from inside a layout pass can be dropped until something else
    // asks for layout, which left a shrunk box drawing nothing.
    box.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> box.post(this::fit));
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
    if (captions != null) {
      // Sized to the picture: small in the box on Now Playing, larger full screen.
      captions.setTextSize(TypedValue.COMPLEX_UNIT_PX, Math.max(11f, Math.min(bw, bh) / 18f));
      captions.setMaxWidth(Math.round(bw * 0.9f));
    }
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
    if (boundTo != null) boundTo.onWindowSize(tw, th);
  }
}
