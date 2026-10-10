package lab.crucible.kopru.ui

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
import lab.crucible.kopru.core.Kopru

class MainActivity : ComponentActivity() {
    private val notifAccess = mutableStateOf(false)

    private val pickFiles = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        sendViaService(this, uris)
    }
    private val askNotifPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) {}

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            askNotifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        setContent {
            KopruTheme {
                KopruScreen(
                    notifAccess = notifAccess.value,
                    onPickFiles = { pickFiles.launch(arrayOf("*/*")) },
                    onSendClipboard = ::sendClipboard,
                    onOpenNotifAccess = {
                        startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    },
                )
            }
        }
    }

    override fun onStart() {
        super.onStart()
        Kopru.discoveryAcquire()
    }

    override fun onResume() {
        super.onResume()
        notifAccess.value = NotificationManagerCompat.getEnabledListenerPackages(this).contains(packageName)
    }

    override fun onStop() {
        Kopru.discoveryRelease()
        super.onStop()
    }

    private fun sendClipboard() {
        val text = getSystemService(ClipboardManager::class.java).primaryClip
            ?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
        if (text.isNullOrEmpty()) Kopru.messages.tryEmit("Panoda metin yok") else Kopru.sendClipboard(text)
    }
}
