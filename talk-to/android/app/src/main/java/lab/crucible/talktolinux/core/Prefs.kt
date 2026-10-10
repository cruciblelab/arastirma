package lab.crucible.talktolinux.core

import android.content.Context
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/** Ayarlar ve eşleşilen bilgisayarlar (belirteç + sabitlenmiş parmak izi). */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("talktolinux", Context.MODE_PRIVATE)

    data class Server(
        val id: String, val name: String, val fp: String, val token: String?,
        val host: String, val port: Int, val kind: String,
    )

    val deviceId: String
        get() = sp.getString("device_id", null) ?: UUID.randomUUID().toString().replace("-", "").also {
            sp.edit().putString("device_id", it).apply()
        }

    var deviceName: String
        get() = sp.getString("device_name", null) ?: Build.MODEL
        set(v) = sp.edit().putString("device_name", v).apply()

    var sendNotifications: Boolean
        get() = sp.getBoolean("send_notifications", true)
        set(v) = sp.edit().putBoolean("send_notifications", v).apply()

    var shareMedia: Boolean
        get() = sp.getBoolean("share_media", true)
        set(v) = sp.edit().putBoolean("share_media", v).apply()

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
                o.optString("kind", "wifi"))
        }
    }

    fun server(id: String?) = servers().firstOrNull { it.id == id }
    fun serverByFp(fp: String) = servers().firstOrNull { it.fp == fp }

    fun saveServer(s: Server) {
        val list = servers().filter { it.id != s.id && it.fp != s.fp } + s
        val arr = JSONArray()
        list.forEach {
            arr.put(JSONObject().put("id", it.id).put("name", it.name).put("fp", it.fp)
                .put("token", it.token ?: "").put("host", it.host).put("port", it.port).put("kind", it.kind))
        }
        sp.edit().putString("servers", arr.toString()).apply()
    }

    fun forgetServer(id: String) {
        val arr = JSONArray()
        servers().filter { it.id != id }.forEach {
            arr.put(JSONObject().put("id", it.id).put("name", it.name).put("fp", it.fp)
                .put("token", it.token ?: "").put("host", it.host).put("port", it.port).put("kind", it.kind))
        }
        sp.edit().putString("servers", arr.toString()).apply()
        if (autoServer == id) autoServer = null
    }
}
