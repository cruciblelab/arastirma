package lab.crucible.talktolinux

import lab.crucible.talktolinux.net.QrPair
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class QrPairTest {
    private val fp = "ab".repeat(32)
    private val key = "cd".repeat(16)
    private fun link(h: String = "192.168.1.34", p: String = "47600", f: String = fp, k: String = key, v: String = "1") =
        "talkto://pair?v=$v&h=$h&p=$p&fp=$f&k=$k&n=Ev%20bilgisayar%C4%B1"

    @Test
    fun parses() {
        val q = QrPair.parse(link(h = "192.168.1.34,100.70.1.2,10.0.0.5"))!!
        assertEquals(listOf("192.168.1.34", "100.70.1.2", "10.0.0.5"), q.hosts)
        assertEquals(47600, q.port)
        assertEquals("Ev bilgisayarı", q.name)
    }

    /** Bağlantı bir web sayfasından da açılabilir: internetteki adrese, ada, bozuk alana gidilmez. */
    @Test
    fun rejectsWhatIsNotLocal() {
        assertNull(QrPair.parse(link(h = "85.105.1.2")))
        assertNull(QrPair.parse(link(h = "evil.example.com")))
        assertEquals(listOf("192.168.1.34"), QrPair.parse(link(h = "8.8.8.8,192.168.1.34"))!!.hosts)
        assertNull(QrPair.parse(link(p = "70000")))
        assertNull(QrPair.parse(link(f = "zz")))
        assertNull(QrPair.parse(link(k = "00")))
        assertNull(QrPair.parse(link(v = "2")))
        assertNull(QrPair.parse("https://example.com"))
        assertNull(QrPair.parse("talkto://pair?v=1"))
    }
}
