package lab.crucible.kopru.core

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.provider.OpenableColumns
import lab.crucible.kopru.net.ClientSession
import java.io.File
import java.io.IOException
import java.io.OutputStream

/** Bilgisayardan gelen dosyalar: İndirilenler/Kopru (MediaStore, izin gerektirmez). */
class DownloadsStore(private val context: Context) : ClientSession.FileStore {
    override fun create(name: String, size: Long, mime: String): ClientSession.Sink {
        val free = Environment.getExternalStorageDirectory().usableSpace
        if (free < size + 50L * 1024 * 1024) throw IOException("telefonda yer yok")
        val clean = name.replace(Regex("[\\x00-\\x1f/\\\\]"), "_").trimStart('.').ifBlank { "dosya" }
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, clean)
            put(MediaStore.Downloads.MIME_TYPE, mime)
            put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Kopru")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("dosya oluşturulamadı")
        val out: OutputStream = resolver.openOutputStream(uri) ?: run {
            resolver.delete(uri, null, null)
            throw IOException("dosya açılamadı")
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

/** Paylaşılan ya da seçilen bir Uri'yi gönderilebilir kaynağa çevirir. */
fun uriSource(context: Context, uri: Uri): ClientSession.Source {
    val resolver = context.contentResolver
    var name = uri.lastPathSegment?.substringAfterLast('/') ?: "dosya"
    var size = -1L
    resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
        if (c.moveToFirst()) {
            c.getString(0)?.let { name = it }
            if (!c.isNull(1)) size = c.getLong(1)
        }
    }
    val mime = resolver.getType(uri) ?: "application/octet-stream"
    if (size < 0) {
        // Boyutu bilinmeyen kaynak (bazı uygulamalar bildirmez): önce önbelleğe kopyala.
        val tmp = File(context.cacheDir, "gonder-${System.nanoTime()}")
        resolver.openInputStream(uri)?.use { i -> tmp.outputStream().use { i.copyTo(it) } }
            ?: throw IOException("dosya okunamadı")
        tmp.deleteOnExit()
        return ClientSession.Source(name, tmp.length(), mime) { tmp.inputStream() }
    }
    return ClientSession.Source(name, size, mime) {
        resolver.openInputStream(uri) ?: throw IOException("dosya okunamadı")
    }
}
