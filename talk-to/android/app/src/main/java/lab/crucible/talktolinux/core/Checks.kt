package lab.crucible.talktolinux.core

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.content.ContextCompat
import lab.crucible.talktolinux.BuildConfig
import lab.crucible.talktolinux.service.NotificationListener

/** Kurulum sihirbazı ve "İzinler ve yetkiler" ekranının denetimleri ve açtığı ayar sayfaları. */
object Checks {
    fun postNotifications(ctx: Context) = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    fun notifAccess() = Talk.notifAccessGranted()

    fun listener() = Talk.listenerConnected.value

    fun battery(ctx: Context) = runCatching {
        ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)
    }.getOrDefault(true)

    fun developerOptions(ctx: Context) =
        Settings.Global.getInt(ctx.contentResolver, Settings.Global.DEVELOPMENT_SETTINGS_ENABLED, 0) == 1

    fun usbDebugging(ctx: Context) = Settings.Global.getInt(ctx.contentResolver, Settings.Global.ADB_ENABLED, 0) == 1

    fun onWifi(ctx: Context): Boolean = runCatching {
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        cm.getNetworkCapabilities(cm.activeNetwork)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
    }.getOrDefault(false)

    fun bluetoothReady(ctx: Context) = BluetoothLink.hasPermission(ctx) && BluetoothLink.enabled(ctx)

    // ---- ayar sayfaları -----------------------------------------------------------

    /** Android 11+: doğrudan Talk To Linux'un bildirim erişimi anahtarı; daha eskide liste. */
    fun notifAccessIntent(ctx: Context): Intent =
        if (Build.VERSION.SDK_INT >= 30) Intent(Settings.ACTION_NOTIFICATION_LISTENER_DETAIL_SETTINGS)
            .putExtra(Settings.EXTRA_NOTIFICATION_LISTENER_COMPONENT_NAME,
                ComponentName(ctx, NotificationListener::class.java).flattenToString())
        else Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)

    fun appNotificationSettings(ctx: Context): Intent =
        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)

    /** Uygulama bilgisi: pil, izinler ve Android 13+'ta "Kısıtlanmış ayarlara izin ver" buradan. */
    fun appDetails(ctx: Context): Intent =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", ctx.packageName, null))

    fun batterySettings(): Intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)

    /** Geliştirici seçenekleri açıksa oraya; değilse "Telefon hakkında" (yapım numarasına 7 kez dokunulur). */
    fun developerSettings(ctx: Context): Intent =
        if (developerOptions(ctx)) Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS)
        else Intent(Settings.ACTION_DEVICE_INFO_SETTINGS)

    fun wifiSettings(): Intent = Intent(Settings.ACTION_WIFI_SETTINGS)

    fun bluetoothSettings(): Intent = Intent(Settings.ACTION_BLUETOOTH_SETTINGS)

    /** Ayar sayfasını açar; bu telefonda o sayfa yoksa genel ayarlara düşer. */
    fun open(ctx: Context, intent: Intent, fallback: Intent = Intent(Settings.ACTION_SETTINGS)) {
        val flags = Intent.FLAG_ACTIVITY_NEW_TASK
        try {
            ctx.startActivity(intent.addFlags(flags))
        } catch (_: ActivityNotFoundException) {
            runCatching { ctx.startActivity(fallback.addFlags(flags)) }
        } catch (_: SecurityException) {
            runCatching { ctx.startActivity(fallback.addFlags(flags)) }
        }
    }

    /** Bu sürümde bildirim/medya özelliği var mı (hafif sürümde yok). */
    val hasNotifications get() = BuildConfig.NOTIFICATIONS

    /** Bilgisayardaki profil izinlerinin Türkçe adları (bilgisayardaki Config.PERMISSIONS ile aynı). */
    val PROFILE_PERMISSIONS = linkedMapOf(
        "notifications" to "Bildirimlerin bilgisayarda gösterilmesi",
        "media" to "Medya kontrolü (iki yön)",
        "files" to "Dosya gönderme",
        "clipboard" to "Pano paylaşımı",
        "open_url" to "Bağlantıyı bilgisayarın tarayıcısında açma",
        "commands" to "Bilgisayar komutlarını çalıştırma",
        "power" to "Uyku / kapat / yeniden başlat",
        "screenshot" to "Bilgisayarın ekran görüntüsünü alma",
    )
}
