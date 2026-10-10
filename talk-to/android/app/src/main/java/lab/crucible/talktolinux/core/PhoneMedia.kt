package lab.crucible.talktolinux.core

import android.annotation.SuppressLint
import android.content.ComponentName
import android.content.Context
import android.graphics.Bitmap
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.os.Handler
import android.os.Looper
import android.util.Base64
import lab.crucible.talktolinux.net.Auth
import lab.crucible.talktolinux.service.NotificationListener
import org.json.JSONObject
import java.io.ByteArrayOutputStream

/**
 * Telefonda çalan medya (Spotify, YouTube, YouTube Music...). Android medya
 * oturumlarını yalnızca bildirim erişimi verilmiş uygulamalara gösterir; bu
 * yüzden NotificationListener bağlanınca başlatılır.
 */
@SuppressLint("StaticFieldLeak")  // yalnızca uygulama bağlamı tutulur
object PhoneMedia {
    private var manager: MediaSessionManager? = null
    private var controller: MediaController? = null
    private var context: Context? = null
    private val main = Handler(Looper.getMainLooper())
    private var lastArtId: String? = null
    private var lastArt: Pair<String, String>? = null  // art_id → base64 JPEG
    private var lastBitmap: Bitmap? = null

    private val sessionsListener = MediaSessionManager.OnActiveSessionsChangedListener { list -> pick(list ?: emptyList()) }

    private val callback = object : MediaController.Callback() {
        override fun onPlaybackStateChanged(state: PlaybackState?) = push()
        override fun onMetadataChanged(metadata: MediaMetadata?) = push()
        override fun onSessionDestroyed() {
            controller = null
            push()
        }
    }

    /** Erişim varsa bir kez başlar; dinleyici bağlanınca ya da bağlantı kurulunca yeniden çağrılabilir. */
    fun start(ctx: Context) {
        if (manager != null) return
        context = ctx.applicationContext
        val m = ctx.getSystemService(MediaSessionManager::class.java) ?: return
        val comp = ComponentName(ctx, NotificationListener::class.java)
        try {
            m.addOnActiveSessionsChangedListener(sessionsListener, comp, main)
            manager = m
            pick(m.getActiveSessions(comp))
        } catch (_: SecurityException) {
            // Bildirim erişimi yok.
        }
    }

    /** Şu an izlenen oynatıcının adı (Spotify, YouTube...). */
    fun playerName(): String? {
        val c = controller ?: return null
        val pm = context?.packageManager ?: return c.packageName
        return runCatching { pm.getApplicationLabel(pm.getApplicationInfo(c.packageName, 0)).toString() }
            .getOrDefault(c.packageName)
    }

    fun stop() {
        manager?.removeOnActiveSessionsChangedListener(sessionsListener)
        controller?.unregisterCallback(callback)
        controller = null
        manager = null
    }

    private fun pick(list: List<MediaController>) {
        val playing = list.firstOrNull { it.playbackState?.state == PlaybackState.STATE_PLAYING }
        val chosen = playing ?: list.firstOrNull { it.packageName == controller?.packageName } ?: list.firstOrNull()
        if (chosen?.sessionToken != controller?.sessionToken) {
            controller?.unregisterCallback(callback)
            controller = chosen
            chosen?.registerCallback(callback, main)
            Talk.sendPhoneStatus()
        }
        push()
    }

    /** Durumu bilgisayara gönderir (bağlı değilse bir şey yapmaz). */
    fun push() {
        if (!Talk.mediaOn()) return
        val c = controller
        val md = c?.metadata
        val st = c?.playbackState
        if (c == null || md == null) {
            Talk.send(JSONObject().put("type", "media_state").put("active", false))
            return
        }
        val ctx = context ?: return
        val appName = runCatching {
            val pm = ctx.packageManager
            pm.getApplicationLabel(pm.getApplicationInfo(c.packageName, 0)).toString()
        }.getOrDefault(c.packageName)
        val art = md.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART) ?: md.getBitmap(MediaMetadata.METADATA_KEY_ART)
        val artId = art?.let { encodeArt(it) }
        if (artId != null && artId != lastArtId) {
            lastArtId = artId
            Talk.send(JSONObject().put("type", "media_art").put("art_id", artId).put("mime", "image/jpeg")
                .put("data", lastArt!!.second))
        }
        val audio = ctx.getSystemService(AudioManager::class.java)
        val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val vol = audio.getStreamVolume(AudioManager.STREAM_MUSIC) * 100 / max.coerceAtLeast(1)
        var pos = st?.position ?: 0L
        if (st?.state == PlaybackState.STATE_PLAYING && st.lastPositionUpdateTime > 0) {
            pos += ((android.os.SystemClock.elapsedRealtime() - st.lastPositionUpdateTime) * st.playbackSpeed).toLong()
        }
        Talk.send(JSONObject().put("type", "media_state").put("active", true)
            .put("player", appName)
            .put("title", md.getString(MediaMetadata.METADATA_KEY_TITLE) ?: "")
            .put("artist", md.getString(MediaMetadata.METADATA_KEY_ARTIST)
                ?: md.getString(MediaMetadata.METADATA_KEY_ALBUM_ARTIST) ?: "")
            .put("album", md.getString(MediaMetadata.METADATA_KEY_ALBUM) ?: "")
            .put("playing", st?.state == PlaybackState.STATE_PLAYING)
            .put("position_ms", pos.coerceAtLeast(0))
            .put("duration_ms", md.getLong(MediaMetadata.METADATA_KEY_DURATION).coerceAtLeast(0))
            .put("volume", vol)
            .put("can_seek", (st?.actions ?: 0L) and PlaybackState.ACTION_SEEK_TO != 0L)
            .put("art_id", artId ?: JSONObject.NULL))
    }

    /** Yeni bağlantıda kapak yeniden gönderilsin. */
    fun resetArt() {
        lastArtId = null
    }

    private fun encodeArt(bmp: Bitmap): String {
        if (bmp === lastBitmap) lastArt?.let { return it.first }
        lastBitmap = bmp
        val scaled = if (bmp.width > 320 || bmp.height > 320) {
            val f = 320f / maxOf(bmp.width, bmp.height)
            Bitmap.createScaledBitmap(bmp, (bmp.width * f).toInt().coerceAtLeast(1),
                (bmp.height * f).toInt().coerceAtLeast(1), true)
        } else bmp
        val out = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 85, out)
        val bytes = out.toByteArray()
        val id = Auth.sha256Hex(bytes).take(16)
        if (lastArt?.first != id) lastArt = id to Base64.encodeToString(bytes, Base64.NO_WRAP)
        return id
    }

    /** Bilgisayardan gelen komut. */
    fun control(action: String, value: Double?) {
        val ctx = context ?: return
        if (action == "volume" && value != null) {
            val audio = ctx.getSystemService(AudioManager::class.java)
            val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            audio.setStreamVolume(AudioManager.STREAM_MUSIC, (value / 100 * max).toInt().coerceIn(0, max), 0)
            main.postDelayed({ push() }, 150)
            return
        }
        val t = controller?.transportControls ?: return
        when (action) {
            "play_pause" -> if (controller?.playbackState?.state == PlaybackState.STATE_PLAYING) t.pause() else t.play()
            "play" -> t.play()
            "pause" -> t.pause()
            "next" -> t.skipToNext()
            "previous" -> t.skipToPrevious()
            "seek" -> if (value != null) t.seekTo(value.toLong())
        }
    }
}
