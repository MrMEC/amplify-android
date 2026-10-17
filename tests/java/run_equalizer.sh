#!/bin/sh
# Compiles Equalizer (plain Java) with its test and runs it.
set -e
D=$(mktemp -d)
cd "$(dirname "$0")/../.."
javac -d "$D" android/app/src/main/java/com/markcoleman/amplify/Equalizer.java tests/java/EqualizerTest.java
java -cp "$D" com.markcoleman.amplify.EqualizerTest
