package com.markcoleman.amplify;

import com.sun.net.httpserver.HttpServer;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** Build 199: the Cast relay for Pluto playlists. Run: see tests/java/run_cast_relay.sh */
public class CastRelayTest {
  static int fails = 0;
  static void ok(boolean c, String name) { System.out.println((c ? "PASS " : "FAIL ") + name); if (!c) fails++; }
  static String[] get(String u, String method) throws Exception {
    HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
    c.setRequestMethod(method);
    c.setRequestProperty("Origin", "https://www.gstatic.com");
    int code = c.getResponseCode();
    InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream();
    String body = in == null ? "" : new String(in.readAllBytes(), StandardCharsets.UTF_8);
    return new String[] {String.valueOf(code), body, String.valueOf(c.getHeaderField("Access-Control-Allow-Origin")), String.valueOf(c.getContentType())};
  }
  public static void main(String[] a) throws Exception {
    try { run(); } catch (Throwable t) { t.printStackTrace(); fails++; }
    System.out.println(fails == 0 ? "ALL PASSED" : "FAILED " + fails);
    System.exit(fails == 0 ? 0 : 1);
  }
  static void run() throws Exception {
    HttpServer up = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    int port = up.getAddress().getPort();
    String U = "http://127.0.0.1:" + port;
    int[] masterHits = {0};
    up.createContext("/v2/stitch/hls/channel/abc/master.m3u8", ex -> {
      masterHits[0]++;
      String q = ex.getRequestURI().getQuery();
      String body = "#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"aud\",NAME=\"en\",URI=\"audio/en.m3u8?jwt=T\"\n"
          + "#EXT-X-STREAM-INF:BANDWIDTH=600000,AUDIO=\"aud\"\n360p/playlist?jwt=T&x=" + q.length() + "\n"
          + "#EXT-X-STREAM-INF:BANDWIDTH=2000000\nhttps://cdn.example/720p/index.m3u8?a=1\n";
      byte[] b = body.getBytes(StandardCharsets.UTF_8); ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); ex.close();
    });
    up.createContext("/v2/stitch/hls/channel/abc/360p/playlist", ex -> {
      String body = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXT-X-KEY:METHOD=AES-128,URI=\"https://keys.example/k1.key\"\n#EXTINF:6,\nhttps://siloh.example/seg1.ts\n#EXT-X-DISCONTINUITY\n#EXT-X-KEY:METHOD=AES-128,URI=\"rel/k2.key\"\n#EXTINF:6,\nseg2.ts\n";
      byte[] b = body.getBytes(StandardCharsets.UTF_8); ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); ex.close();
    });
    up.createContext("/redir", ex -> { ex.getResponseHeaders().add("Location", U + "/v2/stitch/hls/channel/abc/master.m3u8?r=1"); ex.sendResponseHeaders(302, -1); ex.close(); });
    up.createContext("/broken.m3u8", ex -> { ex.sendResponseHeaders(500, -1); ex.close(); });
    up.start();

    ok(CastRelay.needed("https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/5ef3/master.m3u8?jwt=x"), "a Pluto stitcher address needs the relay");
    ok(!CastRelay.needed("https://bdc8100.mediatailor.us-east-2.amazonaws.com/v1/master/x/playlist.m3u8"), "other channels don't");
    ok(!CastRelay.needed("http://media4.tripsmarter.com:1935/LiveTV/x/playlist.m3u8"), "nor plain http channels");

    CastRelay r = CastRelay.get();
    String base = r.startOn("127.0.0.1");
    String wrapped = r.wrap(U + "/v2/stitch/hls/channel/abc/master.m3u8?appName=web&jwt=LONG");
    ok(wrapped.startsWith(base + "/p/") && wrapped.endsWith(".m3u8"), "wrapped address is on the relay " + wrapped);

    String[] m = get(wrapped, "GET");
    System.out.println(m[1]);
    ok(m[0].equals("200"), "master served (" + m[0] + ")");
    ok(m[2].equals("*"), "with an open CORS header (" + m[2] + ")");
    ok(m[3].contains("mpegurl"), "as an HLS playlist (" + m[3] + ")");
    String[] lines = m[1].split("\n");
    String v360 = null, v720 = null, audio = null;
    for (int i = 0; i < lines.length; i++) {
      if (lines[i].startsWith("#EXT-X-STREAM-INF:BANDWIDTH=600000")) v360 = lines[i + 1];
      if (lines[i].startsWith("#EXT-X-STREAM-INF:BANDWIDTH=2000000")) v720 = lines[i + 1];
      if (lines[i].startsWith("#EXT-X-MEDIA")) { int s = lines[i].indexOf("URI=\"") + 5; audio = lines[i].substring(s, lines[i].indexOf('"', s)); }
    }
    ok(v360 != null && v360.startsWith(base + "/p/"), "a relative variant (no .m3u8 in its name) goes through the relay " + v360);
    ok(v720 != null && v720.startsWith(base + "/p/"), "an absolute variant on another host too " + v720);
    ok(audio != null && audio.startsWith(base + "/p/"), "an audio rendition too " + audio);
    ok(masterHits[0] == 1, "the master was fetched once by the phone (" + masterHits[0] + ")");

    String[] v = get(v360, "GET");
    System.out.println(v[1]);
    ok(v[0].equals("200") && v[2].equals("*"), "the variant is served with CORS (" + v[0] + ")");
    ok(v[1].contains("\nhttps://siloh.example/seg1.ts\n"), "absolute video pieces stay on their own server");
    ok(v[1].contains("\n" + U + "/v2/stitch/hls/channel/abc/360p/seg2.ts\n"), "relative pieces are made absolute (straight from the server, not the relay)");
    ok(v[1].contains("URI=\"https://keys.example/k1.key\"") && v[1].contains("URI=\"" + U + "/v2/stitch/hls/channel/abc/360p/rel/k2.key\""), "keys made absolute, not relayed");
    ok(v[1].contains("#EXT-X-DISCONTINUITY"), "other tags kept");

    String[] o = get(wrapped, "OPTIONS");
    ok(o[0].equals("204") && o[2].equals("*"), "a CORS preflight is answered (" + o[0] + ")");
    String[] nf = get(base + "/p/zzzz.m3u8", "GET");
    ok(nf[0].equals("404"), "unknown address 404 (" + nf[0] + ")");
    String[] rd = get(r.wrap(U + "/redir"), "GET");
    ok(rd[0].equals("200") && rd[1].contains("#EXT-X-STREAM-INF"), "redirects are followed (" + rd[0] + ")");
    String[] bad = get(r.wrap(U + "/broken.m3u8"), "GET");
    ok(bad[0].equals("502"), "an upstream error gives 502 (" + bad[0] + ")");
    // parallel requests
    Thread[] ts = new Thread[8]; final int[] good = {0};
    for (int i = 0; i < ts.length; i++) { ts[i] = new Thread(() -> { try { if (get(wrapped, "GET")[0].equals("200")) synchronized (good) { good[0]++; } } catch (Exception e) {} }); ts[i].start(); }
    for (Thread t : ts) t.join();
    ok(good[0] == 8, "8 requests at once all served (" + good[0] + ")");
    ok(CastRelay.lanAddress() == null || CastRelay.lanAddress().matches("\\d+\\.\\d+\\.\\d+\\.\\d+"), "LAN address lookup returns an IPv4 address or nothing (" + CastRelay.lanAddress() + ")");
    r.stop(); up.stop(0);
  }
}
