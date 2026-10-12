#!/bin/sh
# Build 211: SpotifyBridge's player-state logic (our song, relinking, natural end vs the listener
# choosing something else in Spotify), against the real App Remote classes and small stand-ins
# for the few Android classes it uses (there is no Android SDK here).
# Needs the App Remote AAR's classes: unzip android/app/libs/spotify-app-remote-release-0.8.0.aar,
# then classes.jar. Run from the repo root: sh tests/java/spotify/run.sh
set -e
T=$(mktemp -d)
unzip -q -o android/app/libs/spotify-app-remote-release-0.8.0.aar classes.jar -d "$T"
mkdir -p "$T/out"
javac -nowarn -d "$T/out" -cp "$T/classes.jar" $(find tests/java/spotify/stubs -name '*.java') \
  android/app/src/main/java/com/markcoleman/amplify/SpotifyBridge.java tests/java/spotify/BridgeTest.java
java -cp "$T/out:$T/classes.jar" com.markcoleman.amplify.BridgeTest
