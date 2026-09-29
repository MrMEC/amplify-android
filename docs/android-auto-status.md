# Amplify for Android: Android Auto status (25 Sep 2026, updated ~19:10 ET)

- Repo: github.com/MrMEC/amplify-android (private), branch main. CI builds the `latest` release APK on every push.
- Steps 1-3 of the Android Auto menu are built: Home, Library (Artists, Albums, Songs, Playlists, Genres), Stations, Podcasts, the car's blue Search button, and voice ("play X on Amplify"). The Search row and tab were removed at Mark's request.
- Podcast episodes: the notification, lock screen and car show skip back 15 / forward 30 (plain circular arrows, no numbers) instead of Previous/Next.
- Songs and stations show Amplify's own double-arrow Previous/Next, always both together. Steering-wheel and headset skip keys are handled separately; still to confirm in the car.
- The phone app follows what the car plays, and the car follows the phone. The car opens on the last-played item (paused, ready) instead of "Tap to open"; the phone's last-played item wins over the car's restored one. Position is saved every few seconds while playing.
- Car queue from the phone: still showed 1 item in Mark's test of build 23. Build 24 handles every state (phone playing, car restored, car playing with the phone following), and each is covered by tests, but it isn't confirmed on the car yet. Settings > Check storage ends with an "Android Auto" block (notification permission, mode, loaded items, car queue size, saved queue, last queue events). If the queue is still empty, a screenshot of that block shows where it stops.
- Build 25: Mark saw nothing outside the app while playing. The app never asked for notification permission (Android 13+), so it now asks once on launch; the lock screen and notification panel controls need it allowed. Also new: a home-screen Now Playing widget (cover, title, artist, Previous / Play-Pause / Next), added from the phone's widget picker.
- The car shows the same cover art as the phone (custom art, station logos, artist portraits, album covers).
- Phone UI changes this round: Settings card redesign, startup freeze fixed, home rows peek the next thumbnail, Favorites page Edit and mixed Shuffle, "Amplify Radio" labels, Continue Listening as cover tiles, Now Playing slides up and closes with a down arrow or swipe down, queue shown as one list under Up Next with a count, My Library rows flush left, "All Artists" link on the Top Artists page.
- Mark is given locally built, signed APKs directly. Build 25 (commit bfaed2b) is the latest.
- Local main is many commits ahead of GitHub and not pushed: the push fails because the chat session wasn't created with MrMEC/amplify-android as a repository source. Everything is in `amplify-android-handoff.zip` with HANDOFF.md (full technical notes).
- Songs from "Add folder" play in the car; songs from "Add files" do not. Run Add folder again once to link songs imported earlier.
- Deferred: carrying the web-UI changes over to the web Amplify.html (Mark said disregard for now).
