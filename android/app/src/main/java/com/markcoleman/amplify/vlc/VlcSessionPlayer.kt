package com.markcoleman.amplify.vlc

import android.os.Looper
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.common.SimpleBasePlayer
import androidx.media3.common.SimpleBasePlayer.MediaItemData
import androidx.media3.common.SimpleBasePlayer.State
import androidx.media3.common.util.UnstableApi
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture

/**
 * VLC as seen by the media session (build 159): while a video of your own plays in VLC this
 * stands in for the phone's player, so the notification, lock screen, headset and watch
 * controls show it and work it exactly as they do for the phone's own player.
 */
@OptIn(UnstableApi::class)
class VlcSessionPlayer(looper: Looper) : SimpleBasePlayer(looper) {
    companion object {
        /** The one in use (the session holds it while VLC plays). */
        @JvmStatic
        var current: VlcSessionPlayer? = null
            private set

        @JvmStatic
        fun get(looper: Looper): VlcSessionPlayer = current ?: VlcSessionPlayer(looper).also { current = it }
    }

    private var metadata: MediaMetadata = MediaMetadata.EMPTY
    private var seekBackMs = 10_000L
    private var seekForwardMs = 30_000L

    /** What the notification shows (title, artist, artwork), from the page. */
    fun setMetadata(m: MediaMetadata?) {
        metadata = m ?: MediaMetadata.EMPTY
        refresh()
    }

    fun setSeekIncrements(backMs: Long, forwardMs: Long) {
        seekBackMs = backMs
        seekForwardMs = forwardMs
        refresh()
    }

    /** Something changed in VLC: the session reads the state again. */
    fun refresh() {
        invalidateState()
    }

    override fun getState(): State {
        val commands = Player.Commands.Builder()
            .addAll(
                Player.COMMAND_PLAY_PAUSE,
                Player.COMMAND_STOP,
                Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM,
                Player.COMMAND_SEEK_BACK,
                Player.COMMAND_SEEK_FORWARD,
                Player.COMMAND_SET_SPEED_AND_PITCH,
                Player.COMMAND_GET_CURRENT_MEDIA_ITEM,
                Player.COMMAND_GET_TIMELINE,
                Player.COMMAND_GET_METADATA,
            )
            .build()
        val b = State.Builder()
            .setAvailableCommands(commands)
            .setSeekBackIncrementMs(seekBackMs)
            .setSeekForwardIncrementMs(seekForwardMs)
            .setPlaybackParameters(PlaybackParameters(VlcEngine.rate))
        if (!VlcEngine.isActive) {
            return b.setPlaybackState(Player.STATE_IDLE)
                .setPlayWhenReady(false, Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST)
                .build()
        }
        val id = VlcEngine.currentId ?: "vlc"
        val dur = VlcEngine.durationMs()
        val item = MediaItemData.Builder(id)
            .setMediaItem(MediaItem.Builder().setMediaId(id).setMediaMetadata(metadata).build())
            .setMediaMetadata(metadata)
            .setIsSeekable(true)
            .setDurationUs(if (dur > 0) dur * 1000 else C.TIME_UNSET)
            .build()
        return b.setPlaylist(listOf(item))
            .setCurrentMediaItemIndex(0)
            .setPlaybackState(VlcEngine.playbackState)
            .setPlayWhenReady(VlcEngine.playWhenReady, Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST)
            .setContentPositionMs { VlcEngine.positionMs() }
            .build()
    }

    override fun handleSetPlayWhenReady(playWhenReady: Boolean): ListenableFuture<*> {
        if (playWhenReady) VlcEngine.play(true) else VlcEngine.pause(true)
        return Futures.immediateVoidFuture()
    }

    override fun handleSeek(mediaItemIndex: Int, positionMs: Long, seekCommand: Int): ListenableFuture<*> {
        // Skips back and forward arrive with the new position already worked out.
        if (positionMs != C.TIME_UNSET) VlcEngine.seekTo(positionMs, true)
        return Futures.immediateVoidFuture()
    }

    override fun handleStop(): ListenableFuture<*> {
        VlcEngine.pause(true)
        return Futures.immediateVoidFuture()
    }

    override fun handleSetPlaybackParameters(playbackParameters: PlaybackParameters): ListenableFuture<*> {
        VlcEngine.changeRate(playbackParameters.speed)
        return Futures.immediateVoidFuture()
    }

    override fun handleRelease(): ListenableFuture<*> = Futures.immediateVoidFuture()
}
