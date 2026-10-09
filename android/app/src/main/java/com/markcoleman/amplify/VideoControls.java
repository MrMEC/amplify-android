package com.markcoleman.amplify;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PorterDuff;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import java.util.Locale;

/**
 * The video player's controls, drawn on the picture (build 181): Play/Pause in the middle, the
 * progress bar with its times (or LIVE for a live stream) and full screen along the bottom. The
 * page can't draw anything over the native picture, so this mirrors the page's own overlay
 * (#vctl in index.html) from the state the page sends (setVideoControls), and hands its buttons
 * back to the page (play, pause, seek, full). A tap on the picture shows them, a tap on an empty
 * spot hides them, and they hide on their own after 3 seconds while playing.
 *
 * Plain android.* only, so it can be compiled and checked without the rest of the app.
 */
final class VideoControls extends FrameLayout {
  interface Listener {
    /** action: play, pause, seek (value = seconds), full. */
    void onControl(String action, double value);
  }

  static final long HIDE_AFTER_MS = 3000;
  private static final long TICK_MS = 500;
  private static final long FADE_MS = 200;

  private final Listener listener;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final float dp;
  private final View scrim;
  private final Glyph play;
  private final LinearLayout bar;
  private final TextView elapsed, total, liveTag;
  private final SeekBar seek;
  private final Glyph full;

  private boolean enabled, shown, playing, live, isFull, seeking;
  private double pos, dur;
  private long posAt;
  private int accent = 0xFFFFFFFF;

  private final Runnable hideLater =
      new Runnable() {
        @Override
        public void run() {
          if (seeking || !playing) return; // paused: they stay up
          setShown(false);
        }
      };

  private final Runnable tick =
      new Runnable() {
        @Override
        public void run() {
          refreshTimes();
          if (shown && playing && !live) main.postDelayed(this, TICK_MS);
        }
      };

  VideoControls(Context context, Listener listener) {
    super(context);
    this.listener = listener;
    dp = context.getResources().getDisplayMetrics().density;
    setClickable(false); // taps on empty parts fall through to the box, which toggles us

    // A soft dark wash, stronger at the bottom, so white controls read on any picture.
    scrim = new View(context);
    GradientDrawable g =
        new GradientDrawable(
            GradientDrawable.Orientation.BOTTOM_TOP, new int[] {0xA0000000, 0x2E000000, 0x2E000000});
    scrim.setBackground(g);
    addView(scrim, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

    play = new Glyph(context, Glyph.PLAY, true);
    play.setContentDescription("Play");
    play.setOnClickListener(
        new OnClickListener() {
          @Override
          public void onClick(View v) {
            boolean nowPlaying = !playing;
            setPlaying(nowPlaying); // answer the tap at once; the page confirms
            listener.onControl(nowPlaying ? "play" : "pause", 0);
            poke();
          }
        });
    int ps = px(64);
    addView(play, new LayoutParams(ps, ps, Gravity.CENTER));

    bar = new LinearLayout(context);
    bar.setOrientation(LinearLayout.HORIZONTAL);
    bar.setGravity(Gravity.CENTER_VERTICAL);
    bar.setPadding(px(14), 0, px(4), px(4));

    liveTag = new TextView(context);
    liveTag.setText("LIVE");
    liveTag.setTextColor(Color.WHITE);
    liveTag.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
    liveTag.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
    liveTag.setLetterSpacing(0.06f);
    GradientDrawable lb = new GradientDrawable();
    lb.setColor(0xFFE5322D);
    lb.setCornerRadius(px(4));
    liveTag.setBackground(lb);
    liveTag.setPadding(px(7), px(2), px(7), px(2));
    bar.addView(liveTag, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

    elapsed = timeLabel(context);
    bar.addView(elapsed, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

    seek = new SeekBar(context);
    seek.setMax(1000);
    seek.setPadding(px(10), 0, px(10), 0);
    seek.setContentDescription("Seek");
    seek.setOnSeekBarChangeListener(
        new SeekBar.OnSeekBarChangeListener() {
          @Override
          public void onProgressChanged(SeekBar s, int progress, boolean fromUser) {
            if (fromUser && dur > 0) elapsed.setText(format(progress / 1000.0 * dur));
          }

          @Override
          public void onStartTrackingTouch(SeekBar s) {
            seeking = true;
            main.removeCallbacks(hideLater);
          }

          @Override
          public void onStopTrackingTouch(SeekBar s) {
            seeking = false;
            if (dur > 0) {
              pos = s.getProgress() / 1000.0 * dur;
              posAt = SystemClock.uptimeMillis();
              listener.onControl("seek", pos);
            }
            poke();
          }
        });
    LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(0, px(32), 1f);
    bar.addView(seek, sp);

    total = timeLabel(context);
    bar.addView(total, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

    // Keeps the full screen button at the right edge when LIVE stands in for the bar.
    View spacer = new View(context);
    spacer.setTag("spacer");
    bar.addView(spacer, new LinearLayout.LayoutParams(0, 1, 0f));

    full = new Glyph(context, Glyph.FULL, false);
    full.setContentDescription("Full screen");
    full.setOnClickListener(
        new OnClickListener() {
          @Override
          public void onClick(View v) {
            listener.onControl("full", 0);
            poke();
          }
        });
    LinearLayout.LayoutParams fp = new LinearLayout.LayoutParams(px(44), px(44));
    fp.leftMargin = px(4);
    bar.addView(full, fp);

    addView(bar, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(52), Gravity.BOTTOM));

    applyAccent();
    applyMode();
    setVisibility(View.INVISIBLE);
    setAlpha(0f);
  }

  private TextView timeLabel(Context context) {
    TextView t = new TextView(context);
    t.setTextColor(Color.WHITE);
    t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
    t.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
    t.setShadowLayer(3f, 0f, 1f, 0x80000000);
    t.setText("0:00");
    return t;
  }

  private int px(float v) {
    return Math.round(v * dp);
  }

  /** Whether the box shows controls at all (not on the floating window). */
  boolean isActive() {
    return enabled;
  }

  /** The state of what is playing, as the page sees it. */
  void update(
      boolean enabled, boolean playing, double pos, double dur, boolean live, boolean fullScreen, String accentHex) {
    boolean wasEnabled = this.enabled;
    this.enabled = enabled;
    this.live = live;
    this.isFull = fullScreen;
    this.dur = dur > 0 ? dur : 0;
    if (!seeking) {
      this.pos = pos > 0 ? pos : 0;
      this.posAt = SystemClock.uptimeMillis();
    }
    int c = parseColor(accentHex);
    if (c != accent) {
      accent = c;
      applyAccent();
    }
    setPlaying(playing);
    applyMode();
    if (!enabled) {
      setShown(false);
    } else if (!wasEnabled) {
      setShown(true); // first look at the video: show them, then they hide on their own
    }
    refreshTimes();
  }

  private void setPlaying(boolean p) {
    boolean changed = p != playing;
    playing = p;
    play.setKind(p ? Glyph.PAUSE : Glyph.PLAY);
    play.setContentDescription(p ? "Pause" : "Play");
    if (changed && shown) {
      main.removeCallbacks(hideLater);
      if (p) main.postDelayed(hideLater, HIDE_AFTER_MS);
      main.removeCallbacks(tick);
      main.post(tick);
    }
  }

  /** A tap on the picture away from any button: show them, or hide them if they're up. */
  void tapped() {
    setShown(!shown);
  }

  /** Something was touched: keep them up for another 3 seconds. */
  private void poke() {
    main.removeCallbacks(hideLater);
    if (shown && playing) main.postDelayed(hideLater, HIDE_AFTER_MS);
  }

  void setShown(boolean show) {
    if (show && !enabled) show = false;
    main.removeCallbacks(hideLater);
    main.removeCallbacks(tick);
    shown = show;
    animate().cancel();
    if (show) {
      setVisibility(View.VISIBLE);
      animate().alpha(1f).setDuration(FADE_MS).start();
      refreshTimes();
      main.post(tick);
      poke();
    } else if (getVisibility() != View.VISIBLE) {
      setAlpha(0f);
    } else {
      animate()
          .alpha(0f)
          .setDuration(FADE_MS)
          .withEndAction(
              new Runnable() {
                @Override
                public void run() {
                  if (!shown) setVisibility(View.INVISIBLE);
                }
              })
          .start();
    }
  }

  /** Stop all timers (the box is going away). */
  void release() {
    main.removeCallbacks(hideLater);
    main.removeCallbacks(tick);
    animate().cancel();
  }

  private void applyMode() {
    liveTag.setVisibility(live ? View.VISIBLE : View.GONE);
    elapsed.setVisibility(live ? View.GONE : View.VISIBLE);
    total.setVisibility(live ? View.GONE : View.VISIBLE);
    seek.setVisibility(live ? View.GONE : View.VISIBLE);
    seek.setEnabled(!live && dur > 0);
    View spacer = bar.findViewWithTag("spacer");
    if (spacer != null) {
      LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) spacer.getLayoutParams();
      lp.weight = live ? 1f : 0f;
      spacer.setLayoutParams(lp);
    }
    full.setKind(isFull ? Glyph.EXIT_FULL : Glyph.FULL);
    full.setContentDescription(isFull ? "Exit full screen" : "Full screen");
  }

  private void applyAccent() {
    try {
      seek.getProgressDrawable().setColorFilter(accent, PorterDuff.Mode.SRC_IN);
      if (seek.getThumb() != null) seek.getThumb().setColorFilter(accent, PorterDuff.Mode.SRC_IN);
    } catch (Exception ignored) {
      // The phone's own colours are fine too.
    }
  }

  private void refreshTimes() {
    if (live || seeking) return;
    double p = pos;
    if (playing) p += (SystemClock.uptimeMillis() - posAt) / 1000.0;
    if (dur > 0 && p > dur) p = dur;
    elapsed.setText(format(p));
    total.setText(format(dur));
    seek.setProgress(dur > 0 ? (int) Math.round(p / dur * 1000) : 0);
  }

  static String format(double seconds) {
    long s = Math.max(0, Math.round(seconds));
    long h = s / 3600, m = (s % 3600) / 60, r = s % 60;
    if (h > 0) return String.format(Locale.US, "%d:%02d:%02d", h, m, r);
    return String.format(Locale.US, "%d:%02d", m, r);
  }

  /** "#rrggbb" (or "#aarrggbb"); anything else is white. */
  static int parseColor(String hex) {
    if (hex == null) return 0xFFFFFFFF;
    String h = hex.trim();
    try {
      if (h.startsWith("#") && h.length() == 7) return 0xFF000000 | Integer.parseInt(h.substring(1), 16);
      if (h.startsWith("#") && h.length() == 9) return (int) Long.parseLong(h.substring(1), 16);
    } catch (NumberFormatException ignored) {
      // fall through
    }
    return 0xFFFFFFFF;
  }

  /** A button drawn as a shape: play, pause, full screen, leave full screen. */
  static final class Glyph extends View {
    static final int PLAY = 0, PAUSE = 1, FULL = 2, EXIT_FULL = 3;
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint disc = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final RectF r = new RectF();
    private final boolean withDisc;
    private int kind;

    Glyph(Context context, int kind, boolean withDisc) {
      super(context);
      this.kind = kind;
      this.withDisc = withDisc;
      float d = context.getResources().getDisplayMetrics().density;
      fill.setColor(Color.WHITE);
      fill.setStyle(Paint.Style.FILL);
      stroke.setColor(Color.WHITE);
      stroke.setStyle(Paint.Style.STROKE);
      stroke.setStrokeWidth(2f * d);
      stroke.setStrokeCap(Paint.Cap.ROUND);
      stroke.setStrokeJoin(Paint.Join.ROUND);
      disc.setColor(0x73000000);
      disc.setStyle(Paint.Style.FILL);
      setClickable(true);
      setFocusable(true);
    }

    void setKind(int k) {
      if (k == kind) return;
      kind = k;
      invalidate();
    }

    @Override
    protected void onDraw(Canvas c) {
      float w = getWidth(), h = getHeight();
      float cx = w / 2f, cy = h / 2f;
      if (withDisc) c.drawCircle(cx, cy, Math.min(w, h) / 2f, disc);
      // Icons are laid out on a 24-unit grid, like the page's SVGs.
      float u = (withDisc ? Math.min(w, h) * 0.47f : Math.min(w, h) * 0.5f) / 24f;
      float ox = cx - 12 * u, oy = cy - 12 * u;
      path.reset();
      switch (kind) {
        case PLAY:
          path.moveTo(ox + 8 * u, oy + 4.6f * u);
          path.lineTo(ox + 19.6f * u, oy + 12 * u);
          path.lineTo(ox + 8 * u, oy + 19.4f * u);
          path.close();
          c.drawPath(path, fill);
          break;
        case PAUSE:
          r.set(ox + 6 * u, oy + 4.5f * u, ox + 10.2f * u, oy + 19.5f * u);
          c.drawRoundRect(r, 1.2f * u, 1.2f * u, fill);
          r.set(ox + 13.8f * u, oy + 4.5f * u, ox + 18 * u, oy + 19.5f * u);
          c.drawRoundRect(r, 1.2f * u, 1.2f * u, fill);
          break;
        case FULL:
          corner(c, ox, oy, u, 4, 9, 4, 4, 9, 4);
          corner(c, ox, oy, u, 15, 4, 20, 4, 20, 9);
          corner(c, ox, oy, u, 20, 15, 20, 20, 15, 20);
          corner(c, ox, oy, u, 9, 20, 4, 20, 4, 15);
          break;
        default: // EXIT_FULL
          corner(c, ox, oy, u, 9, 4, 9, 9, 4, 9);
          corner(c, ox, oy, u, 20, 9, 15, 9, 15, 4);
          corner(c, ox, oy, u, 15, 20, 15, 15, 20, 15);
          corner(c, ox, oy, u, 4, 15, 9, 15, 9, 20);
          break;
      }
    }

    private void corner(Canvas c, float ox, float oy, float u, float x1, float y1, float x2, float y2, float x3, float y3) {
      path.reset();
      path.moveTo(ox + x1 * u, oy + y1 * u);
      path.lineTo(ox + x2 * u, oy + y2 * u);
      path.lineTo(ox + x3 * u, oy + y3 * u);
      c.drawPath(path, stroke);
    }
  }
}
