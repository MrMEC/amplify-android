package com.markcoleman.amplify;

import androidx.annotation.OptIn;
import androidx.media3.common.C;
import androidx.media3.common.audio.BaseAudioProcessor;
import androidx.media3.common.util.UnstableApi;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Build 240: puts the player's audio through Equalizer (the preset chosen in Settings) on its
 * way to the volume leveler. 16-bit and float PCM; anything else passes by untouched. With the
 * preset Off the audio is copied through as it was.
 */
@OptIn(markerClass = UnstableApi.class)
final class EqProcessor extends BaseAudioProcessor {
  private final Equalizer eq = new Equalizer();
  private float[] work = new float[0];

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
    ByteBuffer out = replaceOutputBuffer(remaining);
    if (!Equalizer.active()) {
      out.put(input);
      out.flip();
      return;
    }
    AudioFormat fmt = inputAudioFormat;
    int channels = Math.max(1, fmt.channelCount);
    boolean pcm16 = fmt.encoding == C.ENCODING_PCM_16BIT;
    int bytesPerSample = pcm16 ? 2 : 4;
    int samples = remaining / bytesPerSample;
    int frames = samples / channels;
    samples = frames * channels;
    if (work.length < samples) work = new float[samples];
    ByteBuffer in = input.slice().order(ByteOrder.nativeOrder());
    if (pcm16) {
      for (int i = 0; i < samples; i++) work[i] = in.getShort() / 32768f;
    } else {
      for (int i = 0; i < samples; i++) work[i] = in.getFloat();
    }
    eq.process(work, frames, channels, fmt.sampleRate);
    if (pcm16) {
      for (int i = 0; i < samples; i++) {
        float v = work[i] * 32768f;
        out.putShort((short) (v > 32767f ? 32767 : (v < -32768f ? -32768 : Math.round(v))));
      }
    } else {
      for (int i = 0; i < samples; i++) out.putFloat(work[i]);
    }
    for (int i = samples * bytesPerSample; i < remaining; i++) out.put(input.get(input.position() + i));
    input.position(input.limit());
    out.flip();
  }

  @Override
  protected void onFlush() {
    eq.reset();
  }
}
