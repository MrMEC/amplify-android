package com.markcoleman.amplify;

import androidx.annotation.OptIn;
import androidx.media3.common.C;
import androidx.media3.common.audio.AudioProcessor;
import androidx.media3.common.audio.BaseAudioProcessor;
import androidx.media3.common.util.UnstableApi;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Build 231: puts the player's audio through Leveler (volume leveling) on its way to the speaker.
 * 16-bit and float PCM; anything else passes by untouched. The gain itself is all in Leveler.
 */
@OptIn(markerClass = UnstableApi.class)
final class LevelingProcessor extends BaseAudioProcessor {
  private final Leveler leveler = new Leveler();
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
    leveler.process(work, frames, channels, fmt.sampleRate);
    // Build 320: Immersive View's glow and particles measure the music here (when asked for).
    if (AudioMeter.enabled) AudioMeter.feed(work, frames, channels, fmt.sampleRate);
    ByteBuffer out = replaceOutputBuffer(remaining);
    if (pcm16) {
      for (int i = 0; i < samples; i++) {
        float v = work[i] * 32768f;
        out.putShort((short) (v > 32767f ? 32767 : (v < -32768f ? -32768 : Math.round(v))));
      }
    } else {
      for (int i = 0; i < samples; i++) out.putFloat(work[i]);
    }
    // A partial frame at the end (never expected) is copied as it was.
    for (int i = samples * bytesPerSample; i < remaining; i++) out.put(input.get(input.position() + i));
    input.position(input.limit());
    out.flip();
  }

  @Override
  protected void onFlush() {
    leveler.reset();
    AudioMeter.reset();
  }
}
