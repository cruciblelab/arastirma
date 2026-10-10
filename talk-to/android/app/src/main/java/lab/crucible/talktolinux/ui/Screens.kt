package lab.crucible.talktolinux.ui

import android.content.Intent
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.VolumeOff
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.AccountCircle
import androidx.compose.material.icons.rounded.Bedtime
import androidx.compose.material.icons.rounded.Bluetooth
import androidx.compose.material.icons.rounded.PowerSettingsNew
import androidx.compose.material.icons.rounded.RestartAlt
import androidx.compose.material.icons.rounded.Screenshot
import androidx.compose.material.icons.rounded.Terminal
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Computer
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material.icons.rounded.SkipPrevious
import androidx.compose.material.icons.rounded.Upload
import androidx.compose.material.icons.rounded.UploadFile
import androidx.compose.material.icons.rounded.Usb
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.layout.ContentScale
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
import lab.crucible.talktolinux.BuildConfig
import lab.crucible.talktolinux.core.BluetoothLink
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.net.Auth
import lab.crucible.talktolinux.net.ClientSession
import lab.crucible.talktolinux.net.Discovery

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TalkScreen(
    notifAccess: Boolean,
    onPickFiles: () -> Unit,
    onSendClipboard: () -> Unit,
    onOpenNotifAccess: () -> Unit,
    onBluetoothPermission: () -> Unit = {},
) {
    val state by Talk.state.collectAsState()
    val passwordFor by Talk.passwordFor.collectAsState()
    var manual by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { Talk.messages.collect { snackbar.showSnackbar(it) } }
    val scroll = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    Scaffold(
        modifier = Modifier.nestedScroll(scroll.nestedScrollConnection),
        topBar = { LargeTopAppBar(title = { Text("Talk To Linux", fontWeight = FontWeight.SemiBold) }, scrollBehavior = scroll) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { pad ->
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding() + 4.dp,
                bottom = pad.calculateBottomPadding() + 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            when (val s = state) {
                is Talk.State.Connected -> connected(s, notifAccess, onPickFiles, onSendClipboard, onOpenNotifAccess)
                is Talk.State.Approval -> item { ApprovalCard(s) }
                is Talk.State.Connecting -> item { ConnectingCard(s) }
                Talk.State.Idle -> disconnected(onManual = { manual = true }, onBluetoothPermission)
            }
        }
    }
    passwordFor?.let { PasswordDialog(it) }
    if (manual) ManualDialog { manual = false }
    CommandResultDialog()
}

// ---- bağlı değilken ------------------------------------------------------------

private fun LazyListScope.disconnected(onManual: () -> Unit, onBluetoothPermission: () -> Unit) {
    item {
        Hero(Icons.Rounded.Computer, "Bilgisayara bağlan",
            "Bilgisayarda Talk To Android uygulamasını aç. Aynı Wi-Fi'deysen aşağıda görünür; kabloyla bağlanmak için USB'yi seç.")
    }
    item { SectionTitle("Yakındaki bilgisayarlar", searching = true) }
    item {
        val found by Talk.found.collectAsState()
        val usb by Talk.usbAvailable.collectAsState()
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (usb) {
                ServerCard(Icons.Rounded.Usb, "USB kablosu", "Bilgisayardaki Talk To Android uygulamasına kabloyla bağlan", false) {
                    Talk.connect(Talk.usbTarget())
                }
            }
            found.sortedBy { it.name }.forEach { f -> FoundCard(f) }
            if (found.isEmpty() && !usb) EmptyHint()
            OutlinedButton(onClick = onManual, modifier = Modifier.fillMaxWidth()) { Text("IP adresiyle bağlan") }
        }
    }
    item { BluetoothSection(onBluetoothPermission) }
    item { PairedList() }
}

@Composable
private fun BluetoothSection(onPermission: () -> Unit) {
    val ctx = LocalContext.current
    val devices by Talk.bluetoothDevices.collectAsState()
    LaunchedEffect(Unit) { while (true) { Talk.refreshBluetooth(); delay(5000) } }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionTitle("Bluetooth")
        when {
            !BluetoothLink.hasPermission(ctx) -> InfoCard(Icons.Rounded.Bluetooth, "Bluetooth ile bağlanmak için izin ver",
                "Yalnızca telefonla önceden eşleştirilmiş bilgisayarları listelemek ve onlara bağlanmak için.",
                "İzin ver", onPermission)
            !BluetoothLink.enabled(ctx) -> InfoCard(Icons.Rounded.Bluetooth, "Bluetooth kapalı",
                "Bluetooth'u açınca eşleşmiş bilgisayarların burada görünür.", "Bluetooth ayarları") {
                ctx.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
            }
            devices.isEmpty() -> InfoCard(Icons.Rounded.Bluetooth, "Eşleşmiş bilgisayar yok",
                "Önce telefonun Bluetooth ayarlarından bilgisayarla eşleştir; bilgisayarda Talk To Android → " +
                    "Bluetooth açık olmalı.", "Bluetooth ayarları") {
                ctx.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
            }
            else -> devices.forEach { d ->
                val known = Talk.prefs.servers().any { it.kind == "bluetooth" && it.host == d.address && it.token != null }
                ServerCard(Icons.Rounded.Bluetooth, d.name,
                    if (known) "Bluetooth · tanınıyor, onay gerekmez" else "Bluetooth · ilk bağlantıda bilgisayarda onay istenir",
                    false) { Talk.connect(Talk.bluetoothTarget(d)) }
            }
        }
    }
}

@Composable
private fun InfoCard(icon: ImageVector, title: String, text: String, action: String, onClick: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(10.dp))
                Text(title, style = MaterialTheme.typography.titleSmall)
            }
            Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            FilledTonalButton(onClick = onClick) { Text(action) }
        }
    }
}

@Composable
private fun FoundCard(f: Discovery.Found) {
    val paired = Talk.prefs.server(f.id)?.takeIf { it.fp == f.fp && it.token != null } != null
    val sub = buildString {
        append(f.host)
        if (paired) append(" · eşleşmiş") else if (f.password) append(" · şifreli")
    }
    ServerCard(Icons.Rounded.Wifi, f.name, sub, f.password && !paired) {
        val t = Talk.targetOf(f)
        if (f.password && !paired) Talk.passwordFor.value = t else Talk.connect(t)
    }
}

@Composable
private fun EmptyHint() {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Henüz bilgisayar görünmüyor", style = MaterialTheme.typography.titleSmall)
            Text("• Wi-Fi: bilgisayarda Talk To Android → “Kablosuz bağlantıyı aç”. Telefon ve bilgisayar aynı ağda olmalı.\n" +
                "• USB: telefonda Geliştirici seçenekleri → USB hata ayıklama'yı aç, kabloyu tak, " +
                "telefonda çıkan “USB hata ayıklamaya izin ver” sorusunu onayla.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
            servers.forEachIndexed { i, s ->
                if (i > 0) HorizontalDivider()
                Row(Modifier.padding(start = 16.dp, end = 4.dp, top = 6.dp, bottom = 6.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(s.name, style = MaterialTheme.typography.bodyLarge)
                        Text("Güvenlik kodu ${Auth.shortFingerprint(s.fp)}", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    IconButton(onClick = { Talk.forget(s.id); servers = Talk.prefs.servers() }) {
                        Icon(Icons.Rounded.Delete, "Unut")
                    }
                }
            }
        }
    }
}

@Composable
private fun ApprovalCard(s: Talk.State.Approval) {
    ElevatedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            IconBadge(Icons.Rounded.Security)
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
    ElevatedCard(Modifier.fillMaxWidth()) {
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

// ---- bağlıyken ------------------------------------------------------------------

private fun LazyListScope.connected(
    s: Talk.State.Connected, notifAccess: Boolean, onPickFiles: () -> Unit,
    onSendClipboard: () -> Unit, onOpenNotifAccess: () -> Unit,
) {
    item { ConnectedHeader(s) }
    if (BuildConfig.NOTIFICATIONS && !notifAccess) item { PermissionCard(onOpenNotifAccess) }
    item { PcMediaCard() }
    item {
        val profile by Talk.profile.collectAsState()
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (profile?.can("files") != false)
                ActionTile(Icons.Rounded.UploadFile, "Dosya gönder", Modifier.weight(1f), onPickFiles)
            if (profile?.can("clipboard") != false)
                ActionTile(Icons.Rounded.ContentPaste, "Panoyu gönder", Modifier.weight(1f), onSendClipboard)
        }
    }
    item { ComputerCard() }
    item { Transfers() }
    item { SettingsCard(s) }
}

@Composable
private fun ConnectedHeader(s: Talk.State.Connected) {
    val cs = MaterialTheme.colorScheme
    Box(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp))
            .background(Brush.linearGradient(listOf(cs.primary, cs.tertiary)))
            .padding(22.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(56.dp).clip(RoundedCornerShape(18.dp)).background(cs.onPrimary.copy(alpha = 0.18f)),
                    contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.Computer, null, tint = cs.onPrimary, modifier = Modifier.size(30.dp))
                }
                Spacer(Modifier.width(16.dp))
                Column {
                    Text(s.serverName, style = MaterialTheme.typography.headlineSmall, color = cs.onPrimary,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(when (s.target.kind) {
                        "usb" -> "USB ile bağlı"
                        "bluetooth" -> "Bluetooth ile bağlı"
                        else -> "Wi-Fi ile bağlı · ${s.target.host}"
                    }, color = cs.onPrimary.copy(alpha = 0.85f))
                }
            }
            val profile by Talk.profile.collectAsState()
            profile?.let {
                Row(Modifier.clip(RoundedCornerShape(50)).background(cs.onPrimary.copy(alpha = 0.18f))
                    .padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.AccountCircle, null, tint = cs.onPrimary, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Bilgisayar seni “${it.name}” profiliyle tanıyor", color = cs.onPrimary,
                        style = MaterialTheme.typography.labelLarge)
                }
            }
            FilledTonalButton(onClick = { Talk.disconnect() }) { Text("Bağlantıyı kes") }
        }
    }
}

@Composable
private fun PermissionCard(onOpen: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Notifications, null)
                Spacer(Modifier.width(10.dp))
                Text("Bildirim erişimi gerekli", style = MaterialTheme.typography.titleMedium)
            }
            Text("Bildirimlerin bilgisayarda görünmesi ve telefonda çalan müziğin (Spotify, YouTube…) " +
                "bilgisayardan kontrol edilmesi için Talk To Linux uygulamasına bildirim erişimi ver.")
            FilledTonalButton(onClick = onOpen) { Text("İzin ver") }
        }
    }
}

@Composable
private fun PcMediaCard() {
    val m by Talk.pcMedia.collectAsState()
    val art by Talk.pcArt.collectAsState()
    ElevatedCard(Modifier.fillMaxWidth()) {
        val media = m
        if (media == null) {
            Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                IconBadge(Icons.Rounded.MusicNote)
                Spacer(Modifier.width(14.dp))
                Column {
                    Text("Bilgisayarda çalan bir şey yok", style = MaterialTheme.typography.titleMedium)
                    Text("Spotify, VLC ya da tarayıcıda YouTube açınca buradan kontrol edebilirsin.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            return@ElevatedCard
        }
        var now by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
        LaunchedEffect(media) { while (true) { now = SystemClock.elapsedRealtime(); delay(500) } }
        val pos = (media.positionMs + if (media.playing) now - media.receivedAt else 0)
            .coerceAtMost(media.durationMs.takeIf { it > 0 } ?: Long.MAX_VALUE)
        var seeking by remember { mutableStateOf<Float?>(null) }

        Column(Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                val bmp = art?.takeIf { it.first == media.artId }?.second
                Box(Modifier.size(84.dp).clip(RoundedCornerShape(16.dp))
                    .background(MaterialTheme.colorScheme.secondaryContainer), contentAlignment = Alignment.Center) {
                    if (bmp != null) Image(bmp.asImageBitmap(), null, contentScale = ContentScale.Crop,
                        modifier = Modifier.size(84.dp))
                    else Icon(Icons.Rounded.MusicNote, null, Modifier.size(36.dp))
                }
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f)) {
                    Text("Bilgisayarda · ${media.player}", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary)
                    Text(media.title.ifEmpty { "Bilinmeyen parça" }, style = MaterialTheme.typography.titleLarge,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    if (media.artist.isNotEmpty()) Text(media.artist, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if (media.durationMs > 0) {
                Slider(value = seeking ?: pos.toFloat(), onValueChange = { seeking = it },
                    onValueChangeFinished = { seeking?.let { Talk.mediaControl("seek", it.toLong()) }; seeking = null },
                    valueRange = 0f..media.durationMs.toFloat(), enabled = media.canSeek,
                    modifier = Modifier.padding(top = 8.dp))
                Row {
                    Text(mmss((seeking?.toLong() ?: pos)), style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(1f))
                    Text(mmss(media.durationMs), style = MaterialTheme.typography.labelSmall)
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Talk.mediaControl("previous") }, Modifier.size(52.dp)) {
                    Icon(Icons.Rounded.SkipPrevious, "Önceki", Modifier.size(32.dp))
                }
                Spacer(Modifier.width(14.dp))
                FilledIconButton(onClick = { Talk.mediaControl("play_pause") }, Modifier.size(68.dp),
                    colors = IconButtonDefaults.filledIconButtonColors()) {
                    Icon(if (media.playing) Icons.Rounded.Pause else Icons.Rounded.PlayArrow,
                        if (media.playing) "Duraklat" else "Oynat", Modifier.size(38.dp))
                }
                Spacer(Modifier.width(14.dp))
                IconButton(onClick = { Talk.mediaControl("next") }, Modifier.size(52.dp)) {
                    Icon(Icons.Rounded.SkipNext, "Sonraki", Modifier.size(32.dp))
                }
            }
            media.volume?.let { v ->
                var vol by remember(v) { mutableFloatStateOf(v.toFloat()) }
                var lastSent by remember { mutableLongStateOf(0L) }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.AutoMirrored.Rounded.VolumeUp, "Ses", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(8.dp))
                    Slider(value = vol, valueRange = 0f..100f, modifier = Modifier.weight(1f), onValueChange = {
                        vol = it
                        val t = SystemClock.elapsedRealtime()
                        if (t - lastSent > 120) { lastSent = t; Talk.mediaControl("volume", it.toLong()) }
                    }, onValueChangeFinished = { Talk.mediaControl("volume", vol.toLong()) })
                }
            }
        }
    }
}

@Composable
private fun Transfers() {
    val list by Talk.transfers.collectAsState()
    if (list.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Aktarımlar")
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
            list.forEachIndexed { i, t ->
                if (i > 0) HorizontalDivider()
                TransferRow(t)
            }
        }
    }
}

@Composable
private fun TransferRow(t: ClientSession.Transfer) {
    Row(Modifier.padding(start = 16.dp, end = 4.dp, top = 10.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(if (t.direction == "in") Icons.Rounded.Download else Icons.Rounded.Upload, null,
            tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(t.name, maxLines = 1, overflow = TextOverflow.Ellipsis)
            val status = when (t.state) {
                "waiting" -> "bilgisayarın kabulü bekleniyor"
                "active" -> "${size(t.done)} / ${size(t.size)}"
                "done" -> if (t.direction == "in") "${size(t.size)} · İndirilenler/TalkToLinux" else "${size(t.size)} · gönderildi"
                "rejected" -> "reddedildi"
                "cancelled" -> "iptal edildi"
                else -> "başarısız: ${t.error ?: ""}"
            }
            Text(status, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (t.state == "active" && t.size > 0) {
                LinearProgressIndicator(progress = { t.done.toFloat() / t.size }, modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
            }
        }
        when (t.state) {
            "active", "waiting" -> IconButton(onClick = { Talk.cancelTransfer(t) }) { Icon(Icons.Rounded.Close, "İptal") }
            "done" -> Icon(Icons.Rounded.CheckCircle, null, tint = MaterialTheme.colorScheme.tertiary, modifier = Modifier.padding(12.dp))
            else -> Icon(Icons.Rounded.ErrorOutline, null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.padding(12.dp))
        }
    }
}

@Composable
private fun SettingsCard(s: Talk.State.Connected) {
    var server by remember(s.serverId) { mutableStateOf(Talk.prefs.server(s.serverId)) }
    val profile by Talk.profile.collectAsState()
    fun change(f: (lab.crucible.talktolinux.core.Prefs.Server) -> lab.crucible.talktolinux.core.Prefs.Server) {
        Talk.updateCurrentServer(f)
        server = Talk.prefs.server(s.serverId)
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("${s.serverName} için ayarlar")
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
            if (BuildConfig.NOTIFICATIONS) {
                SwitchRow("Bildirimleri bu bilgisayara gönder",
                    if (profile?.can("notifications") == false) "Bilgisayardaki profil bildirimlere izin vermiyor"
                    else "Müzik, indirme gibi süren bildirimler hariç", server?.notif != false) { v -> change { it.copy(notif = v) } }
                HorizontalDivider()
                SwitchRow("Telefonda çalanı bu bilgisayarda göster", "Bilgisayardan oynat/duraklat/atla",
                    server?.media != false) { v -> change { it.copy(media = v) } }
            } else {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Hafif sürüm")
                    Text("Telefon bildirimleri ve telefonda çalan müzik bilgisayara gitmez (bunlar için gereken " +
                        "bildirim erişimi yüzünden Play Protect tam sürümü engelleyebiliyor). Tam sürüm için: " +
                        "bilgisayarda Talk To Android → Bağlantı → USB → “Talk To Linux'u güncelle”.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            HorizontalDivider()
            SwitchRow("Kendiliğinden bağlan", "Bağlantı koparsa ya da uygulama açılınca bu bilgisayara yeniden bağlan",
                server?.auto != false) { v -> change { it.copy(auto = v) } }
            HorizontalDivider()
            val ctx = LocalContext.current
            val restricted = runCatching {
                !ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)
            }.getOrDefault(false)
            if (restricted) {
                Row(Modifier.fillMaxWidth().clickable {
                    ctx.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                }.padding(horizontal = 16.dp, vertical = 12.dp)) {
                    Column {
                        Text("Pil kısıtlamasını kaldır")
                        Text("Ekran kapalıyken bağlantı kopmasın diye listeden Talk To Linux uygulamasını “Kısıtlama yok” yap",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                HorizontalDivider()
            }
            Text("Bilgisayardan gelen dosyalar: İndirilenler/TalkToLinux", Modifier.padding(16.dp),
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

// ---- bilgisayar: durum, ses, komutlar ------------------------------------------------

@Composable
private fun ComputerCard() {
    val profile by Talk.profile.collectAsState()
    val commands by Talk.commands.collectAsState()
    val info by Talk.sysinfo.collectAsState()
    var confirm by remember { mutableStateOf<Talk.Command?>(null) }
    LaunchedEffect(Unit) { while (true) { Talk.requestSysinfo(); delay(5000) } }
    val canShot = profile?.can("screenshot") == true

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Bilgisayar")
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                val i = info
                if (i == null) {
                    Text("Bilgisayarın durumu alınıyor…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    Text("${i.host} · ${i.os}", style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Meter("İşlemci", ((i.cpu ?: 0.0) / 100).toFloat(), i.cpu?.let { "%${it.toInt()}" } ?: "…", Modifier.weight(1f))
                        Meter("Bellek", ratio(i.memUsed, i.memTotal), "${gb(i.memUsed)} / ${gb(i.memTotal)} GB", Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Meter("Disk", ratio(i.diskUsed, i.diskTotal), "${gb(i.diskUsed)} / ${gb(i.diskTotal)} GB", Modifier.weight(1f))
                        val b = i.battery
                        if (b != null) Meter("Pil", b.first / 100f, "%${b.first}" + if (b.second) " ⚡" else "", Modifier.weight(1f))
                        else Column(Modifier.weight(1f)) {
                            Text("Açık kalma süresi", style = MaterialTheme.typography.labelSmall)
                            Text(uptime(i.uptime), style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                    if (i.volume != null && profile?.can("media") != false) {
                        var vol by remember(i.volume) { mutableFloatStateOf(i.volume.toFloat()) }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(onClick = { Talk.pcVolume(toggleMute = true) }) {
                                Icon(if (i.muted) Icons.AutoMirrored.Rounded.VolumeOff else Icons.AutoMirrored.Rounded.VolumeUp,
                                    if (i.muted) "Sesi aç" else "Sustur")
                            }
                            Slider(value = vol, valueRange = 0f..100f, modifier = Modifier.weight(1f),
                                onValueChange = { vol = it }, onValueChangeFinished = { Talk.pcVolume(vol.toInt()) })
                            Text("%${vol.toInt()}", style = MaterialTheme.typography.labelMedium, modifier = Modifier.width(44.dp),
                                textAlign = TextAlign.End)
                        }
                    }
                }
                val tiles = buildList {
                    if (canShot) add(Talk.Command("__ekran", "Ekran görüntüsü", "screenshot", false))
                    addAll(commands)
                }
                if (tiles.isNotEmpty()) {
                    HorizontalDivider()
                    tiles.chunked(2).forEach { pair ->
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            pair.forEach { c ->
                                CommandTile(c, Modifier.weight(1f)) {
                                    when {
                                        c.id == "__ekran" -> Talk.requestScreenshot()
                                        c.power -> confirm = c
                                        else -> Talk.runCommand(c.id)
                                    }
                                }
                            }
                            if (pair.size == 1) Spacer(Modifier.weight(1f))
                        }
                    }
                } else if (profile?.can("commands") == false) {
                    Text("Bu telefonun profili bilgisayar komutlarına izin vermiyor " +
                        "(bilgisayarda Cihazlar → Profiller).", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
    confirm?.let { c ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            icon = { Icon(commandIcon(c.icon), null) },
            title = { Text("${c.name}?") },
            text = { Text("Bilgisayarda açık olan kaydedilmemiş işler kaybolabilir.") },
            confirmButton = { TextButton(onClick = { Talk.runCommand(c.id); confirm = null }) { Text(c.name) } },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Vazgeç") } },
        )
    }
}

@Composable
private fun Meter(label: String, fraction: Float, value: String, modifier: Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        LinearProgressIndicator(progress = { fraction.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun CommandTile(c: Talk.Command, modifier: Modifier, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = if (c.power) MaterialTheme.colorScheme.errorContainer
        else MaterialTheme.colorScheme.secondaryContainer)) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(commandIcon(c.icon), null, Modifier.size(22.dp))
            Spacer(Modifier.width(10.dp))
            Text(c.name, style = MaterialTheme.typography.labelLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

private fun commandIcon(name: String): ImageVector = when (name) {
    "lock" -> Icons.Rounded.Lock
    "sleep" -> Icons.Rounded.Bedtime
    "restart" -> Icons.Rounded.RestartAlt
    "power" -> Icons.Rounded.PowerSettingsNew
    "screenshot" -> Icons.Rounded.Screenshot
    else -> Icons.Rounded.Terminal
}

@Composable
private fun CommandResultDialog() {
    val r by Talk.commandResult.collectAsState()
    val res = r ?: return
    if (res.second && res.third.isBlank()) {
        LaunchedEffect(res) {
            Talk.messages.tryEmit("${res.first}: tamamlandı")
            Talk.commandResult.value = null
        }
        return
    }
    AlertDialog(
        onDismissRequest = { Talk.commandResult.value = null },
        title = { Text(res.first) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (res.second) "Tamamlandı" else "Başarısız",
                    color = if (res.second) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error)
                if (res.third.isNotBlank()) Text(res.third, fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.heightIn(max = 320.dp).verticalScroll(rememberScrollState()))
            }
        },
        confirmButton = { TextButton(onClick = { Talk.commandResult.value = null }) { Text("Tamam") } },
    )
}

private fun ratio(a: Long, b: Long) = if (b > 0) a.toFloat() / b else 0f
private fun gb(n: Long) = "%.1f".format(n / 1073741824.0)
private fun uptime(s: Long) = if (s >= 86400) "${s / 86400} gün ${s / 3600 % 24} sa" else "${s / 3600} sa ${s / 60 % 60} dk"

// ---- küçük parçalar ---------------------------------------------------------------

@Composable
private fun Hero(icon: ImageVector, title: String, text: String) {
    val cs = MaterialTheme.colorScheme
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp))
        .background(Brush.linearGradient(listOf(cs.primaryContainer, cs.tertiaryContainer))).padding(22.dp)) {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Box(Modifier.size(52.dp).clip(RoundedCornerShape(16.dp)).background(cs.surface.copy(alpha = 0.5f)),
                contentAlignment = Alignment.Center) { Icon(icon, null, tint = cs.onPrimaryContainer) }
            Text(title, style = MaterialTheme.typography.headlineSmall, color = cs.onPrimaryContainer)
            Text(text, color = cs.onPrimaryContainer.copy(alpha = 0.85f))
        }
    }
}

@Composable
private fun SectionTitle(text: String, searching: Boolean = false) {
    Row(Modifier.padding(start = 4.dp, top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
        if (searching) {
            Spacer(Modifier.width(10.dp))
            CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
        }
    }
}

@Composable
private fun ServerCard(icon: ImageVector, title: String, subtitle: String, locked: Boolean, onClick: () -> Unit) {
    ElevatedCard(Modifier.fillMaxWidth().clip(CardDefaults.elevatedShape).clickable(onClick = onClick)) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            IconBadge(icon)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (locked) Icon(Icons.Rounded.Lock, "Şifreli", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun IconBadge(icon: ImageVector) {
    Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(46.dp)) {
        Box(contentAlignment = Alignment.Center) { Icon(icon, null, tint = MaterialTheme.colorScheme.onPrimaryContainer) }
    }
}

@Composable
private fun ActionTile(icon: ImageVector, label: String, modifier: Modifier, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
        Column(Modifier.padding(18.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Icon(icon, null, Modifier.size(28.dp))
            Text(label, style = MaterialTheme.typography.titleSmall)
        }
    }
}

@Composable
private fun SwitchRow(title: String, sub: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable { onChange(!checked) }.padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title)
            Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked, onChange)
    }
}

private fun mmss(ms: Long): String {
    val s = (ms / 1000).coerceAtLeast(0)
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%d:%02d".format(s / 60, s % 60)
}

private fun size(n: Long): String = when {
    n < 1024 -> "$n B"
    n < 1024 * 1024 -> "%.1f KB".format(n / 1024.0)
    n < 1024L * 1024 * 1024 -> "%.1f MB".format(n / 1048576.0)
    else -> "%.2f GB".format(n / 1073741824.0)
}
