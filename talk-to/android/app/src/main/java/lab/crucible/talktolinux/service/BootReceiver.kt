package lab.crucible.talktolinux.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import lab.crucible.talktolinux.core.Talk

/**
 * Telefon açılınca (ya da uygulama güncellenince) kayıtlı bilgisayara kendiliğinden bağlan: uygulamayı açmak
 * gerekmesin. Yalnızca daha önce eşleşilmiş ve "kendiliğinden bağlan" açık bir bilgisayar varsa; servis
 * bilgisayarı arar, 2 dakikada bulamazsa durur (bilgisayar kapalıysa pil harcamasın).
 *
 * Xiaomi/HyperOS'ta "Otomatik başlatma" izni kapalıyken telefon bu haberi uygulamaya hiç vermez; bilgisayar
 * kurulumda bu izni de verir (phone_setup).
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action !in ACTIONS) return
        if (!Talk.willReconnect()) return
        runCatching {
            ContextCompat.startForegroundService(context, Intent(context, TalkService::class.java))
        }
    }

    companion object {
        val ACTIONS = setOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED,
            "android.intent.action.QUICKBOOT_POWERON")  // bazı üreticilerin hızlı açılışı
    }
}
