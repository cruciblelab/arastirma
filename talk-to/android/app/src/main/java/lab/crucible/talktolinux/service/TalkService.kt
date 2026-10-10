package lab.crucible.talktolinux.service

import android.annotation.SuppressLint
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.BatteryManager
import android.os.IBinder
import androidx.core.app.ServiceCompat
import androidx.core.content.IntentCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.core.Notifs
import org.json.JSONObject

/**
 * Bağlıyken telefonun uygulamayı kapatmaması için ön plan servisi. Bağlantı
 * beklenmedik koparsa 2 dakika boyunca yeniden bağlanmayı dener, sonra kapanır.
 */
class TalkService : Service() {
    companion object {
        const val ACTION_STOP = "lab.crucible.talktolinux.STOP"
        const val ACTION_STOP_RING = "lab.crucible.talktolinux.STOP_RING"
        const val ACTION_SEND = "lab.crucible.talktolinux.SEND"
        const val EXTRA_URIS = "uris"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var discovering = false
    private var lastBattery: Pair<Int, Boolean>? = null

    private val battery = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            val level = i.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) * 100 /
                i.getIntExtra(BatteryManager.EXTRA_SCALE, 100).coerceAtLeast(1)
            val status = i.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            val charging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
            val now = level to charging
            if (now != lastBattery && Talk.isConnected()) {
                lastBattery = now
                Talk.send(JSONObject().put("type", "battery").put("level", level).put("charging", charging))
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // Tür (connectedDevice) ana manifestte tanımlı; lint "tam" sürümün ek manifestine bakınca
    // görmüyor (yanlış alarm, birleştirilmiş manifest aapt ile denetlendi).
    @SuppressLint("ForegroundServiceType")
    override fun onCreate() {
        super.onCreate()
        ServiceCompat.startForeground(this, Notifs.ID_SERVICE, Notifs.service(this, "Bağlanıyor…"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        registerReceiver(battery, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        scope.launch {
            Talk.state.collectLatest { st ->
                when (st) {
                    is Talk.State.Connected -> {
                        setDiscovery(false)
                        lastBattery = null
                        registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))?.let { battery.onReceive(this@TalkService, it) }
                        update("${st.serverName} bilgisayarına bağlı (${if (st.target.kind == "usb") "USB" else "Wi-Fi"})")
                    }
                    is Talk.State.Idle -> {
                        if (Talk.prefs.autoServer == null) {
                            stopSelf()
                        } else {
                            update("Bağlantı koptu, yeniden bağlanmaya çalışılıyor…")
                            setDiscovery(true)
                            delay(120_000)
                            stopSelf()
                        }
                    }
                    else -> update("Bağlanıyor…")
                }
            }
        }
    }

    private fun update(text: String) {
        getSystemService(android.app.NotificationManager::class.java)
            .notify(Notifs.ID_SERVICE, Notifs.service(this, text))
    }

    private fun setDiscovery(on: Boolean) {
        if (on == discovering) return
        discovering = on
        if (on) Talk.discoveryAcquire() else Talk.discoveryRelease()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> Talk.disconnect()
            ACTION_STOP_RING -> Notifs.stopRing(this)
            ACTION_SEND -> {
                // Uri okuma izinleri ClipData ile servise geçer ve servis yaşadıkça sürer.
                val uris = mutableListOf<Uri>()
                intent.clipData?.let { cd -> for (i in 0 until cd.itemCount) cd.getItemAt(i).uri?.let(uris::add) }
                if (uris.isEmpty()) IntentCompat.getParcelableArrayListExtra(intent, EXTRA_URIS, Uri::class.java)?.let(uris::addAll)
                Talk.sendUris(uris)
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        setDiscovery(false)
        unregisterReceiver(battery)
        scope.cancel()
        super.onDestroy()
    }
}
