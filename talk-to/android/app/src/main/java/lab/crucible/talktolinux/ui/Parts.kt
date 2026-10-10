package lab.crucible.talktolinux.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/** Bütün ekranlarda aynı köşe ve renk: düz, hafif ayrışan yüzey. */
internal val PanelShape = RoundedCornerShape(20.dp)

/** "Çalışıyor" işareti: temadan bağımsız, her iki modda okunur yeşil. */
internal val OkGreen = Color(0xFF2E9D5B)

@Composable
internal fun Panel(modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.surfaceContainer,
                   content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), shape = PanelShape, colors = CardDefaults.cardColors(containerColor = color)) {
        Column(content = content)
    }
}

@Composable
internal fun SectionTitle(text: String, searching: Boolean = false) {
    Row(Modifier.padding(start = 4.dp, top = 8.dp, bottom = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
        if (searching) {
            Spacer(Modifier.width(10.dp))
            CircularProgressIndicator(Modifier.size(12.dp), strokeWidth = 2.dp)
        }
    }
}

/** Liste satırı: simge, başlık, alt yazı, sağda isteğe bağlı parça. Dokunulabilir. */
@Composable
internal fun ListRow(
    icon: ImageVector?, title: String, subtitle: String? = null, iconTint: Color = MaterialTheme.colorScheme.primary,
    onClick: (() -> Unit)? = null, trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 60.dp)
            .let { if (onClick != null) it.clickable(onClick = onClick) else it }
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = iconTint, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(16.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (!subtitle.isNullOrEmpty()) Text(subtitle, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (trailing != null) {
            Spacer(Modifier.width(12.dp))
            trailing()
        }
    }
}

@Composable
internal fun SwitchRow(title: String, sub: String?, checked: Boolean, onChange: (Boolean) -> Unit) {
    ListRow(null, title, sub, onClick = { onChange(!checked) }) { Switch(checked, onChange) }
}

@Composable
internal fun RowDivider() = HorizontalDivider(Modifier.padding(start = 16.dp),
    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))

/** Kare hızlı işlem düğmesi (ızgarada kullanılır). */
@Composable
internal fun QuickTile(icon: ImageVector, label: String, modifier: Modifier, danger: Boolean = false,
                       onClick: () -> Unit) {
    val cs = MaterialTheme.colorScheme
    Card(onClick = onClick, modifier = modifier.heightIn(min = 84.dp), shape = PanelShape,
        colors = CardDefaults.cardColors(containerColor = if (danger) cs.errorContainer else cs.secondaryContainer,
            contentColor = if (danger) cs.onErrorContainer else cs.onSecondaryContainer)) {
        Column(Modifier.padding(14.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(icon, null, Modifier.size(24.dp))
            Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** İkişerli ızgara (LazyColumn içinde iç içe kaydırma olmasın diye basit satırlar). */
@Composable
internal fun <T> Grid2(items: List<T>, tile: @Composable (T, Modifier) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items.chunked(2).forEach { pair ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                pair.forEach { tile(it, Modifier.weight(1f)) }
                if (pair.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
internal fun IconBadge(icon: ImageVector, size: Int = 44) {
    Surface(shape = RoundedCornerShape((size * 0.32).dp), color = MaterialTheme.colorScheme.primaryContainer,
        modifier = Modifier.size(size.dp)) {
        Box(contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = MaterialTheme.colorScheme.onPrimaryContainer, modifier = Modifier.size((size * 0.52).dp))
        }
    }
}

internal fun mmss(ms: Long): String {
    val s = (ms / 1000).coerceAtLeast(0)
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%d:%02d".format(s / 60, s % 60)
}

internal fun size(n: Long): String = when {
    n < 1024 -> "$n B"
    n < 1024 * 1024 -> "%.1f KB".format(n / 1024.0)
    n < 1024L * 1024 * 1024 -> "%.1f MB".format(n / 1048576.0)
    else -> "%.2f GB".format(n / 1073741824.0)
}
