package lab.crucible.talktolinux.core

import android.content.Context
import android.os.Build
import lab.crucible.talktolinux.BuildConfig
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Uygulama çökerse nedeni kaybolmasın: yığın izi dosyaya yazılır, bir sonraki bağlantıda bilgisayara
 * gönderilir ("crash_report"); bilgisayar onu ~/.cache/talk-to-android altına kaydeder ve haber verir.
 * Rapor yalnızca bu uygulamanın hata ayrıntısıdır (bildirim içeriği ya da kişisel veri içermez).
 */
object CrashLog {
    private const val FILE = "cokme.txt"

    fun install(context: Context) {
        val app = context.applicationContext
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, e ->
            runCatching {
                val sw = StringWriter()
                e.printStackTrace(PrintWriter(sw))
                val stamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.ROOT).format(Date())
                File(app.filesDir, FILE).writeText(
                    "Talk To ${BuildConfig.VERSION_NAME} (${BuildConfig.FLAVOR}) · Android ${Build.VERSION.RELEASE} " +
                        "(SDK ${Build.VERSION.SDK_INT}) · ${Build.MANUFACTURER} ${Build.MODEL}\n" +
                        "$stamp · iş parçacığı ${thread.name}\n\n" + sw.toString().take(16_000))
            }
            previous?.uncaughtException(thread, e)
        }
    }

    /** Bekleyen rapor (bir kez verilir; okununca silinir). */
    fun takePending(context: Context): String? {
        val f = File(context.filesDir, FILE)
        if (!f.exists()) return null
        val text = runCatching { f.readText() }.getOrNull()
        f.delete()
        return text?.takeIf { it.isNotBlank() }
    }
}
