package lab.crucible.talktolinux.net

import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import javax.net.ssl.SSLEngine
import javax.net.ssl.SSLEngineResult.HandshakeStatus
import javax.net.ssl.SSLEngineResult.Status

/**
 * Herhangi bir girdi/çıktı akışı çifti üzerinde TLS (istemci tarafı).
 *
 * Bluetooth soketi bir java.net.Socket olmadığı için SSLSocket kullanılamaz;
 * bunun yerine SSLEngine ile kayıtlar elle sarılıp açılır. Okuma ve yazma ayrı
 * iş parçacıklarından aynı anda yapılabilir (SSLEngine buna izin verir).
 */
class EngineTls(
    private val engine: SSLEngine,
    private val rawIn: InputStream,
    private val rawOut: OutputStream,
) {
    private var netIn: ByteBuffer = ByteBuffer.allocate(engine.session.packetBufferSize)  // yazma kipinde
    private var appIn: ByteBuffer = ByteBuffer.allocate(engine.session.applicationBufferSize).apply { flip() }
    private val readLock = Any()
    private val writeLock = Any()

    fun handshake() {
        engine.useClientMode = true
        engine.beginHandshake()
        val empty = ByteBuffer.allocate(0)
        while (true) {
            when (engine.handshakeStatus) {
                HandshakeStatus.NEED_WRAP -> wrapAndSend(empty)
                HandshakeStatus.NEED_UNWRAP -> synchronized(readLock) {
                    unwrapOnce(handshaking = true)
                }
                HandshakeStatus.NEED_TASK -> runTasks()
                else -> return  // FINISHED / NOT_HANDSHAKING
            }
        }
    }

    private fun runTasks() {
        while (true) (engine.delegatedTask ?: return).run()
    }

    private fun wrapAndSend(src: ByteBuffer) {
        synchronized(writeLock) {
            var out = ByteBuffer.allocate(engine.session.packetBufferSize)
            do {
                out.clear()
                val res = engine.wrap(src, out)
                when (res.status) {
                    Status.OK -> {}
                    Status.BUFFER_OVERFLOW -> { out = ByteBuffer.allocate(out.capacity() * 2); continue }
                    Status.CLOSED -> throw IOException("TLS kapandı")
                    else -> throw IOException("TLS yazma hatası: ${res.status}")
                }
                out.flip()
                rawOut.write(out.array(), 0, out.limit())
                if (res.handshakeStatus == HandshakeStatus.NEED_TASK) runTasks()
            } while (src.hasRemaining() || engine.handshakeStatus == HandshakeStatus.NEED_WRAP && !handshakeDone())
            rawOut.flush()
        }
    }

    private fun handshakeDone() = engine.handshakeStatus == HandshakeStatus.NOT_HANDSHAKING ||
        engine.handshakeStatus == HandshakeStatus.FINISHED

    /** Bir TLS kaydını açar; uygulama verisi appIn'e eklenir. Akış bittiyse false. */
    private fun unwrapOnce(handshaking: Boolean): Boolean {
        appIn.compact()  // yazma kipine
        try {
            while (true) {
                netIn.flip()
                val res = engine.unwrap(netIn, appIn)
                netIn.compact()
                when (res.status) {
                    Status.OK -> {
                        if (res.handshakeStatus == HandshakeStatus.NEED_TASK) runTasks()
                        // TLS 1.3'te el sıkışmadan sonra da cevap gerekebilir (ör. anahtar güncelleme).
                        if (!handshaking && engine.handshakeStatus == HandshakeStatus.NEED_WRAP) {
                            wrapAndSend(ByteBuffer.allocate(0))
                        }
                        if (handshaking || appIn.position() > 0) return true
                    }
                    Status.BUFFER_UNDERFLOW -> {
                        if (netIn.remaining() == 0 || netIn.capacity() < engine.session.packetBufferSize) {
                            val bigger = ByteBuffer.allocate(maxOf(netIn.capacity() * 2, engine.session.packetBufferSize))
                            netIn.flip(); bigger.put(netIn); netIn = bigger
                        }
                        val n = rawIn.read(netIn.array(), netIn.position(), netIn.remaining())
                        if (n < 0) {
                            if (handshaking) throw EOFException("TLS el sıkışması yarıda kaldı")
                            return false
                        }
                        netIn.position(netIn.position() + n)
                    }
                    Status.BUFFER_OVERFLOW -> {
                        val bigger = ByteBuffer.allocate(appIn.capacity() + engine.session.applicationBufferSize)
                        appIn.flip(); bigger.put(appIn); appIn = bigger
                    }
                    Status.CLOSED -> return false
                    else -> throw IOException("TLS okuma hatası: ${res.status}")
                }
            }
        } finally {
            appIn.flip()  // okuma kipine
        }
    }

    val inputStream: InputStream = object : InputStream() {
        override fun read(): Int {
            val b = ByteArray(1)
            return if (read(b, 0, 1) < 0) -1 else b[0].toInt() and 0xFF
        }

        override fun read(b: ByteArray, off: Int, len: Int): Int {
            if (len == 0) return 0
            synchronized(readLock) {
                while (!appIn.hasRemaining()) {
                    if (!unwrapOnce(handshaking = false)) return -1
                }
                val n = minOf(len, appIn.remaining())
                appIn.get(b, off, n)
                return n
            }
        }

        override fun available(): Int = synchronized(readLock) { appIn.remaining() }
    }

    val outputStream: OutputStream = object : OutputStream() {
        override fun write(b: Int) = write(byteArrayOf(b.toByte()), 0, 1)
        override fun write(b: ByteArray, off: Int, len: Int) {
            val src = ByteBuffer.wrap(b, off, len)
            while (src.hasRemaining()) wrapAndSend(src)
        }
        override fun flush() = synchronized(writeLock) { rawOut.flush() }
    }

    fun peerCertificate(): java.security.cert.Certificate = engine.session.peerCertificates[0]

    fun close() {
        runCatching {
            engine.closeOutbound()
            wrapAndSend(ByteBuffer.allocate(0))
        }
    }
}
