package com.markcoleman.amplify;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * "Artist - Title" parsed from a live stream's ICY metadata, with junk (ads, station slogans, URLs,
 * codes) filtered out, so the car and lock screen can show the song that is on air.
 */
public final class StreamTitle {
  public final String artist;
  public final String raw;
  public final String title;
  private static final Pattern KV = Pattern.compile("(\\w+)\\s*=\\s*\"([^\"]*)\"");
  private static final Pattern SEP = Pattern.compile("\\s+[-–—|~]\\s+");
  private static final Pattern JUNK_WORDS =
      Pattern.compile(
          "^(unknown|unknown artist|unknown"
              + " title|untitled|n/?a|none|null|undefined|advert(isement)?s?|commercials?|commercial"
              + " break|ad ?break|station ?id|-+|\\.+|\\?+)$",
          2);
  private static final Pattern FILLER_WORDS =
      Pattern.compile(
          "^(live|on ?air|now"
              + " playing|jingle|sweeper|promo|news|weather|traffic|stream|radio|music|song|track|artist|title|live"
              + " stream|online radio|internet radio)$",
          2);
  private static final Pattern WEB =
      Pattern.compile("(https?://|www\\.|\\.(com|net|org|fm|io|co\\.uk|de|nl|fr)\\b(/|$))", 2);
  private static final Pattern AD_MARKER =
      Pattern.compile(
          "(adw_ad|adbreak|ad_break|spot_?block|\\badcontext\\b|cue_?in|\\[ad\\]|triton)", 2);
  private static final Set<String> MINOR =
      new HashSet(
          Arrays.asList(
              "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at", "by",
              "in", "of", "on", "to", "up", "via", "vs"));
  private static final Pattern WORD = Pattern.compile("[\\p{L}\\p{N}'’]+");
  private static final Pattern CODES = Pattern.compile("\\s*(§\\s*\\d+|\\[#?\\d{4,}\\])");

  private StreamTitle(String str, String str2, String str3) {
    this.artist = str;
    this.title = str2;
    this.raw = str3;
  }

  public String display() {
    return this.artist.isEmpty() ? this.title : this.title + " · " + this.artist;
  }

  public boolean sameSong(StreamTitle streamTitle) {
    return streamTitle != null
        && streamTitle.artist.equalsIgnoreCase(this.artist)
        && streamTitle.title.equalsIgnoreCase(this.title);
  }

  public static StreamTitle parse(String str, String str2) {
    if (str == null) {
      return null;
    }
    String strClean = clean(str);
    if (strClean.isEmpty()) {
      return null;
    }
    Matcher matcher = KV.matcher(strClean);
    String str3 = null;
    String str4 = null;
    boolean z = false;
    while (matcher.find()) {
      z = true;
      String lowerCase = matcher.group(1).toLowerCase(Locale.ROOT);
      String strClean2 = clean(matcher.group(2));
      if (lowerCase.equals("title") || lowerCase.equals("text") || lowerCase.equals("song")) {
        str3 = strClean2;
      } else if (lowerCase.equals("artist")) {
        str4 = strClean2;
      }
    }
    if (z) {
      if (str3 == null || str3.isEmpty()) {
        return null;
      }
      if (str4 != null && !str4.isEmpty()) {
        return accept(str4, str3, str, str2);
      }
      strClean = str3;
    }
    String str5 = "";
    String strTrim = strClean.replaceAll("^[-–—|~]\\s+|\\s+[-–—|~]$", "").trim();
    if (strTrim.isEmpty()) {
      return null;
    }
    Matcher matcher2 = SEP.matcher(strTrim);
    if (matcher2.find()) {
      String strClean3 = clean(strTrim.substring(0, matcher2.start()));
      strTrim = clean(strTrim.substring(matcher2.end()));
      if (strTrim.isEmpty()) {
        strTrim = strClean3;
      } else {
        str5 = strClean3;
      }
      if (str5.isEmpty() && strTrim.isEmpty()) {
        return null;
      }
    }
    return accept(str5, strTrim, str, str2);
  }

  private static StreamTitle accept(String str, String str2, String str3, String str4) {
    if (!str.isEmpty() && WEB.matcher(str).find()) {
      return null;
    }
    String strStripCodes = stripCodes(str);
    String strStripCodes2 = stripCodes(str2);
    String str5 = "";
    if (isJunk(strStripCodes)) {
      strStripCodes = "";
    }
    if (!(strStripCodes.isEmpty() ? isJunk(strStripCodes2) : isJunkWords(strStripCodes2))) {
      str5 = strStripCodes;
    } else {
      if (strStripCodes.isEmpty()) {
        return null;
      }
      strStripCodes2 = strStripCodes;
    }
    if (str5.isEmpty() && FILLER_WORDS.matcher(strStripCodes2).matches()) {
      return null;
    }
    if (str4 != null) {
      String strNorm = norm(str4);
      if (!strNorm.isEmpty()) {
        if (norm(str5.isEmpty() ? strStripCodes2 : str5 + " " + strStripCodes2).equals(strNorm)
            || norm(strStripCodes2).equals(strNorm)
            || (str5.isEmpty() && norm(strStripCodes2).startsWith(strNorm))) {
          return null;
        }
      }
    }
    return new StreamTitle(str5, titleCase(strStripCodes2), str3);
  }

  static String titleCase(String str) {
    int i = 0;
    int i2 = 0;
    for (int i3 = 0; i3 < str.length(); i3++) {
      char cCharAt = str.charAt(i3);
      if (Character.isUpperCase(cCharAt)) {
        i2++;
      } else if (Character.isLowerCase(cCharAt)) {
        i++;
      }
    }
    if ((i != 0 || i2 < 2) && (i2 != 0 || i <= 0)) {
      return str;
    }
    String lowerCase = str.toLowerCase(Locale.ROOT);
    Matcher matcher = WORD.matcher(lowerCase);
    ArrayList arrayList = new ArrayList();
    while (matcher.find()) {
      arrayList.add(new int[] {matcher.start(), matcher.end()});
    }
    StringBuilder sb = new StringBuilder(lowerCase);
    int i4 = 0;
    while (i4 < arrayList.size()) {
      int i5 = ((int[]) arrayList.get(i4))[0];
      boolean z = true;
      String strSubstring = lowerCase.substring(i5, ((int[]) arrayList.get(i4))[1]);
      if (Character.isLetter(lowerCase.charAt(i5))) {
        String strSubstring2 =
            lowerCase.substring(i4 == 0 ? 0 : ((int[]) arrayList.get(i4 - 1))[1], i5);
        if (i4 != 0
            && i4 != arrayList.size() - 1
            && !strSubstring2.contains("(")
            && !strSubstring2.contains("[")
            && !strSubstring2.contains(":")
            && !strSubstring2.contains(" - ")
            && !strSubstring2.contains("/")) {
          z = false;
        }
        String strReplace = strSubstring.replace((char) 8217, '\'');
        if (strReplace.equals("i") || strReplace.startsWith("i'")) {
          sb.setCharAt(i5, 'I');
        } else if (!MINOR.contains(strReplace) || z) {
          sb.setCharAt(i5, Character.toUpperCase(lowerCase.charAt(i5)));
        }
      }
      i4++;
    }
    return sb.toString();
  }

  private static boolean isJunkWords(String str) {
    if (str.isEmpty() || JUNK_WORDS.matcher(str).matches() || WEB.matcher(str).find()) {
      return true;
    }
    return AD_MARKER.matcher(str).find();
  }

  private static boolean isJunk(String str) {
    if (isJunkWords(str) || str.length() < 2) {
      return true;
    }
    boolean z = false;
    int i = 0;
    while (true) {
      if (i >= str.length()) {
        break;
      }
      if (Character.isLetter(str.charAt(i))) {
        z = true;
        break;
      }
      i++;
    }
    return !z;
  }

  private static String stripCodes(String str) {
    return CODES.matcher(str).replaceAll("").trim();
  }

  private static String clean(String str) {
    String strTrim = str.replace((char) 0, ' ').replaceAll("\\s+", " ").trim();
    while (strTrim.length() >= 2
        && ((strTrim.startsWith("'") && strTrim.endsWith("'"))
            || (strTrim.startsWith("\"") && strTrim.endsWith("\"")))) {
      strTrim = strTrim.substring(1, strTrim.length() - 1).trim();
    }
    return strTrim;
  }

  private static String norm(String str) {
    return str.toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+", "");
  }
}
