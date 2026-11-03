package com.markcoleman.amplify;

import android.app.PictureInPictureParams;
import android.content.Intent;
import android.content.res.Configuration;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.PluginHandle;

public class MainActivity extends BridgeActivity {
  private final Handler imeHandler = new Handler(Looper.getMainLooper());

  /**
   * Build 460: the white gap along the bottom. The window leaves room for the keyboard while
   * the system still counts it as showing, even though no text field is being edited and
   * nothing is drawn there, so the whole app sat on a shortened screen. If the keyboard has
   * been "up" for a moment with nothing to type into, it is told to go away, which hands the
   * room back. A keyboard with a field being edited is never touched.
   */
  private final Runnable imeGhostCheck =
      () -> {
        try {
          View decor = getWindow().getDecorView();
          WindowInsetsCompat insets = ViewCompat.getRootWindowInsets(decor);
          if (insets == null || !insets.isVisible(WindowInsetsCompat.Type.ime())) return;
          InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
          if (imm == null || imm.isAcceptingText()) return;
          WindowInsetsControllerCompat c = WindowCompat.getInsetsController(getWindow(), decor);
          if (c != null) c.hide(WindowInsetsCompat.Type.ime());
          imm.hideSoftInputFromWindow(decor.getWindowToken(), 0);
        } catch (Exception ignored) {
          // Nothing to correct.
        }
      };

  @Override // com.getcapacitor.BridgeActivity, androidx.fragment.app.FragmentActivity,
  // androidx.activity.ComponentActivity, androidx.core.app.ComponentActivity,
  // android.app.Activity
  public void onCreate(Bundle bundle) {
    CrashLog.install(this);
    registerPlugin(AmplifyPlayerPlugin.class);
    super.onCreate(bundle);
    try {
      final View decor = getWindow().getDecorView();
      decor
          .getViewTreeObserver()
          .addOnGlobalLayoutListener(
              () -> {
                WindowInsetsCompat in = ViewCompat.getRootWindowInsets(decor);
                imeHandler.removeCallbacks(imeGhostCheck);
                if (in != null && in.isVisible(WindowInsetsCompat.Type.ime())) {
                  imeHandler.postDelayed(imeGhostCheck, 1500);
                }
              });
    } catch (Exception ignored) {
      // The page just keeps the keyboard room it was given.
    }
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
