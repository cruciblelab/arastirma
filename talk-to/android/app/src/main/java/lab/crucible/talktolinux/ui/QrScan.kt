package lab.crucible.talktolinux.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.QrCodeScanner
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.NotFoundException
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import lab.crucible.talktolinux.core.Checks
import lab.crucible.talktolinux.net.QrPair
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Bilgisayardaki "Telefon ekle" karekodunu okur. Kamera görüntüsü yalnızca telefonda, ZXing ile çözülür;
 * kaydedilmez, hiçbir yere gönderilmez.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QrScanScreen(onBack: () -> Unit, onFound: (QrPair) -> Unit) {
    BackHandler(onBack = onBack)
    val ctx = LocalContext.current
    var granted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var asked by remember { mutableStateOf(false) }
    var wrong by remember { mutableStateOf(false) }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        granted = it
        asked = true
    }
    Scaffold(topBar = {
        TopAppBar(title = { Text("Karekodu tara") }, navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Geri") }
        })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).padding(Gap.screen),
            verticalArrangement = Arrangement.spacedBy(Gap.section), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Bilgisayardaki Talk To'da “Telefon ekle”ye bas ve karekodu çerçeveye getir.",
                style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center)
            if (granted) {
                Box(Modifier.fillMaxWidth().weight(1f, fill = false), contentAlignment = Alignment.Center) {
                    Surface(shape = RoundedCornerShape(24.dp), modifier = Modifier.size(300.dp)) {
                        CameraPreview(onText = { text ->
                            val qr = QrPair.parse(text)
                            if (qr != null) onFound(qr) else wrong = true
                            qr != null
                        })
                    }
                    Box(Modifier.size(220.dp).border(3.dp, Color.White.copy(alpha = 0.85f), RoundedCornerShape(16.dp)))
                }
                if (wrong) Text("Bu bir Talk To karekodu değil. Bilgisayardaki Talk To'nun gösterdiği karekodu okut.",
                    color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            } else {
                Icon(Icons.Rounded.QrCodeScanner, null, Modifier.size(72.dp), tint = MaterialTheme.colorScheme.primary)
                Text("Karekodu okumak için kamera izni gerekiyor.", textAlign = TextAlign.Center)
                FilledTonalButton(onClick = {
                    // Kalıcı reddedildiyse pencere çıkmaz: uygulama ayarları açılır.
                    if (asked) Checks.open(ctx, Checks.appDetails(ctx)) else ask.launch(Manifest.permission.CAMERA)
                }) { Text(if (asked) "Ayarlarda kamerayı aç" else "Kameraya izin ver") }
            }
            Text("Görüntü yalnızca bu telefonda işlenir; kaydedilmez, hiçbir yere gönderilmez.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center)
        }
    }
}

/** Arka kamera önizlemesi; her karede karekod aranır. [onText] true dönerse tarama biter. */
@Composable
private fun CameraPreview(onText: (String) -> Boolean) {
    val ctx = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val view = remember { PreviewView(ctx).apply { scaleType = PreviewView.ScaleType.FILL_CENTER } }
    val worker = remember { Executors.newSingleThreadExecutor() }
    val done = remember { AtomicBoolean(false) }
    val main = remember { Handler(Looper.getMainLooper()) }
    DisposableEffect(owner) {
        val future = ProcessCameraProvider.getInstance(ctx)
        val reader = MultiFormatReader().apply {
            setHints(mapOf(DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE),
                DecodeHintType.TRY_HARDER to true))
        }
        future.addListener({
            val provider = runCatching { future.get() }.getOrNull() ?: return@addListener
            val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(worker) { image ->
                val text = if (done.get()) null else decode(reader, image)
                image.close()
                if (text != null) main.post { if (!done.get() && onText(text)) done.set(true) }
            }
            runCatching {
                provider.unbindAll()
                provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            }
        }, ContextCompat.getMainExecutor(ctx))
        onDispose {
            done.set(true)
            runCatching { future.get().unbindAll() }
            worker.shutdown()
        }
    }
    AndroidView(factory = { view }, modifier = Modifier.fillMaxSize())
}

/** Karenin parlaklık (Y) düzleminde karekod; yoksa null. */
private fun decode(reader: MultiFormatReader, image: ImageProxy): String? {
    val plane = image.planes.firstOrNull() ?: return null
    val w = image.width
    val h = image.height
    val buf = plane.buffer
    val stride = plane.rowStride
    // Satır sonlarında dolgu olabilir (rowStride > genişlik; son satırda olmayabilir): satır satır kopyalanır.
    val data = ByteArray(w * h)
    runCatching {
        for (y in 0 until h) {
            buf.position(y * stride)
            buf.get(data, y * w, w)
        }
    }.onFailure { return null }
    val source = PlanarYUVLuminanceSource(data, w, h, 0, 0, w, h, false)
    return try {
        reader.decodeWithState(BinaryBitmap(HybridBinarizer(source))).text
    } catch (_: NotFoundException) {
        null
    } catch (_: Exception) {
        null
    } finally {
        reader.reset()
    }
}
