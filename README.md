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

## Source history

- Builds 1-6 were built here from this repo's history.
- Builds 7-39 (Android Auto steps 2 and 3, car search and voice, on-air song titles, podcast skip
  buttons, the home-screen widget and the phone UI round) were built outside this repo, and their
  source was never pushed. On 28 Sep 2026 the build 39 APK was turned back into source: the web
  page (`www/index.html`) is the exact file from the APK; the Java was decompiled, with every
  method that was unchanged since build 6 put back as its original source, and the rest cleaned
  up and checked by recompiling it and comparing it method by method against build 39.
- Builds 40-48 were also made outside this repo. On 29 Sep 2026 the build 48 APK was restored
  on top the same way: `www/index.html` is build 48's exact page plus the live stream video
  additions, and its native changes (Export to Downloads, podcast video full screen, an artist's
  stations first in the car) were ported and checked method by method against build 48.
- Version numbers continue from 48 (`BUILD_OFFSET` in `android/app/build.gradle` and
  `.github/workflows/build.yml`), so new builds install over the phone's 1.0.48.
- `docs/` has the notes from that period: `android-auto-status.md` (status as of build 25) and
  `handoff-2026-09-25.md` (technical handoff, written at build 6; the file layout and bridge
  description still apply). `tests/` has the headless page tests (Playwright, mocked Capacitor).
