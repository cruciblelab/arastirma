package lab.crucible.talktolinux.ui

import android.Manifest
import android.content.ClipboardManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.mutableStateOf
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import lab.crucible.talktolinux.core.Checks
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.core.Notifs

class MainActivity : ComponentActivity() {
    private val notifAccess = mutableStateOf(false)

    private val pickFiles = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        sendViaService(this, uris)
    }
    private val askNotifPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        // Daha önce "bir daha sorma" denmişse Android pencere göstermez: ayar sayfasına götür.
        if (!granted && Build.VERSION.SDK_INT >= 33 &&
            !shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS)) {
            Checks.open(this, Checks.appNotificationSettings(this))
        }
        UiTick.bump()
    }
    private val askBluetooth = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        Talk.refreshBluetooth()
        UiTick.bump()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // İlk açılışta izni kurulum sihirbazı ister; sihirbazı geçmiş eski kurulumlarda burada.
        if (Talk.prefs.setupDone && Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            askNotifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        setContent {
            TalkTheme {
                TalkScreen(
                    notifAccess = notifAccess.value,
                    onPickFiles = { pickFiles.launch(arrayOf("*/*")) },
                    onSendClipboard = ::sendClipboard,
                    onOpenNotifAccess = { Checks.open(this, Checks.notifAccessIntent(this)) },
                    onBluetoothPermission = ::askBluetoothPermission,
                    perms = PermActions(
                        notifications = {
                            if (Build.VERSION.SDK_INT >= 33) askNotifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                            else Checks.open(this, Checks.appNotificationSettings(this))
                        },
                        bluetooth = ::askBluetoothPermission,
                    ),
                )
            }
        }
    }

    private fun askBluetoothPermission() {
        if (Build.VERSION.SDK_INT >= 31) askBluetooth.launch(Manifest.permission.BLUETOOTH_CONNECT)
    }

    override fun onStart() {
        super.onStart()
        Talk.discoveryAcquire()
    }

    override fun onResume() {
        super.onResume()
        notifAccess.value = NotificationManagerCompat.getEnabledListenerPackages(this).contains(packageName)
        Talk.ensureListener()
        Talk.sendPhoneStatus()
        UiTick.bump()  // ayar sayfasından dönüldü: denetimler yeniden okunsun
        Notifs.stopRing(this)  // "telefonu bul" çalıyorsa: telefon bulundu
    }

    override fun onStop() {
        Talk.discoveryRelease()
        super.onStop()
    }

    private fun sendClipboard() {
        val text = getSystemService(ClipboardManager::class.java).primaryClip
            ?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
        if (text.isNullOrEmpty()) Talk.messages.tryEmit("Panoda metin yok") else Talk.sendClipboard(text)
    }
}
