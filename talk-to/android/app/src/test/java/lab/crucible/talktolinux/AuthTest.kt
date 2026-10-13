package lab.crucible.talktolinux

import lab.crucible.talktolinux.net.Auth
import lab.crucible.talktolinux.net.Frame
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.DataInputStream
import java.io.File

/** Linux tarafıyla aynı test vektörleri: talk-to/protocol/vectors.json */
class AuthTest {
    private val vec = JSONObject(File("../../protocol/vectors.json").readText())

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
    fun version2MatchesLinux() {
        val pw = vec.getJSONArray("password_proof2")
        for (i in 0 until pw.length()) {
            val v = pw.getJSONObject(i)
            assertEquals(v.getString("proof"), Auth.passwordProof2(v.getString("password"), v.getString("nonce"), v.getString("fp")))
        }
        val pc = vec.getJSONArray("pairing_code2")
        for (i in 0 until pc.length()) {
            val v = pc.getJSONObject(i)
            assertEquals(v.getString("commit"), Auth.commitOf(v.getString("secret")))
            assertEquals(v.getString("code"),
                Auth.pairingCode2(v.getString("nonce"), v.getString("secret"), v.getString("fp"), v.getString("device_id")))
        }
        assertEquals(vec.getInt("_pbkdf2_rounds"), Auth.PBKDF2_ROUNDS)
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
    fun qrProofMatchesLinux() {
        val arr = vec.getJSONArray("qr_proof")
        for (i in 0 until arr.length()) {
            val v = arr.getJSONObject(i)
            assertEquals(v.getString("proof"),
                Auth.qrProof(v.getString("key"), v.getString("nonce"), v.getString("fp"), v.getString("device_id")))
        }
    }

    /** Linux'un çizdiği karekod (kareleri) ZXing ile çözülür ve QrPair alanları doğru çıkar. */
    @Test
    fun qrMatrixDecodes() {
        val m = vec.getJSONObject("qr_matrix")
        val rows = m.getJSONArray("rows")
        val n = rows.length()
        val scale = 4
        val quiet = 4
        val side = (n + 2 * quiet) * scale
        val px = IntArray(side * side) { 0xFFFFFF }
        for (y in 0 until n) for (x in 0 until n) if (rows.getString(y)[x] == '1') {
            for (dy in 0 until scale) for (dx in 0 until scale)
                px[((y + quiet) * scale + dy) * side + (x + quiet) * scale + dx] = 0
        }
        val bmp = com.google.zxing.BinaryBitmap(com.google.zxing.common.HybridBinarizer(
            com.google.zxing.RGBLuminanceSource(side, side, px)))
        val text = com.google.zxing.qrcode.QRCodeReader().decode(bmp).text
        assertEquals(m.getString("text"), text)
        val qr = lab.crucible.talktolinux.net.QrPair.parse(text)!!
        assertEquals(listOf("192.168.1.34", "10.0.0.5"), qr.hosts)
        assertEquals(47600, qr.port)
        assertEquals("Ali'nin bilgisayarı", qr.name)
        assertEquals("00112233445566778899aabbccddeeff", qr.key)
    }

    @Test
    fun shortFingerprint() {
        assertEquals("3F1C 9A0B 7D2E 4F6A", Auth.shortFingerprint("3f1c9a0b7d2e4f6a8b9c"))
    }
}
