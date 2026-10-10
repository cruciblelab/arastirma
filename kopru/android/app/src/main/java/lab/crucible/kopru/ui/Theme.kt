package lab.crucible.kopru.ui

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val Light = lightColorScheme(
    primary = Color(0xFF2557D6), onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE2FF), onPrimaryContainer = Color(0xFF001550),
    secondary = Color(0xFF5A5D72), secondaryContainer = Color(0xFFDFE1F9),
    tertiary = Color(0xFF0F7A6C), tertiaryContainer = Color(0xFFA0F2E0),
    surface = Color(0xFFFBF8FF), surfaceContainer = Color(0xFFEFEDF6),
)

private val Dark = darkColorScheme(
    primary = Color(0xFFB6C4FF), onPrimary = Color(0xFF00287D),
    primaryContainer = Color(0xFF003BAF), onPrimaryContainer = Color(0xFFDCE2FF),
    secondary = Color(0xFFC3C5DD), secondaryContainer = Color(0xFF424659),
    tertiary = Color(0xFF84D5C4), tertiaryContainer = Color(0xFF005046),
    surface = Color(0xFF121318), surfaceContainer = Color(0xFF1E1F25),
)

@Composable
fun KopruTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val ctx = LocalContext.current
    val scheme = when {
        Build.VERSION.SDK_INT >= 31 -> if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        dark -> Dark
        else -> Light
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
