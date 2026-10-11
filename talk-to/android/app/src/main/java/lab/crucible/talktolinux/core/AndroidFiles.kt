package lab.crucible.talktolinux.core

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.provider.OpenableColumns
import lab.crucible.talktolinux.net.ClientSession
import java.io.File
import java.io.IOException
import java.io.OutputStream

/** Bilgisayardan gelen dosyalar: İndirilenler/Talk (MediaStore, izin gerektirmez). */
class DownloadsStore(private val context: Context) : ClientSession.FileStore {
    override fun create(name: String, size: Long, mime: String): ClientSession.Sink {
        val free = Environment.getExternalStorageDirectory().usableSpace
        if (free < size + 50L * 1024 * 1024) throw IOException("telefonda yer yok")
        val clean = name.replace(Regex("[\\x00-\\x1f/\\\\]"), "_").trimStart('.').ifBlank { "dosya" }
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, clean)
            put(MediaStore.Downloads.MIME_TYPE, mime)
            put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/TalkToLinux")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("dosya oluşturulamadı")
        val out: OutputStream = try {
            resolver.openOutputStream(uri) ?: throw IOException("dosya açılamadı")
        } catch (e: Exception) {
            runCatching { resolver.delete(uri, null, null) }  // yarım "bekliyor" kaydı kalmasın
            throw e
        }
        val buffered = out.buffered(256 * 1024)
        return object : ClientSession.Sink {
            override fun write(data: ByteArray) = buffered.write(data)
            override fun commit(): String {
                buffered.close()
                resolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
                return uri.toString()
            }
            override fun abort() {
                runCatching { buffered.close() }
                runCatching { resolver.delete(uri, null, null) }
            }
        }
    }
}

private const val TEMP_PREFIX = "gonder-"

/** Önceki çalışmadan kalmış geçici kopyaları siler (uygulama açılışında). */
fun cleanTempCopies(context: Context) {
    runCatching { context.cacheDir.listFiles { f -> f.name.startsWith(TEMP_PREFIX) }?.forEach { it.delete() } }
}

/** Paylaşılan ya da seçilen bir Uri'yi gönderilebilir kaynağa çevirir. */
fun uriSource(context: Context, uri: Uri): ClientSession.Source {
    val resolver = context.contentResolver
    var name = uri.lastPathSegment?.substringAfterLast('/') ?: "dosya"
    var size = -1L
    // Bazı sağlayıcılar projeksiyonu yok sayar ya da sütunları başka sırada döndürür: adla bul.
    runCatching {
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val n = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (n >= 0 && !c.isNull(n)) c.getString(n)?.takeIf { it.isNotBlank() }?.let { name = it }
                val z = c.getColumnIndex(OpenableColumns.SIZE)
                if (z >= 0 && !c.isNull(z)) size = c.getLong(z)
            }
        }
    }
    val mime = resolver.getType(uri) ?: "application/octet-stream"
    if (size < 0) {
        // Boyutu bilinmeyen kaynak (bazı uygulamalar bildirmez): önce önbelleğe kopyala.
        // Android'de deleteOnExit çalışmaz: gönderim bitince cleanup siler, kalan olursa açılışta silinir.
        val tmp = File(context.cacheDir, "$TEMP_PREFIX${System.nanoTime()}")
        try {
            resolver.openInputStream(uri)?.use { i -> tmp.outputStream().use { i.copyTo(it) } }
                ?: throw IOException("dosya okunamadı")
        } catch (e: Exception) {
            tmp.delete()
            throw e
        }
        return ClientSession.Source(name, tmp.length(), mime, cleanup = { tmp.delete() }) { tmp.inputStream() }
    }
    return ClientSession.Source(name, size, mime) {
        resolver.openInputStream(uri) ?: throw IOException("dosya okunamadı")
    }
}
