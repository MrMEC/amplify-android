package com.markcoleman.amplify;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import java.util.concurrent.TimeUnit;

/**
 * Build 274: reads every followed podcast's feed about once an hour, app open or not (WorkManager
 * keeps the schedule through restarts and reboots, and runs it when there's a connection). The
 * page shows the saved result as soon as it starts, so the morning's episodes are already there.
 */
public class PodcastRefreshWorker extends Worker {
  private static final String NAME = "amplifyPodcastRefresh";

  public PodcastRefreshWorker(@NonNull Context context, @NonNull WorkerParameters params) {
    super(context, params);
  }

  @NonNull
  @Override
  public Result doWork() {
    try {
      PodcastFeeds.refreshAll(getApplicationContext());
      return Result.success();
    } catch (Exception e) {
      return Result.retry();
    }
  }

  /** Safe to call every start: an existing schedule is kept as it is. */
  public static void schedule(Context c) {
    try {
      Constraints k = new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build();
      PeriodicWorkRequest req =
          new PeriodicWorkRequest.Builder(PodcastRefreshWorker.class, 1, TimeUnit.HOURS, 20, TimeUnit.MINUTES)
              .setConstraints(k)
              .build();
      WorkManager.getInstance(c.getApplicationContext())
          .enqueueUniquePeriodicWork(NAME, ExistingPeriodicWorkPolicy.KEEP, req);
    } catch (Exception ignored) {
      // no background refresh this time; the page still refreshes when opened
    }
  }
}
