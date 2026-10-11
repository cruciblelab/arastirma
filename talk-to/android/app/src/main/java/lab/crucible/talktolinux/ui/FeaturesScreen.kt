package lab.crucible.talktolinux.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import lab.crucible.talktolinux.core.Features
import lab.crucible.talktolinux.core.Talk

/** Basit mod ve sonradan eklenen özellikler (Features). Ayar yalnızca ekranı sadeleştirir. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeaturesScreen(onBack: () -> Unit) {
    BackHandler(onBack = onBack)
    val enabled by Features.enabled.collectAsState()
    val simple by Features.simple.collectAsState()
    Scaffold(topBar = {
        TopAppBar(title = { Text("Görünüm ve özellikler") },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Geri") } })
    }) { pad ->
        LazyColumn(
            contentPadding = PaddingValues(start = Gap.screen, end = Gap.screen, top = pad.calculateTopPadding() + 8.dp,
                bottom = pad.calculateBottomPadding() + Gap.section),
            verticalArrangement = Arrangement.spacedBy(Gap.section),
        ) {
            item {
                Panel {
                    SwitchRow("Basit mod", "Yalnızca bağlantı, bildirimler ve çalan müzik görünür", simple) {
                        Features.setSimple(Talk.prefs, it)
                    }
                }
                Text("Hafif sürümden farklı: hiçbir özellik kaldırılmaz, yalnızca ekran sadeleşir. Neye izin " +
                    "verildiğini bilgisayardaki profil belirler.", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 4.dp, end = 4.dp, top = Gap.inner))
            }
            if (simple) item {
                Section("Basit modda da göster") {
                    Panel {
                        Features.EXTRAS.entries.forEachIndexed { i, (key, text) ->
                            if (i > 0) RowDivider()
                            SwitchRow(text.first, text.second, key in enabled) { Features.setExtra(Talk.prefs, key, it) }
                        }
                    }
                }
            }
        }
    }
}

/** Basit moddayken ana sayfanın altında: neyin gizli olduğu ve nereden ekleneceği (T7, gizli özellik kaybolmasın). */
@Composable
internal fun SimpleModeHint(onOpen: () -> Unit) {
    val enabled by Features.enabled.collectAsState()
    val simple by Features.simple.collectAsState()
    if (!simple) return
    val hidden = Features.EXTRAS.filterKeys { it !in enabled }.values.map { it.first.lowercase() }
    if (hidden.isEmpty()) return
    Panel {
        ListRow(Icons.Rounded.GridView, "Basit mod açık", "Gizli: ${hidden.joinToString(", ")}. Dokunarak ekle.",
            onClick = onOpen)
    }
}
