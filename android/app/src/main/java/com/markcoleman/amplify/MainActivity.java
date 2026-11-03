package com.markcoleman.amplify;

import android.app.PictureInPictureParams;
import android.content.Intent;
import android.content.res.Configuration;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.ViewCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.WindowInsetsCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.PluginHandle;

public class MainActivity extends BridgeActivity {
  @Override // com.getcapacitor.BridgeActivity, androidx.fragment.app.FragmentActivity,
  // androidx.activity.ComponentActivity, androidx.core.app.ComponentActivity,
  // android.app.Activity
  public void onCreate(Bundle bundle) {
    CrashLog.install(this);
    registerPlugin(AmplifyPlayerPlugin.class);
    super.onCreate(bundle);
    fitWindowAroundBarsAndKeyboard();
    // Build 274: followed podcasts are refreshed in the background about once an hour.
    PodcastRefreshWorker.schedule(this);
    // Build 237: while a Favorites cover on Home is held to drag it, the WebView's own long
    // press is skipped (see AmplifyPlayerPlugin.holdTouch); otherwise it behaves as before.
    try {
      if (getBridge() != null && getBridge().getWebView() != null) {
        getBridge().getWebView().setOnLongClickListener(v -> AmplifyPlayerPlugin.holdingTile());
        // Build 336: the tour's welcome voice starts by itself, without waiting for a touch.
        getBridge().getWebView().getSettings().setMediaPlaybackRequiresUserGesture(false);
      }
    } catch (Exception ignored) {
      // No WebView yet: nothing to change.
    }
    if (Build.VERSION.SDK_INT < 33
        || ContextCompat.checkSelfPermission(this, "android.permission.POST_NOTIFICATIONS") == 0) {
      return;
    }
    ActivityCompat.requestPermissions(
        this, new String[] {"android.permission.POST_NOTIFICATIONS"}, 7);
  }

  /**
   * Build 463: the white gap along the bottom of the screen. Capacitor's own handling made room
   * for the keyboard twice: it shrank the window by the keyboard's height and also passed the
   * keyboard on to the WebView, which shrank the page by it as well -- and the WebView kept that
   * second shrink after the keyboard had gone, leaving the page on the top half of the screen.
   * Capacitor's handling is off (capacitor.config.json, SystemBars.insetsHandling) and this is the
   * only place the window is fitted: around the status and navigation bars, and the keyboard
   * while it is showing. Everything is consumed here, so the WebView never sees the keyboard and
   * always fills the space it is given.
   */
  private void fitWindowAroundBarsAndKeyboard() {
    final View decor = getWindow().getDecorView();
    ViewCompat.setOnApplyWindowInsetsListener(
        decor,
        (v, insets) -> {
          Insets bars =
              insets.getInsets(
                  WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
          int bottom = bars.bottom;
          if (insets.isVisible(WindowInsetsCompat.Type.ime())) {
            bottom = Math.max(bottom, insets.getInsets(WindowInsetsCompat.Type.ime()).bottom);
          }
          if (v.getPaddingLeft() != bars.left
              || v.getPaddingTop() != bars.top
              || v.getPaddingRight() != bars.right
              || v.getPaddingBottom() != bottom) {
            v.setPadding(bars.left, bars.top, bars.right, bottom);
          }
          return WindowInsetsCompat.CONSUMED;
        });
    ViewCompat.requestApplyInsets(decor);
  }

  /**
   * Build 223: opened as the player for a music file. BridgeActivity also calls this with the
   * launch intent while it starts up, so a cold start arrives here too; OpenedFile marks each
   * intent it takes, so a recreated activity never starts the same file over.
   */
  @Override
  protected void onNewIntent(Intent intent) {
    super.onNewIntent(intent);
    if (intent != getIntent()) setIntent(intent);
    OpenedFile.handle(this, intent);
  }

  @Nullable
  private AmplifyPlayerPlugin player() {
    try {
      PluginHandle h = getBridge() == null ? null : getBridge().getPlugin("AmplifyPlayer");
      return h == null ? null : (AmplifyPlayerPlugin) h.getInstance();
    } catch (Exception e) {
      return null;
    }
  }

  /**
   * Leaving the app (home button or gesture) while a video plays: shrink it into a floating window.
   * Android 12+ already does this by itself (auto-enter, set by the plugin).
   */
  @Override
  protected void onUserLeaveHint() {
    super.onUserLeaveHint();
    if (Build.VERSION.SDK_INT < 26 || Build.VERSION.SDK_INT >= 31) return;
    AmplifyPlayerPlugin p = player();
    if (p == null || !p.pipAllowed()) return;
    try {
      PictureInPictureParams params = p.pipParams();
      if (params != null) enterPictureInPictureMode(params);
    } catch (Exception ignored) {
      // Picture-in-picture turned off for the app in the phone's settings.
    }
  }

  @Override
  public void onPictureInPictureModeChanged(boolean active, Configuration newConfig) {
    super.onPictureInPictureModeChanged(active, newConfig);
    AmplifyPlayerPlugin p = player();
    if (p != null) p.onPipChanged(active);
  }
}
