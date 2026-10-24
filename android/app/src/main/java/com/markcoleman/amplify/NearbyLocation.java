package com.markcoleman.amplify;

import android.content.Context;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import androidx.annotation.Nullable;
import java.util.List;

/**
 * Build 310: the phone's rough position for Stations Near Me. Only the coarse (city-level)
 * permission is asked for, so this uses the network / fused providers, never GPS. A recent
 * last-known position is used as it is; otherwise one fresh fix is asked for, falling back to
 * the last known one (however old) when none comes within the timeout.
 */
final class NearbyLocation {
  interface Result {
    void done(@Nullable Location loc, @Nullable String error);
  }

  private NearbyLocation() {}

  @Nullable
  static Location lastKnown(LocationManager lm) {
    Location best = null;
    List<String> providers;
    try {
      providers = lm.getProviders(true);
    } catch (Exception e) {
      return null;
    }
    for (String p : providers) {
      try {
        Location l = lm.getLastKnownLocation(p);
        if (l != null && (best == null || l.getTime() > best.getTime())) best = l;
      } catch (SecurityException ignored) {
        // GPS needs the precise permission; skipped.
      } catch (Exception ignored) {
      }
    }
    return best;
  }

  @Nullable
  private static String freshProvider(LocationManager lm) {
    try {
      if (Build.VERSION.SDK_INT >= 31 && lm.isProviderEnabled(LocationManager.FUSED_PROVIDER)) {
        return LocationManager.FUSED_PROVIDER;
      }
      if (lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
        return LocationManager.NETWORK_PROVIDER;
      }
    } catch (Exception ignored) {
    }
    return null;
  }

  static void get(Context ctx, long maxAgeMs, long timeoutMs, Result out) {
    Handler main = new Handler(Looper.getMainLooper());
    LocationManager lm = (LocationManager) ctx.getSystemService(Context.LOCATION_SERVICE);
    if (lm == null) {
      out.done(null, "UNAVAILABLE");
      return;
    }
    final Location fallback = lastKnown(lm);
    if (fallback != null && System.currentTimeMillis() - fallback.getTime() <= maxAgeMs) {
      out.done(fallback, null);
      return;
    }
    String provider = freshProvider(lm);
    if (provider == null) {
      out.done(fallback, fallback == null ? "OFF" : null);
      return;
    }
    final boolean[] finished = {false};
    final LocationListener[] legacy = {null};
    final Runnable timeout =
        () -> {
          if (finished[0]) return;
          finished[0] = true;
          if (legacy[0] != null) {
            try {
              lm.removeUpdates(legacy[0]);
            } catch (Exception ignored) {
            }
          }
          out.done(fallback, fallback == null ? "TIMEOUT" : null);
        };
    main.postDelayed(timeout, timeoutMs);
    try {
      if (Build.VERSION.SDK_INT >= 30) {
        lm.getCurrentLocation(
            provider,
            null,
            main::post,
            loc -> {
              if (finished[0]) return;
              finished[0] = true;
              main.removeCallbacks(timeout);
              Location use = loc != null ? loc : fallback;
              out.done(use, use == null ? "TIMEOUT" : null);
            });
      } else {
        legacy[0] =
            new LocationListener() {
              @Override
              public void onLocationChanged(Location loc) {
                if (finished[0]) return;
                finished[0] = true;
                main.removeCallbacks(timeout);
                try {
                  lm.removeUpdates(this);
                } catch (Exception ignored) {
                }
                out.done(loc, null);
              }

              @Override
              @SuppressWarnings("deprecation")
              public void onStatusChanged(String p, int status, Bundle extras) {}

              @Override
              public void onProviderEnabled(String p) {}

              @Override
              public void onProviderDisabled(String p) {}
            };
        lm.requestLocationUpdates(provider, 0L, 0f, legacy[0], Looper.getMainLooper());
      }
    } catch (SecurityException e) {
      if (finished[0]) return;
      finished[0] = true;
      main.removeCallbacks(timeout);
      out.done(fallback, fallback == null ? "DENIED" : null);
    } catch (Exception e) {
      if (finished[0]) return;
      finished[0] = true;
      main.removeCallbacks(timeout);
      out.done(fallback, fallback == null ? "UNAVAILABLE" : null);
    }
  }
}
