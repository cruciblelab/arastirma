package lab.crucible.talktolinux.ui

import android.app.Activity
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.RemoteViews
import android.widget.Toast
import lab.crucible.talktolinux.R
import lab.crucible.talktolinux.core.Talk

/**
 * Ana ekran widget'ı: bağlı bilgisayar ve nasıl bağlı olduğu, (dizüstüyse) pili, bilgisayarda çalan
 * (oynat/duraklat, sonraki) ve hızlı düğmeler: kilitle, uyut, panoyu gönder. Kilitle ve uyut bilgisayardaki
 * hazır komutlardır; profil izin vermiyorsa söylenir. İçerik Talk'ın durumu değişince yenilenir.
 */
class PcWidget : AppWidgetProvider() {

    override fun onUpdate(ctx: Context, manager: AppWidgetManager, ids: IntArray) = update(ctx)

    override fun onEnabled(ctx: Context) {
        if (Talk.isConnected()) Talk.requestSysinfo()
    }

    override fun onReceive(ctx: Context, intent: Intent) {
        super.onReceive(ctx, intent)
        val action = intent.action ?: return
        if (!action.startsWith(PREFIX)) return
        if (!Talk.isConnected()) {
            // Bağlı değilken düğmeler uygulamayı açar (bağlanmak için).
            ctx.startActivity(Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        when (action) {
            PLAY -> Talk.mediaControl("play_pause")
            NEXT -> Talk.mediaControl("next")
            LOCK -> command(ctx, "lock", "kilitleme")
            SLEEP -> command(ctx, "sleep", "uyutma")
        }
    }

    private fun command(ctx: Context, icon: String, what: String) {
        val c = Talk.commands.value.firstOrNull { it.icon == icon }
        if (c == null) Toast.makeText(ctx, "Bu bilgisayar bu telefona $what izni vermiyor (profil)", Toast.LENGTH_LONG).show()
        else Talk.runCommand(c.id)
    }

    companion object {
        private const val PREFIX = "lab.crucible.talktolinux.widget."
        private const val PLAY = PREFIX + "PLAY"
        private const val NEXT = PREFIX + "NEXT"
        private const val LOCK = PREFIX + "LOCK"
        private const val SLEEP = PREFIX + "SLEEP"
        private val main by lazy { Handler(Looper.getMainLooper()) }
        @Volatile private var refreshing = false

        fun ids(ctx: Context): IntArray =
            AppWidgetManager.getInstance(ctx).getAppWidgetIds(ComponentName(ctx, PcWidget::class.java))

        /** Bütün widget'ları Talk'ın şimdiki durumuyla yeniden çizer (widget yoksa hiçbir şey yapmaz). */
        fun update(ctx: Context) {
            val ids = runCatching { ids(ctx) }.getOrNull()
            if (ids == null || ids.isEmpty()) return
            AppWidgetManager.getInstance(ctx).updateAppWidget(ids, views(ctx))
            keepFresh(ctx)
        }

        /** Bağlıyken bilgisayarın pili birkaç dakikada bir sorulur (widget varken). */
        private fun keepFresh(ctx: Context) {
            if (refreshing || !Talk.isConnected()) return
            refreshing = true
            Talk.requestSysinfo()
            main.postDelayed({
                refreshing = false
                if (runCatching { ids(ctx).isNotEmpty() }.getOrDefault(false)) keepFresh(ctx)
            }, 3 * 60_000L)
        }

        private fun views(ctx: Context): RemoteViews {
            val v = RemoteViews(ctx.packageName, R.layout.widget_pc)
            val state = Talk.state.value
            val connected = state as? Talk.State.Connected
            val sys = Talk.sysinfo.value
            v.setTextViewText(R.id.w_name, connected?.serverName ?: "Talk To")
            v.setTextViewText(R.id.w_status, when (state) {
                is Talk.State.Connected -> "Bağlı · " + when (state.target.kind) {
                    "usb" -> "USB"; "bluetooth" -> "Bluetooth"; else -> "Wi-Fi"
                }
                is Talk.State.Connecting, is Talk.State.Approval -> "Bağlanıyor…"
                else -> "Bağlı değil · dokun, aç"
            })
            val battery = sys?.battery?.takeIf { connected != null }
            v.setTextViewText(R.id.w_battery, battery?.let { (level, charging) -> "%$level" + if (charging) " ⚡" else "" } ?: "")
            v.setViewVisibility(R.id.w_battery, if (battery != null) View.VISIBLE else View.GONE)

            val media = Talk.pcMedia.value?.takeIf { connected != null }
            v.setViewVisibility(R.id.w_media, if (media != null) View.VISIBLE else View.GONE)
            if (media != null) {
                v.setTextViewText(R.id.w_title, listOf(media.title, media.artist).filter { it.isNotBlank() }
                    .joinToString(" — ").ifEmpty { media.player })
                v.setImageViewResource(R.id.w_play, if (media.playing) R.drawable.w_pause else R.drawable.w_play)
            }
            v.setViewVisibility(R.id.w_actions, if (connected != null) View.VISIBLE else View.GONE)

            v.setOnClickPendingIntent(R.id.w_head, PendingIntent.getActivity(ctx, 0,
                Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE))
            for ((id, action) in listOf(R.id.w_play to PLAY, R.id.w_next to NEXT, R.id.w_lock to LOCK, R.id.w_sleep to SLEEP)) {
                v.setOnClickPendingIntent(id, PendingIntent.getBroadcast(ctx, id,
                    Intent(ctx, PcWidget::class.java).setAction(action), PendingIntent.FLAG_IMMUTABLE))
            }
            // Android 10+ panoyu yalnızca öndeki uygulamaya okutur: görünmez bir ekran bir anlığına açılıp okur.
            v.setOnClickPendingIntent(R.id.w_clip, PendingIntent.getActivity(ctx, 1,
                Intent(ctx, ClipSendActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_NO_ANIMATION), PendingIntent.FLAG_IMMUTABLE))
            return v
        }
    }
}

/** Widget'taki "Panoyu gönder": öne gelince (Android ancak o zaman izin verir) panoyu okur, gönderir, kapanır. */
class ClipSendActivity : Activity() {
    private var done = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Talk.isConnected()) {
            Toast.makeText(this, "Bilgisayara bağlı değil", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (!hasFocus || done) return
        done = true
        val item = runCatching { getSystemService(ClipboardManager::class.java).primaryClip }.getOrNull()
            ?.takeIf { it.itemCount > 0 }?.getItemAt(0)
        val text = (item?.text ?: item?.htmlText)?.toString()
        if (text.isNullOrEmpty()) Toast.makeText(this, "Panoda metin yok", Toast.LENGTH_SHORT).show()
        else if (Talk.profile.value?.can("clipboard") == false)
            Toast.makeText(this, "Bu bilgisayar bu telefona pano izni vermiyor (profil)", Toast.LENGTH_LONG).show()
        else {
            Talk.sendClipboard(text)
            Toast.makeText(this, "Pano bilgisayara gönderildi", Toast.LENGTH_SHORT).show()
        }
        finish()
        @Suppress("DEPRECATION") overridePendingTransition(0, 0)
    }
}
