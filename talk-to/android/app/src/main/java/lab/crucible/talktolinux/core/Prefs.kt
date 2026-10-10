package lab.crucible.talktolinux.core

import android.content.Context
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * Ayarlar ve eşleşilen bilgisayarlar. Her bilgisayarın kendi ayarları var
 * (bildirim gönder, medya paylaş, kendiliğinden bağlan); bağlanınca o
 * bilgisayarın ayarları uygulanır.
 */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("talktolinux", Context.MODE_PRIVATE)

    data class Server(
        val id: String, val name: String, val fp: String, val token: String?,
        val host: String, val port: Int, val kind: String,
        val notif: Boolean = true, val media: Boolean = true, val auto: Boolean = true,
    )

    val deviceId: String
        get() = sp.getString("device_id", null) ?: UUID.randomUUID().toString().replace("-", "").also {
            sp.edit().putString("device_id", it).apply()
        }

    var deviceName: String
        get() = sp.getString("device_name", null) ?: Build.MODEL
        set(v) = sp.edit().putString("device_name", v).apply()

    /** İlk açılıştaki kurulum sihirbazı bitirildi ya da atlandı. */
    var setupDone: Boolean
        get() = sp.getBoolean("setup_done", false)
        set(v) = sp.edit().putBoolean("setup_done", v).apply()

    /** Kullanıcı "bağlantıyı kes" demediyse otomatik yeniden bağlanılacak bilgisayar. */
    var autoServer: String?
        get() = sp.getString("auto_server", null)
        set(v) = sp.edit().putString("auto_server", v).apply()

    fun servers(): List<Server> {
        val arr = JSONArray(sp.getString("servers", "[]"))
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            Server(o.getString("id"), o.optString("name"), o.getString("fp"),
                o.optString("token").ifEmpty { null }, o.optString("host"), o.optInt("port", 47600),
                o.optString("kind", "wifi"), o.optBoolean("notif", true), o.optBoolean("media", true),
                o.optBoolean("auto", true))
        }
    }

    fun server(id: String?) = servers().firstOrNull { it.id == id }
    fun serverByFp(fp: String) = servers().firstOrNull { it.fp == fp }

    private fun write(list: List<Server>) {
        val arr = JSONArray()
        list.forEach {
            arr.put(JSONObject().put("id", it.id).put("name", it.name).put("fp", it.fp)
                .put("token", it.token ?: "").put("host", it.host).put("port", it.port).put("kind", it.kind)
                .put("notif", it.notif).put("media", it.media).put("auto", it.auto))
        }
        sp.edit().putString("servers", arr.toString()).apply()
    }

    /** Kaydeder; aynı bilgisayar daha önce kayıtlıysa onun ayarları korunur. */
    fun saveServer(s: Server) {
        val old = servers().firstOrNull { it.id == s.id || it.fp == s.fp }
        val merged = if (old != null) s.copy(notif = old.notif, media = old.media, auto = old.auto) else s
        write(servers().filter { it.id != s.id && it.fp != s.fp } + merged)
    }

    fun updateServer(id: String, change: (Server) -> Server) {
        write(servers().map { if (it.id == id) change(it) else it })
    }

    fun forgetServer(id: String) {
        write(servers().filter { it.id != id })
        if (autoServer == id) autoServer = null
    }
}
