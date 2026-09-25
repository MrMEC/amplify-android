# Amplify for Android

The Amplify web app (`www/index.html`) inside a Capacitor shell, with native Media3 playback:
background audio, notification / lock-screen / Bluetooth controls, and plain-http stations.

- `android/app/src/main/java/com/markcoleman/amplify/` – `PlaybackService` (ExoPlayer + MediaSession),
  `SkipAwarePlayer` (routes outside transport commands to the page), `AmplifyPlayerPlugin` (the page ↔ player bridge).
- The page detects the app (`Capacitor.isNativePlatform()`) and swaps its `<audio>` element and
  `navigator.mediaSession` for the native player; in a browser nothing changes.
- Every push to `main` builds the APK in GitHub Actions and publishes it as the `latest` release
  (and to the `build-output` branch with the build log).

Personal sideload build; the signing key in `android/app/amplify.keystore` is only for that.
