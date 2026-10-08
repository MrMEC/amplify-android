import com.markcoleman.amplify.StreamTitle;
import java.nio.charset.StandardCharsets;
public class IcyTitleTest {
  static int fails = 0;
  static void eq(String name, String got, String want){ boolean ok = want == null ? got == null : want.equals(got); System.out.println((ok?"PASS ":"FAIL ")+name+" -> "+got); if(!ok) fails++; }
  static byte[] b(String s){ byte[] x = s.getBytes(StandardCharsets.UTF_8); byte[] y = new byte[((x.length/16)+1)*16]; System.arraycopy(x,0,y,0,x.length); return y; }
  public static void main(String[] a) throws Exception {
    eq("plain apostrophe", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Like You Don't Love Me';")), "Janet Jackson - Like You Don't Love Me");
    eq("with url", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Let's Wait Awhile';StreamUrl='';")), "Janet Jackson - Let's Wait Awhile");
    eq("semicolon after apostrophe", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Like You Don';t Love Me';StreamUrl='http://x';")), "Janet Jackson - Like You Don't Love Me");
    eq("backslash escape", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Let\\'s Wait Awhile';")), "Janet Jackson - Let's Wait Awhile");
    eq("no final semicolon", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Let's Wait Awhile'")), "Janet Jackson - Let's Wait Awhile");
    eq("no quote at all at end", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Let's Wait Awhile")), "Janet Jackson - Let's Wait Awhile");
    byte[] w = "StreamTitle='Janet Jackson - Don’t Stand';".getBytes("windows-1252");
    eq("windows-1252 curly apostrophe", StreamTitle.icyTitle(w), "Janet Jackson - Don’t Stand");
    eq("utf8 curly", StreamTitle.icyTitle(b("StreamTitle='A - Don’t Stand';")), "A - Don’t Stand");
    eq("iheart style", StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - text=\"Like You Don't Love Me\" song_spot=\"M\" length=\"00:04:20\"';StreamUrl='';")), "Janet Jackson - text=\"Like You Don't Love Me\" song_spot=\"M\" length=\"00:04:20\"");
    eq("empty title", StreamTitle.icyTitle(b("StreamTitle='';StreamUrl='';")), "");
    eq("no title key", StreamTitle.icyTitle(b("StreamUrl='x';")), null);
    eq("lowercase key", StreamTitle.icyTitle(b("streamtitle='A - B';")), "A - B");
    StreamTitle t = StreamTitle.parse(StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Like You Don't Love Me';")), "Exclusively Janet Jackson");
    eq("parsed title", t.title, "Like You Don't Love Me"); eq("parsed artist", t.artist, "Janet Jackson");
    StreamTitle t2 = StreamTitle.parse(StreamTitle.icyTitle(b("StreamTitle='JANET JACKSON - LET'S WAIT AWHILE';")), null);
    eq("title case keeps apostrophe", t2.title, "Let's Wait Awhile");
    StreamTitle t3 = StreamTitle.parse(StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Like You Don&#39;t Love Me';")), null);
    eq("html entity apostrophe", t3.title, "Like You Don't Love Me");
    StreamTitle t4 = StreamTitle.parse(StreamTitle.icyTitle(b("StreamTitle='Janet Jackson - Let&apos;s Wait Awhile';")), null);
    eq("named entity", t4.title, "Let's Wait Awhile");
    StreamTitle t5 = StreamTitle.parse(StreamTitle.icyTitle(b("StreamTitle='Simon &amp; Garfunkel - Cecilia';")), null);
    eq("amp entity artist", t5.artist, "Simon & Garfunkel");
    byte[] moj = "StreamTitle='Janet Jackson - Don\u00e2\u20ac\u2122t Stand';".getBytes(StandardCharsets.UTF_8);
    StreamTitle t6 = StreamTitle.parse(StreamTitle.icyTitle(moj), null);
    eq("mojibake curly apostrophe", t6.title, "Don\u2019t Stand");
    eq("plain accents untouched", StreamTitle.fixText("Beyonc\u00e9 - Halo"), "Beyonc\u00e9 - Halo");
    System.out.println(fails == 0 ? "ALL PASSED" : "FAILED " + fails);
  }
}
