package com.markcoleman.amplify.vlc

import java.io.Serializable

/**
 * Settings for one LibVLC instance and the media it plays.
 *
 * [libVlcArgs] go to the LibVLC constructor (they apply to everything this instance plays);
 * [mediaOptions] are added to each Media (":option=value" form, per file).
 */
data class VlcPlayerConfig(
    /** false = software decoding only (avcodec). Use it for files the phone's hardware decoder mangles. */
    val hardwareAcceleration: Boolean = true,
    /** true = never fall back to software if the hardware decoder fails (rarely what you want). */
    val forceHardware: Boolean = false,
    /** ms LibVLC reads ahead for a local file. */
    val fileCachingMs: Int = 300,
    /** Skip the H.264 loop filter on slow devices: 0 none, 1 non-ref, 2 bidir, 3 non-key, 4 all. */
    val skipLoopFilter: Int = 0,
    /** Decoder threads; 0 = let avcodec decide. */
    val decoderThreads: Int = 0,
    /** Draw into a TextureView instead of a SurfaceView (needed for animations/transforms of the view). */
    val useTextureView: Boolean = false,
    val enableSubtitles: Boolean = true,
    /** LibVLC's own log in logcat (tag "VLC"). */
    val verboseLogging: Boolean = false,
    /** Anything else for the LibVLC constructor, e.g. "--audio-time-stretch". */
    val extraLibVlcArgs: List<String> = emptyList(),
    /** Anything else per media, e.g. ":avcodec-fast" or ":start-time=30". */
    val extraMediaOptions: List<String> = emptyList(),
) : Serializable {

    fun libVlcArgs(): ArrayList<String> = arrayListOf<String>().apply {
        add("--file-caching=$fileCachingMs")
        add("--avcodec-threads=$decoderThreads")
        add("--avcodec-skiploopfilter=$skipLoopFilter")
        add("--audio-time-stretch")          // keeps pitch right if playback rate changes
        if (!hardwareAcceleration) add("--avcodec-hw=none")
        add(if (verboseLogging) "-vvv" else "--quiet")
        addAll(extraLibVlcArgs)
    }

    fun mediaOptions(): List<String> = buildList {
        add(":file-caching=$fileCachingMs")
        addAll(extraMediaOptions)
    }
}
