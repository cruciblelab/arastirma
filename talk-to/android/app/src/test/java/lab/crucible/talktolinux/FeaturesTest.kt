package lab.crucible.talktolinux

import lab.crucible.talktolinux.core.Features
import org.junit.Assert.assertEquals
import org.junit.Test

class FeaturesTest {
    @Test
    fun simpleModeShowsOnlyAddedExtras() {
        assertEquals(emptySet<String>(), Features.compute(true, emptySet()))
        assertEquals(setOf("files"), Features.compute(true, setOf("files", "bilinmeyen")))
    }

    @Test
    fun fullModeShowsEverything() {
        assertEquals(Features.EXTRAS.keys, Features.compute(false, emptySet()))
    }
}
