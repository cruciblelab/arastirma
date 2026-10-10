package lab.crucible.kopru.net

import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** Linux tarafındaki kopru/auth.py ile birebir aynı hesaplar. */
object Auth {
    fun sha256Hex(data: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }

    fun passwordProof(password: String, nonce: String, serverFp: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        // Boş şifre: SecretKeySpec boş anahtarı kabul etmez; HMAC tanımı gereği
        // boş anahtar 64 sıfır baytla aynıdır.
        val key = password.toByteArray(Charsets.UTF_8).let { if (it.isEmpty()) ByteArray(64) else it }
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal("$nonce:$serverFp".toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }

    fun pairingCode(nonce: String, serverFp: String, deviceId: String): String {
        val d = MessageDigest.getInstance("SHA-256").digest("$nonce:$serverFp:$deviceId".toByteArray(Charsets.UTF_8))
        val n = ((d[0].toLong() and 0xFF) shl 24) or ((d[1].toLong() and 0xFF) shl 16) or
            ((d[2].toLong() and 0xFF) shl 8) or (d[3].toLong() and 0xFF)
        return "%06d".format(n % 1_000_000)
    }

    fun shortFingerprint(fp: String): String = fp.take(16).uppercase().chunked(4).joinToString(" ")
}
