package com.markcoleman.amplify;

import androidx.annotation.OptIn;
import androidx.media3.common.C;
import androidx.media3.common.audio.BaseAudioProcessor;
import androidx.media3.common.util.UnstableApi;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Build 600: passes the audio through unchanged and, while the visualizer is showing (Viz.enabled),
 * measures it: a 1024-point FFT every 512 frames of the mono mix, grouped into Viz.BANDS bands
 * spaced evenly on a log scale from 40 Hz up, each scaled to 0..1 over a 66 dB range.
 */
@OptIn(markerClass = UnstableApi.class)
final class VizProcessor extends BaseAudioProcessor {
  private static final int N = 1024, HOP = 512;
  private final float[] win = new float[N];
  private final float[] hist = new float[N];
  private final float[] re = new float[N], im = new float[N];
  private final float[] cosT = new float[N / 2], sinT = new float[N / 2];
  private final int[] rev = new int[N];
  private final float[] bands = new float[Viz.BANDS];
  private int[] edges = new int[Viz.BANDS + 1];
  private int edgesRate = -1;
  private int filled, sinceHop, pos;
  private long frames;

  VizProcessor() {
    for (int i = 0; i < N; i++) win[i] = (float) (0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1)));
    for (int i = 0; i < N / 2; i++) {
      cosT[i] = (float) Math.cos(-2 * Math.PI * i / N);
      sinT[i] = (float) Math.sin(-2 * Math.PI * i / N);
    }
    int bits = Integer.numberOfTrailingZeros(N);
    for (int i = 0; i < N; i++) rev[i] = Integer.reverse(i) >>> (32 - bits);
  }

  @Override
  protected AudioFormat onConfigure(AudioFormat in) throws UnhandledAudioFormatException {
    if (in.encoding != C.ENCODING_PCM_16BIT && in.encoding != C.ENCODING_PCM_FLOAT) {
      return AudioFormat.NOT_SET;
    }
    return in;
  }

  @Override
  public void queueInput(ByteBuffer input) {
    int remaining = input.remaining();
    if (remaining == 0) return;
    AudioFormat fmt = inputAudioFormat;
    int channels = Math.max(1, fmt.channelCount);
    boolean pcm16 = fmt.encoding == C.ENCODING_PCM_16BIT;
    int bytesPerSample = pcm16 ? 2 : 4;
    int count = (remaining / bytesPerSample) / channels;
    if (Viz.enabled) {
      ByteBuffer in = input.duplicate().order(ByteOrder.nativeOrder());
      for (int f = 0; f < count; f++) {
        float s = 0;
        for (int c = 0; c < channels; c++) s += pcm16 ? in.getShort() / 32768f : in.getFloat();
        // a ring of the last N frames (pos is where the next one goes, i.e. the oldest)
        hist[pos] = s / channels;
        pos = (pos + 1) & (N - 1);
        if (filled < N) filled++;
        frames++;
        if (filled == N && ++sinceHop >= HOP) {
          sinceHop = 0;
          analyse(fmt.sampleRate);
          Viz.push(frames, fmt.sampleRate, bands);
        }
      }
    } else {
      frames += count;
      filled = 0; sinceHop = 0; pos = 0;
    }
    ByteBuffer out = replaceOutputBuffer(remaining);
    out.put(input);
    out.flip();
  }

  private void analyse(int rate) {
    for (int i = 0; i < N; i++) { re[rev[i]] = hist[(pos + i) & (N - 1)] * win[i]; im[rev[i]] = 0; }
    for (int size = 2; size <= N; size <<= 1) {
      int half = size >> 1, step = N / size;
      for (int i = 0; i < N; i += size) {
        for (int j = 0; j < half; j++) {
          float wr = cosT[j * step], wi = sinT[j * step];
          int a = i + j, b = a + half;
          float tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr;
          re[b] = re[a] - tr; im[b] = im[a] - ti;
          re[a] += tr; im[a] += ti;
        }
      }
    }
    if (rate != edgesRate) {
      edgesRate = rate;
      double lo = 40, hi = Math.min(16000, rate / 2.0 - 1);
      for (int b = 0; b <= Viz.BANDS; b++) {
        double f = lo * Math.pow(hi / lo, b / (double) Viz.BANDS);
        edges[b] = Math.max(1, Math.min(N / 2 - 1, (int) Math.round(f * N / rate)));
      }
    }
    for (int b = 0; b < Viz.BANDS; b++) {
      int from = edges[b], to = Math.max(from + 1, edges[b + 1]);
      float peak = 0;
      for (int k = from; k < to && k < N / 2; k++) {
        float m = re[k] * re[k] + im[k] * im[k];
        if (m > peak) peak = m;
      }
      // magnitude relative to a full-scale sine (N/4 with the Hann window), in dB
      double db = 10 * Math.log10(peak / ((N / 4.0) * (N / 4.0)) + 1e-12);
      float v = (float) ((db + 66) / 66);
      bands[b] = v < 0 ? 0 : (v > 1 ? 1 : v);
    }
  }

  @Override
  protected void onFlush() {
    frames = 0; filled = 0; sinceHop = 0;
    Viz.onFlush();
  }

  @Override
  protected void onReset() {
    frames = 0; filled = 0; sinceHop = 0;
  }
}
