package lab.crucible.talktolinux

import android.app.Application
import lab.crucible.talktolinux.core.CrashLog
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.core.Notifs
import lab.crucible.talktolinux.core.cleanTempCopies

class TalkApp : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashLog.install(this)
        Talk.init(this)
        Notifs.createChannels(this)
        cleanTempCopies(this)  // önceki çalışmadan kalan gönderim kopyaları
    }
}
