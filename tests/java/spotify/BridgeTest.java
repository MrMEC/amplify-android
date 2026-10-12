package com.markcoleman.amplify;
import com.spotify.protocol.types.*;
import java.lang.reflect.*;
public class BridgeTest {
  static int fails = 0;
  static void check(boolean c, String m){ System.out.println((c?"PASS ":"FAIL ")+m); if(!c) fails++; }
  static class Prefs implements android.content.SharedPreferences {
    java.util.Map<String,Object> m = new java.util.HashMap<>();
    public String getString(String k,String d){ Object v=m.get(k); return v==null?d:(String)v; }
    public long getLong(String k,long d){ Object v=m.get(k); return v==null?d:(Long)v; }
    public Editor edit(){ final Prefs self=this; return new Editor(){
      public Editor putString(String k,String v){ self.m.put(k,v); return this; }
      public Editor putLong(String k,long v){ self.m.put(k,v); return this; }
      public Editor remove(String k){ self.m.remove(k); return this; }
      public void apply(){} }; }
  }
  static final Prefs PREFS = new Prefs();
  static class Ctx extends android.content.Context { public android.content.Context getApplicationContext(){return this;} public android.content.SharedPreferences getSharedPreferences(String n,int m){return PREFS;} }
  static java.util.List<String> advanced = new java.util.ArrayList<>();
  static java.util.List<String> errors = new java.util.ArrayList<>();
  static Object b; static Class<?> C;
  static void set(String f, Object v) throws Exception { Field x = C.getDeclaredField(f); x.setAccessible(true); x.set(b, v); }
  static Object call(String m) throws Exception { Method x = C.getDeclaredMethod(m); x.setAccessible(true); return x.invoke(b); }
  static void state(String uri, long dur, boolean paused, long pos) throws Exception {
    Track t = new Track(null, null, null, dur, "x", uri, null, false, false);
    PlayerState s = new PlayerState(t, paused, 1f, pos, null, null);
    Method m = C.getDeclaredMethod("onState", PlayerState.class); m.setAccessible(true); m.invoke(b, s);
  }
  static void fresh(String uri) throws Exception {
    C = Class.forName("com.markcoleman.amplify.SpotifyBridge");
    Constructor<?> k = C.getDeclaredConstructor(android.content.Context.class); k.setAccessible(true);
    b = k.newInstance(new Ctx());
    set("wantUri", uri); set("loading", true); set("requested", true); set("wantPlay", true);
    advanced.clear(); errors.clear();
    ((SpotifyBridge) b).setListener(new SpotifyBridge.Listener(){
      public void onSpotifyState(){}
      public void onSpotifyAuth(boolean ok, String e){}
      public void onSpotifyError(String m){ errors.add(m); }
      public void onSpotifyAdvance(String key){ advanced.add(key); }
    });
  }
  static void next(String... uriKey){
    java.util.List<String[]> l = new java.util.ArrayList<>();
    for(int i = 0; i < uriKey.length; i += 2) l.add(new String[]{ uriKey[i], uriKey[i+1] });
    ((SpotifyBridge) b).setNext(l);
  }
  static Object get(String f) throws Exception { Field x = C.getDeclaredField(f); x.setAccessible(true); return x.get(b); }
  public static void main(String[] a) throws Exception {
    fresh("spotify:track:A");
    state("spotify:track:A", 200000, false, 1000);
    check((Boolean)call("isPlaying") && "ready".equals(call("stateName")), "plays our song");
    state("spotify:track:A", 200000, true, 50000);
    check(!(Boolean)call("isPlaying") && (Boolean)call("playWhenReady") && (Long)call("positionMs") == 50000L, "paused in Spotify: not playing, position kept");
    fresh("spotify:track:A");
    state("spotify:track:A2", 180000, false, 0);
    check((Boolean)call("isPlaying"), "a relinked uri counts as ours");
    fresh("spotify:track:A");
    state("spotify:track:A", 200000, false, 197000);
    Thread.sleep(10);
    state("spotify:track:B", 210000, false, 0);
    check("ended".equals(call("stateName")) && !(Boolean)call("isPlaying"), "song finished and autoplay moved on: ended");
    fresh("spotify:track:A");
    state("spotify:track:A", 200000, false, 30000);
    state("spotify:track:C", 210000, false, 0);
    check("ready".equals(call("stateName")) && !(Boolean)call("isPlaying") && !(Boolean)call("playWhenReady"), "listener picked another song mid-way: Amplify lets go (paused, not ended)");
    state("spotify:track:D", 210000, false, 0);
    check(!"ended".equals(call("stateName")), "and stays let go");
    fresh("spotify:track:A");
    state("spotify:track:A", 200000, false, 100000);
    state("spotify:track:A", 200000, true, 199500);
    check("ended".equals(call("stateName")), "rests paused at its end: ended");
    fresh("spotify:track:A");
    set("requested", false);
    state("spotify:track:OLD", 200000, false, 5000);
    check(!(Boolean)call("isPlaying") && "buffering".equals(call("stateName")), "what Spotify was playing before the request isn't taken as ours");
    // ---- carrying on by itself (build 211)
    fresh("spotify:track:A");
    next("spotify:track:B", "song:b", "spotify:track:C", "song:c");
    state("spotify:track:A", 200000, false, 190000);
    set("queuedUri", "spotify:track:B"); // what queueNextNow does 15s from the end
    state("spotify:track:B", 210000, false, 0);
    check(advanced.equals(java.util.Arrays.asList("song:b")) && (Boolean)call("isPlaying") && "spotify:track:B".equals(get("wantUri")),
        "Spotify moved on to the queued song: it's ours now, and the page is told which");
    check(get("queuedUri") == null && ((java.util.List<?>)get("nextList")).size() == 1, "the one after it is next in line");
    state("spotify:track:B", 210000, false, 206000);
    state("spotify:track:ZZ", 180000, false, 0);  // not queued in time (or relinked): autoplay came on
    check(advanced.equals(java.util.Arrays.asList("song:b", "song:c")) && "spotify:track:C".equals(get("wantUri")) && !"ended".equals(call("stateName")),
        "a song ending without the queue still carries on to the next one");
    fresh("spotify:track:A");
    next("spotify:track:B", "song:b");
    state("spotify:track:A", 200000, false, 40000);
    state("spotify:track:Q", 200000, false, 0);
    check(advanced.isEmpty() && !(Boolean)call("playWhenReady"), "picking another song mid-way still lets go (no carrying on)");
    fresh("spotify:track:A");
    state("spotify:track:A", 200000, false, 195000);
    state("spotify:track:ZZ", 180000, false, 0);
    check(advanced.isEmpty() && "ended".equals(call("stateName")), "with nothing next, the end is just the end");
    fresh("spotify:track:A");
    next("spotify:track:B", "song:b");
    ((SpotifyBridge) b).loadFromPage("spotify:track:X", true, 0L);
    check(((java.util.List<?>)get("nextList")).isEmpty(), "the page playing something itself drops the old list");
    System.out.println(fails == 0 ? "ALL PASS" : ("FAILS: " + fails));
  }
}
