package lab.crucible.talktolinux.net

import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException

/**
 * Yerel ağda bilgisayar arar (UDP 47601) ve USB tünelinin (127.0.0.1:47600)
 * açık olup olmadığını yoklar. Android'e bağımlı değildir; MulticastLock'u
 * çağıran taraf alır.
 */
class Discovery(
    private val onFound: (List<Found>) -> Unit,
    private val onUsb: (Boolean) -> Unit,
    private val usbAllowed: () -> Boolean,
    private val udpPort: Int = 47601,
    private val tcpPort: Int = 47600,
) {
    data class Found(
        val id: String, val name: String, val host: String, val port: Int,
        val fp: String, val password: Boolean, val seenAt: Long,
    )

    @Volatile private var running = false
    private var thread: Thread? = null
    private var socket: DatagramSocket? = null
    private val found = LinkedHashMap<String, Found>()

    fun start() {
        if (running) return
        running = true
        thread = Thread({ loop() }, "talkto-kesif").apply { isDaemon = true; start() }
    }

    fun stop() {
        running = false
        socket?.close()
        thread = null
    }

    private fun openSocket(): DatagramSocket {
        val s = try {
            DatagramSocket(null).apply { reuseAddress = true; bind(InetSocketAddress(udpPort)) }
        } catch (_: Exception) {
            DatagramSocket(InetSocketAddress(0))  // port meşgul: yalnızca probe cevaplarını alırız
        }
        s.broadcast = true
        s.soTimeout = 500
        return s
    }

    /** Beklenmeyen bir hatada (ağ değişti, soket kapandı) iş parçacığı ölmesin: kısa bekleyip yeniden kur. */
    private fun loop() {
        while (running) {
            runOnce()
            if (running) runCatching { Thread.sleep(2000) }
        }
    }

    private fun runOnce() {
        var lastProbe = 0L
        var lastUsb = 0L
        var usb = false
        val buf = ByteArray(2048)
        try {
            val s = openSocket().also { socket = it }
            val probe = JSONObject().put("talkto", 1).put("type", "probe").toString().toByteArray()
            while (running) {
                val now = System.currentTimeMillis()
                if (now - lastProbe > 3000) {
                    lastProbe = now
                    runCatching {
                        s.send(DatagramPacket(probe, probe.size, InetAddress.getByName("255.255.255.255"), udpPort))
                    }
                    prune(now)
                    publish()  // liste değişmese de: otomatik yeniden bağlanma bu turu dinler
                }
                if (now - lastUsb > 3000) {
                    lastUsb = now
                    usb = usbAllowed() && probeUsb()
                    onUsb(usb)
                }
                try {
                    val p = DatagramPacket(buf, buf.size)
                    s.receive(p)
                    handle(String(p.data, 0, p.length, Charsets.UTF_8), p.address.hostAddress ?: continue)
                } catch (_: SocketTimeoutException) {
                }
            }
        } catch (e: Exception) {
            if (running) System.err.println("talkto keşif: ${e.message}")
        } finally {
            socket?.close()
            if (usb) onUsb(false)
        }
    }

    private fun handle(text: String, host: String) {
        val o = runCatching { JSONObject(text) }.getOrNull() ?: return
        if (o.optInt("talkto") != 1 || o.optString("type") != "announce") return
        val id = o.optString("id").ifEmpty { return }
        val f = Found(id, o.optString("name", host), host, o.optInt("port", tcpPort),
            o.optString("fp"), o.optBoolean("password"), System.currentTimeMillis())
        // Anahtar kimlik + güvenlik kodu: aynı kimlikle yapılan sahte bir duyuru gerçeğini ezmesin.
        val changed = synchronized(found) {
            val old = found.put("$id|${f.fp}", f)
            old == null || old.copy(seenAt = 0) != f.copy(seenAt = 0)
        }
        if (changed) publish()
    }

    private fun prune(now: Long) {
        synchronized(found) { found.values.removeAll { now - it.seenAt > 10_000 } }
    }

    private fun publish() = onFound(synchronized(found) { found.values.toList() })

    /**
     * Bilgisayarda sunucu yokken de adb reverse kuralı kalmış olabilir: adb bağlantıyı kabul edip hemen
     * kapatır. TLS sunucusu ise ClientHello bekler ve kendisi bir şey yollamaz; kısa okuma bunu ayırır.
     */
    private fun probeUsb(): Boolean = try {
        Socket().use {
            it.connect(InetSocketAddress("127.0.0.1", tcpPort), 300)
            it.soTimeout = 400
            it.getInputStream().read() != -1
        }
    } catch (_: SocketTimeoutException) {
        true
    } catch (_: Exception) {
        false
    }
}
