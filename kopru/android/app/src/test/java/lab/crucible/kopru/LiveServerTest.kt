package lab.crucible.kopru

import lab.crucible.kopru.net.ClientSession
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import kotlin.random.Random

/**
 * Gerçek Linux sunucusuna karşı uçtan uca test (Android cihaz gerekmez).
 * Yalnızca KOPRU_TEST_PORT tanımlıysa çalışır; bkz. kopru/linux/tests/android_canli_test.sh
 */
class LiveServerTest {
    private val port = System.getenv("KOPRU_TEST_PORT")?.toIntOrNull()
    private val password = System.getenv("KOPRU_TEST_PASSWORD")
    private val receiveDir = System.getenv("KOPRU_TEST_RECEIVE_DIR")

    private class Events : ClientSession.Listener {
        val transfers = LinkedBlockingQueue<ClientSession.Transfer>()
        val messages = LinkedBlockingQueue<JSONObject>()
        var code: String? = null
        override fun onPairingCode(code: String) { this.code = code }
        override fun onTransfer(t: ClientSession.Transfer) { if (t.state != "active" && t.state != "waiting") transfers.put(t) }
        override fun onMessage(msg: JSONObject) { messages.put(msg) }
    }

    private class MemoryStore : ClientSession.FileStore {
        val files = HashMap<String, ByteArray>()
        override fun create(name: String, size: Long, mime: String) = object : ClientSession.Sink {
            val buf = ByteArrayOutputStream()
            override fun write(data: ByteArray) = buf.write(data)
            override fun commit(): String { files[name] = buf.toByteArray(); return "mem://$name" }
            override fun abort() {}
        }
    }

    @Test
    fun pairSendReceiveAgainstLinux() {
        assumeTrue("KOPRU_TEST_PORT tanımlı değil", port != null)
        val ev = Events()
        val store = MemoryStore()

        // 1) Şifreyle eşleş (sunucu bağlantıyı Wi-Fi sayacak şekilde başlatılır).
        val s = ClientSession(ev, store)
        val fp = s.open("127.0.0.1", port!!)
        val first = s.handshake("kotlin-test-cihazi", "Kotlin Testi", "JVM", null, null)
        assertEquals(ClientSession.AuthResult.Failed("password_needed"), first)
        s.close()

        val s2 = ClientSession(ev, store)
        assertEquals(fp, s2.open("127.0.0.1", port))
        val res = s2.handshake("kotlin-test-cihazi", "Kotlin Testi", "JVM", null, password)
        assertTrue("$res", res is ClientSession.AuthResult.Welcome)
        val token = (res as ClientSession.AuthResult.Welcome).token!!
        s2.start()

        // 2) Telefondan bilgisayara dosya (gerçek SHA-256 doğrulaması sunucuda).
        val data = Random(7).nextBytes(900_000)
        s2.sendFile(ClientSession.Source("kotlin-dosyasi.bin", data.size.toLong(), "application/octet-stream") { data.inputStream() })
        val sent = ev.transfers.poll(20, TimeUnit.SECONDS)!!
        assertEquals("done", sent.state)
        assertArrayEquals(data, File(receiveDir, "kotlin-dosyasi.bin").readBytes())

        // 3) Bildirim ve medya iletileri bağlantıyı bozmadan gider; sunucu ping'lere cevap verir.
        s2.send(JSONObject().put("type", "notification").put("key", "k").put("package", "com.test")
            .put("app", "Test").put("title", "Merhaba").put("text", "Kotlin istemcisinden"))
        s2.send(JSONObject().put("type", "battery").put("level", 55).put("charging", false))
        s2.send(JSONObject().put("type", "ping"))
        Thread.sleep(300)
        assertTrue(!s2.closed)
        s2.close()

        // 4) Belirteçle yeniden bağlan: şifre sorulmaz.
        val s3 = ClientSession(ev, store)
        s3.open("127.0.0.1", port)
        val again = s3.handshake("kotlin-test-cihazi", "Kotlin Testi", "JVM", token, null)
        assertTrue("$again", again is ClientSession.AuthResult.Welcome)
        s3.start()

        // 5) Bilgisayardan telefona dosya: sunucuya sahte_telefon değil bu istemci bağlı;
        //    sunucu tarafı testi tetikler (KOPRU_TEST_SEND dosyası).
        File(receiveDir!!).parentFile!!.resolve("gonder-tetik").writeText("kotlin-test-cihazi")
        val got = ev.transfers.poll(20, TimeUnit.SECONDS)
        assertEquals("in", got?.direction)
        assertEquals("done", got?.state)
        assertEquals(System.getenv("KOPRU_TEST_SEND_SHA"), lab.crucible.kopru.net.Auth.sha256Hex(store.files[got!!.name]!!))
        s3.close()
    }
}
