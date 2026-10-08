package com.markcoleman.amplify.vlc

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.util.Log
import android.view.View
import android.widget.SeekBar
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.markcoleman.amplify.R
import com.markcoleman.amplify.databinding.ActivityVlcPlayerBinding
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import java.io.File
import java.util.Locale

/**
 * The VLC player screen (build 153): plays one local video (content:// or a file path) with
 * LibVLC, for files the phone's own decoders can't handle (AVI/Xvid, WMV, MPEG-2, DTS audio...).
 *
 * Started by AmplifyPlayerPlugin.playWithVlc. When it closes it hands back where it got to
 * (RESULT_POSITION / RESULT_DURATION), whether the video ended (RESULT_ENDED) and any error
 * (RESULT_ERROR), so the page keeps the video's progress and can go on to the next one.
 *
 * Lifecycle:
 *  - onCreate:  LibVLC + MediaPlayer are created once and the media is loaded.
 *  - onResume:  the video views are attached and playback resumes where it was.
 *  - onPause:   the position is remembered, playback pauses and the views are detached
 *               (the Surface goes away while the screen is hidden).
 *  - onDestroy: player, file descriptor and LibVLC are released, in that order.
 */
class VlcPlayerActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "VlcPlayer"
        const val EXTRA_URI = "vlc.uri"
        const val EXTRA_TITLE = "vlc.title"
        const val EXTRA_START_MS = "vlc.startMs"
        const val EXTRA_HW = "vlc.hw"
        const val RESULT_POSITION = "vlc.position"
        const val RESULT_DURATION = "vlc.duration"
        const val RESULT_ENDED = "vlc.ended"
        const val RESULT_ERROR = "vlc.error"
        private const val STATE_POSITION = "vlc.statePosition"
        private const val STATE_PLAYING = "vlc.statePlaying"
        private const val HIDE_CONTROLS_MS = 3500L
        private const val SKIP_MS = 10_000L

        /** The Intent that opens [source] (content://, file://, or Uri.fromFile(path)). */
        @JvmStatic
        fun intent(context: Context, source: Uri, title: String?, startMs: Long, hardware: Boolean): Intent =
            Intent(context, VlcPlayerActivity::class.java)
                .putExtra(EXTRA_URI, source)
                .putExtra(EXTRA_TITLE, title ?: "")
                .putExtra(EXTRA_START_MS, startMs)
                .putExtra(EXTRA_HW, hardware)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

        fun start(context: Context, path: String, config: VlcPlayerConfig = VlcPlayerConfig()) =
            context.startActivity(intent(context, Uri.fromFile(File(path)), File(path).name, 0L, config.hardwareAcceleration))
    }

    private lateinit var binding: ActivityVlcPlayerBinding
    private lateinit var config: VlcPlayerConfig
    private val main = Handler(Looper.getMainLooper())
    private val hideControls = Runnable { showControls(false) }

    private var libVlc: LibVLC? = null
    private var player: MediaPlayer? = null
    /** Kept open for as long as LibVLC reads a content:// file through it. */
    private var fileDescriptor: ParcelFileDescriptor? = null

    private var resumePositionMs = 0L
    private var resumePlaying = true
    private var viewsAttached = false
    private var lengthMs = 0L
    private var ended = false
    private var error: String? = null
    private var dragging = false
    private var retriedInSoftware = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityVlcPlayerBinding.inflate(layoutInflater)
        setContentView(binding.root)

        config = VlcPlayerConfig(hardwareAcceleration = intent.getBooleanExtra(EXTRA_HW, true))
        resumePositionMs = intent.getLongExtra(EXTRA_START_MS, 0L)
        savedInstanceState?.let {
            resumePositionMs = it.getLong(STATE_POSITION, resumePositionMs)
            resumePlaying = it.getBoolean(STATE_PLAYING, true)
        }
        binding.title.text = intent.getStringExtra(EXTRA_TITLE) ?: ""
        setUpControls()

        val source = intentUri()
        if (source == null) {
            fail("Nothing to play")
            return
        }
        try {
            startPlayer(source)
        } catch (e: Exception) {
            Log.e(TAG, "Could not start LibVLC", e)
            fail("VLC can't open this file: ${e.message}")
        }
    }

    // ---- the player ----

    private fun startPlayer(source: Uri) {
        val vlc = LibVLC(this, config.libVlcArgs())
        libVlc = vlc
        player = MediaPlayer(vlc).apply {
            setEventListener { onPlayerEvent(it) }
            videoScale = MediaPlayer.ScaleType.SURFACE_BEST_FIT
        }
        loadMedia(vlc, source)
        binding.engine.text = if (config.hardwareAcceleration) "VLC" else "VLC · software"
    }

    private fun loadMedia(vlc: LibVLC, source: Uri) {
        val media = when (source.scheme) {
            "content" -> {
                // LibVLC can't open content:// itself; it is handed the open file instead.
                val pfd = contentResolver.openFileDescriptor(source, "r")
                    ?: throw IllegalStateException("Can't open $source")
                fileDescriptor = pfd
                Media(vlc, pfd.fileDescriptor)
            }
            "file", null -> Media(vlc, source.path ?: throw IllegalArgumentException("No path in $source"))
            else -> Media(vlc, source)
        }
        try {
            media.setHWDecoderEnabled(config.hardwareAcceleration, config.forceHardware)
            config.mediaOptions().forEach { media.addOption(it) }
            if (resumePositionMs > 0) media.addOption(":start-time=${resumePositionMs / 1000.0}")
            player?.media = media
        } finally {
            media.release()  // the player keeps its own reference
        }
    }

    private fun releasePlayer() {
        player?.let { p ->
            p.setEventListener(null)
            p.stop()
            if (viewsAttached) p.detachViews()
            p.release()
        }
        player = null
        viewsAttached = false
        try {
            fileDescriptor?.close()
        } catch (_: Exception) {
        }
        fileDescriptor = null
        libVlc?.release()
        libVlc = null
    }

    // ---- lifecycle ----

    override fun onResume() {
        super.onResume()
        hideSystemUi()
        val p = player ?: return
        if (!viewsAttached) {
            p.attachViews(binding.videoLayout, null, config.enableSubtitles, config.useTextureView)
            viewsAttached = true
        }
        if (resumePlaying && !p.isPlaying && !ended) {
            p.play()
            if (resumePositionMs > 0 && p.length > 0) p.setTime(resumePositionMs)
        }
        showControls(true)
    }

    override fun onPause() {
        // In split screen the screen stays visible while paused: keep playing there.
        val inMultiWindow = Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && isInMultiWindowMode
        player?.let { p ->
            if (p.time > 0) resumePositionMs = p.time
            if (!inMultiWindow) {
                resumePlaying = p.isPlaying
                p.pause()
                if (viewsAttached) {
                    p.detachViews()
                    viewsAttached = false
                }
            }
        }
        main.removeCallbacks(hideControls)
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putLong(STATE_POSITION, player?.time?.takeIf { it > 0 } ?: resumePositionMs)
        outState.putBoolean(STATE_PLAYING, resumePlaying)
    }

    override fun finish() {
        // What the page needs to carry on: where it got to and whether it ended.
        val pos = if (ended) lengthMs else (player?.time?.takeIf { it > 0 } ?: resumePositionMs)
        setResult(
            Activity.RESULT_OK,
            Intent()
                .putExtra(RESULT_POSITION, pos)
                .putExtra(RESULT_DURATION, if (lengthMs > 0) lengthMs else (player?.length ?: 0L))
                .putExtra(RESULT_ENDED, ended)
                .putExtra(RESULT_ERROR, error)
        )
        super.finish()
    }

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null)
        releasePlayer()
        super.onDestroy()
    }

    // ---- events ----

    private fun onPlayerEvent(event: MediaPlayer.Event) {
        when (event.type) {
            MediaPlayer.Event.Buffering ->
                binding.buffering.visibility = if (event.buffering < 100f) View.VISIBLE else View.GONE
            MediaPlayer.Event.Playing -> {
                binding.buffering.visibility = View.GONE
                binding.playPause.setImageResource(R.drawable.ic_vlc_pause)
                scheduleHide()
            }
            MediaPlayer.Event.Paused -> {
                binding.playPause.setImageResource(R.drawable.ic_vlc_play)
                showControls(true)
            }
            MediaPlayer.Event.LengthChanged -> {
                lengthMs = event.lengthChanged
                binding.seek.max = lengthMs.coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
                binding.duration.text = clock(lengthMs)
            }
            MediaPlayer.Event.TimeChanged -> {
                val t = event.timeChanged
                if (t > 0) resumePositionMs = t
                if (!dragging) {
                    binding.seek.progress = t.coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
                    binding.position.text = clock(t)
                }
            }
            MediaPlayer.Event.EndReached -> {
                ended = true
                finish()
            }
            MediaPlayer.Event.EncounteredError -> {
                Log.w(TAG, "Playback error (hardware decoding ${config.hardwareAcceleration})")
                // Posted: the player can't be released from inside its own event callback.
                if (config.hardwareAcceleration && !retriedInSoftware) main.post { retryInSoftware() }
                else fail("VLC couldn't play this file")
            }
        }
    }

    /** The hardware decoder gave up: start again with software decoding, from the same place. */
    private fun retryInSoftware() {
        val source = intentUri() ?: return
        retriedInSoftware = true
        resumePositionMs = player?.time?.takeIf { it > 0 } ?: resumePositionMs
        releasePlayer()
        config = config.copy(hardwareAcceleration = false)
        try {
            startPlayer(source)
            player?.attachViews(binding.videoLayout, null, config.enableSubtitles, config.useTextureView)
            viewsAttached = true
            player?.play()
        } catch (e: Exception) {
            fail("VLC couldn't play this file: ${e.message}")
        }
    }

    // ---- controls ----

    private fun setUpControls() {
        binding.root.setOnClickListener { showControls(binding.controls.visibility != View.VISIBLE) }
        binding.controls.setOnClickListener { showControls(false) }
        binding.back.setOnClickListener { finish() }
        binding.playPause.setOnClickListener {
            val p = player ?: return@setOnClickListener
            if (p.isPlaying) p.pause() else p.play()
            scheduleHide()
        }
        binding.rewind.setOnClickListener { skip(-SKIP_MS) }
        binding.forward.setOnClickListener { skip(SKIP_MS) }
        binding.seek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(bar: SeekBar, progress: Int, fromUser: Boolean) {
                if (fromUser) binding.position.text = clock(progress.toLong())
            }

            override fun onStartTrackingTouch(bar: SeekBar) {
                dragging = true
                main.removeCallbacks(hideControls)
            }

            override fun onStopTrackingTouch(bar: SeekBar) {
                dragging = false
                player?.setTime(bar.progress.toLong())
                scheduleHide()
            }
        })
    }

    private fun skip(deltaMs: Long) {
        val p = player ?: return
        val to = (p.time + deltaMs).coerceIn(0L, if (lengthMs > 0) lengthMs - 500 else Long.MAX_VALUE)
        p.setTime(to)
        scheduleHide()
    }

    private fun showControls(show: Boolean) {
        binding.controls.visibility = if (show) View.VISIBLE else View.GONE
        if (show) scheduleHide() else main.removeCallbacks(hideControls)
    }

    private fun scheduleHide() {
        main.removeCallbacks(hideControls)
        if (player?.isPlaying == true && !dragging) main.postDelayed(hideControls, HIDE_CONTROLS_MS)
    }

    // ---- helpers ----

    private fun intentUri(): Uri? =
        if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(EXTRA_URI, Uri::class.java)
        else @Suppress("DEPRECATION") intent.getParcelableExtra(EXTRA_URI)

    private fun fail(message: String) {
        error = message
        finish()
    }

    private fun hideSystemUi() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowCompat.getInsetsController(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    private fun clock(ms: Long): String {
        val s = (ms / 1000).coerceAtLeast(0)
        val h = s / 3600
        val m = (s % 3600) / 60
        val sec = s % 60
        return if (h > 0) String.format(Locale.US, "%d:%02d:%02d", h, m, sec)
        else String.format(Locale.US, "%d:%02d", m, sec)
    }
}
