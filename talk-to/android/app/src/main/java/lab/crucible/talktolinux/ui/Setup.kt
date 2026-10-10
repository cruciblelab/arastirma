package lab.crucible.talktolinux.ui

import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Computer
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.BatteryChargingFull
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.RadioButtonUnchecked
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.SwapHoriz
import androidx.compose.material.icons.rounded.Usb
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.MutableStateFlow
import lab.crucible.talktolinux.core.Checks
import lab.crucible.talktolinux.core.Talk

/** Etkinlikten gelen izin istekleri (ActivityResult kayıtları etkinlikte yapılır). */
class PermActions(
    val notifications: () -> Unit = {},
    val bluetooth: () -> Unit = {},
)

/** Ayarlardan dönülünce (onResume) ve "Kontrol et"e basılınca denetimler yeniden okunsun. */
object UiTick {
    val tick = MutableStateFlow(0)
    fun bump() { tick.value += 1 }
}

/** Bir denetim satırı: durum, neden gerekli, ayarı açan düğme, "Kontrol et". */
class Item(
    val title: String,
    val text: String,
    val check: (() -> Boolean)?,      // null: yalnızca bilgi
    val action: String? = null,
    val onAction: (() -> Unit)? = null,
    val optional: Boolean = false,
    val hint: String? = null,         // kapalıyken gösterilen ek açıklama
    val hintAction: String? = null,
    val onHint: (() -> Unit)? = null,
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CheckRow(item: Item) {
    val ok = item.check?.invoke()
    val cs = MaterialTheme.colorScheme
    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.Top) {
            val (icon, tint) = when (ok) {
                true -> Icons.Rounded.CheckCircle to OkGreen
                false -> Icons.Rounded.RadioButtonUnchecked to (if (item.optional) cs.onSurfaceVariant else cs.error)
                null -> Icons.Rounded.Info to cs.primary
            }
            Icon(icon, null, tint = tint, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(item.title, style = MaterialTheme.typography.titleSmall)
                Text(when (ok) {
                    true -> "Tamam"
                    false -> if (item.optional) "Kapalı (isteğe bağlı)" else "Kapalı"
                    null -> ""
                }.takeIf { it.isNotEmpty() } ?: item.text,
                    style = MaterialTheme.typography.labelMedium,
                    color = if (ok == false && !item.optional) cs.error else cs.onSurfaceVariant)
                if (ok == false) Text(item.text, style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant)
                if (ok == false && item.hint != null) {
                    Text(item.hint, style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant,
                        modifier = Modifier.padding(top = 4.dp))
                }
            }
        }
        if (ok != true && (item.onAction != null || item.check != null)) {
            FlowRow(Modifier.padding(start = 38.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (item.onAction != null && item.action != null) {
                    FilledTonalButton(onClick = item.onAction) { Text(item.action) }
                }
                if (ok == false && item.onHint != null && item.hintAction != null) {
                    TextButton(onClick = item.onHint) { Text(item.hintAction) }
                }
                if (item.check != null) {
                    TextButton(onClick = {
                        UiTick.bump()
                        Talk.messages.tryEmit(if (item.check.invoke()) "✓ ${item.title}: tamam"
                        else "${item.title}: hâlâ kapalı")
                    }) { Text("Kontrol et") }
                }
            }
        }
    }
}

@Composable
private fun CheckPanel(items: List<Item>) {
    Panel {
        items.forEachIndexed { i, it ->
            if (i > 0) RowDivider()
            CheckRow(it)
        }
    }
}

// ---- denetim grupları (sihirbaz ve izinler ekranı ortak) ------------------------------

@Composable
private fun notificationItems(perms: PermActions): List<Item> {
    val ctx = LocalContext.current
    if (!Checks.hasNotifications) {
        return listOf(Item("Hafif sürüm",
            "Bu sürüm telefon bildirimlerini ve telefonda çalan müziği bilgisayara gönderemez. Tam sürüm için " +
                "bilgisayarda Talk To Android → Bağlantı → USB → “Talk To Linux'u güncelle”.", null))
    }
    val restricted = if (Build.VERSION.SDK_INT >= 33)
        "Ayar gri ve açılmıyorsa: Uygulama bilgisi → sağ üstteki ⋮ → “Kısıtlanmış ayarlara izin ver”, sonra tekrar dene."
    else null
    return listOfNotNull(
        Item("Bildirim gösterme izni",
            "Bilgisayardan gelen dosya, bildirim ve “telefonu bul” uyarıları için.",
            { Checks.postNotifications(ctx) }, "İzin ver", perms.notifications),
        Item("Bildirim erişimi",
            "Telefon bildirimlerinin bilgisayarda görünmesi ve telefonda çalan müziğin (Spotify, YouTube…) " +
                "bilgisayardan kontrolü için. Açılan sayfada Talk To Linux'u aç.",
            { Checks.notifAccess() }, "Ayarı aç", { Checks.open(ctx, Checks.notifAccessIntent(ctx)) },
            hint = restricted, hintAction = restricted?.let { "Uygulama bilgisi" },
            onHint = { Checks.open(ctx, Checks.appDetails(ctx)) }),
        // Erişim kapalıyken dinleyici zaten çalışamaz; bu satır yalnızca erişim açıkken anlamlı.
        if (Checks.notifAccess()) Item("Bildirim dinleyicisi çalışıyor",
            "Erişim açıkken Android'in dinleyiciyi başlatmış olması gerekir. Başlamadıysa erişimi kapatıp aç " +
                "ya da telefonu yeniden başlat.",
            { Checks.listener() }, "Yeniden başlat", { Talk.ensureListener(); UiTick.bump() }) else null,
    )
}

@Composable
private fun backgroundItems(): List<Item> {
    val ctx = LocalContext.current
    return listOf(
        Item("Pil kısıtlaması yok",
            "Ekran kapalıyken bağlantı kopmasın diye. Açılan listede Talk To Linux'u “Kısıtlama yok” / " +
                "“Optimize etme” yap. Bazı telefonlarda (Xiaomi, Huawei, Samsung) ayrıca “Otomatik başlat” açılmalı.",
            { Checks.battery(ctx) }, "Ayarı aç", { Checks.open(ctx, Checks.batterySettings(), Checks.appDetails(ctx)) },
            optional = true, hint = "Bulamazsan: Uygulama bilgisi → Pil.", hintAction = "Uygulama bilgisi",
            onHint = { Checks.open(ctx, Checks.appDetails(ctx)) }),
    )
}

@Composable
private fun connectionItems(perms: PermActions): List<Item> {
    val ctx = LocalContext.current
    return listOf(
        Item("USB: Geliştirici seçenekleri",
            "Kabloyla bağlanmak için. Kapalıysa: açılan “Telefon hakkında” sayfasında “Yapım numarası”na 7 kez dokun.",
            { Checks.developerOptions(ctx) }, "Ayarı aç", { Checks.open(ctx, Checks.developerSettings(ctx)) },
            optional = true),
        Item("USB: USB hata ayıklama",
            "Geliştirici seçeneklerinde “USB hata ayıklama”yı aç. Kabloyu takınca çıkan “USB hata ayıklamaya izin " +
                "ver” sorusunu onayla. Kablo yalnızca şarj ediyorsa bilgisayar telefonu göremez.",
            { Checks.usbDebugging(ctx) }, "Ayarı aç", { Checks.open(ctx, Checks.developerSettings(ctx)) },
            optional = true),
        Item("Wi-Fi",
            "Kablosuz bağlanmak için telefon ve bilgisayar aynı Wi-Fi ağında olmalı; bilgisayarda “Kablosuz " +
                "bağlantıyı aç” açık olmalı.",
            { Checks.onWifi(ctx) }, "Wi-Fi ayarları", { Checks.open(ctx, Checks.wifiSettings()) }, optional = true),
        Item("Bluetooth",
            "Bluetooth ile bağlanmak için: izin ver, Bluetooth'u aç ve bilgisayarla sistemin Bluetooth ayarlarından " +
                "eşleştir.",
            { Checks.bluetoothReady(ctx) },
            if (lab.crucible.talktolinux.core.BluetoothLink.hasPermission(ctx)) "Bluetooth ayarları" else "İzin ver",
            {
                if (lab.crucible.talktolinux.core.BluetoothLink.hasPermission(ctx)) Checks.open(ctx, Checks.bluetoothSettings())
                else perms.bluetooth()
            }, optional = true),
    )
}

// ---- kurulum sihirbazı ----------------------------------------------------------------

private class Step(val icon: ImageVector, val title: String, val text: String)

private val STEPS = listOf(
    Step(Icons.Rounded.SwapHoriz, "Talk To Linux'a hoş geldin",
        "Telefonunu Linux bilgisayarına bağlar: bildirimler bilgisayarda görünür, müzik iki yönden kontrol edilir, " +
            "dosya ve pano gider gelir, bilgisayara komut verirsin. Birkaç ayar gerekiyor; her adımda ne olduğunu " +
            "ve “Kontrol et” düğmesini göreceksin. Ayarlar kapalı kalsa da uygulama açılır, istediğin zaman " +
            "İzinler ekranından tamamlayabilirsin."),
    Step(Icons.Rounded.Notifications, "Bildirimler ve müzik",
        "Telefonun bildirimlerinin ve çalan müziğin bilgisayara gitmesi için."),
    Step(Icons.Rounded.BatteryChargingFull, "Arka planda çalışma",
        "Android pil tasarrufu için arka plandaki uygulamaları kapatabilir; o zaman bağlantı kopar."),
    Step(Icons.Rounded.Usb, "Nasıl bağlanacaksın?",
        "Birini hazırlaman yeterli. USB en hızlısı, Wi-Fi kablosuz, Bluetooth ağ olmadan da çalışır."),
    Step(Icons.Rounded.Computer, "Bilgisayar tarafı",
        "Bilgisayarda Talk To Android uygulaması kurulu ve açık olmalı (Ubuntu'da .deb dosyasına çift tıkla). " +
            "Açıkken bu telefon onu Wi-Fi'de kendiliğinden bulur; USB'de kabloyu takman yeter. İlk bağlantıda " +
            "bilgisayarda bir onay penceresi çıkar ve iki ekranda aynı 6 haneli kod görünür."),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetupWizard(perms: PermActions, initialStep: Int = 0, onDone: () -> Unit) {
    var step by rememberSaveable { mutableIntStateOf(initialStep) }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { Talk.messages.collect { snackbar.showSnackbar(it) } }
    @Suppress("UNUSED_VARIABLE") val tick by UiTick.tick.collectAsState()  // ayardan dönünce yeniden çiz
    BackHandler(enabled = step > 0) { step-- }
    val s = STEPS[step]
    val last = step == STEPS.lastIndex

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Kurulum · ${step + 1}/${STEPS.size}") },
                actions = { if (!last) TextButton(onClick = onDone) { Text("Atla") } })
        },
        bottomBar = {
            Surface(tonalElevation = 2.dp) {
                Column(Modifier.navigationBarsPadding().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    LinearProgressIndicator(progress = { (step + 1f) / STEPS.size }, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        if (step > 0) OutlinedButton(onClick = { step-- }, Modifier.weight(1f)) { Text("Geri") }
                        Button(onClick = { if (last) onDone() else step++ }, Modifier.weight(1f)) {
                            Text(when { step == 0 -> "Başla"; last -> "Bitir"; else -> "İleri" })
                        }
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { pad ->
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding() + 8.dp,
                bottom = pad.calculateBottomPadding() + 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.padding(horizontal = 4.dp)) {
                    IconBadge(s.icon, 56)
                    Text(s.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
                    Text(s.text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            when (step) {
                1 -> item { CheckPanel(notificationItems(perms)) }
                2 -> item { CheckPanel(backgroundItems()) }
                3 -> item { CheckPanel(connectionItems(perms)) }
            }
        }
    }
}

// ---- izinler ve yetkiler ------------------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PermissionsScreen(perms: PermActions, onBack: () -> Unit, onOpenWizard: () -> Unit) {
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { Talk.messages.collect { snackbar.showSnackbar(it) } }
    @Suppress("UNUSED_VARIABLE") val tick by UiTick.tick.collectAsState()
    val state by Talk.state.collectAsState()
    val profile by Talk.profile.collectAsState()
    BackHandler(onBack = onBack)

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("İzinler ve yetkiler") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Geri") } })
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { pad ->
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding() + 4.dp,
                bottom = pad.calculateBottomPadding() + 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { SectionTitle("Bildirimler ve müzik") }
            item { CheckPanel(notificationItems(perms)) }
            item { SectionTitle("Arka planda çalışma") }
            item { CheckPanel(backgroundItems()) }
            item { SectionTitle("Bağlantı yolları") }
            item { CheckPanel(connectionItems(perms)) }
            item { SectionTitle("Bilgisayarın bu telefona verdiği yetkiler") }
            item {
                val connected = state as? Talk.State.Connected
                val p = profile
                Panel {
                    if (connected == null || p == null) {
                        ListRow(Icons.Rounded.Security, "Bir bilgisayara bağlı değilsin",
                            "Bağlanınca bilgisayarın bu telefonu hangi profille tanıdığı ve neye izin verdiği burada görünür.")
                    } else {
                        ListRow(Icons.Rounded.Security, "${connected.serverName}: “${p.name}” profili",
                            "Yetkileri bilgisayarın sahibi belirler: Talk To Android → Cihazlar → Profiller.")
                        Checks.PROFILE_PERMISSIONS.forEach { (key, label) ->
                            RowDivider()
                            val on = p.can(key)
                            ListRow(if (on) Icons.Rounded.CheckCircle else Icons.Rounded.RadioButtonUnchecked, label,
                                if (on) "İzin var" else "İzin yok",
                                iconTint = if (on) OkGreen else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            item {
                OutlinedButton(onClick = onOpenWizard, modifier = Modifier.fillMaxWidth()) { Text("Kurulum sihirbazını aç") }
            }
        }
    }
}
