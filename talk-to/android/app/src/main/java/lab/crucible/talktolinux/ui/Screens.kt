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
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.DropdownMenu
import androidx.compose.material.icons.rounded.Lan
import androidx.compose.material.icons.rounded.MoreVert
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
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
import lab.crucible.talktolinux.core.Checks
import lab.crucible.talktolinux.core.Features
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
    perms: PermActions = PermActions(bluetooth = onBluetoothPermission),
    showSetup: Boolean = !Talk.prefs.setupDone,
) {
    // Ana ekran, ilk açılıştaki kurulum sihirbazı ya da "İzinler ve yetkiler".
    var screen by rememberSaveable { mutableStateOf(if (showSetup) "kurulum" else "ana") }
    // Sihirbaz İzinler ekranından açıldıysa bitince/geri tuşunda oraya dönülür.
    var wizardFrom by rememberSaveable { mutableStateOf("ana") }
    // Seçili sekme alt ekranlara gidip dönünce sıfırlanmasın: when'den önce tanımlanır.
    var tab by rememberSaveable { mutableStateOf(initialTab) }
    var manual by remember { mutableStateOf(false) }
    var askDisconnect by remember { mutableStateOf(false) }
    // Bilgisayardan "Bağlan" gelince sihirbaz kapanır: adımları bilgisayar yapıyor, telefonda tekrar gerekmez.
    // Yalnızca yeni gelen istek için (döndürmede ya da sihirbaz sonradan elle açılınca kapatılmasın).
    val pcConnect by Talk.pcConnect.collectAsState()
    var pcHandled by rememberSaveable { mutableIntStateOf(Talk.pcConnect.value) }
    LaunchedEffect(pcConnect) {
        if (pcConnect != pcHandled) {
            pcHandled = pcConnect
            if (screen == "kurulum") screen = "ana"
        }
    }
    when (screen) {
        "kurulum" -> {
            SetupWizard(perms, onBack = if (wizardFrom == "izinler") ({ screen = "izinler" }) else null) {
                Talk.prefs.setupDone = true
                screen = wizardFrom
            }
            return
        }
        "izinler" -> {
            PermissionsScreen(perms, onBack = { screen = "ana" },
                onOpenWizard = { wizardFrom = "izinler"; screen = "kurulum" })
            return
        }
        "ozellikler" -> {
            FeaturesScreen(onBack = { screen = "ana" })
            return
        }
    }
    val state by Talk.state.collectAsState()
    val passwordFor by Talk.passwordFor.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { Talk.messages.collect { snackbar.showSnackbar(it) } }
    val connected = state as? Talk.State.Connected
    val list = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val openPerms = { screen = "izinler" }
    val openFeatures = { screen = "ozellikler" }
    // Basit modda Dosyalar sekmesi yok (Features); gizlenen sekmede kalınmaz.
    val enabled by Features.enabled.collectAsState()
    val tabs = Tab.entries.filter { it != Tab.FILES || "files" in enabled }
    val shown = if (tab in tabs) tab else Tab.HOME

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
                                // Renk tek başına anlam taşımasın: noktanın yanında "bağlı" yazar (T1).
                                Text(listOfNotNull("${kindLabel(connected.target)} ile bağlı", profile?.name)
                                    .joinToString(" · "),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                            }
                        }
                    },
                    actions = {
                        MoreMenu(
                            "İzinler ve yetkiler" to openPerms,
                            "Görünüm ve özellikler" to openFeatures,
                            "Kurulum yardımcısı" to { wizardFrom = "ana"; screen = "kurulum" },
                            "Bağlantıyı kes" to { askDisconnect = true },
                        )
                    },
                )
            } else {
                TopAppBar(title = { Text("Talk To", fontWeight = FontWeight.SemiBold) }, actions = {
                    MoreMenu(
                        "İzinler ve yetkiler" to openPerms,
                        "Görünüm ve özellikler" to openFeatures,
                        "Kurulum yardımcısı" to { wizardFrom = "ana"; screen = "kurulum" },
                    )
                })
            }
        },
        bottomBar = {
            if (connected != null) {
                // libadwaita görünüm değiştirici çubuğu gibi: seçili sekme hafif gri zeminli, renk vurgusuz.
                NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceVariant) {
                    tabs.forEach {
                        NavigationBarItem(selected = shown == it, onClick = {
                            // Seçili sekmeye yeniden dokunmak başa kaydırır (M3 gezinme çubuğu).
                            if (shown == it) scope.launch { list.animateScrollToItem(0) } else tab = it
                        }, icon = { Icon(it.icon, null) }, label = { Text(it.label) },
                            colors = NavigationBarItemDefaults.colors(
                                indicatorColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.10f),
                                selectedIconColor = MaterialTheme.colorScheme.onSurface,
                                selectedTextColor = MaterialTheme.colorScheme.onSurface,
                                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant))
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { pad ->
        LazyColumn(
            state = list,
            contentPadding = PaddingValues(start = Gap.screen, end = Gap.screen, top = pad.calculateTopPadding() + 8.dp,
                bottom = pad.calculateBottomPadding() + Gap.section),
            verticalArrangement = Arrangement.spacedBy(Gap.section),
        ) {
            when (val s = state) {
                is Talk.State.Connected -> when (shown) {
                    Tab.HOME -> homeTab(notifAccess, onOpenNotifAccess, onPickFiles, onSendClipboard, openPerms,
                        openFeatures, enabled) { tab = it }
                    Tab.MEDIA -> mediaTab()
                    Tab.FILES -> filesTab(onPickFiles, onSendClipboard)
                    Tab.PC -> computerTab(s, enabled)
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
            text = { Text("Kendiliğinden yeniden bağlanma da durur. Eşleşme silinmez; yeniden bağlanmak için " +
                "listeden bilgisayarı seçmen yeter.") },
            confirmButton = { TextButton(onClick = { askDisconnect = false; Talk.disconnect() }) { Text("Bağlantıyı kes") } },
            dismissButton = { TextButton(onClick = { askDisconnect = false }) { Text("Vazgeç") } },
        )
    }
    CommandResultDialog()
}

/** Üç nokta menüsü: her seçenek yazılı (yazısız simge yerine, T3/A3). */
@Composable
private fun MoreMenu(vararg items: Pair<String, () -> Unit>) {
    var open by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { open = true }) { Icon(Icons.Rounded.MoreVert, "Diğer seçenekler") }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            items.forEach { (label, run) ->
                DropdownMenuItem(text = { Text(label) }, onClick = { open = false; run() })
            }
        }
    }
}

private fun kindLabel(t: Talk.Target) = when (t.kind) {
    "usb" -> "USB"
    "bluetooth" -> "Bluetooth"
    else -> "Wi-Fi"
}

// ---- bağlı değilken ------------------------------------------------------------

private fun LazyListScope.disconnected(onManual: () -> Unit, onBluetoothPermission: () -> Unit) {
    item {
        // "Bağlı değil" bir hata değil: nötr (T5).
        StatusCard(Icons.Rounded.Computer, "Bir bilgisayara bağlı değil",
            "Bilgisayarda Talk To açıkken aşağıda görünür. Bir kez eşleştirdiğin bilgisayara sonra " +
                "kendiliğinden bağlanılır.")
    }
    item {
        val found by Talk.found.collectAsState()
        val usb by Talk.usbAvailable.collectAsState()
        Section("Bulunan bilgisayarlar", searching = true) {
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
                    ListRow(Icons.Rounded.Wifi, "Aranıyor…",
                        "Wi-Fi: bilgisayarda “Kablosuz bağlantı” açık ve ikisi aynı ağda olmalı. " +
                            "USB: kabloyu tak, telefonda USB hata ayıklama açık olmalı.")
                }
            }
        }
    }
    item { BluetoothSection(onBluetoothPermission) }
    item { PairedList() }
    item {
        // Teknik yol varsayılan akışta değil (T11).
        Section("Diğer yollar") {
            Panel {
                ListRow(Icons.Rounded.Lan, "IP adresiyle bağlan",
                    "Bilgisayar listede görünmüyorsa: adresi bilgisayardaki pencerede yazar", onClick = onManual) {
                    Icon(Icons.AutoMirrored.Rounded.ArrowForward, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
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
    // İzin ve açık/kapalı durumu akış değil: döngüdeki tik ve dönüşteki UiTick ile yeniden okunur.
    var tick by remember { mutableIntStateOf(0) }
    UiTick.tick.collectAsState().value
    LaunchedEffect(Unit) { while (true) { if (Talk.uiVisible) { Talk.refreshBluetooth(); tick++ }; delay(3000) } }
    tick
    Section("Bluetooth") {
        Panel {
            when {
                !BluetoothLink.hasPermission(ctx) -> ListRow(Icons.Rounded.Bluetooth, "Bluetooth izni ver",
                    "Yalnızca eşleşmiş bilgisayarları listelemek ve onlara bağlanmak için", onClick = onPermission)
                !BluetoothLink.enabled(ctx) -> ListRow(Icons.Rounded.Bluetooth, "Bluetooth kapalı",
                    "Açınca eşleşmiş bilgisayarlar burada görünür", onClick = {
                        Checks.open(ctx, Checks.bluetoothSettings())
                    })
                devices.isEmpty() -> ListRow(Icons.Rounded.Bluetooth, "Eşleşmiş bilgisayar yok",
                    "Önce telefonun Bluetooth ayarlarından bilgisayarla eşleştir", onClick = {
                        Checks.open(ctx, Checks.bluetoothSettings())
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
    var forget by remember { mutableStateOf<lab.crucible.talktolinux.core.Prefs.Server?>(null) }
    forget?.let { s ->
        ForgetDialog(s.name, onDismiss = { forget = null }) {
            Talk.forget(s.id)
            servers = Talk.prefs.servers()
            forget = null
        }
    }
    if (servers.isEmpty()) return
    Section("Eşleşmiş bilgisayarlar") {
        Panel {
            servers.forEachIndexed { i, s ->
                if (i > 0) RowDivider()
                ListRow(Icons.Rounded.Computer, s.name, "Güvenlik kodu ${Auth.shortFingerprint(s.fp)}") {
                    IconButton(onClick = { forget = s }) {
                        Icon(Icons.Rounded.Delete, "Unut", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

/**
 * Eşleşme: stresli an, tek iş (Norman). Numara 3+3 gruplu ve bilgisayardakiyle aynı biçimde; karar
 * bilgisayarda "Numaralar aynı / Numaralar farklı" ile verilir (Uzun ve ark. 2007).
 */
@Composable
private fun ApprovalCard(s: Talk.State.Approval) {
    Panel {
        Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            IconBadge(Icons.Rounded.Security, 56)
            Text("Numaraları karşılaştır", style = MaterialTheme.typography.headlineSmall)
            Text(groupedCode(s.code), fontFamily = FontFamily.Monospace, fontSize = 44.sp,
                fontWeight = FontWeight.Bold, letterSpacing = 4.sp, color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.semantics { contentDescription = "Eşleşme numarası ${s.code.toList().joinToString(" ")}" })
            Text("Bilgisayarda da aynı numara görünüyorsa orada “Numaralar aynı”yı seç; farklıysa " +
                "“Numaralar farklı”yı. Bu numarayı bir yere yazmana gerek yok.",
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
                    Text("Güvenlik kodu: ${Auth.shortFingerprint(it)}\nBilgisayardaki Talk To penceresinde de aynısı yazmalı.",
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
                Text("Adres bilgisayardaki Talk To penceresinde, “Kablosuz” bölümünde yazar.",
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
