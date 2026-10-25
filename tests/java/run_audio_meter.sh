#!/bin/sh
# Compiles AudioMeter (plain Java) with its test and runs it.
set -e
D=$(mktemp -d)
cd "$(dirname "$0")/../.."
javac -d "$D" android/app/src/main/java/com/markcoleman/amplify/AudioMeter.java tests/java/AudioMeterTest.java
java -cp "$D" com.markcoleman.amplify.AudioMeterTest
