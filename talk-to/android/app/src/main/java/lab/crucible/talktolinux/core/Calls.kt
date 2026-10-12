package lab.crucible.talktolinux.core

import android.Manifest
import android.annotation.SuppressLint
import android.app.ActivityOptions
import android.app.Notification
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.PixelFormat
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.telecom.TelecomManager
import android.util.Log
import android.view.View
import android.view.WindowManager
import lab.crucible.talktolinux.BuildConfig
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

    /** Arama bildirimleri (düğmesi kalmamış olsa da): kapanınca bilgisayara "arama bitti" denir. Arama
     *  biterken uygulamalar bildirimi önce düğmesiz günceller; anahtar düğmelerle birlikte unutulursa
     *  kaldırılınca "arama bitti" gitmiyor, bilgisayarda arama hep sürüyor görünüyordu. */
    private val calls = ConcurrentHashMap.newKeySet<String>()

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
        calls.add(key)
        if (list.isNullOrEmpty()) actions.remove(key) else actions[key] = list
        if (actions.size > 20) actions.keys.take(actions.size - 20).forEach { actions.remove(it) }
        if (calls.size > 20) calls.take(calls.size - 20).forEach { calls.remove(it) }
    }

    /** Bildirim kalktı: arama idiyse true (düğmeleri daha önce kalkmış olsa da). */
    fun forget(key: String): Boolean {
        actions.remove(key)
        return calls.remove(key)
    }

    /** Bilgisayar düğmeye bastı: uygulamanın kendi niyeti çalıştırılır (telefonda basmak gibi).
     *  Sonuç: (düğmenin adı, hata ya da null) — bilgisayara bildirilir, günlüğe yazılır. */
    fun press(ctx: Context, key: String, index: Int): Pair<String?, String?> {
        val a = actions[key]?.getOrNull(index)
            ?: return null to "düğme bulunamadı (arama bitmiş ya da bildirim değişmiş olabilir)"
        val title = a.title?.toString()
        val answer = isAnswer(title)
        if (answer && BuildConfig.OVERLAY_TRICK && Settings.canDrawOverlays(ctx)) {  // Play sürümünde yok
            // "Cevapla" çoğu uygulamada arama ekranını açar; Android arka plandaki uygulamanın ekran açmasını
            // sessizce engelliyor. Ekranda görünür (görünmez küçüklükte) bir penceremiz varken engel yok:
            // bir anlığına açılır, düğmeye basılır, kapanır. Sonuç bilgisayara arama durumundan anlaşılır.
            main.post {
                val dot = showDot(ctx)
                main.postDelayed({
                    send(ctx, a)?.let { Log.w(TAG, "Cevapla: $it") }
                    if (canAnswer(ctx)) main.postDelayed({ acceptRinging(ctx) }, 700)
                    main.postDelayed({ hideDot(ctx, dot) }, 2500)
                }, 150)
            }
            return title to null
        }
        val error = send(ctx, a)
        // Bazı telefonlarda (HyperOS) arama uygulamasının "Cevapla"sı başka uygulamadan basılınca sessizce
        // çalışmıyor: hâlâ çalıyorsa Android'in resmi yoluyla cevaplanır (izin verildiyse). Zaten cevaplandıysa
        // çalan arama kalmamıştır, bir şey olmaz.
        if (answer && canAnswer(ctx)) {
            if (error != null) acceptRinging(ctx) else main.postDelayed({ acceptRinging(ctx) }, 700)
            return title to null
        }
        return title to error
    }

    private val main by lazy { Handler(Looper.getMainLooper()) }
    private const val TAG = "TalkToCalls"

    /** Uygulamanın kendi düğmesine basar; hata varsa açıklaması. */
    private fun send(ctx: Context, a: Notification.Action): String? = runCatching {
        if (Build.VERSION.SDK_INT >= 34) {
            // "Cevapla" çoğu uygulamada arama ekranını açar: arka plandan açmaya izin verdiğimizi söyle.
            val opts = ActivityOptions.makeBasic().setPendingIntentBackgroundActivityStartMode(
                ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED)
            a.actionIntent.send(ctx, 0, null, null, null, null, opts.toBundle())
        } else a.actionIntent.send()
        null
    }.getOrElse { e -> "${e.javaClass.simpleName}: ${e.message ?: "telefon düğmeyi çalıştıramadı"}" }

    /** 1×1, saydam, dokunulmaz pencere ("diğer uygulamaların üzerinde göster" izniyle). */
    private fun showDot(ctx: Context): View? = runCatching {
        val v = View(ctx.applicationContext)
        val lp = WindowManager.LayoutParams(1, 1, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT)
        ctx.getSystemService(WindowManager::class.java).addView(v, lp)
        v
    }.onFailure { Log.w(TAG, "nokta açılamadı", it) }.getOrNull()

    private fun hideDot(ctx: Context, v: View?) {
        if (v != null) runCatching { ctx.getSystemService(WindowManager::class.java).removeView(v) }
    }

    /** "Cevapla / Yanıtla / Answer / Accept" gibi düğmeler. */
    fun isAnswer(title: String?): Boolean =
        title != null && Regex("cevapla|yanıtla|yanitla|answer|accept|kabul", RegexOption.IGNORE_CASE).containsMatchIn(title)

    fun canAnswer(ctx: Context): Boolean =
        ctx.checkSelfPermission(Manifest.permission.ANSWER_PHONE_CALLS) == PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")  // canAnswer denetliyor
    @Suppress("DEPRECATION")  // API 29'da InCallService önerilir; başka uygulamanın aramasını cevaplamanın tek yolu bu
    private fun acceptRinging(ctx: Context) {
        runCatching { ctx.getSystemService(TelecomManager::class.java)?.acceptRingingCall() }
    }

    /** Görüşme sesi (WhatsApp ve Instagram aramaları da bu ses akışını kullanır).
     *  Sonuç bilgisayara gider: önceki/sonraki seviye, en yüksek, telefonun ses kipi ve varsa hata. */
    fun volume(ctx: Context, up: Boolean): org.json.JSONObject {
        val r = org.json.JSONObject().put("kind", "volume")
        val am = ctx.getSystemService(AudioManager::class.java) ?: return r.put("error", "ses servisi yok")
        val stream = AudioManager.STREAM_VOICE_CALL
        r.put("before", am.getStreamVolume(stream)).put("max", am.getStreamMaxVolume(stream))
            .put("mode", when (am.mode) {
                AudioManager.MODE_IN_CALL -> "telefon görüşmesi"
                AudioManager.MODE_IN_COMMUNICATION -> "internet araması"
                AudioManager.MODE_RINGTONE -> "çalıyor"
                else -> "normal (görüşme yok)"
            })
        runCatching {
            am.adjustStreamVolume(stream, if (up) AudioManager.ADJUST_RAISE else AudioManager.ADJUST_LOWER,
                AudioManager.FLAG_SHOW_UI)
        }.onFailure { r.put("error", "${it.javaClass.simpleName}: ${it.message}") }
        return r.put("after", am.getStreamVolume(stream))
    }
}
