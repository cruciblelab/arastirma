package lab.crucible.talktolinux.service

import android.app.Notification
import android.graphics.Bitmap
import android.graphics.Canvas
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Base64
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.core.PhoneMedia
import org.json.JSONObject
import java.io.ByteArrayOutputStream

/** Telefon bildirimlerini bilgisayara iletir; medya oturumlarına erişimi de sağlar. */
class NotificationListener : NotificationListenerService() {
    private val lastSent = HashMap<String, String>()

    override fun onListenerConnected() {
        PhoneMedia.start(this)
    }

    override fun onListenerDisconnected() {
        PhoneMedia.stop()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (!Talk.isConnected() || !Talk.prefs.sendNotifications) return
        if (sbn.packageName == packageName) return
        val n = sbn.notification
        // Süren işler (müzik, indirme, navigasyon) ve grup özetleri gönderilmez.
        if (sbn.isOngoing || n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        if (n.category == Notification.CATEGORY_TRANSPORT || n.category == Notification.CATEGORY_PROGRESS) return
        val extras = n.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: extras.getCharSequence(Notification.EXTRA_TEXT))
            ?.toString() ?: ""
        if (title.isEmpty() && text.isEmpty()) return
        val sig = "$title\u0000$text"
        if (lastSent[sbn.key] == sig) return  // aynı içerikle güncelleme
        lastSent[sbn.key] = sig
        if (lastSent.size > 300) lastSent.clear()

        val appName = runCatching {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(sbn.packageName, 0)).toString()
        }.getOrDefault(sbn.packageName)
        Talk.sendAppIconOnce(sbn.packageName) { iconPng(sbn.packageName) }
        Talk.send(JSONObject().put("type", "notification").put("key", sbn.key).put("package", sbn.packageName)
            .put("app", appName).put("title", title).put("text", text.take(4000)).put("time_ms", sbn.postTime))
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        if (lastSent.remove(sbn.key) != null) {
            Talk.send(JSONObject().put("type", "notification_removed").put("key", sbn.key))
        }
    }

    private fun iconPng(pkg: String): String? = runCatching {
        val d = packageManager.getApplicationIcon(pkg)
        val bmp = Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888)
        d.setBounds(0, 0, 96, 96)
        d.draw(Canvas(bmp))
        val out = ByteArrayOutputStream()
        bmp.compress(Bitmap.CompressFormat.PNG, 100, out)
        Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
    }.getOrNull()
}
