package lab.crucible.talktolinux.net

import org.json.JSONObject
import java.io.DataInputStream
import java.io.IOException
import java.nio.ByteBuffer

/** Tel düzeyi çerçeveleme (PROTOKOL.md, "Çerçeve"). Linux: talkto/protocol.py */
object Frame {
    const val JSON = 0x4A
    const val BINARY = 0x42
    const val MAX_JSON = 4 * 1024 * 1024
    const val MAX_BINARY = 1024 * 1024 + 4
    const val CHUNK = 256 * 1024

    sealed class In {
        class Json(val msg: JSONObject) : In() {
            val type: String get() = msg.getString("type")
        }
        class Binary(val tid: Long, val data: ByteArray) : In()
    }

    fun encodeJson(msg: JSONObject): ByteArray {
        val body = msg.toString().toByteArray(Charsets.UTF_8)
        if (body.size > MAX_JSON) throw IOException("JSON çerçevesi çok büyük")
        return ByteBuffer.allocate(5 + body.size).put(JSON.toByte()).putInt(body.size).put(body).array()
    }

    fun encodeBinary(tid: Long, data: ByteArray, len: Int = data.size): ByteArray =
        ByteBuffer.allocate(9 + len).put(BINARY.toByte()).putInt(len + 4).putInt(tid.toInt())
            .put(data, 0, len).array()

    fun read(input: DataInputStream): In {
        val kind = input.readUnsignedByte()
        val length = input.readInt()
        when (kind) {
            JSON -> {
                if (length < 0 || length > MAX_JSON) throw IOException("JSON çerçevesi sınırı aşıyor")
                val body = ByteArray(length)
                input.readFully(body)
                val msg = JSONObject(String(body, Charsets.UTF_8))
                if (msg.optString("type").isEmpty()) throw IOException("'type' yok")
                return In.Json(msg)
            }
            BINARY -> {
                if (length < 4 || length > MAX_BINARY) throw IOException("ikili çerçeve uzunluğu geçersiz")
                val tid = input.readInt().toLong() and 0xFFFFFFFFL
                val data = ByteArray(length - 4)
                input.readFully(data)
                return In.Binary(tid, data)
            }
            else -> throw IOException("bilinmeyen çerçeve türü: $kind")
        }
    }
}
