package lab.crucible.talktolinux.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.rounded.Bluetooth
import androidx.compose.material.icons.rounded.Computer
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.LinkOff
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Usb
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import lab.crucible.talktolinux.core.BluetoothLink
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.net.Auth
import lab.crucible.talktolinux.net.Discovery

/** Bağlıyken alttaki sekmeler. */
enum class Tab(val label: String, val icon: ImageVector) {
    HOME("Ana sayfa", Icons.Rounded.Home),
    MEDIA("Medya", Icons.Rounded.MusicNote),
    FILES("Dosyalar", Icons.Rounded.Folder),
    PC("Bilgisayar", Icons.Rounded.Computer),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TalkScreen(
    notifAccess: Boolean,
    onPickFiles: () -> Unit,
    onSendClipboard: () -> Unit,
    onOpenNotifAccess: () -> Unit,
    onBluetoothPermission: () -> Unit = {},
    initialTab: Tab = Tab.HOME,
) {
    val state by Talk.state.collectAsState()
    val passwordFor by Talk.passwordFor.collectAsState()
    var manual by remember { mutableStateOf(false) }
    var tab by rememberSaveable { mutableStateOf(initialTab) }
    var askDisconnect by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { Talk.messages.collect { snackbar.showSnackbar(it) } }
    val connected = state as? Talk.State.Connected

    Scaffold(
        topBar = {
            if (connected != null) {
                val profile by Talk.profile.collectAsState()
                TopAppBar(
                    title = {
                        Column {
                            Text(connected.serverName, maxLines = 1, overflow = TextOverflow.Ellipsis,
                                fontWeight = FontWeight.SemiBold)
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Surface(shape = CircleShape, color = OkGreen,
                                    modifier = Modifier.size(8.dp)) {}
                                Spacer(Modifier.width(6.dp))
                                Text(listOfNotNull(kindLabel(connected.target), profile?.name).joinToString(" · "),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                            }
                        }
                    },
                    actions = {
                        IconButton(onClick = { askDisconnect = true }) { Icon(Icons.Rounded.LinkOff, "Bağlantıyı kes") }
                    },
                )
            } else {
                TopAppBar(title = { Text("Talk To Linux", fontWeight = FontWeight.SemiBold) })
            }
        },
        bottomBar = {
            if (connected != null) {
                NavigationBar {
                    Tab.entries.forEach {
                        NavigationBarItem(selected = tab == it, onClick = { tab = it },
                            icon = { Icon(it.icon, null) }, label = { Text(it.label) })
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { pad ->
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding() + 4.dp,
                bottom = pad.calculateBottomPadding() + 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            when (val s = state) {
                is Talk.State.Connected -> when (tab) {
                    Tab.HOME -> homeTab(notifAccess, onOpenNotifAccess, onPickFiles, onSendClipboard) { tab = it }
                    Tab.MEDIA -> mediaTab()
                    Tab.FILES -> filesTab(onPickFiles, onSendClipboard)
                    Tab.PC -> computerTab(s)
                }
                is Talk.State.Approval -> item { ApprovalCard(s) }
                is Talk.State.Connecting -> item { ConnectingCard(s) }
                Talk.State.Idle -> disconnected(onManual = { manual = true }, onBluetoothPermission)
            }
        }
    }
    passwordFor?.let { PasswordDialog(it) }
    if (manual) ManualDialog { manual = false }
    if (askDisconnect && connected != null) {
        AlertDialog(
            onDismissRequest = { askDisconnect = false },
            title = { Text("${connected.serverName} bağlantısı kesilsin mi?") },
            text = { Text("Kendiliğinden yeniden bağlanma da durur. Tekrar bağlanmak için listeden bilgisayarı seçersin.") },
            confirmButton = { TextButton(onClick = { askDisconnect = false; Talk.disconnect() }) { Text("Bağlantıyı kes") } },
            dismissButton = { TextButton(onClick = { askDisconnect = false }) { Text("Vazgeç") } },
        )
    }
    CommandResultDialog()
}

private fun kindLabel(t: Talk.Target) = when (t.kind) {
    "usb" -> "USB"
    "bluetooth" -> "Bluetooth"
    else -> "Wi-Fi"
}

// ---- bağlı değilken ------------------------------------------------------------

private fun LazyListScope.disconnected(onManual: () -> Unit, onBluetoothPermission: () -> Unit) {
    item {
        Text("Bilgisayarda Talk To Android açıkken burada görünür. Bir kez onayladığın bilgisayara sonra kendiliğinden bağlanılır.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 4.dp))
    }
    item { SectionTitle("Bilgisayarlar", searching = true) }
    item {
        val found by Talk.found.collectAsState()
        val usb by Talk.usbAvailable.collectAsState()
        Panel {
            if (usb) {
                ListRow(Icons.Rounded.Usb, "USB kablosu", "Kabloyla bağlı bilgisayar", onClick = {
                    Talk.connect(Talk.usbTarget())
                }) { Icon(Icons.AutoMirrored.Rounded.ArrowForward, null) }
            }
            found.sortedBy { it.name }.forEachIndexed { i, f ->
                if (i > 0 || usb) RowDivider()
                FoundRow(f)
            }
            if (found.isEmpty() && !usb) {
                ListRow(Icons.Rounded.Wifi, "Henüz bilgisayar görünmüyor",
                    "Wi-Fi: bilgisayarda “Kablosuz bağlantıyı aç”, ikisi aynı ağda olmalı. " +
                        "USB: telefonda USB hata ayıklama açık olmalı.")
            }
            RowDivider()
            ListRow(null, "IP adresiyle bağlan", onClick = onManual)
        }
    }
    item { BluetoothSection(onBluetoothPermission) }
    item { PairedList() }
}

@Composable
private fun FoundRow(f: Discovery.Found) {
    val paired = Talk.prefs.server(f.id)?.takeIf { it.fp == f.fp && it.token != null } != null
    val sub = buildString {
        append("Wi-Fi · ").append(f.host)
        if (paired) append(" · eşleşmiş") else if (f.password) append(" · şifreli")
    }
    ListRow(Icons.Rounded.Wifi, f.name, sub, onClick = {
        val t = Talk.targetOf(f)
        if (f.password && !paired) Talk.passwordFor.value = t else Talk.connect(t)
    }) {
        Icon(if (f.password && !paired) Icons.Rounded.Lock else Icons.AutoMirrored.Rounded.ArrowForward, null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun BluetoothSection(onPermission: () -> Unit) {
    val ctx = LocalContext.current
    val devices by Talk.bluetoothDevices.collectAsState()
    LaunchedEffect(Unit) { while (true) { Talk.refreshBluetooth(); delay(5000) } }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Bluetooth")
        Panel {
            when {
                !BluetoothLink.hasPermission(ctx) -> ListRow(Icons.Rounded.Bluetooth, "Bluetooth izni ver",
                    "Yalnızca eşleşmiş bilgisayarları listelemek ve onlara bağlanmak için", onClick = onPermission)
                !BluetoothLink.enabled(ctx) -> ListRow(Icons.Rounded.Bluetooth, "Bluetooth kapalı",
                    "Açınca eşleşmiş bilgisayarlar burada görünür", onClick = {
                        ctx.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    })
                devices.isEmpty() -> ListRow(Icons.Rounded.Bluetooth, "Eşleşmiş bilgisayar yok",
                    "Önce telefonun Bluetooth ayarlarından bilgisayarla eşleştir", onClick = {
                        ctx.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    })
                else -> devices.forEachIndexed { i, d ->
                    if (i > 0) RowDivider()
                    val known = Talk.prefs.servers().any { it.kind == "bluetooth" && it.host == d.address && it.token != null }
                    ListRow(Icons.Rounded.Bluetooth, d.name,
                        if (known) "Tanınıyor, onay gerekmez" else "İlk bağlantıda bilgisayarda onay istenir",
                        onClick = { Talk.connect(Talk.bluetoothTarget(d)) }) {
                        Icon(Icons.AutoMirrored.Rounded.ArrowForward, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun PairedList() {
    val state by Talk.state.collectAsState()
    var servers by remember(state) { mutableStateOf(Talk.prefs.servers()) }
    if (servers.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Eşleşmiş bilgisayarlar")
        Panel {
            servers.forEachIndexed { i, s ->
                if (i > 0) RowDivider()
                ListRow(Icons.Rounded.Computer, s.name, "Güvenlik kodu ${Auth.shortFingerprint(s.fp)}") {
                    IconButton(onClick = { Talk.forget(s.id); servers = Talk.prefs.servers() }) {
                        Icon(Icons.Rounded.Delete, "Unut", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun ApprovalCard(s: Talk.State.Approval) {
    Panel {
        Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            IconBadge(Icons.Rounded.Security, 56)
            Text("Bilgisayarda onayla", style = MaterialTheme.typography.headlineSmall)
            Text("${s.code.take(3)} ${s.code.drop(3)}", fontFamily = FontFamily.Monospace, fontSize = 44.sp,
                fontWeight = FontWeight.Bold, letterSpacing = 4.sp, color = MaterialTheme.colorScheme.primary)
            Text("Bilgisayardaki pencerede aynı kod görünüyorsa orada “Bağlan”a bas. Kod farklıysa onaylama.",
                textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
            LinearProgressIndicator(Modifier.fillMaxWidth())
            TextButton(onClick = { Talk.cancelConnecting() }) { Text("Vazgeç") }
        }
    }
}

@Composable
private fun ConnectingCard(s: Talk.State.Connecting) {
    Panel {
        Row(Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(Modifier.size(28.dp), strokeWidth = 3.dp)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text("${s.target.name} bilgisayarına bağlanılıyor", style = MaterialTheme.typography.titleMedium)
                Text(if (s.target.kind == "usb") "USB" else s.target.host, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton(onClick = { Talk.cancelConnecting() }) { Text("Vazgeç") }
        }
    }
}

@Composable
private fun PasswordDialog(t: Talk.Target) {
    var pw by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { Talk.passwordFor.value = null },
        icon = { Icon(Icons.Rounded.Lock, null) },
        title = { Text("${t.name} şifre istiyor") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(pw, { pw = it }, label = { Text("Şifre") }, singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                t.fp?.let {
                    Text("Güvenlik kodu: ${Auth.shortFingerprint(it)}\nBilgisayardaki Talk To Android penceresinde de aynısı yazmalı.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        },
        confirmButton = { TextButton(onClick = { Talk.connect(t, pw) }, enabled = pw.isNotEmpty()) { Text("Bağlan") } },
        dismissButton = { TextButton(onClick = { Talk.passwordFor.value = null }) { Text("Vazgeç") } },
    )
}

@Composable
private fun ManualDialog(onClose: () -> Unit) {
    var host by remember { mutableStateOf("") }
    var port by remember { mutableStateOf("47600") }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text("IP adresiyle bağlan") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Adres bilgisayardaki Talk To Android penceresinde, “Kablosuz” bölümünde yazar.",
                    style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(host, { host = it.trim() }, label = { Text("IP adresi") }, singleLine = true,
                    placeholder = { Text("192.168.1.20") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
                OutlinedTextField(port, { port = it.filter(Char::isDigit).take(5) }, label = { Text("Port") },
                    singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            }
        },
        confirmButton = {
            TextButton(enabled = host.isNotEmpty(), onClick = {
                onClose()
                Talk.connect(Talk.Target(host, port.toIntOrNull() ?: 47600, "wifi", null, host, null))
            }) { Text("Bağlan") }
        },
        dismissButton = { TextButton(onClick = onClose) { Text("Vazgeç") } },
    )
}
