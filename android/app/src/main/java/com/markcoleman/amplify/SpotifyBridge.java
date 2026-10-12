package com.markcoleman.amplify;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import com.spotify.android.appremote.api.ConnectionParams;
import com.spotify.android.appremote.api.Connector;
import com.spotify.android.appremote.api.SpotifyAppRemote;
import com.spotify.protocol.client.Subscription;
import com.spotify.protocol.types.PlayerState;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONObject;

/**
 * Build 211: Top 100 songs play through Spotify. Two parts, both Spotify's own, official routes:
 *
 * <p>Sign-in (for the Web API search that finds each song): the authorization-code flow with
 * PKCE in the browser. No client secret: the code is exchanged with a one-time verifier, and the
 * refresh token is kept so the listener signs in once.
 *
 * <p>Playback: the Spotify App Remote SDK. The Spotify app plays the song; Amplify tells it what
 * to play, pauses, resumes and seeks it, and follows its player state, which the plugin hands to
 * the page exactly like its own player's (so Now Playing works the same). A Premium account is
 * needed to play a chosen song (Spotify's rule).
 */
public final class SpotifyBridge {
  static final String REDIRECT = "amplify-spotify://callback";
  private static final String PREFS = "spotify";
  private static final String SCOPES = "app-remote-control user-read-playback-state";

  interface Listener {
    /** Player state changed (playing, paused, position, ended). Called on the main thread. */
    void onSpotifyState();
    /** Sign-in finished (ok) or failed (error). Called on the main thread. */
    void onSpotifyAuth(boolean ok, String error);
    /** Playback couldn't start (not installed, not Premium, connection refused). Main thread. */
    void onSpotifyError(String message);
    /** Carried on to the next song by itself (the page may be asleep); key is the page's id for it. */
    void onSpotifyAdvance(String key);
  }

  // ---- carrying on by itself (the page can be asleep on a locked phone) ----
  // The page hands over the next few songs it has already found on Spotify. Near the end of
  // each song the next one is put in Spotify's queue, so Spotify moves on seamlessly; if that
  // doesn't happen (or a song was relinked), the end starts the next one directly. Either way
  // the page is told which song is playing now, and catches up when it wakes.
  private static final long QUEUE_BEFORE_END_MS = 15000L;
  private final List<String[]> nextList = new ArrayList<>(); // {uri, key}
  private String queuedUri;
  private final Runnable queueTask = this::queueNextNow;

  private final Context app;
  private final Handler main = new Handler(Looper.getMainLooper());
  private Listener listener;
  private Context uiContext; // an Activity, so Spotify can show its own permission screen

  private SpotifyAppRemote remote;
  private boolean connecting;
  private final List<Runnable> afterConnect = new ArrayList<>();
  private Subscription<PlayerState> sub;

  // What the page asked for, and what Spotify is doing.
  private String wantUri;     // the song asked for
  private String ourUri;      // the song Spotify reported for it (can differ: regional relinking)
  private boolean wantPlay;
  private long wantStartMs;
  private boolean loading;    // asked, not yet reported as playing it
  private boolean ended;      // it finished (or Spotify moved on by itself)
  private boolean requested;  // Spotify has accepted the play request for this load
  private boolean released;   // the listener chose something else in Spotify: hands off
  private long ourDuration;   // our song's length, and where it last was
  private long ourPos;
  private long ourPosAt;
  private boolean ourPaused = true;
  private long playId;        // which load a late answer belongs to
  private PlayerState last;
  private long lastAt;

  SpotifyBridge(Context context) {
    this.app = context.getApplicationContext();
  }

  void setListener(Listener l) {
    this.listener = l;
  }

  void setUiContext(Context c) {
    this.uiContext = c;
  }

  private SharedPreferences prefs() {
    return app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
  }

  String clientId() {
    return prefs().getString("clientId", "");
  }

  void setClientId(String id) {
    String clean = id == null ? "" : id.trim();
    if (!clean.equals(clientId())) {
      // A different app: its sign-in doesn't carry over.
      prefs().edit().putString("clientId", clean).remove("access").remove("refresh").remove("expires").apply();
      disconnect();
    }
  }

  boolean installed() {
    try {
      return SpotifyAppRemote.isSpotifyInstalled(app);
    } catch (Throwable t) {
      return false;
    }
  }

  boolean signedIn() {
    return !prefs().getString("refresh", "").isEmpty();
  }

  boolean connected() {
    return remote != null && remote.isConnected();
  }

  // ---------------- sign-in (PKCE) ----------------

  /** The address to open in the browser; remembers the verifier for the answer. */
  String authUrl() throws Exception {
    byte[] raw = new byte[48];
    new SecureRandom().nextBytes(raw);
    String verifier = b64url(raw);
    byte[] raw2 = new byte[12];
    new SecureRandom().nextBytes(raw2);
    String state = b64url(raw2);
    String challenge =
        b64url(MessageDigest.getInstance("SHA-256").digest(verifier.getBytes(StandardCharsets.US_ASCII)));
    prefs().edit().putString("verifier", verifier).putString("state", state).apply();
    return "https://accounts.spotify.com/authorize?response_type=code"
        + "&client_id=" + enc(clientId())
        + "&redirect_uri=" + enc(REDIRECT)
        + "&code_challenge_method=S256&code_challenge=" + enc(challenge)
        + "&state=" + enc(state)
        + "&scope=" + enc(SCOPES);
  }

  static boolean isRedirect(Uri uri) {
    return uri != null && "amplify-spotify".equals(uri.getScheme()) && "callback".equals(uri.getHost());
  }

  /** The browser came back with amplify-spotify://callback?code=...&state=... (or an error). */
  void handleRedirect(Uri uri) {
    final String error = uri.getQueryParameter("error");
    final String code = uri.getQueryParameter("code");
    final String state = uri.getQueryParameter("state");
    final String wantState = prefs().getString("state", "");
    final String verifier = prefs().getString("verifier", "");
    if (error != null || code == null) {
      authDone(false, error == null ? "Spotify didn't sign you in" : ("Spotify said: " + error));
      return;
    }
    if (!wantState.isEmpty() && !wantState.equals(state)) {
      authDone(false, "That sign-in didn't come from Amplify; please try again");
      return;
    }
    new Thread(
            () -> {
              try {
                JSONObject r =
                    tokenCall(
                        "grant_type=authorization_code&code=" + enc(code)
                            + "&redirect_uri=" + enc(REDIRECT)
                            + "&client_id=" + enc(clientId())
                            + "&code_verifier=" + enc(verifier));
                saveTokens(r);
                prefs().edit().remove("verifier").remove("state").apply();
                authDone(true, null);
              } catch (Exception e) {
                authDone(false, "Sign-in failed: " + e.getMessage());
              }
            })
        .start();
  }

  private void authDone(boolean ok, String error) {
    main.post(
        () -> {
          if (listener != null) listener.onSpotifyAuth(ok, error);
        });
  }

  /** A current access token for the Web API, refreshed when needed. Call off the main thread. */
  synchronized String token() throws Exception {
    SharedPreferences p = prefs();
    String access = p.getString("access", "");
    long expires = p.getLong("expires", 0L);
    if (!access.isEmpty() && System.currentTimeMillis() < expires - 60_000L) return access;
    String refresh = p.getString("refresh", "");
    if (refresh.isEmpty()) throw new Exception("Not signed in to Spotify");
    JSONObject r =
        tokenCall("grant_type=refresh_token&refresh_token=" + enc(refresh) + "&client_id=" + enc(clientId()));
    saveTokens(r);
    return prefs().getString("access", "");
  }

  void signOut() {
    prefs().edit().remove("access").remove("refresh").remove("expires").apply();
    disconnect();
  }

  private void saveTokens(JSONObject r) {
    SharedPreferences.Editor e = prefs().edit();
    e.putString("access", r.optString("access_token", ""));
    e.putLong("expires", System.currentTimeMillis() + r.optLong("expires_in", 3600L) * 1000L);
    String refresh = r.optString("refresh_token", "");
    if (!refresh.isEmpty()) e.putString("refresh", refresh);
    e.apply();
  }

  private static JSONObject tokenCall(String body) throws Exception {
    HttpURLConnection c = (HttpURLConnection) new URL("https://accounts.spotify.com/api/token").openConnection();
    c.setRequestMethod("POST");
    c.setConnectTimeout(12000);
    c.setReadTimeout(12000);
    c.setDoOutput(true);
    c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
    try (OutputStream o = c.getOutputStream()) {
      o.write(body.getBytes(StandardCharsets.UTF_8));
    }
    int status = c.getResponseCode();
    InputStream in = status >= 400 ? c.getErrorStream() : c.getInputStream();
    String text = read(in);
    c.disconnect();
    JSONObject j = text.isEmpty() ? new JSONObject() : new JSONObject(text);
    if (status >= 400) {
      String why = j.optString("error_description", j.optString("error", "HTTP " + status));
      if ("invalid_grant".equals(j.optString("error"))) {
        // A refresh token Spotify no longer accepts: signed out.
        throw new Exception("Spotify sign-in expired (" + why + ")");
      }
      throw new Exception(why);
    }
    return j;
  }

  private static String read(InputStream in) throws Exception {
    if (in == null) return "";
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    byte[] buf = new byte[8192];
    int n;
    while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
    in.close();
    return new String(out.toByteArray(), StandardCharsets.UTF_8);
  }

  private static String b64url(byte[] b) {
    return Base64.encodeToString(b, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
  }

  private static String enc(String s) {
    try {
      return URLEncoder.encode(s == null ? "" : s, "UTF-8").replace("+", "%20");
    } catch (Exception e) {
      return "";
    }
  }

  // ---------------- playback (App Remote) ----------------

  private void connect(Runnable then) {
    if (connected()) {
      then.run();
      return;
    }
    afterConnect.add(then);
    if (connecting) return;
    String id = clientId();
    if (id.isEmpty()) {
      failAll("Add your Spotify Client ID in Settings first");
      return;
    }
    if (!installed()) {
      failAll("The Spotify app isn't installed on this phone");
      return;
    }
    connecting = true;
    ConnectionParams params =
        new ConnectionParams.Builder(id).setRedirectUri(REDIRECT).showAuthView(true).build();
    Context ctx = uiContext != null ? uiContext : app;
    try {
      SpotifyAppRemote.connect(
          ctx,
          params,
          new Connector.ConnectionListener() {
            @Override
            public void onConnected(SpotifyAppRemote r) {
              connecting = false;
              remote = r;
              subscribe();
              List<Runnable> run = new ArrayList<>(afterConnect);
              afterConnect.clear();
              for (Runnable x : run) x.run();
            }

            @Override
            public void onFailure(Throwable t) {
              connecting = false;
              remote = null;
              failAll(describe(t));
            }
          });
    } catch (Throwable t) {
      connecting = false;
      failAll(describe(t));
    }
  }

  private void failAll(String message) {
    afterConnect.clear();
    loading = false;
    if (listener != null) listener.onSpotifyError(message);
  }

  /** Spotify's own errors, said plainly. */
  static String describe(Throwable t) {
    String n = t == null ? "" : t.getClass().getSimpleName();
    String m = t == null || t.getMessage() == null ? "" : t.getMessage();
    if (n.contains("NotLoggedIn")) return "Open the Spotify app and log in first";
    if (n.contains("CouldNotFindSpotifyApp")) return "The Spotify app isn't installed on this phone";
    if (n.contains("UserNotAuthorized")) return "Spotify didn't allow Amplify to control it (" + m + ")";
    if (n.contains("UnsupportedFeatureVersion")) return "Please update the Spotify app";
    if (n.contains("OfflineMode")) return "Spotify is offline";
    if (m.toLowerCase().contains("premium")) return "Playing a chosen song needs Spotify Premium";
    return "Spotify couldn't play it" + (m.isEmpty() ? "" : " (" + m + ")");
  }

  private void subscribe() {
    if (remote == null) return;
    try {
      if (sub != null) sub.cancel();
    } catch (Throwable ignored) {
    }
    sub = remote.getPlayerApi().subscribeToPlayerState();
    sub.setEventCallback(this::onState);
  }

  private void onState(PlayerState s) {
    last = s;
    lastAt = System.currentTimeMillis();
    if (wantUri == null || released) {
      if (listener != null) listener.onSpotifyState();
      return;
    }
    String u = s == null || s.track == null ? null : s.track.uri;
    if (u != null && ourUri == null && requested && loading) {
      // The first song Spotify reports once it has taken the request is ours, even if Spotify
      // relinked it to another uri for this country.
      ourUri = u;
    }
    if (u != null && (u.equals(wantUri) || u.equals(ourUri))) {
      if (ourUri == null) ourUri = u;
      loading = false;
      ourDuration = s.track.duration;
      ourPos = s.playbackPosition;
      ourPosAt = lastAt;
      ourPaused = s.isPaused;
      // Played to the end with nothing after it: it rests at the end, paused.
      if (!ended && s.isPaused && ourDuration > 0 && s.playbackPosition >= ourDuration - 1500 && wantPlay) {
        if (!advance(null)) ended = true;
      }
    } else if (u != null && queuedUri != null && u.equals(queuedUri) && ourUri != null && !loading) {
      // Spotify moved on to the song queued for it: the next one down the list.
      advance(u);
    } else if (ourUri != null && !ended && !loading) {
      // Spotify is on another song. If ours had about reached its end, it finished and
      // Spotify's autoplay moved on: that's our end, and Amplify plays the next chart song.
      // Otherwise the listener picked something else in Spotify: Amplify lets go (shown as
      // paused) instead of fighting over it.
      long at = ourPos + (ourPaused ? 0L : (lastAt - ourPosAt));
      if (ourDuration > 0 && at >= ourDuration - 6000) {
        if (!advance(null)) {
          ended = true;
          try {
            remote.getPlayerApi().pause();
          } catch (Throwable ignored) {
          }
        }
      } else {
        released = true;
        wantPlay = false;
      }
    }
    scheduleQueue();
    if (listener != null) listener.onSpotifyState();
  }

  /** The page plays something itself: any list it gave for the last song no longer applies. */
  void loadFromPage(String uri, boolean play, long startMs) {
    nextList.clear();
    load(uri, play, startMs);
  }

  /** Plays uri (spotify:track:...) from startMs; paused straight away if !play. */
  void load(String uri, boolean play, long startMs) {
    final long id = ++playId;
    wantUri = uri;
    ourUri = null;
    wantPlay = play;
    wantStartMs = startMs;
    loading = true;
    ended = false;
    requested = false;
    released = false;
    queuedUri = null;
    main.removeCallbacks(queueTask);
    ourDuration = 0L;
    ourPos = 0L;
    ourPaused = true;
    connect(
        () -> {
          if (id != playId || remote == null) return;
          remote
              .getPlayerApi()
              .play(uri)
              .setResultCallback(
                  empty -> {
                    if (id != playId || remote == null) return;
                    requested = true;
                    if (wantStartMs > 1000) remote.getPlayerApi().seekTo(wantStartMs);
                    if (!wantPlay) remote.getPlayerApi().pause();
                    // In case its state arrived before this answer did.
                    main.postDelayed(
                        () -> {
                          if (id != playId || remote == null) return;
                          remote.getPlayerApi().getPlayerState().setResultCallback(this::onState);
                        },
                        400L);
                  })
              .setErrorCallback(
                  t -> {
                    if (id != playId) return;
                    loading = false;
                    if (listener != null) listener.onSpotifyError(describe(t));
                  });
        });
  }

  void play() {
    if (wantUri == null) return;
    wantPlay = true;
    if (ended || released) {
      // Played again after it finished (from the top), or after the listener used Spotify for
      // something else (back to where it was).
      load(wantUri, true, ended ? 0L : positionMs());
      return;
    }
    connect(() -> remote.getPlayerApi().resume());
  }

  void pause() {
    wantPlay = false;
    if (connected() && !released && !ended) remote.getPlayerApi().pause();
  }

  void seek(long ms) {
    if (released || ended) {
      ourPos = ms;
      ourPosAt = System.currentTimeMillis();
      return;
    }
    if (connected() && wantUri != null) remote.getPlayerApi().seekTo(ms);
  }

  /** Something else plays now: Spotify stops (pauses) if it's on our song. */
  void stop() {
    boolean wasOurs = (ourUri != null || loading) && !released && !ended;
    wantUri = null;
    ourUri = null;
    loading = false;
    ended = false;
    requested = false;
    released = false;
    queuedUri = null;
    nextList.clear();
    main.removeCallbacks(queueTask);
    playId++;
    if (wasOurs && connected()) {
      try {
        remote.getPlayerApi().pause();
      } catch (Throwable ignored) {
      }
    }
  }

  void disconnect() {
    try {
      if (sub != null) sub.cancel();
    } catch (Throwable ignored) {
    }
    sub = null;
    if (remote != null) {
      try {
        SpotifyAppRemote.disconnect(remote);
      } catch (Throwable ignored) {
      }
    }
    remote = null;
  }

  /** The songs after this one, in order ({uri, key} each); replaces any earlier list. */
  void setNext(List<String[]> items) {
    nextList.clear();
    if (items != null) nextList.addAll(items);
    scheduleQueue();
  }

  private void scheduleQueue() {
    main.removeCallbacks(queueTask);
    if (queuedUri != null || nextList.isEmpty() || !isPlaying() || ourDuration <= 0) return;
    long left = ourDuration - positionMs();
    main.postDelayed(queueTask, Math.max(0L, left - QUEUE_BEFORE_END_MS));
  }

  private void queueNextNow() {
    if (queuedUri != null || nextList.isEmpty() || !isPlaying() || !connected()) return;
    if (ourDuration - positionMs() > QUEUE_BEFORE_END_MS + 2000L) {
      scheduleQueue();
      return;
    }
    final String uri = nextList.get(0)[0];
    queuedUri = uri;
    try {
      remote.getPlayerApi().queue(uri);
    } catch (Throwable t) {
      queuedUri = null;
    }
  }

  /** Our song is over and a next one is known: it becomes ours. */
  private boolean advance(String nowPlayingUri) {
    if (nextList.isEmpty()) return false;
    String[] nx = nextList.remove(0);
    queuedUri = null;
    if (nowPlayingUri != null) {
      // Spotify is already on it (from its queue).
      wantUri = nx[0];
      ourUri = nowPlayingUri;
      loading = false;
      ended = false;
      released = false;
      requested = true;
      ourDuration = last != null && last.track != null ? last.track.duration : 0L;
      ourPos = last != null ? last.playbackPosition : 0L;
      ourPosAt = lastAt;
      ourPaused = last != null && last.isPaused;
    } else {
      load(nx[0], true, 0L);
    }
    if (listener != null) listener.onSpotifyAdvance(nx[1]);
    return true;
  }

  // ---------------- state for the page ----------------

  boolean isOnOurSong() {
    return wantUri != null && !loading && !ended && !released && last != null && last.track != null
        && (last.track.uri.equals(wantUri) || last.track.uri.equals(ourUri));
  }

  boolean isPlaying() {
    return isOnOurSong() && !last.isPaused;
  }

  boolean playWhenReady() {
    return wantPlay && !ended && !released;
  }

  long positionMs() {
    if (ended) return ourDuration;
    if (released || !isOnOurSong()) return ourUri != null ? ourPos : wantStartMs;
    long p = last.playbackPosition;
    if (!last.isPaused) p += (long) ((System.currentTimeMillis() - lastAt) * Math.max(0.1f, last.playbackSpeed));
    return Math.max(0L, Math.min(p, last.track.duration));
  }

  long durationMs() {
    return ourDuration > 0 ? ourDuration : -1L;
  }

  String stateName() {
    if (ended) return "ended";
    if (released) return "ready";
    if (loading) return "buffering";
    return isOnOurSong() ? "ready" : "buffering";
  }

  /** Whether Amplify should stay running for it: playing, or paused only briefly. */
  boolean holdsPlayback() {
    return wantUri != null && !released && !ended;
  }

  String trackName() {
    return isOnOurSong() && last.track.name != null ? last.track.name : "";
  }

  boolean ended() {
    return ended;
  }
}
