package lab.crucible.kopru

import android.app.Application
import lab.crucible.kopru.core.Kopru
import lab.crucible.kopru.core.Notifs

class KopruApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Kopru.init(this)
        Notifs.createChannels(this)
    }
}
