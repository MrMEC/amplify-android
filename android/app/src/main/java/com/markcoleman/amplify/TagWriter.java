package com.markcoleman.amplify;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.zip.CRC32;

/**
 * Info & Tags saving: replaces the tag at the front of a song file (an ID3v2 tag, or a FLAC
 * file's metadata blocks) with a new one built by the page. The audio after it is never changed.
 *
 * <p>The page says how many bytes the old tag takes and gives a checksum of them, so a file that
 * changed since it was read is left alone. The rest of the file is copied aside first: when the
 * new tag is the same length it is written in place, otherwise the file is rewritten as new tag
 * plus that copy, and if writing fails part way the old bytes are put back.
 */
final class TagWriter {
  private TagWriter() {}

  /** The file is not what the page read: a different size, or different bytes in the tag. */
  static final class Changed extends Exception {
    Changed() {
      super("The file changed since it was read");
    }
  }

  /** The few ways the file itself is reached (a content: URI on the phone, a File in tests). */
  interface Io {
    /** Current length in bytes, or -1 when unknown. */
    long size() throws IOException;

    InputStream read() throws IOException;

    /** Opens for writing from the start, truncating whatever was there. */
    OutputStream rewrite() throws IOException;

    /** Overwrites the first bytes without changing anything after them. */
    void writeInPlace(byte[] data) throws IOException;
  }

  static void replaceHead(Io io, byte[] head, int replace, long crc, long expectSize, File tmpDir)
      throws IOException, Changed {
    long size = io.size();
    if (expectSize >= 0 && size >= 0 && size != expectSize) throw new Changed();
    if (replace < 0 || (size >= 0 && replace > size)) throw new Changed();
    byte[] old = new byte[replace];
    File tail = File.createTempFile("tag-tail", ".bin", tmpDir);
    boolean keepTail = false;
    try {
      long tailLen;
      try (InputStream in = io.read()) {
        readFully(in, old);
        CRC32 c = new CRC32();
        c.update(old, 0, old.length);
        if (c.getValue() != (crc & 0xffffffffL)) throw new Changed();
        try (OutputStream out = new FileOutputStream(tail)) {
          tailLen = copy(in, out);
        }
      }
      if (size >= 0 && tailLen != size - replace) {
        throw new IOException("The whole file could not be read");
      }
      if (head.length == replace) {
        try {
          io.writeInPlace(head);
          return;
        } catch (SecurityException e) {
          throw e;
        } catch (Exception inPlaceFailed) {
          // Some storage can't be written in place: rewrite the whole file instead.
        }
      }
      boolean ok = false;
      try {
        writeAll(io, head, tail);
        ok = true;
      } finally {
        if (!ok) {
          try {
            writeAll(io, old, tail);
          } catch (Exception restoreFailed) {
            keepTail = true; // the audio stays in the app's cache rather than being lost
          }
        }
      }
    } finally {
      if (!keepTail) {
        //noinspection ResultOfMethodCallIgnored
        tail.delete();
      }
    }
  }

  private static void writeAll(Io io, byte[] head, File tail) throws IOException {
    try (OutputStream out = io.rewrite();
        InputStream in = new FileInputStream(tail)) {
      out.write(head);
      copy(in, out);
      out.flush();
    }
  }

  private static void readFully(InputStream in, byte[] buf) throws IOException {
    int off = 0;
    while (off < buf.length) {
      int n = in.read(buf, off, buf.length - off);
      if (n < 0) throw new IOException("The file ended early");
      off += n;
    }
  }

  private static long copy(InputStream in, OutputStream out) throws IOException {
    byte[] b = new byte[64 * 1024];
    long total = 0;
    int n;
    while ((n = in.read(b)) > 0) {
      out.write(b, 0, n);
      total += n;
    }
    return total;
  }
}
