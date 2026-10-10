package lab.crucible.talktolinux

import android.app.Application
import lab.crucible.talktolinux.core.Talk
import lab.crucible.talktolinux.core.Notifs

class TalkApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Talk.init(this)
        Notifs.createChannels(this)
    }
}
