#!/bin/sh
# Compiles ChapterCheck (plain Java) with its test and runs it.
set -e
D=$(mktemp -d)
cd "$(dirname "$0")/../.."
javac -d "$D" android/app/src/main/java/com/markcoleman/amplify/ChapterCheck.java tests/java/ChapterCheckTest.java
java -Dhttp.nonProxyHosts='127.0.0.1|localhost' -cp "$D" com.markcoleman.amplify.ChapterCheckTest
