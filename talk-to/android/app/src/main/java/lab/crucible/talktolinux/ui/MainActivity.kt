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
    /** İstek kullanıcının bastığı düğmeden mi geldi (yalnızca o zaman ayar sayfasına götürülür). */
    private var notifFromUser = false
    private val askNotifPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        // Daha önce "bir daha sorma" denmişse Android pencere göstermez: kullanıcı düğmeye bastıysa ayar sayfasına götür.
        if (!granted && notifFromUser && Build.VERSION.SDK_INT >= 33 &&
            !shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS)) {
            Checks.open(this, Checks.appNotificationSettings(this))
        }
        notifFromUser = false
        UiTick.bump()
    }
    private val askAnswer = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted && !shouldShowRequestPermissionRationale(Manifest.permission.ANSWER_PHONE_CALLS)) {
            Checks.open(this, Checks.appDetails(this))  // kalıcı reddedildiyse: uygulama ayarlarından
        }
        UiTick.bump()
    }
    private val askBluetooth = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        // Kalıcı reddedildiyse pencere çıkmaz; düğme bir şey yapmıyor gibi görünmesin.
        if (!granted && Build.VERSION.SDK_INT >= 31 &&
            !shouldShowRequestPermissionRationale(Manifest.permission.BLUETOOTH_CONNECT)) {
            Checks.open(this, Checks.appDetails(this))
        }
        Talk.refreshBluetooth()
        UiTick.bump()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // İlk açılışta izni kurulum sihirbazı ister; sihirbazı geçmiş eski kurulumlarda burada, yalnızca bir kez
        // (döndürmede, tema değişiminde ve her açılışta yeniden sorulmaz).
        if (savedInstanceState == null) handlePcIntent(intent)
        if (savedInstanceState == null && Talk.prefs.setupDone && !Talk.prefs.notifAsked && Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            Talk.prefs.notifAsked = true
            askNotifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        setContent {
            TalkTheme {
                TalkScreen(
                    notifAccess = notifAccess.value,
                    onPickFiles = { pickFiles.launch(arrayOf("*/*")) },
                    onSendClipboard = ::sendClipboard,
                    onOpenNotifAccess = { Checks.openNotifAccess(this) },
                    onBluetoothPermission = ::askBluetoothPermission,
                    perms = PermActions(
                        notifications = {
                            if (Build.VERSION.SDK_INT >= 33) {
                                notifFromUser = true
                                askNotifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                            } else Checks.open(this, Checks.appNotificationSettings(this))
                        },
                        bluetooth = ::askBluetoothPermission,
                        answerCalls = { askAnswer.launch(Manifest.permission.ANSWER_PHONE_CALLS) },
                    ),
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handlePcIntent(intent)
    }

    /** Bilgisayardaki "Bağlan" (adb ile, yalnızca adb'nin açabildiği .ui.UsbBaglan kapısından). */
    private fun handlePcIntent(intent: Intent?) {
        if (intent?.component?.className == "$packageName.ui.UsbBaglan") Talk.connectFromPc()
    }

    private fun askBluetoothPermission() {
        if (Build.VERSION.SDK_INT >= 31) askBluetooth.launch(Manifest.permission.BLUETOOTH_CONNECT)
    }

    override fun onStart() {
        super.onStart()
        Talk.uiVisible = true
        Talk.discoveryAcquire()
        // Bağlanırken uygulama arka plandaysa ön plan servisi başlatılamamış olabilir: şimdi (önde) tamamla.
        if (Talk.isConnected()) runCatching {
            ContextCompat.startForegroundService(this, Intent(this, lab.crucible.talktolinux.service.TalkService::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        notifAccess.value = Talk.notifAccessGranted()
        Talk.ensureListener()
        Talk.sendPhoneStatus()
        UiTick.bump()  // ayar sayfasından dönüldü: denetimler yeniden okunsun
        Notifs.stopRing(this)  // "telefonu bul" çalıyorsa: telefon bulundu
    }

    override fun onStop() {
        Talk.uiVisible = false
        Talk.discoveryRelease()
        super.onStop()
    }

    private fun sendClipboard() {
        // Yalnızca metin: resim/dosya kopyalanmışsa coerceToText "content://…" verir, o gönderilmez.
        val item = runCatching { getSystemService(ClipboardManager::class.java).primaryClip }.getOrNull()
            ?.takeIf { it.itemCount > 0 }?.getItemAt(0)
        val text = (item?.text ?: item?.htmlText)?.toString()
        if (text.isNullOrEmpty()) Talk.messages.tryEmit("Panoda metin yok") else Talk.sendClipboard(text)
    }
}
