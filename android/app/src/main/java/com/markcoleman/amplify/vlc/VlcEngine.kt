package com.markcoleman.amplify.vlc

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.util.Log
import android.view.TextureView
import androidx.media3.common.Player
import com.markcoleman.amplify.VideoOverlay
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.interfaces.IMedia
import org.videolan.libvlc.interfaces.IVLCVout
import kotlin.math.roundToInt

/**
 * VLC as the player for videos of your own (movies, TV, music videos) — build 159.
 *
 * It plays inside the app exactly where the phone's own player does: the page drives it through
 * the same plugin calls (load, play, pause, seek, rate, volume, tracks) and hears the same
 * events back, the picture goes into the same native video box (Now Playing, full screen, the
 * floating window, picture-in-picture), and while it plays it stands in for the phone's player
 * in the media session ([VlcSessionPlayer]), so the notification, lock screen and headset
 * buttons work the same.
 *
 * One LibVLC and one MediaPlayer for the life of the app, made in the background when the app
 * starts, so a video starts without waiting for VLC to load.
 */
object VlcEngine {
    private const val TAG = "AmplifyVlc"

    interface Listener {
        /** Playing / paused / buffering / ended / position jumped. external = not asked for by the page. */
        fun onVlcState(external: Boolean)

        /** Whether there is a picture, or its size, changed. */
        fun onVlcVideo()

        fun onVlcError(message: String)
    }

    @JvmStatic
    var listener: Listener? = null

    private val main = Handler(Looper.getMainLooper())
    private var appContext: Context? = null

    @Volatile
    private var lib: LibVLC? = null
    private var player: MediaPlayer? = null
    private var mediaFd: ParcelFileDescriptor? = null
    private val subtitleFds = ArrayList<ParcelFileDescriptor>()

    /** A VLC item is the current item (the plugin routes everything here while it is). */
    @JvmStatic
    var isActive = false
        private set

    @JvmStatic
    var currentId: String? = null
        private set

    // What the page and the media session read.
    @JvmStatic
    var playWhenReady = false
        private set

    @JvmStatic
    var playbackState = Player.STATE_IDLE
        private set

    @JvmStatic
    var hasVideo = false
        private set

    @JvmStatic
    var videoWidth = 0
        private set

    @JvmStatic
    var videoHeight = 0
        private set

    @JvmStatic
    var pixelRatio = 1f
        private set

    @JvmStatic
    var rate = 1f
        private set

    private var lengthMs = -1L
    private var lastTimeMs = 0L
    private var pendingSeekMs = -1L
    private var textOff: Boolean? = null
    private var tracksApplied = false
    private var ignoreStop = false
    private var voutCount = 0
    private var hardware = true
    private var triedSoftware = false
    private var sourceUri: Uri? = null
    private var subtitleUris: List<Uri> = emptyList()
    private var winW = 0
    private var winH = 0

    /** Warms VLC up in the background (the native library and its plugins take a moment). */
    @JvmStatic
    fun warm(context: Context) {
        appContext = context.applicationContext
        Thread({
            try {
                libVlc()
            } catch (t: Throwable) {
                Log.w(TAG, "VLC failed to start", t)
            }
        }, "vlc-warm").start()
    }

    @Synchronized
    private fun libVlc(): LibVLC =
        lib ?: LibVLC(appContext!!, VlcPlayerConfig().libVlcArgs()).also { lib = it }

    private fun mp(): MediaPlayer =
        player ?: MediaPlayer(libVlc()).also { p ->
            p.setEventListener { onEvent(it) }
            p.videoScale = MediaPlayer.ScaleType.SURFACE_BEST_FIT
            p.vlcVout.addCallback(voutCallback)
            player = p
        }

    // ---------------- loading ----------------

    /** Loads (and, if play, starts) a file: content://, file:// or a path. Main thread. */
    @JvmStatic
    fun load(
        context: Context,
        id: String,
        uri: Uri,
        startMs: Long,
        play: Boolean,
        rate: Float,
        volume: Float,
        hardware: Boolean,
        subtitles: List<Uri>,
        textOff: Boolean?,
    ) {
        appContext = context.applicationContext
        currentId = id
        isActive = true
        this.textOff = textOff
        this.hardware = hardware
        triedSoftware = !hardware
        sourceUri = uri
        subtitleUris = subtitles
        hasVideo = true // only videos come here; the size follows once it is known
        videoWidth = 0
        videoHeight = 0
        pixelRatio = 1f
        this.rate = rate
        start(startMs, play, volume)
    }

    private fun start(startMs: Long, play: Boolean, volume: Float) {
        val p = mp()
        ignoreStop = true
        p.stop()
        closeFiles()
        lengthMs = -1L
        lastTimeMs = startMs
        pendingSeekMs = -1L
        tracksApplied = false
        voutCount = 0
        playWhenReady = play
        playbackState = Player.STATE_BUFFERING
        val uri = sourceUri ?: return
        try {
            val media = openMedia(uri)
            try {
                media.setHWDecoderEnabled(hardware, false)
                VlcPlayerConfig().mediaOptions().forEach { media.addOption(it) }
                if (startMs > 0) media.addOption(":start-time=${startMs / 1000.0}")
                p.media = media
            } finally {
                media.release() // the player keeps its own reference
            }
            subtitleUris.forEach { addSubtitle(p, it) }
            p.rate = rate
            p.setVolume((volume * 100).roundToInt().coerceIn(0, 100))
            p.setAspectRatio(null)
            p.scale = 0f
            if (play) {
                requestFocus()
                p.play()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Couldn't open $uri", e)
            playbackState = Player.STATE_IDLE
            playWhenReady = false
            listener?.onVlcError("VLC couldn't open this file: ${e.message}")
        }
        notifyState(false)
    }

    private fun openMedia(uri: Uri): Media {
        val lib = libVlc()
        return when (uri.scheme) {
            // LibVLC can't open content:// itself; it is handed the open file instead.
            "content" -> {
                val pfd = appContext!!.contentResolver.openFileDescriptor(uri, "r")
                    ?: throw IllegalStateException("Can't open $uri")
                mediaFd = pfd
                Media(lib, pfd.fileDescriptor)
            }
            "file", null -> Media(lib, uri.path ?: uri.toString())
            else -> Media(lib, uri)
        }
    }

    private fun addSubtitle(p: MediaPlayer, uri: Uri) {
        try {
            val mrl = if (uri.scheme == "content") {
                val pfd = appContext!!.contentResolver.openFileDescriptor(uri, "r") ?: return
                subtitleFds.add(pfd)
                "fd://${pfd.fd}"
            } else {
                uri.toString()
            }
            p.addSlave(IMedia.Slave.Type.Subtitle, mrl, false)
        } catch (e: Exception) {
            Log.w(TAG, "Subtitle file skipped: $uri", e)
        }
    }

    private fun closeFiles() {
        try {
            mediaFd?.close()
        } catch (_: Exception) {
        }
        mediaFd = null
        subtitleFds.forEach {
            try {
                it.close()
            } catch (_: Exception) {
            }
        }
        subtitleFds.clear()
    }

    /** Something else is playing now: VLC lets go (the plugin has already moved on). */
    @JvmStatic
    fun deactivate() {
        if (!isActive) return
        isActive = false
        currentId = null
        ignoreStop = true
        player?.stop()
        closeFiles()
        playWhenReady = false
        playbackState = Player.STATE_IDLE
        abandonFocus()
        VlcSessionPlayer.current?.refresh()
    }

    // ---------------- controls ----------------

    @JvmStatic
    fun play() = play(false)

    internal fun play(external: Boolean) {
        val p = player ?: return
        if (!isActive) return
        playWhenReady = true
        if (playbackState == Player.STATE_ENDED || playbackState == Player.STATE_IDLE) {
            // Played to the end (or stopped): from the start again.
            val vol = p.getVolume().coerceAtLeast(0) / 100f
            start(0L, true, vol)
            return
        }
        requestFocus()
        p.play()
        notifyState(external)
    }

    @JvmStatic
    fun pause() = pause(false)

    internal fun pause(external: Boolean) {
        val p = player ?: return
        playWhenReady = false
        if (p.isPlaying) p.pause()
        notifyState(external)
    }

    @JvmStatic
    fun seekTo(ms: Long) = seekTo(ms, false)

    internal fun seekTo(ms: Long, external: Boolean) {
        val p = player ?: return
        val target = ms.coerceAtLeast(0L).let { if (lengthMs > 0) it.coerceAtMost(lengthMs) else it }
        lastTimeMs = target
        if (playbackState == Player.STATE_ENDED) {
            start(target, playWhenReady, p.getVolume().coerceAtLeast(0) / 100f)
            return
        }
        if (!p.isSeekable || lengthMs <= 0) {
            pendingSeekMs = target // applied once it is playing
        } else {
            p.setTime(target, false)
        }
        notifyState(external)
    }

    @JvmStatic
    fun seekBy(deltaMs: Long) = seekTo(positionMs() + deltaMs, true)

    @JvmStatic
    fun changeRate(r: Float) {
        rate = r.coerceIn(0.25f, 4f)
        player?.rate = rate
        notifyState(false)
    }

    @JvmStatic
    fun setVolume(v: Float) {
        player?.setVolume((v * 100).roundToInt().coerceIn(0, 100))
    }

    @JvmStatic
    fun positionMs(): Long {
        val p = player ?: return lastTimeMs
        if (!isActive) return 0L
        if (pendingSeekMs >= 0) return pendingSeekMs
        val t = p.time
        if (t >= 0 && (p.isPlaying || playbackState == Player.STATE_READY)) lastTimeMs = t
        return lastTimeMs
    }

    /** -1 while not known yet. */
    @JvmStatic
    fun durationMs(): Long = lengthMs

    @JvmStatic
    fun isPlaying(): Boolean = isActive && player?.isPlaying == true

    // ---------------- tracks (audio and subtitles) ----------------

    /** [[id, name, selected], ...] for "audio" or "text" (VLC's "Disable" entry left out). */
    @JvmStatic
    fun tracks(audio: Boolean): List<Triple<Int, String, Boolean>> {
        val p = player ?: return emptyList()
        val list = (if (audio) p.audioTracks else p.spuTracks) ?: return emptyList()
        val sel = if (audio) p.audioTrack else p.spuTrack
        return list.filter { it.id >= 0 }.map { Triple(it.id, it.name ?: "", it.id == sel) }
    }

    @JvmStatic
    fun subtitlesOff(): Boolean = (player?.spuTrack ?: -1) < 0

    @JvmStatic
    fun selectTrack(audio: Boolean, id: Int) {
        val p = player ?: return
        if (audio) p.setAudioTrack(id) else p.setSpuTrack(id)
    }

    /** Subtitles as the page asked: off, or (when on) the first one if VLC picked none. */
    private fun applyTrackChoices(p: MediaPlayer) {
        if (tracksApplied) return
        tracksApplied = true
        when (textOff) {
            true -> p.setSpuTrack(-1)
            false -> if (p.spuTrack < 0) p.spuTracks?.firstOrNull { it.id >= 0 }?.let { p.setSpuTrack(it.id) }
            else -> {}
        }
    }

    // ---------------- the picture ----------------

    /** The native video box binds VLC's output to its TextureView through this. */
    @JvmStatic
    val target: VideoOverlay.Target = object : VideoOverlay.Target {
        override fun bind(view: TextureView) {
            val p = mp()
            val vout = p.vlcVout
            if (vout.areViewsAttached()) vout.detachViews()
            vout.setVideoView(view)
            vout.attachViews(layoutListener)
            if (winW > 0 && winH > 0) vout.setWindowSize(winW, winH)
            p.setVideoTrackEnabled(true)
        }

        override fun unbind(view: TextureView) {
            val vout = player?.vlcVout ?: return
            if (vout.areViewsAttached()) vout.detachViews()
        }

        override fun onWindowSize(width: Int, height: Int) {
            winW = width
            winH = height
            val vout = player?.vlcVout ?: return
            if (vout.areViewsAttached()) vout.setWindowSize(width, height)
        }
    }

    private val layoutListener = IVLCVout.OnNewVideoLayoutListener { _, _, _, visibleWidth, visibleHeight, sarNum, sarDen ->
        if (visibleWidth <= 0 || visibleHeight <= 0) return@OnNewVideoLayoutListener
        val ratio = if (sarNum > 0 && sarDen > 0) sarNum.toFloat() / sarDen else 1f
        setVideoSize(visibleWidth, visibleHeight, ratio)
    }

    private val voutCallback = object : IVLCVout.Callback {
        override fun onSurfacesCreated(vlcVout: IVLCVout) {
            // A picture surface again (back from hidden): if the video didn't come back on its
            // own, the video track is switched off and on to make VLC draw again.
            main.postDelayed({
                val p = player ?: return@postDelayed
                if (!isActive || voutCount > 0 || !p.vlcVout.areViewsAttached()) return@postDelayed
                val t = p.videoTrack
                if (t >= 0) {
                    p.setVideoTrack(-1)
                    p.setVideoTrack(t)
                } else {
                    p.setVideoTrackEnabled(true)
                }
            }, 600)
        }

        override fun onSurfacesDestroyed(vlcVout: IVLCVout) {}
    }

    private fun setVideoSize(w: Int, h: Int, ratio: Float) {
        if (w == videoWidth && h == videoHeight && ratio == pixelRatio) return
        videoWidth = w
        videoHeight = h
        pixelRatio = ratio
        listener?.onVlcVideo()
    }

    private fun readVideoTrack(p: MediaPlayer) {
        val vt = p.currentVideoTrack ?: return
        if (vt.width <= 0 || vt.height <= 0) return
        val swapped = vt.orientation == IMedia.VideoTrack.Orientation.LeftBottom ||
            vt.orientation == IMedia.VideoTrack.Orientation.RightTop
        val ratio = if (vt.sarNum > 0 && vt.sarDen > 0) vt.sarNum.toFloat() / vt.sarDen else 1f
        if (swapped) setVideoSize(vt.height, vt.width, 1f / ratio) else setVideoSize(vt.width, vt.height, ratio)
    }

    // ---------------- events ----------------

    private fun onEvent(e: MediaPlayer.Event) {
        val p = player ?: return
        if (!isActive) return
        when (e.type) {
            MediaPlayer.Event.Opening -> {
                ignoreStop = false
                playbackState = Player.STATE_BUFFERING
                notifyState(false)
            }
            MediaPlayer.Event.Playing -> {
                ignoreStop = false
                playbackState = Player.STATE_READY
                playWhenReady = true
                if (pendingSeekMs >= 0) {
                    val s = pendingSeekMs
                    pendingSeekMs = -1L
                    p.setTime(s, false)
                }
                applyTrackChoices(p)
                readVideoTrack(p)
                notifyState(false)
            }
            MediaPlayer.Event.Paused -> {
                playbackState = Player.STATE_READY
                notifyState(playWhenReady) // paused by something other than us
                playWhenReady = false
            }
            MediaPlayer.Event.Stopped -> {
                if (ignoreStop) return
                if (playbackState != Player.STATE_ENDED) {
                    playbackState = Player.STATE_IDLE
                    notifyState(false)
                }
            }
            MediaPlayer.Event.EndReached -> {
                lastTimeMs = if (lengthMs > 0) lengthMs else lastTimeMs
                playbackState = Player.STATE_ENDED
                abandonFocus()
                notifyState(false)
            }
            MediaPlayer.Event.EncounteredError -> {
                if (!triedSoftware) {
                    // The hardware decoder gave up: once more in software, from the same place.
                    triedSoftware = true
                    hardware = false
                    val at = positionMs()
                    val vol = p.getVolume().coerceAtLeast(0) / 100f
                    main.post { start(at, true, vol) }
                    return
                }
                playbackState = Player.STATE_IDLE
                playWhenReady = false
                abandonFocus()
                listener?.onVlcError("VLC couldn't play this file")
                notifyState(false)
            }
            MediaPlayer.Event.TimeChanged -> lastTimeMs = e.timeChanged
            MediaPlayer.Event.LengthChanged -> {
                lengthMs = e.lengthChanged
                if (pendingSeekMs >= 0 && p.isSeekable && playbackState == Player.STATE_READY) {
                    val s = pendingSeekMs
                    pendingSeekMs = -1L
                    p.setTime(s, false)
                }
                notifyState(false)
            }
            MediaPlayer.Event.Vout -> {
                voutCount = e.voutCount
                if (voutCount > 0) readVideoTrack(p)
            }
            MediaPlayer.Event.ESAdded, MediaPlayer.Event.ESSelected -> {
                if (e.esChangedType == IMedia.Track.Type.Video) readVideoTrack(p)
            }
        }
    }

    private fun notifyState(external: Boolean) {
        listener?.onVlcState(external)
        VlcSessionPlayer.current?.refresh()
        updateNoisyReceiver()
    }

    // ---------------- audio focus and headphones ----------------

    private var focusRequest: AudioFocusRequest? = null
    private var hasFocus = false
    private var pausedByFocus = false

    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        main.post {
            when (change) {
                AudioManager.AUDIOFOCUS_LOSS -> {
                    pausedByFocus = false
                    hasFocus = false
                    if (playWhenReady) pause(true)
                }
                AudioManager.AUDIOFOCUS_LOSS_TRANSIENT, AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> {
                    if (playWhenReady) {
                        pausedByFocus = true
                        pause(true)
                    }
                }
                AudioManager.AUDIOFOCUS_GAIN -> {
                    hasFocus = true
                    if (pausedByFocus) {
                        pausedByFocus = false
                        play(true)
                    }
                }
            }
        }
    }

    private fun audioManager(): AudioManager? =
        appContext?.getSystemService(Context.AUDIO_SERVICE) as? AudioManager

    private fun requestFocus() {
        if (hasFocus) return
        val am = audioManager() ?: return
        val granted = if (Build.VERSION.SDK_INT >= 26) {
            val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MOVIE)
                        .build(),
                )
                .setOnAudioFocusChangeListener(focusListener, main)
                .build()
            focusRequest = req
            am.requestAudioFocus(req)
        } else {
            @Suppress("DEPRECATION")
            am.requestAudioFocus(focusListener, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN)
        }
        hasFocus = granted == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
    }

    private fun abandonFocus() {
        if (!hasFocus) return
        hasFocus = false
        pausedByFocus = false
        val am = audioManager() ?: return
        if (Build.VERSION.SDK_INT >= 26) {
            focusRequest?.let { am.abandonAudioFocusRequest(it) }
        } else {
            @Suppress("DEPRECATION")
            am.abandonAudioFocus(focusListener)
        }
    }

    // Headphones pulled out: pause, as the phone's own player does.
    private var noisyRegistered = false
    private val noisyReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == AudioManager.ACTION_AUDIO_BECOMING_NOISY && playWhenReady) pause(true)
        }
    }

    private fun updateNoisyReceiver() {
        val ctx = appContext ?: return
        val want = isActive && playWhenReady
        if (want == noisyRegistered) return
        try {
            if (want) {
                val filter = IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY)
                if (Build.VERSION.SDK_INT >= 33) ctx.registerReceiver(noisyReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
                else ctx.registerReceiver(noisyReceiver, filter)
            } else {
                ctx.unregisterReceiver(noisyReceiver)
            }
            noisyRegistered = want
        } catch (e: Exception) {
            Log.w(TAG, "Headphone listener", e)
        }
    }
}
