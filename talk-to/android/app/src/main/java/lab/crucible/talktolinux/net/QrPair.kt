package lab.crucible.talktolinux.net

import java.net.URLDecoder

/**
 * Bilgisayarın gösterdiği karekod (Linux: talkto/karekod.py):
 * `talkto://pair?v=1&h=192.168.1.34,10.0.0.5&p=47600&fp=<64 hex>&k=<32 hex>&n=<ad>`.
 * Adresler yalnızca yerel ağ IP'si olabilir (ev/iş ağı, Tailscale): bağlantı bir web sayfasından açılsa bile
 * telefon internetteki bir sunucuya yönlendirilemez; ad çözümlemesi de yapılmaz.
 */
data class QrPair(val hosts: List<String>, val port: Int, val fp: String, val key: String, val name: String) {
    companion object {
        private val HEX64 = Regex("^[0-9a-f]{64}$")
        private val HEX32 = Regex("^[0-9a-f]{32}$")
        private val IPV4 = Regex("^(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}$")

        /** 10/8, 172.16/12, 192.168/16, 169.254/16 (yerel), 100.64/10 (Tailscale). */
        fun local(ip: String): Boolean {
            val (a, b) = ip.split('.').take(2).map { it.toInt() }
            return a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168) || (a == 169 && b == 254) ||
                (a == 100 && b in 64..127)
        }

        /** Talk To karekodu değilse ya da bozuksa null. */
        fun parse(text: String): QrPair? {
            val t = text.trim()
            if (!t.startsWith("talkto://pair?")) return null
            val q = t.substringAfter('?').split('&').mapNotNull { part ->
                val i = part.indexOf('=')
                if (i <= 0) null else part.substring(0, i) to runCatching {
                    URLDecoder.decode(part.substring(i + 1), "UTF-8")
                }.getOrNull()
            }.toMap()
            if (q["v"] != "1") return null
            val hosts = q["h"]?.split(',')?.filter { IPV4.matches(it) && local(it) }?.take(6).orEmpty()
            val port = q["p"]?.toIntOrNull()?.takeIf { it in 1..65535 } ?: return null
            val fp = q["fp"]?.takeIf { HEX64.matches(it) } ?: return null
            val key = q["k"]?.takeIf { HEX32.matches(it) } ?: return null
            if (hosts.isEmpty()) return null
            val name = q["n"]?.take(40)?.filter { !it.isISOControl() }?.ifBlank { null } ?: "Bilgisayar"
            return QrPair(hosts, port, fp, key, name)
        }
    }
}
