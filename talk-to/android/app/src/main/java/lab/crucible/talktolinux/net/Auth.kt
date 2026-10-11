package lab.crucible.talktolinux.net

import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** Linux tarafındaki talkto/auth.py ile birebir aynı hesaplar. */
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

    /** Linux'taki auth.PBKDF2_ROUNDS ile aynı. */
    const val PBKDF2_ROUNDS = 100_000

    /** Sürüm 2: HMAC-SHA256(anahtar=PBKDF2(şifre, "talkto:parmakizi"), "nonce:parmakizi"). */
    fun passwordProof2(password: String, nonce: String, serverFp: String): String {
        val spec = javax.crypto.spec.PBEKeySpec(password.toCharArray(),
            "talkto:$serverFp".toByteArray(Charsets.UTF_8), PBKDF2_ROUNDS, 256)
        val key = javax.crypto.SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal("$nonce:$serverFp".toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }

    fun newSecret(): String = ByteArray(32).also { java.security.SecureRandom().nextBytes(it) }
        .joinToString("") { "%02x".format(it) }

    fun commitOf(secret: String): String = sha256Hex(secret.toByteArray(Charsets.UTF_8))

    /** Sürüm 2 onay kodu: telefonun önceden taahhüt ettiği rastgele değer de koda girer. */
    fun pairingCode2(nonce: String, secret: String, serverFp: String, deviceId: String): String =
        sixDigits("$nonce:$secret:$serverFp:$deviceId")

    private fun sixDigits(text: String): String {
        val d = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
        val n = ((d[0].toLong() and 0xFF) shl 24) or ((d[1].toLong() and 0xFF) shl 16) or
            ((d[2].toLong() and 0xFF) shl 8) or (d[3].toLong() and 0xFF)
        return "%06d".format(n % 1_000_000)
    }

    fun pairingCode(nonce: String, serverFp: String, deviceId: String): String {
        val d = MessageDigest.getInstance("SHA-256").digest("$nonce:$serverFp:$deviceId".toByteArray(Charsets.UTF_8))
        val n = ((d[0].toLong() and 0xFF) shl 24) or ((d[1].toLong() and 0xFF) shl 16) or
            ((d[2].toLong() and 0xFF) shl 8) or (d[3].toLong() and 0xFF)
        return "%06d".format(n % 1_000_000)
    }

    fun shortFingerprint(fp: String): String = fp.take(16).uppercase().chunked(4).joinToString(" ")
}
