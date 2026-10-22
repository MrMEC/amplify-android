package android.util;
import org.xmlpull.v1.XmlPullParser;
/** Android's own parser is kxml2, same as here. */
public final class Xml { public static XmlPullParser newPullParser() { return new org.kxml2.io.KXmlParser(); } }
