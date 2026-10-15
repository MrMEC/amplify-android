#!/bin/sh
# Compiles SleepTimer (plain Java) with its test and runs it.
set -e
D=$(mktemp -d)
cd "$(dirname "$0")/../.."
javac -d "$D" android/app/src/main/java/com/markcoleman/amplify/SleepTimer.java tests/java/SleepTimerTest.java
java -cp "$D" com.markcoleman.amplify.SleepTimerTest
