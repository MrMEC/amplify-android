package com.markcoleman.amplify;

import android.os.Build;
import android.os.Bundle;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
  @Override // com.getcapacitor.BridgeActivity, androidx.fragment.app.FragmentActivity,
            // androidx.activity.ComponentActivity, androidx.core.app.ComponentActivity,
            // android.app.Activity
  public void onCreate(Bundle bundle) {
    registerPlugin(AmplifyPlayerPlugin.class);
    super.onCreate(bundle);
    if (Build.VERSION.SDK_INT < 33
        || ContextCompat.checkSelfPermission(this, "android.permission.POST_NOTIFICATIONS") == 0) {
      return;
    }
    ActivityCompat.requestPermissions(
        this, new String[] {"android.permission.POST_NOTIFICATIONS"}, 7);
  }
}
