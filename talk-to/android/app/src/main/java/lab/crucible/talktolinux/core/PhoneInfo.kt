package lab.crucible.talktolinux.core

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.os.SystemClock
import lab.crucible.talktolinux.BuildConfig
import org.json.JSONObject

/**
 * Telefonun sistem bilgileri (bilgisayarda üst karttaki baloncuğa tıklayınca görünür): model, Android
 * sürümü, pil (sıcaklık, sağlık), depolama, bellek, ağ türü, açık kalma süresi. Yalnızca izin gerektirmeyen
 * bilgiler; Wi-Fi adı (konum izni ister) ve telefon numarası gibi kişisel şeyler gönderilmez.
 */
object PhoneInfo {
    fun collect(ctx: Context): JSONObject {
        val o = JSONObject()
            .put("type", "phone_info")
            .put("manufacturer", Build.MANUFACTURER)
            .put("model", Build.MODEL)
            .put("android", Build.VERSION.RELEASE)
            .put("sdk", Build.VERSION.SDK_INT)
            .put("security_patch", Build.VERSION.SECURITY_PATCH)
            // Bilgisayar USB'deki telefonla bu bağlantıyı eşleştirsin (adb'den ro.build.fingerprint okunur).
            .put("fingerprint", Build.FINGERPRINT)
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("uptime_s", SystemClock.elapsedRealtime() / 1000)
        runCatching {
            val b = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            if (b != null) {
                val level = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                val scale = b.getIntExtra(BatteryManager.EXTRA_SCALE, 100).coerceAtLeast(1)
                val status = b.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                o.put("battery", JSONObject()
                    .put("level", if (level >= 0) level * 100 / scale else JSONObject.NULL)
                    .put("charging", status == BatteryManager.BATTERY_STATUS_CHARGING ||
                        status == BatteryManager.BATTERY_STATUS_FULL)
                    .put("temp_c", b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
                        .takeIf { it != Int.MIN_VALUE }?.let { it / 10.0 } ?: JSONObject.NULL)
                    .put("health", health(b.getIntExtra(BatteryManager.EXTRA_HEALTH, 0))))
            }
        }
        runCatching {
            val s = StatFs(Environment.getDataDirectory().path)
            o.put("storage", JSONObject().put("total", s.totalBytes).put("free", s.availableBytes))
        }
        runCatching {
            val mi = ActivityManager.MemoryInfo()
            ctx.getSystemService(ActivityManager::class.java).getMemoryInfo(mi)
            o.put("ram", JSONObject().put("total", mi.totalMem).put("free", mi.availMem))
        }
        runCatching {
            val cm = ctx.getSystemService(ConnectivityManager::class.java)
            val caps = cm.getNetworkCapabilities(cm.activeNetwork)
            o.put("network", when {
                caps == null -> "none"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
                else -> "other"
            })
        }
        return o
    }

    private fun health(h: Int) = when (h) {
        BatteryManager.BATTERY_HEALTH_GOOD -> "good"
        BatteryManager.BATTERY_HEALTH_OVERHEAT -> "overheat"
        BatteryManager.BATTERY_HEALTH_DEAD -> "dead"
        BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> "over_voltage"
        BatteryManager.BATTERY_HEALTH_COLD -> "cold"
        else -> JSONObject.NULL
    }
}
