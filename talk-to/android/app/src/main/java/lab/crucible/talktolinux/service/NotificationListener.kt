package lab.crucible.talktolinux.service

import android.app.Notification
import android.graphics.Bitmap
import android.graphics.Canvas
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Base64
import lab.crucible.talktolinux.core.Calls
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.core.PhoneMedia
import org.json.JSONObject
import java.io.ByteArrayOutputStream

/** Telefon bildirimlerini bilgisayara iletir; medya oturumlarına erişimi de sağlar. */
class NotificationListener : NotificationListenerService() {
    private val lastSent = HashMap<String, String>()

    override fun onListenerConnected() {
        Talk.listenerConnected.value = true
        lab.crucible.talktolinux.ui.UiTick.bump()  // açık ekranlardaki denetimler yeniden okunsun
        // Erişim kapatılıp açıldıysa eski kayıt geçersiz: baştan kur.
        PhoneMedia.stop()
        PhoneMedia.start(this)
        Talk.sendPhoneStatus()
    }

    override fun onListenerDisconnected() {
        Talk.listenerConnected.value = false
        Talk.sendPhoneStatus()
        // Android bazen dinleyiciyi bırakıyor (bellek, güncelleme); geri bağlanmasını iste.
        runCatching { requestRebind(android.content.ComponentName(this, NotificationListener::class.java)) }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (!Talk.notificationsOn()) return
        if (sbn.packageName == packageName && sbn.tag != lab.crucible.talktolinux.core.Notifs.TEST_TAG) return
        val n = sbn.notification
        // Aramalar "süren" bildirim olsa da gönderilir: ayrı ileti, düğmeleriyle (bkz. Calls).
        if (Calls.isCall(n.category, n.extras.getString(Notification.EXTRA_TEMPLATE))) {
            sendCall(sbn)
            return
        }
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
        Talk.notificationsSent.value += 1
        Talk.send(JSONObject().put("type", "notification").put("key", sbn.key).put("package", sbn.packageName)
            .put("app", appName).put("title", title).put("text", text.take(4000)).put("time_ms", sbn.postTime))
    }

    private fun sendCall(sbn: StatusBarNotification) {
        val n = sbn.notification
        val caller = Calls.caller(n)
        val text = n.extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val state = Calls.stateOf(n)
        val buttons = n.actions.orEmpty().map { it.title?.toString().orEmpty() }
        val sig = "call\u0000$state\u0000$caller\u0000$text\u0000${buttons.joinToString("\u0000")}"
        Calls.remember(sbn.key, n.actions)
        if (lastSent[sbn.key] == sig) return
        lastSent[sbn.key] = sig
        val appName = runCatching {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(sbn.packageName, 0)).toString()
        }.getOrDefault(sbn.packageName)
        Talk.sendAppIconOnce(sbn.packageName) { iconPng(sbn.packageName) }
        val arr = org.json.JSONArray()
        buttons.forEachIndexed { i, t -> if (t.isNotBlank()) arr.put(JSONObject().put("i", i).put("title", t)) }
        Talk.send(JSONObject().put("type", "call").put("key", sbn.key).put("package", sbn.packageName)
            .put("app", appName).put("caller", caller).put("text", text.take(300)).put("state", state)
            .put("actions", arr))
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        if (Calls.forget(sbn.key)) {
            lastSent.remove(sbn.key)
            Talk.send(JSONObject().put("type", "call_ended").put("key", sbn.key))
            return
        }
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
