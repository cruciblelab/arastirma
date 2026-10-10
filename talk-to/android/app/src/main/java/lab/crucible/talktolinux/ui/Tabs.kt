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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.VolumeOff
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Bedtime
import androidx.compose.material.icons.rounded.BatteryAlert
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PhoneAndroid
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.PowerSettingsNew
import androidx.compose.material.icons.rounded.RestartAlt
import androidx.compose.material.icons.rounded.Screenshot
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material.icons.rounded.SkipPrevious
import androidx.compose.material.icons.rounded.Terminal
import androidx.compose.material.icons.rounded.Upload
import androidx.compose.material.icons.rounded.UploadFile
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import lab.crucible.talktolinux.BuildConfig
import lab.crucible.talktolinux.core.Notifs
import lab.crucible.talktolinux.core.Prefs
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.net.ClientSession

// ---- Ana sayfa ----------------------------------------------------------------------

internal fun LazyListScope.homeTab(
    notifAccess: Boolean, onOpenNotifAccess: () -> Unit, onPickFiles: () -> Unit,
    onSendClipboard: () -> Unit, goTo: (Tab) -> Unit,
) {
    item { HealthCard(notifAccess, onOpenNotifAccess) }
    item { NowPlayingMini { goTo(Tab.MEDIA) } }
    item { SectionTitle("Hızlı işlemler") }
    item { QuickActions(onPickFiles, onSendClipboard) }
    item { RecentTransfers(limit = 3) { goTo(Tab.FILES) } }
}

/** Bildirimler ve müzik bilgisayara gidiyor mu; gitmiyorsa neden ve nasıl düzelir. */
@Composable
private fun HealthCard(notifAccess: Boolean, onOpenNotifAccess: () -> Unit) {
    val ctx = LocalContext.current
    val listener by Talk.listenerConnected.collectAsState()
    val sent by Talk.notificationsSent.collectAsState()
    val player by Talk.phonePlayer.collectAsState()
    val profile by Talk.profile.collectAsState()
    val server = Talk.currentServer()

    data class Issue(val title: String, val text: String, val action: String?, val run: () -> Unit)
    val issues = buildList {
        when {
            !BuildConfig.NOTIFICATIONS -> add(Issue("Hafif sürüm",
                "Bu sürüm bildirimleri ve telefonda çalan müziği bilgisayara gönderemez. Tam sürüm için bilgisayarda " +
                    "Talk To Android → Bağlantı → USB → “Talk To Linux'u güncelle”.", null) {})
            !notifAccess -> add(Issue("Bildirim erişimi kapalı",
                "Bildirimler ve telefonda çalan müzik bilgisayara gitmez.", "İzin ver", onOpenNotifAccess))
            !listener -> add(Issue("Android bildirim dinleyicisini başlatmadı",
                "Erişim açık ama Android henüz bağlamadı (genelde güncellemeden sonra olur). Ayarlardan Talk To Linux'u " +
                    "kapatıp açman düzeltir; olmazsa telefonu yeniden başlat.", "Ayarları aç", onOpenNotifAccess))
        }
        if (profile?.can("notifications") == false)
            add(Issue("Bilgisayar bildirimlere izin vermiyor",
                "Bilgisayarda Talk To Android → Cihazlar → Profiller'den bu telefonun profilini değiştir.", null) {})
        if (server?.notif == false)
            add(Issue("Bu bilgisayara bildirim gönderme kapalı", "Bilgisayar sekmesindeki ayarlardan açılır.", null) {})
    }

    if (issues.isNotEmpty()) {
        Panel(color = MaterialTheme.colorScheme.errorContainer) {
            issues.forEachIndexed { i, it ->
                if (i > 0) RowDivider()
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Rounded.Warning, null, tint = MaterialTheme.colorScheme.onErrorContainer)
                        Spacer(Modifier.width(10.dp))
                        Text(it.title, style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onErrorContainer)
                    }
                    Text(it.text, style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer)
                    if (it.action != null) FilledTonalButton(onClick = it.run) { Text(it.action) }
                }
            }
        }
        return
    }
    Panel {
        ListRow(Icons.Rounded.CheckCircle, "Bildirimler ve müzik bilgisayara gidiyor",
            buildString {
                append(if (sent == 0) "Bu bağlantıda henüz bildirim gelmedi" else "Bu bağlantıda $sent bildirim gönderildi")
                append(" · ")
                append(player?.let { "Telefonda çalan: $it" } ?: "Telefonda çalan bir şey yok")
            }, iconTint = OkGreen)
        RowDivider()
        ListRow(Icons.Rounded.Notifications, "Deneme bildirimi gönder",
            "Telefonda bir bildirim çıkar; bilgisayarda da görünmeli", onClick = {
                if (!Notifs.test(ctx)) Talk.messages.tryEmit("Talk To Linux'un bildirim gösterme izni kapalı")
            })
    }
}

@Composable
private fun NowPlayingMini(onOpen: () -> Unit) {
    val m by Talk.pcMedia.collectAsState()
    val art by Talk.pcArt.collectAsState()
    val media = m ?: return
    Panel(Modifier.clickable(onClick = onOpen)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Cover(art?.takeIf { it.first == media.artId }?.second, 52)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text("Bilgisayarda · ${media.player}", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary, maxLines = 1)
                Text(media.title.ifEmpty { "Bilinmeyen parça" }, style = MaterialTheme.typography.titleMedium,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (media.artist.isNotEmpty()) Text(media.artist, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            IconButton(onClick = { Talk.mediaControl("play_pause") }) {
                Icon(if (media.playing) Icons.Rounded.Pause else Icons.Rounded.PlayArrow,
                    if (media.playing) "Duraklat" else "Oynat")
            }
            IconButton(onClick = { Talk.mediaControl("next") }) { Icon(Icons.Rounded.SkipNext, "Sonraki") }
        }
    }
}

@Composable
private fun QuickActions(onPickFiles: () -> Unit, onSendClipboard: () -> Unit) {
    val profile by Talk.profile.collectAsState()
    val commands by Talk.commands.collectAsState()
    data class A(val icon: ImageVector, val label: String, val run: () -> Unit)
    val actions = buildList {
        if (profile?.can("files") != false) add(A(Icons.Rounded.UploadFile, "Dosya gönder", onPickFiles))
        if (profile?.can("clipboard") != false) add(A(Icons.Rounded.ContentPaste, "Panoyu gönder", onSendClipboard))
        if (profile?.can("screenshot") == true) add(A(Icons.Rounded.Screenshot, "Ekran görüntüsü") { Talk.requestScreenshot() })
        commands.firstOrNull { it.icon == "lock" }?.let { c -> add(A(Icons.Rounded.Lock, c.name) { Talk.runCommand(c.id) }) }
    }
    Grid2(actions) { a, mod -> QuickTile(a.icon, a.label, mod, onClick = a.run) }
}

// ---- Medya ---------------------------------------------------------------------------

internal fun LazyListScope.mediaTab() {
    item { SectionTitle("Bilgisayarda çalan") }
    item { PcPlayer() }
    item { PcVolume() }
    item { SectionTitle("Telefonda çalan") }
    item { PhonePlaying() }
}

@Composable
private fun Cover(bmp: android.graphics.Bitmap?, sizeDp: Int, modifier: Modifier = Modifier) {
    Box(modifier.size(sizeDp.dp).clip(RoundedCornerShape((sizeDp / 5).dp))
        .background(MaterialTheme.colorScheme.secondaryContainer), contentAlignment = Alignment.Center) {
        if (bmp != null) Image(bmp.asImageBitmap(), null, contentScale = ContentScale.Crop, modifier = Modifier.size(sizeDp.dp))
        else Icon(Icons.Rounded.MusicNote, null, Modifier.size((sizeDp * 0.42).dp),
            tint = MaterialTheme.colorScheme.onSecondaryContainer)
    }
}

@Composable
private fun PcPlayer() {
    val m by Talk.pcMedia.collectAsState()
    val art by Talk.pcArt.collectAsState()
    val media = m
    if (media == null) {
        Panel {
            ListRow(Icons.Rounded.MusicNote, "Bilgisayarda çalan bir şey yok",
                "Spotify, VLC ya da tarayıcıda YouTube açınca burada görünür ve buradan kontrol edilir.")
        }
        return
    }
    var now by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    LaunchedEffect(media) { while (true) { now = SystemClock.elapsedRealtime(); delay(500) } }
    val pos = (media.positionMs + if (media.playing) now - media.receivedAt else 0)
        .coerceAtMost(media.durationMs.takeIf { it > 0 } ?: Long.MAX_VALUE)
    var seeking by remember { mutableStateOf<Float?>(null) }

    Panel {
        Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            val cover = art?.takeIf { it.first == media.artId }?.second
            Cover(cover, if (cover != null) 200 else 120)
            Spacer(Modifier.size(16.dp))
            Text(media.title.ifEmpty { "Bilinmeyen parça" }, style = MaterialTheme.typography.titleLarge,
                maxLines = 2, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            Text(listOf(media.artist, media.player).filter { it.isNotEmpty() }.joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (media.durationMs > 0) {
                Slider(value = seeking ?: pos.toFloat(), onValueChange = { seeking = it },
                    onValueChangeFinished = { seeking?.let { Talk.mediaControl("seek", it.toLong()) }; seeking = null },
                    valueRange = 0f..media.durationMs.toFloat(), enabled = media.canSeek,
                    modifier = Modifier.padding(top = 8.dp))
                Row(Modifier.fillMaxWidth()) {
                    Text(mmss(seeking?.toLong() ?: pos), style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(1f))
                    Text(mmss(media.durationMs), style = MaterialTheme.typography.labelSmall)
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Talk.mediaControl("previous") }, Modifier.size(56.dp)) {
                    Icon(Icons.Rounded.SkipPrevious, "Önceki", Modifier.size(34.dp))
                }
                FilledIconButton(onClick = { Talk.mediaControl("play_pause") }, Modifier.size(72.dp)) {
                    Icon(if (media.playing) Icons.Rounded.Pause else Icons.Rounded.PlayArrow,
                        if (media.playing) "Duraklat" else "Oynat", Modifier.size(40.dp))
                }
                IconButton(onClick = { Talk.mediaControl("next") }, Modifier.size(56.dp)) {
                    Icon(Icons.Rounded.SkipNext, "Sonraki", Modifier.size(34.dp))
                }
            }
            media.volume?.let { v ->
                var vol by remember(v) { mutableFloatStateOf(v.toFloat()) }
                var lastSent by remember { mutableLongStateOf(0L) }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.MusicNote, "Oynatıcının sesi", tint = MaterialTheme.colorScheme.onSurfaceVariant)
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

/** Bilgisayarın genel ses düzeyi (oynatıcıdan bağımsız). */
@Composable
private fun PcVolume() {
    val info by Talk.sysinfo.collectAsState()
    val profile by Talk.profile.collectAsState()
    val i = info ?: return
    if (i.volume == null || profile?.can("media") == false) return
    var vol by remember(i.volume) { mutableFloatStateOf(i.volume.toFloat()) }
    Panel {
        Row(Modifier.padding(start = 4.dp, end = 16.dp, top = 4.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Talk.pcVolume(toggleMute = true) }) {
                Icon(if (i.muted) Icons.AutoMirrored.Rounded.VolumeOff else Icons.AutoMirrored.Rounded.VolumeUp,
                    if (i.muted) "Sesi aç" else "Sustur")
            }
            Column(Modifier.weight(1f)) {
                Text("Bilgisayarın sesi", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Slider(value = vol, valueRange = 0f..100f, onValueChange = { vol = it },
                    onValueChangeFinished = { Talk.pcVolume(vol.toInt()) })
            }
            Text("%${vol.toInt()}", style = MaterialTheme.typography.labelLarge, modifier = Modifier.width(48.dp),
                textAlign = TextAlign.End)
        }
    }
}

@Composable
private fun PhonePlaying() {
    val player by Talk.phonePlayer.collectAsState()
    Panel {
        ListRow(Icons.Rounded.PhoneAndroid, player?.let { "$it" } ?: "Telefonda çalan bir şey yok",
            if (player != null) "Bilgisayarda üst çubuktaki medya denetiminde ve klavyenin medya tuşlarında görünür"
            else "Spotify ya da YouTube'da bir şey açınca bilgisayardan da kontrol edilebilir")
    }
}

// ---- Dosyalar ------------------------------------------------------------------------

internal fun LazyListScope.filesTab(onPickFiles: () -> Unit, onSendClipboard: () -> Unit) {
    item {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            QuickTile(Icons.Rounded.UploadFile, "Dosya gönder", Modifier.weight(1f), onClick = onPickFiles)
            QuickTile(Icons.Rounded.ContentPaste, "Panoyu gönder", Modifier.weight(1f), onClick = onSendClipboard)
        }
    }
    item {
        Panel {
            ListRow(Icons.Rounded.Folder, "Bilgisayardan gelenler",
                "İndirilenler/TalkToLinux klasörüne kaydedilir. Başka uygulamalarda Paylaş → Talk To Linux ile de gönderebilirsin.")
        }
    }
    item { RecentTransfers(limit = 30, onMore = null) }
}

@Composable
private fun RecentTransfers(limit: Int, onMore: (() -> Unit)?) {
    val list by Talk.transfers.collectAsState()
    if (list.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) { SectionTitle("Aktarımlar") }
            if (onMore != null && list.size > limit) TextButton(onClick = onMore) { Text("Tümü") }
        }
        Panel {
            list.take(limit).forEachIndexed { i, t ->
                if (i > 0) RowDivider()
                TransferRow(t)
            }
        }
    }
}

@Composable
private fun TransferRow(t: ClientSession.Transfer) {
    val status = when (t.state) {
        "waiting" -> "bilgisayarın kabulü bekleniyor"
        "active" -> "${size(t.done)} / ${size(t.size)}"
        "done" -> if (t.direction == "in") "${size(t.size)} · İndirilenler/TalkToLinux" else "${size(t.size)} · gönderildi"
        "rejected" -> "reddedildi"
        "cancelled" -> "iptal edildi"
        else -> "başarısız: ${t.error ?: ""}"
    }
    Column {
        ListRow(if (t.direction == "in") Icons.Rounded.Download else Icons.Rounded.Upload, t.name, status) {
            when (t.state) {
                "active", "waiting" -> IconButton(onClick = { Talk.cancelTransfer(t) }) { Icon(Icons.Rounded.Close, "İptal") }
                "done" -> Icon(Icons.Rounded.CheckCircle, null, tint = OkGreen)
                else -> Icon(Icons.Rounded.ErrorOutline, null, tint = MaterialTheme.colorScheme.error)
            }
        }
        if (t.state == "active" && t.size > 0) {
            LinearProgressIndicator(progress = { t.done.toFloat() / t.size },
                modifier = Modifier.fillMaxWidth().padding(start = 56.dp, end = 16.dp, bottom = 10.dp))
        }
    }
}

// ---- Bilgisayar ----------------------------------------------------------------------

internal fun LazyListScope.computerTab(s: Talk.State.Connected) {
    item { SysInfoCard() }
    item { Commands() }
    item { SectionTitle("Bu bilgisayar için ayarlar") }
    item { ServerSettings(s) }
    item {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedButton(onClick = { Talk.disconnect() }, Modifier.weight(1f)) { Text("Bağlantıyı kes") }
            TextButton(onClick = { Talk.forget(s.serverId) }, Modifier.weight(1f)) {
                Text("Bilgisayarı unut", color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun SysInfoCard() {
    val info by Talk.sysinfo.collectAsState()
    LaunchedEffect(Unit) { while (true) { Talk.requestSysinfo(); delay(5000) } }
    Panel {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            val i = info
            if (i == null) {
                Text("Bilgisayarın durumu alınıyor…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                return@Column
            }
            Text("${i.host} · ${i.os}", style = MaterialTheme.typography.titleSmall, maxLines = 1,
                overflow = TextOverflow.Ellipsis)
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Meter("İşlemci", ((i.cpu ?: 0.0) / 100).toFloat(), i.cpu?.let { "%${it.toInt()}" } ?: "…", Modifier.weight(1f))
                Meter("Bellek", ratio(i.memUsed, i.memTotal), "${gb(i.memUsed)} / ${gb(i.memTotal)} GB", Modifier.weight(1f))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Meter("Disk", ratio(i.diskUsed, i.diskTotal), "${gb(i.diskUsed)} / ${gb(i.diskTotal)} GB", Modifier.weight(1f))
                val b = i.battery
                if (b != null) Meter("Pil", b.first / 100f, "%${b.first}" + if (b.second) " · şarjda" else "", Modifier.weight(1f))
                else Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Açık kalma süresi", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(uptime(i.uptime), style = MaterialTheme.typography.bodySmall)
                }
            }
        }
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
private fun Commands() {
    val profile by Talk.profile.collectAsState()
    val commands by Talk.commands.collectAsState()
    var confirm by remember { mutableStateOf<Talk.Command?>(null) }
    val tiles = buildList {
        if (profile?.can("screenshot") == true) add(Talk.Command("__ekran", "Ekran görüntüsü", "screenshot", false))
        addAll(commands)
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Komutlar")
        when {
            tiles.isNotEmpty() -> Grid2(tiles) { c, mod ->
                QuickTile(commandIcon(c.icon), c.name, mod, danger = c.power) {
                    when {
                        c.id == "__ekran" -> Talk.requestScreenshot()
                        c.power -> confirm = c
                        else -> Talk.runCommand(c.id)
                    }
                }
            }
            profile?.can("commands") == false -> Panel {
                ListRow(Icons.Rounded.Terminal, "Komutlara izin yok",
                    "Bilgisayarda Cihazlar → Profiller'den bu telefonun profiline izin verilebilir.")
            }
            else -> Panel {
                ListRow(Icons.Rounded.Terminal, "Henüz komut yok",
                    "Bilgisayarda Talk To Android → Komutlar'dan eklenir.")
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

private fun commandIcon(name: String): ImageVector = when (name) {
    "lock" -> Icons.Rounded.Lock
    "sleep" -> Icons.Rounded.Bedtime
    "restart" -> Icons.Rounded.RestartAlt
    "power" -> Icons.Rounded.PowerSettingsNew
    "screenshot" -> Icons.Rounded.Screenshot
    else -> Icons.Rounded.Terminal
}

@Composable
private fun ServerSettings(s: Talk.State.Connected) {
    var server by remember(s.serverId) { mutableStateOf(Talk.prefs.server(s.serverId)) }
    val profile by Talk.profile.collectAsState()
    fun change(f: (Prefs.Server) -> Prefs.Server) {
        Talk.updateCurrentServer(f)
        server = Talk.prefs.server(s.serverId)
    }
    val ctx = LocalContext.current
    Panel {
        if (BuildConfig.NOTIFICATIONS) {
            SwitchRow("Bildirimleri gönder",
                if (profile?.can("notifications") == false) "Bilgisayardaki profil bildirimlere izin vermiyor"
                else "Müzik, indirme gibi süren bildirimler hariç", server?.notif != false) { v -> change { it.copy(notif = v) } }
            RowDivider()
            SwitchRow("Telefonda çalanı paylaş", "Bilgisayardan oynat, duraklat, atla",
                server?.media != false) { v -> change { it.copy(media = v) } }
            RowDivider()
        }
        SwitchRow("Kendiliğinden bağlan", "Bağlantı koparsa ya da uygulama açılınca yeniden bağlan",
            server?.auto != false) { v -> change { it.copy(auto = v) } }
        val restricted = runCatching {
            !ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)
        }.getOrDefault(false)
        if (restricted) {
            RowDivider()
            ListRow(Icons.Rounded.BatteryAlert, "Pil kısıtlamasını kaldır",
                "Ekran kapalıyken bağlantı kopmasın diye Talk To Linux'u “Kısıtlama yok” yap",
                iconTint = MaterialTheme.colorScheme.error, onClick = {
                    ctx.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                })
        }
    }
}

private fun ratio(a: Long, b: Long) = if (b > 0) a.toFloat() / b else 0f
private fun gb(n: Long) = "%.1f".format(n / 1073741824.0)
private fun uptime(s: Long) = if (s >= 86400) "${s / 86400} gün ${s / 3600 % 24} sa" else "${s / 3600} sa ${s / 60 % 60} dk"

@Composable
internal fun CommandResultDialog() {
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
