#!/bin/sh
# Compiles Leveler (plain Java) with its test and runs it.
set -e
D=$(mktemp -d)
cd "$(dirname "$0")/../.."
javac -d "$D" android/app/src/main/java/com/markcoleman/amplify/Leveler.java tests/java/LevelerTest.java
java -cp "$D" com.markcoleman.amplify.LevelerTest
