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
    // ---- Build 238: files on the phone ----
    java.io.File song = java.io.File.createTempFile("amplify-song", ".mp3");
    byte[] data = new byte[300000];
    for (int i = 0; i < data.length; i++) data[i] = (byte) (i * 7 + (i >> 8));
    java.nio.file.Files.write(song.toPath(), data);
    ok(CastRelay.isLocal(song.toURI().toString()) && CastRelay.isLocal("content://com.android.externalstorage.documents/tree/x/document/y")
        && !CastRelay.isLocal("https://example.com/a.mp3"), "local addresses are recognised");
    String fu = r.wrapFile(song.toURI().toString(), "mp3");
    ok(fu.startsWith(base + "/f/") && fu.endsWith(".mp3"), "a song gets a relay address " + fu);
    HttpURLConnection fc = (HttpURLConnection) new URL(fu).openConnection();
    fc.setRequestProperty("Origin", "https://www.gstatic.com");
    byte[] whole = fc.getInputStream().readAllBytes();
    ok(fc.getResponseCode() == 200 && java.util.Arrays.equals(whole, data), "the whole file is served (" + whole.length + " bytes)");
    ok("audio/mpeg".equals(fc.getContentType()) && "*".equals(fc.getHeaderField("Access-Control-Allow-Origin")) && "bytes".equals(fc.getHeaderField("Accept-Ranges"))
        && String.valueOf(data.length).equals(fc.getHeaderField("Content-Length")), "as audio/mpeg with CORS, ranges and its length (" + fc.getContentType() + ")");
    HttpURLConnection rc = (HttpURLConnection) new URL(fu).openConnection();
    rc.setRequestProperty("Range", "bytes=1000-1999");
    byte[] part = rc.getInputStream().readAllBytes();
    ok(rc.getResponseCode() == 206 && part.length == 1000 && java.util.Arrays.equals(part, java.util.Arrays.copyOfRange(data, 1000, 2000))
        && ("bytes 1000-1999/" + data.length).equals(rc.getHeaderField("Content-Range")), "a byte range is served (seeking) " + rc.getHeaderField("Content-Range"));
    HttpURLConnection oc = (HttpURLConnection) new URL(fu).openConnection();
    oc.setRequestProperty("Range", "bytes=299000-");
    byte[] tail = oc.getInputStream().readAllBytes();
    ok(oc.getResponseCode() == 206 && tail.length == 1000 && tail[999] == data[data.length - 1], "an open-ended range to the end (" + tail.length + ")");
    HttpURLConnection sc = (HttpURLConnection) new URL(fu).openConnection();
    sc.setRequestProperty("Range", "bytes=-500");
    byte[] last = sc.getInputStream().readAllBytes();
    ok(sc.getResponseCode() == 206 && last.length == 500, "the last N bytes (" + last.length + ")");
    HttpURLConnection bc = (HttpURLConnection) new URL(fu).openConnection();
    bc.setRequestProperty("Range", "bytes=999999-");
    ok(bc.getResponseCode() == 416, "a range past the end is refused (" + bc.getResponseCode() + ")");
    HttpURLConnection hc = (HttpURLConnection) new URL(fu).openConnection();
    hc.setRequestMethod("HEAD");
    ok(hc.getResponseCode() == 200 && String.valueOf(data.length).equals(hc.getHeaderField("Content-Length")), "HEAD gives the length without the body");
    String vu = r.wrapFile(song.toURI().toString(), "mkv");
    HttpURLConnection vc = (HttpURLConnection) new URL(vu).openConnection();
    vc.getInputStream().readAllBytes();
    ok("video/x-matroska".equals(vc.getContentType()), "a video's kind comes from its extension (" + vc.getContentType() + ")");
    ok(CastRelay.isVideoExt("mp4") && CastRelay.isVideoExt("mkv") && !CastRelay.isVideoExt("flac"), "videos and songs told apart by extension");
    // a content:// file through the app's reader
    CastRelay.FileSource prev = CastRelay.fileSource;
    CastRelay.fileSource = new CastRelay.FileSource() {
      @Override public long size(String uri) { return uri.startsWith("content://") ? data.length : -1; }
      @Override public InputStream open(String uri, long off) { return new java.io.ByteArrayInputStream(data, (int) off, data.length - (int) off); }
    };
    HttpURLConnection cc2 = (HttpURLConnection) new URL(r.wrapFile("content://docs/tree/a/document/b", "flac")).openConnection();
    cc2.setRequestProperty("Range", "bytes=10-19");
    byte[] cpart = cc2.getInputStream().readAllBytes();
    ok(cc2.getResponseCode() == 206 && java.util.Arrays.equals(cpart, java.util.Arrays.copyOfRange(data, 10, 20)) && "audio/flac".equals(cc2.getContentType()), "a content:// file is served through the app's reader");
    CastRelay.fileSource = prev;
    // the cover picture
    byte[] jpg = new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff, 1, 2, 3};
    String bu = r.wrapBytes(jpg, "jpg");
    HttpURLConnection jc = (HttpURLConnection) new URL(bu).openConnection();
    ok(java.util.Arrays.equals(jc.getInputStream().readAllBytes(), jpg) && "image/jpeg".equals(jc.getContentType()), "a cover picture is served " + bu);
    ok(get(base + "/f/nope.mp3", "GET")[0].equals("404"), "an unknown file 404");
    // two Chromecast reads at once (it often opens a second connection to seek)
    Thread[] fts = new Thread[4]; final int[] fgood = {0};
    for (int i = 0; i < fts.length; i++) { final int k = i; fts[i] = new Thread(() -> { try {
      HttpURLConnection x = (HttpURLConnection) new URL(fu).openConnection(); x.setRequestProperty("Range", "bytes=" + (k * 1000) + "-" + (k * 1000 + 99999));
      if (x.getInputStream().readAllBytes().length == 100000) synchronized (fgood) { fgood[0]++; } } catch (Exception e) {} }); fts[i].start(); }
    for (Thread t : fts) t.join();
    ok(fgood[0] == 4, "4 ranged reads at once (" + fgood[0] + ")");
    // a reader that hangs up mid-file doesn't break the relay
    java.net.Socket hang = new java.net.Socket("127.0.0.1", Integer.parseInt(base.substring(base.lastIndexOf(':') + 1)));
    hang.getOutputStream().write(("GET " + fu.substring(base.length()) + " HTTP/1.1\r\nHost: x\r\n\r\n").getBytes(StandardCharsets.ISO_8859_1));
    hang.getInputStream().read(new byte[100]);
    hang.close();
    HttpURLConnection after = (HttpURLConnection) new URL(fu).openConnection();
    ok(after.getInputStream().readAllBytes().length == data.length, "still serving after a reader hung up");
    // what a file is from its first bytes
    byte[] id3 = new byte[64]; id3[0]='I'; id3[1]='D'; id3[2]='3'; id3[9]=10; id3[20]=(byte)0xff; id3[21]=(byte)0xfb;
    ok(CastRelay.sniffExt(id3, 64, false).equals("mp3"), "ID3 + MP3 is mp3");
    byte[] id3f = new byte[64]; id3f[0]='I'; id3f[1]='D'; id3f[2]='3'; id3f[9]=4; id3f[14]='f'; id3f[15]='L'; id3f[16]='a'; id3f[17]='C';
    ok(CastRelay.sniffExt(id3f, 64, false).equals("flac"), "ID3 + FLAC is flac");
    byte[] m4a = new byte[32]; m4a[4]='f'; m4a[5]='t'; m4a[6]='y'; m4a[7]='p'; m4a[8]='M'; m4a[9]='4'; m4a[10]='A'; m4a[11]=' ';
    ok(CastRelay.sniffExt(m4a, 32, false).equals("m4a") && CastRelay.sniffExt(m4a, 32, true).equals("m4a"), "an M4A brand is m4a");
    byte[] mp4 = new byte[32]; mp4[4]='f'; mp4[5]='t'; mp4[6]='y'; mp4[7]='p'; mp4[8]='i'; mp4[9]='s'; mp4[10]='o'; mp4[11]='m';
    ok(CastRelay.sniffExt(mp4, 32, true).equals("mp4") && CastRelay.sniffExt(mp4, 32, false).equals("m4a"), "isom is mp4 for a video, m4a for a song");
    byte[] mkv = new byte[40]; mkv[0]=0x1a; mkv[1]=0x45; mkv[2]=(byte)0xdf; mkv[3]=(byte)0xa3; System.arraycopy("matroska".getBytes(), 0, mkv, 20, 8);
    ok(CastRelay.sniffExt(mkv, 40, true).equals("mkv"), "Matroska is mkv");
    byte[] ogg = "OggS....".getBytes(); byte[] wav = "RIFF....WAVEfmt ".getBytes(); byte[] fl = "fLaC....".getBytes();
    ok(CastRelay.sniffExt(ogg, ogg.length, false).equals("ogg") && CastRelay.sniffExt(wav, wav.length, false).equals("wav") && CastRelay.sniffExt(fl, fl.length, false).equals("flac"), "Ogg, WAV, FLAC");
    ok(CastRelay.extOfName("content://x/document/primary%3AMusic%2FSong.FLAC").equals("flac") && CastRelay.extOfName("file:///cache/abc.bin").equals("bin")
        && CastRelay.extOfName("content://x/document/1234").equals(""), "extensions from names and addresses");
    java.io.File cached = java.io.File.createTempFile("abc", ".bin");
    java.nio.file.Files.write(cached.toPath(), id3f);
    ok(CastRelay.extFor(cached.toURI().toString(), null, false).equals("flac"), "a cached .bin song is sniffed (flac)");
    ok(CastRelay.extFor(song.toURI().toString(), "Track.mp3", false).equals("mp3"), "a known extension is used as is");
    cached.delete();
    song.delete();
    ok(CastRelay.lanAddress() == null || CastRelay.lanAddress().matches("\\d+\\.\\d+\\.\\d+\\.\\d+"), "LAN address lookup returns an IPv4 address or nothing (" + CastRelay.lanAddress() + ")");
    r.stop(); up.stop(0);
  }
}
