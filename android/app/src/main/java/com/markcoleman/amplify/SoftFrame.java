package com.markcoleman.amplify;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.graphics.YuvImage;
import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.net.Uri;
import android.os.Build;
import androidx.annotation.Nullable;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;

/**
 * Build 384: one frame of a video, decoded here with the phone's software decoder.
 *
 * <p>MediaMetadataRetriever borrows one of the phone's hardware video decoders; on Mark's phone
 * (with a music video playing) those requests stalled, and a stalled one kept its decoder, until
 * nothing could be read at all. A software decoder isn't one of those few shared decoders; this
 * opens it, decodes from the key frame before the point up to the point, and lets everything go,
 * every time, with a deadline on the whole thing.
 */
final class SoftFrame {
  private SoftFrame() {}

  static final class Unsupported extends Exception {
    Unsupported(String m) {
      super(m);
    }
  }

  /** A software decoder for this kind of video, or null. */
  @Nullable
  static String softDecoder(String mime) {
    MediaCodecInfo[] all = new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos();
    String fallback = null;
    for (MediaCodecInfo info : all) {
      if (info.isEncoder()) continue;
      boolean handles = false;
      for (String t : info.getSupportedTypes()) if (t.equalsIgnoreCase(mime)) handles = true;
      if (!handles) continue;
      String n = info.getName();
      boolean soft;
      if (Build.VERSION.SDK_INT >= 29) soft = info.isSoftwareOnly();
      else soft = n.startsWith("OMX.google.") || n.startsWith("c2.android.");
      if (soft) {
        if (n.startsWith("c2.android.") || n.startsWith("OMX.google.")) return n;
        if (fallback == null) fallback = n;
      }
    }
    return fallback;
  }

  /**
   * A JPEG of the frame at (or just after) `ms`, at most `maxW` wide. Not `exact`: the key frame
   * at or before the point, which is quick. `exact`: decoded on to the point itself.
   */
  static byte[] jpeg(Context ctx, Uri uri, long ms, boolean exact, int maxW, long deadlineMs) throws Exception {
    long until = System.currentTimeMillis() + deadlineMs;
    MediaExtractor ex = new MediaExtractor();
    MediaCodec codec = null;
    try {
      try {
        ex.setDataSource(ctx, uri, null);
      } catch (Exception e) {
        throw new Unsupported("This kind of file can't be opened here");
      }
      int track = -1;
      MediaFormat fmt = null;
      for (int i = 0; i < ex.getTrackCount(); i++) {
        MediaFormat f = ex.getTrackFormat(i);
        String m = f.getString(MediaFormat.KEY_MIME);
        if (m != null && m.startsWith("video/")) {
          track = i;
          fmt = f;
          break;
        }
      }
      if (track < 0) throw new Unsupported("No video in this file");
      String mime = fmt.getString(MediaFormat.KEY_MIME);
      String name = softDecoder(mime);
      if (name == null) throw new Unsupported("No software decoder for " + mime);
      ex.selectTrack(track);
      long target = Math.max(0, ms) * 1000L;
      ex.seekTo(target, MediaExtractor.SEEK_TO_PREVIOUS_SYNC);
      fmt.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
      codec = MediaCodec.createByCodecName(name);
      codec.configure(fmt, null, null, 0);
      codec.start();
      MediaCodec.BufferInfo bi = new MediaCodec.BufferInfo();
      boolean inputDone = false;
      int frames = 0;
      while (true) {
        if (System.currentTimeMillis() > until) throw new Exception("Reading the frame took too long");
        if (!inputDone) {
          int in = codec.dequeueInputBuffer(10_000);
          if (in >= 0) {
            ByteBuffer buf = codec.getInputBuffer(in);
            int n = buf == null ? -1 : ex.readSampleData(buf, 0);
            if (n < 0) {
              codec.queueInputBuffer(in, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
              inputDone = true;
            } else {
              codec.queueInputBuffer(in, 0, n, ex.getSampleTime(), 0);
              ex.advance();
            }
          }
        }
        int out = codec.dequeueOutputBuffer(bi, 10_000);
        if (out >= 0) {
          boolean eos = (bi.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
          frames++;
          boolean take = bi.size > 0 && (!exact || bi.presentationTimeUs >= target - 20_000 || eos);
          // Never more than ~10 seconds of video decoded for one frame.
          if (bi.size > 0 && frames > 300) take = true;
          // Running out of time on the way to an exact frame: the nearest one reached will do.
          if (bi.size > 0 && System.currentTimeMillis() > until - 2500) take = true;
          if (take) {
            Image img = codec.getOutputImage(out);
            if (img == null) throw new Exception("The decoder gave no picture");
            try {
              return scaled(toJpeg(img), maxW);
            } finally {
              img.close();
              codec.releaseOutputBuffer(out, false);
            }
          }
          codec.releaseOutputBuffer(out, false);
          if (eos) throw new Exception("No picture at that point");
        }
      }
    } finally {
      if (codec != null) {
        try {
          codec.stop();
        } catch (Throwable ignored) {
        }
        try {
          codec.release();
        } catch (Throwable ignored) {
        }
      }
      try {
        ex.release();
      } catch (Throwable ignored) {
      }
    }
  }

  /** YUV_420_888 (any strides) to NV21, then to JPEG. */
  private static byte[] toJpeg(Image img) {
    Rect crop = img.getCropRect();
    int w = crop.width(), h = crop.height();
    w &= ~1;
    h &= ~1;
    byte[] nv21 = new byte[w * h * 3 / 2];
    Image.Plane[] p = img.getPlanes();
    ByteBuffer yb = p[0].getBuffer(), ub = p[1].getBuffer(), vb = p[2].getBuffer();
    int yRow = p[0].getRowStride(), yPix = p[0].getPixelStride();
    int uRow = p[1].getRowStride(), uPix = p[1].getPixelStride();
    int vRow = p[2].getRowStride(), vPix = p[2].getPixelStride();
    int pos = 0;
    for (int y = 0; y < h; y++) {
      int row = (crop.top + y) * yRow + crop.left * yPix;
      for (int x = 0; x < w; x++) nv21[pos++] = yb.get(row + x * yPix);
    }
    for (int y = 0; y < h / 2; y++) {
      int uR = (crop.top / 2 + y) * uRow + (crop.left / 2) * uPix;
      int vR = (crop.top / 2 + y) * vRow + (crop.left / 2) * vPix;
      for (int x = 0; x < w / 2; x++) {
        nv21[pos++] = vb.get(vR + x * vPix);
        nv21[pos++] = ub.get(uR + x * uPix);
      }
    }
    ByteArrayOutputStream bos = new ByteArrayOutputStream();
    new YuvImage(nv21, ImageFormat.NV21, w, h, null).compressToJpeg(new Rect(0, 0, w, h), 90, bos);
    return bos.toByteArray();
  }

  private static byte[] scaled(byte[] jpeg, int maxW) {
    BitmapFactory.Options o = new BitmapFactory.Options();
    o.inJustDecodeBounds = true;
    BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length, o);
    if (o.outWidth <= maxW) return jpeg;
    Bitmap b = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length);
    if (b == null) return jpeg;
    int th = Math.max(1, Math.round((float) maxW * b.getHeight() / b.getWidth()));
    Bitmap s = Bitmap.createScaledBitmap(b, maxW, th, true);
    if (s != b) b.recycle();
    ByteArrayOutputStream bos = new ByteArrayOutputStream();
    s.compress(Bitmap.CompressFormat.JPEG, 85, bos);
    s.recycle();
    return bos.toByteArray();
  }
}
