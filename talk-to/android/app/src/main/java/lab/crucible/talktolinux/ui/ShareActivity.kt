package lab.crucible.talktolinux.ui

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.Intent
import android.content.res.Configuration
import android.net.Uri
import android.os.Bundle
import androidx.core.content.IntentCompat
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.service.TalkService

/**
 * "Paylaş → Talk To Linux": dosyalar bilgisayara gider, bağlantılar bilgisayarda açılır, metin panoya kopyalanır.
 *
 * Etkinlik dışa açık olduğundan herhangi bir uygulama doğrudan çağırabilir; bu yüzden her paylaşım
 * kısa bir onayla gönderilir (kullanıcı ne gideceğini ve nereye gideceğini görür).
 */
class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val uris = runCatching {
            when (intent.action) {
                Intent.ACTION_SEND -> listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
                Intent.ACTION_SEND_MULTIPLE ->
                    IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java) ?: emptyList()
                else -> emptyList()
            }
        }.getOrDefault(emptyList())
        val text = runCatching { intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() }.getOrNull()
            ?.takeIf { it.isNotBlank() }
        if (uris.isEmpty() && text == null) {
            finish()
            return
        }
        val connected = Talk.isConnected()
        val pc = (Talk.state.value as? Talk.State.Connected)?.serverName ?: Talk.prefs.server(Talk.prefs.autoServer)?.name
        if (!connected && (pc == null || !Talk.willReconnect())) {
            dialog().setTitle("Bilgisayara bağlı değilsin")
                .setMessage("Göndermek için önce Talk To Linux'ta bir bilgisayara bağlan, sonra yeniden paylaş.")
                .setPositiveButton("Uygulamayı aç") { _, _ ->
                    startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                }
                .setNegativeButton("Kapat", null)
                .show()
            return
        }
        val name = pc ?: "Bilgisayar"
        val (title, body) = when {
            uris.isNotEmpty() -> "${uris.size} dosya $name bilgisayarına gönderilsin mi?" to
                uris.take(5).joinToString("\n") { it.lastPathSegment?.substringAfterLast('/') ?: "dosya" } +
                if (uris.size > 5) "\n… ve ${uris.size - 5} dosya daha" else ""
            Talk.isUrl(text!!) -> "Bağlantı $name bilgisayarının tarayıcısında açılsın mı?" to text.trim().take(400)
            else -> "Metin $name bilgisayarının panosuna kopyalansın mı?" to
                (if (text.length > 300) text.take(300) + "… (${text.length} karakter)" else text)
        }
        val note = if (connected) "" else "\n\nŞu an bağlı değil; bağlantı gelince (2 dakika içinde) gönderilir."
        dialog().setTitle(title)
            .setMessage(body + note)
            .setPositiveButton("Gönder") { _, _ ->
                if (uris.isNotEmpty()) sendViaService(this, uris) else {
                    // Bağlı değilse yeniden bağlanmayı servis yürütür.
                    if (!connected) runCatching { startService(Intent(this, TalkService::class.java)) }
                    Talk.sendText(text!!)
                }
            }
            .setNegativeButton("Vazgeç", null)
            .show()
    }

    private fun dialog(): AlertDialog.Builder {
        val night = resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES
        return AlertDialog.Builder(this, if (night) android.R.style.Theme_DeviceDefault_Dialog_Alert
            else android.R.style.Theme_DeviceDefault_Light_Dialog_Alert)
            .setOnDismissListener { finish() }
    }
}

/** Uri okuma iznini servise devrederek gönderir (etkinlik kapansa da gönderim sürer). */
fun sendViaService(activity: Activity, uris: List<Uri>) {
    if (uris.isEmpty()) return
    val clip = ClipData.newRawUri("talktolinux", uris[0])
    uris.drop(1).forEach { clip.addItem(ClipData.Item(it)) }
    val i = Intent(activity, TalkService::class.java).setAction(TalkService.ACTION_SEND)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    i.clipData = clip
    runCatching { activity.startService(i) }
        .onFailure { Talk.sendUris(uris) }  // servis başlatılamadıysa (arka plan kısıtı) en azından doğrudan dene
}
