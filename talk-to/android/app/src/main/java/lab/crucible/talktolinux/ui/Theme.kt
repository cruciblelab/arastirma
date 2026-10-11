package lab.crucible.talktolinux.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * Bilgisayardaki uygulamayla aynı görünüm: GNOME'un Adwaita renkleri (libadwaita).
 * Android 12+'nın duvar kağıdından renk türetmesi (Material You) bilerek kullanılmaz: iki uygulama
 * aynı ürünün iki yüzü gibi görünsün, renkler telefondan telefona değişmesin.
 *
 * Adwaita: vurgu #3584e4, pencere #fafafa, kart #ffffff, yazı %80 siyah; karanlıkta pencere #242424,
 * kart #303030. Başarı #26a269, hata #e01b24.
 */
internal object Adw {
    val Accent = Color(0xFF3584E4)
    val AccentDark = Color(0xFF1C71D8)
    val Success = Color(0xFF26A269)
}

private val Light = lightColorScheme(
    primary = Adw.Accent, onPrimary = Color.White,
    primaryContainer = Color(0xFFDDE8F9), onPrimaryContainer = Color(0xFF0D3B78),
    secondary = Color(0xFF5E5C64), onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFFFFF), onSecondaryContainer = Color(0xFF2E2E32),
    tertiary = Adw.Success, onTertiary = Color.White, tertiaryContainer = Color(0xFFD6F2E2),
    background = Color(0xFFFAFAFA), onBackground = Color(0xFF2E2E32),
    surface = Color(0xFFFAFAFA), onSurface = Color(0xFF2E2E32),
    surfaceVariant = Color(0xFFEBEBEB), onSurfaceVariant = Color(0xFF6E6D73),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color.White,
    surfaceContainer = Color.White, surfaceContainerHigh = Color(0xFFF0F0F0),
    surfaceContainerHighest = Color(0xFFE8E8E8),
    outline = Color(0xFFC0BFC4), outlineVariant = Color(0xFFE0E0E0),
    error = Color(0xFFE01B24), onError = Color.White,
    errorContainer = Color(0xFFFBDADB), onErrorContainer = Color(0xFF7A0A10),
)

private val Dark = darkColorScheme(
    primary = Adw.Accent, onPrimary = Color.White,
    primaryContainer = Color(0xFF1E3A5F), onPrimaryContainer = Color(0xFFD3E4FB),
    secondary = Color(0xFFC0BFC4), onSecondary = Color(0xFF242424),
    secondaryContainer = Color(0xFF303030), onSecondaryContainer = Color.White,
    tertiary = Color(0xFF57E389), onTertiary = Color(0xFF0B3A1E), tertiaryContainer = Color(0xFF1F4A31),
    background = Color(0xFF242424), onBackground = Color.White,
    surface = Color(0xFF242424), onSurface = Color.White,
    surfaceVariant = Color(0xFF303030), onSurfaceVariant = Color(0xFFA8A7AD),
    surfaceContainerLowest = Color(0xFF1E1E1E), surfaceContainerLow = Color(0xFF2A2A2A),
    surfaceContainer = Color(0xFF303030), surfaceContainerHigh = Color(0xFF383838),
    surfaceContainerHighest = Color(0xFF404040),
    outline = Color(0xFF5E5C64), outlineVariant = Color(0xFF3A3A3A),
    error = Color(0xFFFF7B63), onError = Color(0xFF3B0A0A),
    errorContainer = Color(0xFF5C1A1A), onErrorContainer = Color(0xFFFFDAD3),
)

@Composable
fun TalkTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Dark else Light, content = content)
}
