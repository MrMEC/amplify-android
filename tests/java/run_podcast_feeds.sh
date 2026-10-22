#!/bin/sh
# Build 274: compiles PodcastFeeds with test stand-ins for Context / Xml and runs its test.
# Needs kxml2 (Android's XML parser) and org.json jars: KXML and JSONJAR, fetched if missing.
set -e
D=$(mktemp -d)
cd "$(dirname "$0")/../.."
KXML=${KXML:-$D/kxml2.jar}; JSONJAR=${JSONJAR:-$D/json.jar}
[ -f "$KXML" ] || curl -sSfL -o "$KXML" https://repo1.maven.org/maven2/net/sf/kxml/kxml2/2.3.0/kxml2-2.3.0.jar
[ -f "$JSONJAR" ] || curl -sSfL -o "$JSONJAR" https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar
CP="$KXML:$JSONJAR"
javac -cp "$CP" -d "$D/out" tests/java/stubs/android/content/*.java tests/java/stubs/android/util/*.java \
  android/app/src/main/java/com/markcoleman/amplify/PodcastFeeds.java tests/java/PodcastFeedsTest.java
java -Dhttp.nonProxyHosts='127.0.0.1|localhost' -cp "$D/out:$CP" com.markcoleman.amplify.PodcastFeedsTest
