package lab.crucible.talktolinux

import lab.crucible.talktolinux.net.Auth
import lab.crucible.talktolinux.net.Frame
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.DataInputStream
import java.io.File

/** Linux tarafıyla aynı test vektörleri: talk-to/protokol-test-vektorleri.json */
class AuthTest {
    private val vec = JSONObject(File("../../protokol-test-vektorleri.json").readText())

    private fun hex(b: ByteArray) = b.joinToString("") { "%02x".format(it) }

    @Test
    fun passwordProofMatchesLinux() {
        val arr = vec.getJSONArray("password_proof")
        for (i in 0 until arr.length()) {
            val v = arr.getJSONObject(i)
            assertEquals(v.getString("proof"), Auth.passwordProof(v.getString("password"), v.getString("nonce"), v.getString("fp")))
        }
    }

    @Test
    fun pairingCodeMatchesLinux() {
        val arr = vec.getJSONArray("pairing_code")
        for (i in 0 until arr.length()) {
            val v = arr.getJSONObject(i)
            assertEquals(v.getString("code"), Auth.pairingCode(v.getString("nonce"), v.getString("fp"), v.getString("device_id")))
        }
    }

    @Test
    fun framesMatchLinux() {
        val arr = vec.getJSONArray("frames")
        for (i in 0 until arr.length()) {
            val v = arr.getJSONObject(i)
            val bytes = v.getString("hex").chunked(2).map { it.toInt(16).toByte() }.toByteArray()
            if (v.has("json")) {
                assertEquals(v.getString("hex"), hex(Frame.encodeJson(v.getJSONObject("json"))))
                val f = Frame.read(DataInputStream(ByteArrayInputStream(bytes))) as Frame.In.Json
                assertEquals(v.getJSONObject("json").getString("type"), f.type)
            } else {
                val data = v.getString("data").chunked(2).map { it.toInt(16).toByte() }.toByteArray()
                assertEquals(v.getString("hex"), hex(Frame.encodeBinary(v.getLong("tid"), data)))
                val f = Frame.read(DataInputStream(ByteArrayInputStream(bytes))) as Frame.In.Binary
                assertEquals(v.getLong("tid"), f.tid)
                assertEquals(v.getString("data"), hex(f.data))
            }
        }
    }

    @Test
    fun shortFingerprint() {
        assertEquals("3F1C 9A0B 7D2E 4F6A", Auth.shortFingerprint("3f1c9a0b7d2e4f6a8b9c"))
    }
}
