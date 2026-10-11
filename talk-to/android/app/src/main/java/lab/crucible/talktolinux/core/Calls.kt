package lab.crucible.talktolinux.core

import android.app.ActivityOptions
import android.app.Notification
import android.content.Context
import android.media.AudioManager
import android.os.Build
import java.util.concurrent.ConcurrentHashMap

/**
 * Aramalar (WhatsApp, Instagram, Telegram, telefonun kendisi): bildirimleri "süren" türden olduğu için
 * sıradan bildirim gibi gönderilmiyordu. Burada ayrı tanınır, bilgisayara arayan, durum (çalıyor / sürüyor)
 * ve uygulamanın kendi düğmeleriyle (Cevapla, Reddet, Kapat) gider; bilgisayar bu düğmelere basabilir ve
 * görüşme sesini açıp kısabilir.
 *
 * Yapılamayanlar (Android başka uygulamanın aramasına izin vermiyor): hoparlör/ahize/kulaklık değiştirmek,
 * WhatsApp/Instagram'da mikrofonu kapatmak (uygulamanın kendi düğmesi bildirimde varsa o çalışır).
 */
object Calls {
    const val CALL_STYLE = "android.app.Notification\$CallStyle"
    private const val EXTRA_CALL_TYPE = "android.callType"  // Notification.EXTRA_CALL_TYPE (API 31)

    /** Bilgisayarın basabileceği düğmeler: bildirim anahtarı → uygulamanın düğmeleri. */
    private val actions = ConcurrentHashMap<String, Array<Notification.Action>>()

    /** Arama bildirimi mi: kategori "call" ya da Android 12'nin arama şablonu. */
    fun isCall(category: String?, template: String?): Boolean =
        category == Notification.CATEGORY_CALL || template == CALL_STYLE

    /** "ringing" ya da "ongoing": şablon türü yazar (1 gelen, 2 süren, 3 süzülen); yoksa tam ekran açan çalıyordur. */
    fun state(callType: Int, fullScreen: Boolean): String = when (callType) {
        1, 3 -> "ringing"
        2 -> "ongoing"
        else -> if (fullScreen) "ringing" else "ongoing"
    }

    fun stateOf(n: Notification): String = state(n.extras.getInt(EXTRA_CALL_TYPE, 0), n.fullScreenIntent != null)

    /** Arayanın adı: arama şablonundaki kişi, yoksa başlık. */
    fun caller(n: Notification): String {
        val person = when {
            Build.VERSION.SDK_INT >= 33 ->
                n.extras.getParcelable("android.callPerson", android.app.Person::class.java)?.name?.toString()
            Build.VERSION.SDK_INT >= 28 ->
                @Suppress("DEPRECATION") n.extras.getParcelable<android.app.Person>("android.callPerson")?.name?.toString()
            else -> null
        }
        return person?.takeIf { it.isNotBlank() }
            ?: n.extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
    }

    fun remember(key: String, list: Array<Notification.Action>?) {
        if (list.isNullOrEmpty()) actions.remove(key) else actions[key] = list
        if (actions.size > 20) actions.keys.take(actions.size - 20).forEach { actions.remove(it) }
    }

    fun forget(key: String) = actions.remove(key) != null

    /** Bilgisayar düğmeye bastı: uygulamanın kendi niyeti çalıştırılır (telefonda basmak gibi). */
    fun press(ctx: Context, key: String, index: Int): Boolean {
        val a = actions[key]?.getOrNull(index) ?: return false
        return runCatching {
            if (Build.VERSION.SDK_INT >= 34) {
                // "Cevapla" çoğu uygulamada arama ekranını açar: arka plandan açmaya izin verdiğimizi söyle.
                val opts = ActivityOptions.makeBasic().setPendingIntentBackgroundActivityStartMode(
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED)
                a.actionIntent.send(ctx, 0, null, null, null, null, opts.toBundle())
            } else a.actionIntent.send()
            true
        }.getOrDefault(false)  // PendingIntent.CanceledException: arama bu arada bitti
    }

    /** Görüşme sesi (WhatsApp ve Instagram aramaları da bu ses akışını kullanır). */
    fun volume(ctx: Context, up: Boolean) {
        val am = ctx.getSystemService(AudioManager::class.java) ?: return
        runCatching {
            am.adjustStreamVolume(AudioManager.STREAM_VOICE_CALL,
                if (up) AudioManager.ADJUST_RAISE else AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
        }
    }
}
