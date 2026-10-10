package lab.crucible.kopru.ui

import android.app.Activity
import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.core.content.IntentCompat
import lab.crucible.kopru.core.Kopru
import lab.crucible.kopru.service.KopruService

/** "Paylaş → Köprü": dosyalar bilgisayara gider, bağlantılar bilgisayarda açılır, metin panoya kopyalanır. */
class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Kopru.isConnected()) {
            Toast.makeText(this, "Önce bilgisayara bağlan", Toast.LENGTH_LONG).show()
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }
        val uris = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
            Intent.ACTION_SEND_MULTIPLE ->
                IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java) ?: emptyList()
            else -> emptyList()
        }
        if (uris.isNotEmpty()) {
            sendViaService(this, uris)
            Toast.makeText(this, "${uris.size} dosya gönderiliyor", Toast.LENGTH_SHORT).show()
        } else {
            intent.getStringExtra(Intent.EXTRA_TEXT)?.let {
                Kopru.sendText(it)
                Toast.makeText(this, "Bilgisayara gönderildi", Toast.LENGTH_SHORT).show()
            }
        }
        finish()
    }
}

/** Uri okuma iznini servise devrederek gönderir (etkinlik kapansa da gönderim sürer). */
fun sendViaService(activity: Activity, uris: List<Uri>) {
    if (uris.isEmpty()) return
    val clip = ClipData.newRawUri("kopru", uris[0])
    uris.drop(1).forEach { clip.addItem(ClipData.Item(it)) }
    val i = Intent(activity, KopruService::class.java).setAction(KopruService.ACTION_SEND)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    i.clipData = clip
    activity.startService(i)
}
