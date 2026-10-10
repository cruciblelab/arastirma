package lab.crucible.talktolinux.net

import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.DataInputStream
import java.io.IOException
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509TrustManager

/**
 * Bilgisayara tek bir bağlantı. Android'e bağımlı değildir; bu yüzden JVM
 * testleri gerçek Linux sunucusuna karşı çalıştırabilir.
 *
 * Sertifika zinciri doğrulanmaz (bilgisayarın sertifikası kendinden imzalı);
 * onun yerine SHA-256 parmak izi ilk eşleşmede kaydedilir ve sonra sabitlenir.
 */
class ClientSession(
    private val listener: Listener,
    private val files: FileStore,
) {
    interface Listener {
        /** Onay yönteminde iki ekranda da görünen kod. */
        fun onPairingCode(code: String) {}
        /** Dosya dışındaki her ileti (medya, pano, zil...). Okuyucu iş parçacığında çağrılır. */
        fun onMessage(msg: JSONObject) {}
        fun onTransfer(t: Transfer) {}
        fun onClosed(reason: String?) {}
    }

    /** Gelen dosyanın yazılacağı yer (Android'de MediaStore → İndirilenler/Talk). */
    interface FileStore {
        /** Kabul etmezse IOException fırlatır (sebep karşı tarafa iletilir). */
        fun create(name: String, size: Long, mime: String): Sink
    }

    interface Sink {
        fun write(data: ByteArray)
        /** Tamamlanan dosyanın kullanıcıya gösterilecek yeri (uri ya da yol). */
        fun commit(): String
        fun abort()
    }

    class Source(val name: String, val size: Long, val mime: String, val open: () -> InputStream)

    data class Transfer(
        val direction: String, val tid: Long, val name: String, val size: Long, val done: Long,
        val state: String, val error: String? = null, val location: String? = null,
    )

    sealed class AuthResult {
        data class Welcome(val token: String?, val serverId: String, val serverName: String) : AuthResult()
        data class Failed(val reason: String) : AuthResult()
    }

    class FingerprintMismatch(val actual: String) : IOException("güvenlik kodu değişti")

    /** TCP'de SSLSocket; Bluetooth'ta null (zaman aşımı uygulanamaz, kopunca okuma hata verir). */
    private var socket: SSLSocket? = null
    private var closer: () -> Unit = {}
    private lateinit var input: DataInputStream
    private lateinit var output: BufferedOutputStream
    private val writeLock = Any()
    @Volatile var closed = false
        private set
    lateinit var fingerprint: String
        private set

    private class Incoming(val tid: Long, val name: String, val size: Long, val sink: Sink) {
        var received = 0L
        val sha: MessageDigest = MessageDigest.getInstance("SHA-256")
    }
    private class Outgoing { @Volatile var cancelled = false; val reply = java.util.concurrent.LinkedBlockingQueue<JSONObject>() }
    private val incoming = ConcurrentHashMap<Long, Incoming>()
    private val outgoing = ConcurrentHashMap<Long, Outgoing>()
    private val nextTid = AtomicLong(1)

    /** TLS bağlantısını kurar ve sertifikanın parmak izini döndürür. */
    fun open(host: String, port: Int, timeoutMs: Int = 5000): String {
        val ctx = SSLContext.getInstance("TLS")
        ctx.init(null, arrayOf(AcceptAll), SecureRandom())
        val raw = Socket()
        raw.connect(InetSocketAddress(host, port), timeoutMs)
        raw.tcpNoDelay = true
        val ssl = ctx.socketFactory.createSocket(raw, host, port, true) as SSLSocket
        socket = ssl
        closer = { ssl.close() }
        ssl.soTimeout = timeoutMs * 3
        ssl.startHandshake()
        fingerprint = Auth.sha256Hex(ssl.session.peerCertificates[0].encoded)
        input = DataInputStream(ssl.inputStream.buffered(64 * 1024))
        output = BufferedOutputStream(ssl.outputStream, 64 * 1024)
        return fingerprint
    }

    /**
     * Önceden açılmış bir akış (Bluetooth RFCOMM) üzerinde TLS kurar ve
     * sertifikanın parmak izini döndürür. [close] alttaki bağlantıyı kapatır.
     */
    fun openStreams(rawIn: java.io.InputStream, rawOut: java.io.OutputStream, close: () -> Unit): String {
        val ctx = SSLContext.getInstance("TLS")
        ctx.init(null, arrayOf(AcceptAll), SecureRandom())
        val tls = EngineTls(ctx.createSSLEngine(), rawIn, rawOut)
        closer = { tls.close(); close() }
        try {
            tls.handshake()
        } catch (e: Exception) {
            close()
            throw e as? java.io.IOException ?: java.io.IOException(e.message, e)
        }
        fingerprint = Auth.sha256Hex(tlsPeerCert(tls).encoded)
        input = DataInputStream(tls.inputStream.buffered(64 * 1024))
        output = BufferedOutputStream(tls.outputStream, 64 * 1024)
        return fingerprint
    }

    private fun tlsPeerCert(tls: EngineTls) = tls.peerCertificate()

    /**
     * Engelleyen el sıkışma. [password] yalnızca bilgisayar şifre isterse
     * kullanılır; isterse ve yoksa sonuç Failed("password_needed") olur.
     */
    fun handshake(deviceId: String, name: String, model: String, token: String?, password: String?): AuthResult {
        send(JSONObject().put("type", "hello").put("proto", 1).put("device_id", deviceId)
            .put("name", name).put("model", model).put("platform", "android").put("app", "talk-to-linux")
            .put("token", token ?: JSONObject.NULL))
        val hello = readJson()
        if (hello.optString("type") != "hello") return AuthResult.Failed("protocol")
        val serverId = hello.optString("device_id")
        val serverName = hello.optString("name", "Linux")
        var msg = readJson()
        if (msg.optString("type") == "auth_required") {
            val nonce = msg.getString("nonce")
            if (msg.optString("method") == "password") {
                if (password == null) return AuthResult.Failed("password_needed")
                send(JSONObject().put("type", "auth_password")
                    .put("proof", Auth.passwordProof(password, nonce, fingerprint)))
                msg = readJson()
            } else {
                listener.onPairingCode(Auth.pairingCode(nonce, fingerprint, deviceId))
                socket?.soTimeout = 75_000  // kullanıcı bilgisayarda onaylayana kadar
                msg = readJson()
            }
        }
        return when (msg.optString("type")) {
            "welcome" -> AuthResult.Welcome(msg.optString("token").ifEmpty { null }, serverId, serverName)
            "auth_failed" -> AuthResult.Failed(msg.optString("reason", "rejected"))
            else -> AuthResult.Failed("protocol")
        }
    }

    private fun readJson(): JSONObject {
        while (true) {
            val f = Frame.read(input)
            if (f is Frame.In.Json && f.type != "ping") return f.msg
        }
    }

    /** Kimlik doğrulandıktan sonra okuyucu ve ping iş parçacıklarını başlatır. */
    fun start() {
        socket?.soTimeout = 50_000
        Thread({ readLoop() }, "talkto-okuyucu").start()
        Thread({
            try {
                while (!closed) {
                    Thread.sleep(15_000)
                    send(JSONObject().put("type", "ping"))
                }
            } catch (_: Exception) {
            }
        }, "talkto-ping").apply { isDaemon = true }.start()
    }

    private fun readLoop() {
        var reason: String? = null
        try {
            while (!closed) {
                when (val f = Frame.read(input)) {
                    is Frame.In.Json -> dispatch(f.msg)
                    is Frame.In.Binary -> onChunk(f.tid, f.data)
                }
            }
        } catch (e: Exception) {
            if (!closed) reason = e.message ?: e.javaClass.simpleName
        } finally {
            close()
            listener.onClosed(reason)
        }
    }

    private fun dispatch(msg: JSONObject) {
        val tid = msg.optLong("transfer_id")
        when (msg.optString("type")) {
            "ping" -> send(JSONObject().put("type", "pong"))
            "pong" -> {}
            "file_offer" -> onOffer(msg)
            "file_done" -> onFileDone(msg)
            "file_accept", "file_reject", "file_result" -> outgoing[tid]?.reply?.offer(msg)
            "file_cancel" -> {
                incoming.remove(tid)?.let {
                    it.sink.abort()
                    listener.onTransfer(Transfer("in", tid, it.name, it.size, it.received, "cancelled"))
                }
                outgoing[tid]?.let { it.cancelled = true; it.reply.offer(msg) }
            }
            else -> listener.onMessage(msg)
        }
    }

    private fun onOffer(msg: JSONObject) {
        val tid = msg.optLong("transfer_id")
        val name = msg.optString("name", "dosya")
        val size = msg.optLong("size", -1)
        if (tid <= 0 || size < 0 || incoming.containsKey(tid)) {
            send(JSONObject().put("type", "file_reject").put("transfer_id", tid).put("reason", "geçersiz teklif"))
            return
        }
        val sink = try {
            files.create(name, size, msg.optString("mime", "application/octet-stream"))
        } catch (e: IOException) {
            send(JSONObject().put("type", "file_reject").put("transfer_id", tid).put("reason", e.message))
            listener.onTransfer(Transfer("in", tid, name, size, 0, "failed", e.message))
            return
        }
        incoming[tid] = Incoming(tid, name, size, sink)
        listener.onTransfer(Transfer("in", tid, name, size, 0, "active"))
        send(JSONObject().put("type", "file_accept").put("transfer_id", tid))
    }

    private var lastProgress = 0L

    private fun onChunk(tid: Long, data: ByteArray) {
        val inc = incoming[tid] ?: return
        try {
            if (inc.received + data.size > inc.size) throw IOException("bildirilen boyuttan fazla veri")
            inc.sink.write(data)
        } catch (e: IOException) {
            incoming.remove(tid)
            inc.sink.abort()
            listener.onTransfer(Transfer("in", tid, inc.name, inc.size, inc.received, "failed", e.message))
            send(JSONObject().put("type", "file_cancel").put("transfer_id", tid))
            return
        }
        inc.sha.update(data)
        inc.received += data.size
        val now = System.currentTimeMillis()
        if (now - lastProgress > 250) {
            lastProgress = now
            listener.onTransfer(Transfer("in", tid, inc.name, inc.size, inc.received, "active"))
        }
    }

    private fun onFileDone(msg: JSONObject) {
        val tid = msg.optLong("transfer_id")
        val inc = incoming.remove(tid) ?: return
        val ok = inc.received == inc.size &&
            inc.sha.digest().joinToString("") { "%02x".format(it) } == msg.optString("sha256").lowercase()
        if (!ok) {
            inc.sink.abort()
            listener.onTransfer(Transfer("in", tid, inc.name, inc.size, inc.received, "failed", "doğrulama başarısız"))
            send(JSONObject().put("type", "file_result").put("transfer_id", tid).put("ok", false))
            return
        }
        val location = try {
            inc.sink.commit()
        } catch (e: IOException) {
            send(JSONObject().put("type", "file_result").put("transfer_id", tid).put("ok", false).put("reason", e.message))
            listener.onTransfer(Transfer("in", tid, inc.name, inc.size, inc.received, "failed", e.message))
            return
        }
        send(JSONObject().put("type", "file_result").put("transfer_id", tid).put("ok", true))
        listener.onTransfer(Transfer("in", tid, inc.name, inc.size, inc.size, "done", location = location))
    }

    /** Engelleyen gönderim; ayrı iş parçacığında çağrılmalı. */
    fun sendFile(src: Source) {
        val tid = nextTid.getAndIncrement()
        val o = Outgoing()
        outgoing[tid] = o
        var sent = 0L
        fun event(state: String, err: String? = null) =
            listener.onTransfer(Transfer("out", tid, src.name, src.size, sent, state, err))
        try {
            event("waiting")
            send(JSONObject().put("type", "file_offer").put("transfer_id", tid).put("name", src.name)
                .put("size", src.size).put("mime", src.mime))
            val reply = o.reply.poll(120, java.util.concurrent.TimeUnit.SECONDS) ?: throw IOException("zaman aşımı")
            if (reply.optString("type") != "file_accept") {
                event(if (reply.optString("type") == "file_reject") "rejected" else "cancelled", reply.optString("reason"))
                return
            }
            val sha = MessageDigest.getInstance("SHA-256")
            val buf = ByteArray(Frame.CHUNK)
            var last = 0L
            src.open().use { ins ->
                while (true) {
                    if (o.cancelled || closed) throw IOException("iptal edildi")
                    val n = ins.readNBytesCompat(buf)
                    if (n <= 0) break
                    sha.update(buf, 0, n)
                    sendRaw(Frame.encodeBinary(tid, buf, n))
                    sent += n
                    val now = System.currentTimeMillis()
                    if (now - last > 250) { last = now; event("active") }
                }
            }
            if (sent != src.size) throw IOException("dosya boyutu değişti")
            send(JSONObject().put("type", "file_done").put("transfer_id", tid)
                .put("sha256", sha.digest().joinToString("") { "%02x".format(it) }))
            val res = o.reply.poll(60, java.util.concurrent.TimeUnit.SECONDS) ?: throw IOException("zaman aşımı")
            if (res.optString("type") == "file_result" && res.optBoolean("ok")) event("done")
            else throw IOException(res.optString("reason").ifEmpty { "bilgisayar doğrulayamadı" })
        } catch (e: Exception) {
            event(if (o.cancelled) "cancelled" else "failed", e.message)
            if (!closed) runCatching { send(JSONObject().put("type", "file_cancel").put("transfer_id", tid)) }
        } finally {
            outgoing.remove(tid)
        }
    }

    fun cancelTransfer(direction: String, tid: Long) {
        if (direction == "out") {
            outgoing[tid]?.let { it.cancelled = true; it.reply.offer(JSONObject().put("type", "file_cancel")) }
        } else incoming.remove(tid)?.let {
            it.sink.abort()
            listener.onTransfer(Transfer("in", tid, it.name, it.size, it.received, "cancelled"))
            send(JSONObject().put("type", "file_cancel").put("transfer_id", tid))
        }
    }

    fun send(msg: JSONObject) = sendRaw(Frame.encodeJson(msg))

    private fun sendRaw(bytes: ByteArray) {
        synchronized(writeLock) {
            if (closed) throw IOException("bağlantı kapalı")
            output.write(bytes)
            output.flush()
        }
    }

    /** Kapanmış bağlantıya yazmayı sessizce yok sayar. */
    fun trySend(msg: JSONObject): Boolean = try { send(msg); true } catch (_: IOException) { false }

    fun close() {
        if (closed) return
        closed = true
        incoming.values.forEach { it.sink.abort() }
        incoming.clear()
        outgoing.values.forEach { it.cancelled = true; it.reply.offer(JSONObject().put("type", "file_cancel")) }
        runCatching { closer() }
    }

    /**
     * Bilinçli olarak zincir doğrulaması yapmaz: bilgisayarın sertifikası kendinden
     * imzalıdır. Güven, open() sonrası SHA-256 parmak izinin kayıtlı olanla
     * karşılaştırılmasından (Talk.doConnect) ve şifre/onay kodundan gelir.
     */
    @Suppress("CustomX509TrustManager", "TrustAllX509TrustManager")
    private object AcceptAll : X509TrustManager {
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
            if (chain.isNullOrEmpty()) throw java.security.cert.CertificateException("sertifika yok")
        }
        override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
    }
}

/** InputStream.readNBytes API 33+; tamponu olabildiğince doldurur. */
internal fun InputStream.readNBytesCompat(buf: ByteArray): Int {
    var total = 0
    while (total < buf.size) {
        val n = read(buf, total, buf.size - total)
        if (n < 0) break
        total += n
    }
    return total
}
