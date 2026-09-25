package com.markcoleman.amplify;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
  @Override
  public void onCreate(Bundle savedInstanceState) {
    registerPlugin(AmplifyPlayerPlugin.class);
    super.onCreate(savedInstanceState);
  }
}
