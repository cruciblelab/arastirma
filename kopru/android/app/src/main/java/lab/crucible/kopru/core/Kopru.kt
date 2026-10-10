package lab.crucible.kopru.core

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.util.Base64
import android.widget.Toast
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import lab.crucible.kopru.net.ClientSession
import lab.crucible.kopru.net.Discovery
import lab.crucible.kopru.service.KopruService
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.Executors

/** Uygulamanın tek durumu: bağlantı, keşif, bilgisayardaki medya, aktarımlar. */
object Kopru {
    lateinit var app: Context
        private set
    lateinit var prefs: Prefs
        private set

    data class Target(val host: String, val port: Int, val kind: String, val serverId: String?,
                      val name: String, val fp: String?)

    sealed class State {
        object Idle : State()
        data class Connecting(val target: Target) : State()
        data class Approval(val target: Target, val code: String) : State()
        data class Connected(val target: Target, val serverId: String, val serverName: String) : State()
    }

    data class PcMedia(val title: String, val artist: String, val player: String, val playing: Boolean,
                       val positionMs: Long, val durationMs: Long, val volume: Int?, val canSeek: Boolean,
                       val artId: String?, val receivedAt: Long)

    val state = MutableStateFlow<State>(State.Idle)
    val found = MutableStateFlow<List<Discovery.Found>>(emptyList())
    val usbAvailable = MutableStateFlow(false)
    val pcMedia = MutableStateFlow<PcMedia?>(null)
    val pcArt = MutableStateFlow<Pair<String, Bitmap>?>(null)
    val transfers = MutableStateFlow<List<ClientSession.Transfer>>(emptyList())
    /** Şifre isteyen bilgisayar (arayüz şifre penceresini açar). */
    val passwordFor = MutableStateFlow<Target?>(null)
    val messages = MutableSharedFlow<String>(extraBufferCapacity = 8)

    @Volatile private var session: ClientSession? = null
    private val connector = Executors.newSingleThreadExecutor()
    private val sender = Executors.newSingleThreadExecutor()
    private val fileSender = Executors.newFixedThreadPool(2)
    private val main = Handler(Looper.getMainLooper())
    private var discovery: Discovery? = null
    private var discoveryUsers = 0
    private var multicastLock: WifiManager.MulticastLock? = null
    private var lastAutoAttempt = 0L
    private val iconsSent = HashSet<String>()

    fun init(context: Context) {
        app = context.applicationContext
        prefs = Prefs(app)
    }

    fun isConnected() = session != null && state.value is State.Connected

    private fun say(text: String) {
        messages.tryEmit(text)
    }

    // ---- bağlanma ----------------------------------------------------------------

    fun connect(target: Target, password: String? = null) {
        if (state.value !is State.Idle) return
        passwordFor.value = null
        state.value = State.Connecting(target)
        connector.execute { doConnect(target, password) }
    }

    @Volatile private var pending: ClientSession? = null

    /** Bağlanırken ya da onay beklerken vazgeç. */
    fun cancelConnecting() {
        pending?.close()
    }

    private fun doConnect(target: Target, password: String?) {
        val s = ClientSession(listener, DownloadsStore(app))
        pending = s
        try {
            val fp = s.open(target.host, target.port)
            val stored = prefs.server(target.serverId)
            if (stored != null && stored.fp != fp) {
                s.close()
                fail("${stored.name} bilgisayarının güvenlik kodu değişmiş. Köprü yeniden kurulduysa " +
                    "bilgisayarı listeden unutup tekrar eşleştir; kurulmadıysa bağlanma.", auto = false)
                return
            }
            val known = prefs.serverByFp(fp)
            approvalTarget = target
            val res = s.handshake(prefs.deviceId, prefs.deviceName, Build.MANUFACTURER + " " + Build.MODEL,
                known?.token, password)
            approvalTarget = null
            when (res) {
                is ClientSession.AuthResult.Welcome -> {
                    prefs.saveServer(Prefs.Server(res.serverId, res.serverName, fp, res.token ?: known?.token,
                        target.host, target.port, target.kind))
                    prefs.autoServer = res.serverId
                    session = s
                    iconsSent.clear()
                    PhoneMedia.resetArt()
                    state.value = State.Connected(target.copy(fp = fp), res.serverId, res.serverName)
                    s.start()
                    main.post {
                        ContextCompat.startForegroundService(app, Intent(app, KopruService::class.java))
                        PhoneMedia.push()
                    }
                }
                is ClientSession.AuthResult.Failed -> {
                    s.close()
                    when (res.reason) {
                        "password_needed" -> { state.value = State.Idle; passwordFor.value = target.copy(fp = fp) }
                        "wrong_password" -> { state.value = State.Idle; say("Şifre yanlış"); passwordFor.value = target.copy(fp = fp) }
                        "rejected" -> fail("Bilgisayarda reddedildi ya da süre doldu", auto = false)
                        "too_many_attempts" -> fail("Çok fazla hatalı deneme. 10 dakika sonra tekrar dene.", auto = false)
                        else -> fail("Bağlantı kurulamadı (${res.reason})")
                    }
                }
            }
        } catch (e: Exception) {
            val cancelled = s.closed
            s.close()
            approvalTarget = null
            when {
                cancelled -> fail("Vazgeçildi", auto = false)
                e is IOException -> fail("${target.name}: bağlanılamadı (${e.message ?: e.javaClass.simpleName})")
                else -> fail("Beklenmeyen hata: ${e.message}")
            }
        } finally {
            pending = null
        }
    }

    @Volatile private var approvalTarget: Target? = null

    private fun fail(text: String, auto: Boolean = true) {
        state.value = State.Idle
        if (!auto) prefs.autoServer = null
        say(text)
    }

    /** Kullanıcı bağlantıyı kesti: otomatik yeniden bağlanma da durur. */
    fun disconnect() {
        prefs.autoServer = null
        val s = session
        session = null
        state.value = State.Idle
        pcMedia.value = null
        connector.execute { s?.close() }
        app.stopService(Intent(app, KopruService::class.java))
    }

    fun forget(serverId: String) {
        if ((state.value as? State.Connected)?.serverId == serverId) disconnect()
        prefs.forgetServer(serverId)
    }

    private val listener = object : ClientSession.Listener {
        override fun onPairingCode(code: String) {
            approvalTarget?.let { state.value = State.Approval(it, code) }
        }

        override fun onClosed(reason: String?) {
            val wasConnected = state.value is State.Connected
            session = null
            pcMedia.value = null
            state.value = State.Idle
            if (wasConnected) {
                say("Bağlantı koptu" + (reason?.let { " ($it)" } ?: ""))
                lastAutoAttempt = 0
                // Servis açık kalır ve keşifle yeniden bağlanmayı dener (bkz. KopruService).
            }
        }

        override fun onTransfer(t: ClientSession.Transfer) {
            val key = t.direction + t.tid
            transfers.value = (listOf(t) + transfers.value.filter { it.direction + it.tid != key }).take(30)
            if (t.direction == "in" && t.state == "done" && t.location != null) {
                Notifs.fileReceived(app, t.name, t.location, app.contentResolver.getType(Uri.parse(t.location)))
            }
            if (t.state == "failed") say("${t.name}: ${t.error ?: "aktarım başarısız"}")
            if (t.state == "rejected") say("${t.name} bilgisayarda reddedildi")
        }

        override fun onMessage(msg: JSONObject) {
            when (msg.optString("type")) {
                "media_state" -> pcMedia.value = if (!msg.optBoolean("active")) null else PcMedia(
                    msg.optString("title"), msg.optString("artist"), msg.optString("player"),
                    msg.optBoolean("playing"), msg.optLong("position_ms"), msg.optLong("duration_ms"),
                    if (msg.isNull("volume")) null else msg.optInt("volume"), msg.optBoolean("can_seek"),
                    msg.optString("art_id").ifEmpty { null }.takeUnless { msg.isNull("art_id") },
                    SystemClock.elapsedRealtime())
                "media_art" -> runCatching {
                    val bytes = Base64.decode(msg.getString("data"), Base64.DEFAULT)
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.let { pcArt.value = msg.getString("art_id") to it }
                }
                "media_control" -> {
                    val v = if (msg.isNull("value")) null else msg.optDouble("value").takeUnless { it.isNaN() }
                    main.post { PhoneMedia.control(msg.optString("action"), v) }
                }
                "ring" -> Notifs.ring(app)
                "ring_stop" -> Notifs.stopRing(app)
                "clipboard" -> main.post {
                    val cm = app.getSystemService(ClipboardManager::class.java)
                    cm.setPrimaryClip(ClipData.newPlainText("Köprü", msg.optString("text")))
                    if (Build.VERSION.SDK_INT < 33) Toast.makeText(app, "Bilgisayarın panosu kopyalandı", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // ---- gönderme ----------------------------------------------------------------

    /** İletiyi arka planda gönderir; bağlı değilse yok sayar. Ana iş parçacığından çağrılabilir. */
    fun send(msg: JSONObject) {
        val s = session ?: return
        sender.execute { s.trySend(msg) }
    }

    fun sendAppIconOnce(pkg: String, png: () -> String?) {
        if (!isConnected() || !iconsSent.add(pkg)) return
        png()?.let { send(JSONObject().put("type", "app_icon").put("package", pkg).put("data", it)) }
    }

    fun sendUris(uris: List<Uri>) {
        val s = session ?: run { say("Önce bir bilgisayara bağlan"); return }
        for (uri in uris) {
            fileSender.execute {
                try {
                    s.sendFile(uriSource(app, uri))
                } catch (e: IOException) {
                    say("Dosya okunamadı: ${e.message}")
                }
            }
        }
    }

    fun cancelTransfer(t: ClientSession.Transfer) {
        val s = session ?: return
        sender.execute { s.cancelTransfer(t.direction, t.tid) }
    }

    fun sendText(text: String) {
        val t = text.trim()
        if (Regex("^https?://\\S+$", RegexOption.IGNORE_CASE).matches(t)) {
            send(JSONObject().put("type", "open_url").put("url", t))
            say("Bağlantı bilgisayarda açılıyor")
        } else {
            send(JSONObject().put("type", "clipboard").put("text", text))
            say("Metin bilgisayarın panosuna kopyalandı")
        }
    }

    fun sendClipboard(text: String) {
        send(JSONObject().put("type", "clipboard").put("text", text))
        say("Pano bilgisayara gönderildi")
    }

    fun mediaControl(action: String, value: Long? = null) {
        send(JSONObject().put("type", "media_control").put("action", action).put("value", value ?: JSONObject.NULL))
    }

    // ---- keşif ve otomatik bağlanma -------------------------------------------------

    /** Arayüz ve servis kendi ihtiyaçları için açar/kapatır (sayaçlı). */
    @Synchronized
    fun discoveryAcquire() {
        if (discoveryUsers++ > 0) return
        multicastLock = app.getSystemService(WifiManager::class.java)?.createMulticastLock("kopru")?.apply {
            setReferenceCounted(false); acquire()
        }
        discovery = Discovery(
            onFound = { list -> found.value = list; main.post { maybeAutoConnect() } },
            onUsb = { ok -> usbAvailable.value = ok; main.post { maybeAutoConnect() } },
            usbAllowed = { adbEnabled() },
        ).also { it.start() }
    }

    @Synchronized
    fun discoveryRelease() {
        if (discoveryUsers == 0 || --discoveryUsers > 0) return
        discovery?.stop()
        discovery = null
        multicastLock?.release()
        multicastLock = null
        found.value = emptyList()
        usbAvailable.value = false
    }

    private fun adbEnabled() = Settings.Global.getInt(app.contentResolver, Settings.Global.ADB_ENABLED, 0) == 1

    fun usbTarget() = Target("127.0.0.1", 47600, "usb", null, "USB kablosu", null)

    fun targetOf(f: Discovery.Found) = Target(f.host, f.port, "wifi", f.id, f.name, f.fp)

    private fun maybeAutoConnect() {
        if (state.value !is State.Idle || passwordFor.value != null) return
        val auto = prefs.server(prefs.autoServer) ?: return
        if (auto.token == null) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastAutoAttempt < 8_000) return
        val target = if (auto.kind == "usb" && usbAvailable.value) usbTarget()
        else found.value.firstOrNull { it.id == auto.id }?.let { targetOf(it) }
        if (target != null) {
            lastAutoAttempt = now
            connect(target)
        }
    }
}
