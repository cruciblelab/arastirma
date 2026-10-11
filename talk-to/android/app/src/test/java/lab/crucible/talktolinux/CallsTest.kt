package lab.crucible.talktolinux

import lab.crucible.talktolinux.core.Calls
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Arama bildirimlerinin tanınması: önceden "süren" bildirim diye eleniyor, bilgisayara hiç gitmiyordu. */
class CallsTest {
    @Test
    fun recognisesCalls() {
        assertTrue(Calls.isCall("call", null))  // WhatsApp, Instagram, telefon
        assertTrue(Calls.isCall(null, "android.app.Notification\$CallStyle"))  // Android 12+ arama şablonu
        assertFalse(Calls.isCall("msg", null))
        assertFalse(Calls.isCall("transport", "android.app.Notification\$MediaStyle"))
    }

    @Test
    fun ringingOrOngoing() {
        assertEquals("ringing", Calls.state(1, false))  // CallStyle: gelen
        assertEquals("ongoing", Calls.state(2, true))   // CallStyle: süren (tam ekran olsa da)
        assertEquals("ringing", Calls.state(3, false))  // süzülen arama da çalıyor sayılır
        assertEquals("ringing", Calls.state(0, true))   // eski tarz: tam ekran açan çalan aramadır
        assertEquals("ongoing", Calls.state(0, false))
    }
}
