package lab.crucible.talktolinux.core

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ComponentName
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
import android.service.notification.NotificationListenerService
import android.util.Base64
import android.widget.Toast
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import lab.crucible.talktolinux.BuildConfig
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import lab.crucible.talktolinux.net.ClientSession
import lab.crucible.talktolinux.net.QrPair
import lab.crucible.talktolinux.net.Discovery
import lab.crucible.talktolinux.service.NotificationListener
import lab.crucible.talktolinux.service.TalkService
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.Executors

/** Uygulamanın tek durumu: bağlantı, keşif, bilgisayardaki medya, aktarımlar. */
@SuppressLint("StaticFieldLeak")  // yalnızca uygulama bağlamı (applicationContext) tutulur
object Talk {
    lateinit var app: Context
        private set
    lateinit var prefs: Prefs
        private set

    /** [knownOnly]: yalnızca güvenlik kodu kayıtlı (belirteci olan) bir bilgisayara bağlan (otomatik USB). */
    /** [qrKey]: karekoddan; [fp] o zaman karekoddaki güvenlik kodudur ve bağlanılan bilgisayarınki onunla tutmalı. */
    data class Target(val host: String, val port: Int, val kind: String, val serverId: String?,
                      val name: String, val fp: String?, val knownOnly: Boolean = false, val qrKey: String? = null)

    sealed class State {
        object Idle : State()
        data class Connecting(val target: Target) : State()
        data class Approval(val target: Target, val code: String) : State()
        data class Connected(val target: Target, val serverId: String, val serverName: String) : State()
    }

    /** Bilgisayarın bu telefonu tanıdığı profil ve verdiği izinler. */
    data class Profile(val id: String, val name: String, val permissions: Map<String, Boolean>) {
        fun can(p: String) = permissions[p] == true
    }

    data class Command(val id: String, val name: String, val icon: String, val power: Boolean)

    data class SysInfo(val host: String, val os: String, val cpu: Double?, val memUsed: Long, val memTotal: Long,
                       val diskUsed: Long, val diskTotal: Long, val battery: Pair<Int, Boolean>?, val uptime: Long,
                       val volume: Int?, val muted: Boolean)

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
    val profile = MutableStateFlow<Profile?>(null)
    val commands = MutableStateFlow<List<Command>>(emptyList())
    val sysinfo = MutableStateFlow<SysInfo?>(null)
    /** Son komutun sonucu (başlık, başarılı mı, çıktı); arayüz bir pencerede gösterir. */
    val commandResult = MutableStateFlow<Triple<String, Boolean, String>?>(null)
    val bluetoothDevices = MutableStateFlow<List<BluetoothLink.Device>>(emptyList())
    /** Android bildirim dinleyicisini bağladı mı (erişim verilmiş olsa da bağlamayabiliyor). */
    val listenerConnected = MutableStateFlow(false)
    /** Bu bağlantıda bilgisayara gönderilen bildirim sayısı (tanılama için). */
    val notificationsSent = MutableStateFlow(0)
    /** Bilgisayarın USB'den verdiği izinlerin sonucu: (özet, başarılı mı); null: istenmedi. */
    val setupResult = MutableStateFlow<Pair<String, Boolean>?>(null)
    /** "Bilgisayar ayarlasın" isteği sürüyor. */
    val setupRunning = MutableStateFlow(false)

    /** Başka bir uygulamadan (kamera) açılan karekod bağlantısı: arayüz önce sorar ("… ile eşleşilsin mi?"). */
    val qrRequest = MutableStateFlow<QrPair?>(null)

    /** Telefonda izlenen oynatıcı (Spotify, YouTube...); yoksa null. */
    val phonePlayer = MutableStateFlow<String?>(null)

    private val FINISHED = setOf("done", "failed", "cancelled", "rejected")
    const val CLIPBOARD_MAX = 100_000

    @Volatile private var session: ClientSession? = null
    private val connector = Executors.newSingleThreadExecutor()
    private val sender = Executors.newSingleThreadExecutor()
    private val fileSender = Executors.newFixedThreadPool(2)
    private val main = Handler(Looper.getMainLooper())

    /** Bilgisayardaki "Telefonda titreşim" (profil iletisiyle gelir; varsayılan kapalı). */
    @Volatile var vibrate = false

    /** Bilgisayar telefonda bir şey yaptı (arama düğmesi, oynat/atla, zamanlayıcı): açıksa kısa bir "tık". */
    private fun tick() {
        if (!vibrate) return
        runCatching {
            val v = if (android.os.Build.VERSION.SDK_INT >= 31)
                app.getSystemService(android.os.VibratorManager::class.java)?.defaultVibrator
            else @Suppress("DEPRECATION") app.getSystemService(android.os.Vibrator::class.java)
            if (v == null || !v.hasVibrator()) return
            v.vibrate(android.os.VibrationEffect.createPredefined(android.os.VibrationEffect.EFFECT_TICK))
        }
    }
    private var discovery: Discovery? = null
    private var discoveryUsers = 0
    private var multicastLock: WifiManager.MulticastLock? = null
    private var lastAutoAttempt = 0L
    @Volatile private var autoPausedUntil = 0L
    /** Uygulama ekranı önde mi (periyodik istekler yalnızca o zaman). */
    @Volatile var uiVisible = false
    private val iconsSent = HashSet<String>()

    fun init(context: Context) {
        app = context.applicationContext
        prefs = Prefs(app)
        Features.load(prefs)
    }

    fun isConnected() = session != null && state.value is State.Connected

    /** Bağlı bilgisayarın kaydı (bu bilgisayara özel ayarlar). */
    fun currentServer(): Prefs.Server? = (state.value as? State.Connected)?.let { prefs.server(it.serverId) }

    /** Bildirim gönderilsin mi: bu bilgisayar için açık ve bilgisayardaki profil izin veriyor. */
    fun notificationsOn() = isConnected() && currentServer()?.notif != false && profile.value?.can("notifications") != false

    fun mediaOn() = isConnected() && currentServer()?.media != false && profile.value?.can("media") != false

    /**
     * Sistem servisine sorulur: ayar metni (enabled_notification_listeners) erişim verildikten biraz sonra
     * yazılabiliyor; bilgisayar adb ile verince eski metin "kapalı" dedirtiyordu. Dinleyici bağlıysa erişim
     * zaten vardır.
     */
    fun notifAccessGranted() = BuildConfig.NOTIFICATIONS && (listenerConnected.value || runCatching {
        app.getSystemService(android.app.NotificationManager::class.java)
            .isNotificationListenerAccessGranted(ComponentName(app, NotificationListener::class.java))
    }.getOrElse {
        NotificationManagerCompat.getEnabledListenerPackages(app).contains(app.packageName)
    })

    /**
     * Erişim verilmiş ama dinleyici bağlı değilse (ör. uygulama USB'den güncellendikten sonra bazı
     * telefonlarda) Android'den yeniden bağlamasını iste. Medya oturumları dinleyicinin bağlı olmasını
     * beklemez; erişim yeterli, o yüzden burada da başlatılır.
     */
    fun ensureListener() {
        if (!notifAccessGranted()) return
        PhoneMedia.start(app)
        if (!listenerConnected.value) {
            runCatching {
                NotificationListenerService.requestRebind(ComponentName(app, NotificationListener::class.java))
            }
        }
    }

    /** Bildirim ve medyanın neden gelip gelmediğini bilgisayar da görsün. */
    fun sendPhoneStatus() {
        if (!isConnected()) return
        send(JSONObject().put("type", "phone_status").put("flavor", BuildConfig.FLAVOR)
            .put("sdk", Build.VERSION.SDK_INT)
            .put("notif_access", notifAccessGranted())
            .put("listener", listenerConnected.value)
            .put("player", PhoneMedia.playerName() ?: JSONObject.NULL)
            .put("notifications_sent", notificationsSent.value)
            .put("version", BuildConfig.VERSION_NAME))
    }

    private fun say(text: String) {
        messages.tryEmit(text)
    }

    // ---- bağlanma ----------------------------------------------------------------

    /** Bilgisayar "Bağlan" dedi: kurulumu bilgisayar yönetiyor, telefondaki sihirbaz atlanır. */
    val pcConnect = MutableStateFlow(0)

    /** Bilgisayar adb ile USB tünelini hazırlayıp bu uygulamayı açtı: tanımasak da USB'den bağlan. */
    fun connectFromPc() {
        prefs.setupDone = true
        pcConnect.value += 1
        autoPausedUntil = 0
        if (state.value is State.Idle) connect(usbTarget())
    }

    fun connect(target: Target, password: String? = null) {
        if (state.value !is State.Idle) return
        passwordFor.value = null
        state.value = State.Connecting(target)
        connector.execute { doConnect(target, password) }
    }

    /** Karekoddaki adreslerden ulaşılabilen ilkine bağlanır (ev ağı önce; karekod onları sıralı verir). */
    fun connectQr(qr: QrPair) {
        if (state.value !is State.Idle) {
            say("Önce şu anki bağlantıyı kes (⋮ → Bağlantıyı kes), sonra karekodu yeniden okut.")
            return
        }
        passwordFor.value = null
        val first = Target(qr.hosts.first(), qr.port, "wifi", null, qr.name, qr.fp, qrKey = qr.key)
        state.value = State.Connecting(first)
        connector.execute {
            val host = qr.hosts.firstOrNull { h ->
                runCatching { java.net.Socket().use { it.connect(java.net.InetSocketAddress(h, qr.port), 1500) } }.isSuccess
            }
            if (host == null) {
                fail("${qr.name}: bağlanılamadı. Telefon ve bilgisayar aynı Wi-Fi ağında mı? (Denenen: " +
                    "${qr.hosts.joinToString()}.) Misafir ağları cihazların birbirini görmesini engelleyebilir.")
                return@execute
            }
            val t = first.copy(host = host)
            state.value = State.Connecting(t)
            doConnect(t, null)
        }
    }

    @Volatile private var pending: ClientSession? = null

    /** Bağlanırken ya da onay beklerken vazgeç. */
    fun cancelConnecting() {
        // Kapanış (TLS close_notify) takılabilir: ana iş parçacığında ve bağlantı kuyruğunda değil.
        pending?.let { s -> Thread({ s.close() }, "talkto-kapat").start() }
    }

    private fun doConnect(target: Target, password: String?) {
        val s = ClientSession(listener, DownloadsStore(app))
        pending = s
        try {
            val fp = if (target.kind == "bluetooth") {
                val bt = BluetoothLink.connect(app, target.host)
                s.openStreams(bt.inputStream, bt.outputStream) { runCatching { bt.close() } }
            } else s.open(target.host, target.port)
            if (target.qrKey != null && fp != target.fp) {
                // Karekoddaki güvenlik kodu tutmuyor: bu adreste başka bir bilgisayar (ya da araya giren biri) var.
                s.close()
                fail("Bu adresteki bilgisayar karekoddaki bilgisayar değil; bağlanılmadı. Bilgisayarda yeni karekod " +
                    "açıp tekrar dene.")
                return
            }
            val stored = prefs.server(target.serverId)
            if (stored != null && stored.fp != fp) {
                s.close()
                if (target.knownOnly) {
                    // Kendiliğinden denemede ağdaki sahte bir duyuru otomatik bağlanmayı kapatmasın.
                    state.value = State.Idle
                    autoPausedUntil = SystemClock.elapsedRealtime() + 60_000
                } else fail(fpChanged(stored.name), auto = false)
                return
            }
            val known = prefs.serverByFp(fp)
            if (target.knownOnly && known?.token == null) {
                // Telefondaki 127.0.0.1:47600'ü tanımadığımız bir şey açmış (başka bilgisayar ya da başka
                // bir uygulama): kendiliğinden eşleşmeye girilmez, kullanıcı isterse kendisi dokunur.
                s.close()
                state.value = State.Idle
                autoPausedUntil = SystemClock.elapsedRealtime() + 60_000
                say("USB'deki bilgisayar tanınmıyor; eşleşmek için “USB kablosu”na dokun.")
                return
            }
            approvalTarget = target
            // Duyurudaki kimlik doğrulanmamış bir iddia: bilgisayarın hello'da söylediği kimlik de
            // kayıtlıysa güvenlik kodu (parmak izi) onunla da tutmalı; yoksa gerçek bilgisayarın
            // kaydı başka bir sertifikayla değiştirilebilirdi.
            val res = s.handshake(prefs.deviceId, prefs.deviceName, Build.MANUFACTURER + " " + Build.MODEL,
                known?.token, password, target.qrKey) { id ->
                    prefs.server(id)?.takeIf { it.fp != fp }?.let { "fp_changed:${it.name}" } }
            approvalTarget = null
            when (res) {
                is ClientSession.AuthResult.Welcome -> {
                    if (s.closed) throw IOException("vazgeçildi")  // bu arada "Bağlantıyı kes"e basıldı
                    prefs.saveServer(Prefs.Server(res.serverId, res.serverName, fp, res.token ?: known?.token,
                        target.host, target.port, target.kind))
                    prefs.autoServer = res.serverId.takeIf { prefs.server(it)?.auto != false }
                    profile.value = null
                    notificationsSent.value = 0
                    commands.value = emptyList()
                    sysinfo.value = null
                    session = s
                    iconsSent.clear()
                    PhoneMedia.resetArt()
                    state.value = State.Connected(target.copy(fp = fp), res.serverId, res.serverName)
                    s.start()
                    main.post {
                        try {
                            ContextCompat.startForegroundService(app, Intent(app, TalkService::class.java))
                        } catch (e: IllegalStateException) {
                            // Android 12+: uygulama arka plandayken servis başlatılamayabilir;
                            // bağlantı yine çalışır, yalnızca sistem süreci erken kapatabilir.
                        }
                        ensureListener()
                        PhoneMedia.push()
                        sendPhoneStatus()
                        runCatching { send(PhoneInfo.collect(app)) }
                        CrashLog.takePending(app)?.let { send(JSONObject().put("type", "crash_report").put("text", it)) }
                        flushPending()
                    }
                }
                is ClientSession.AuthResult.Failed -> {
                    s.close()
                    when (res.reason) {
                        "password_needed" -> {
                            // Belirteçle bağlandık ama şifre istendi: bilgisayar bu telefonu unutmuş.
                            known?.takeIf { it.token != null }?.let { k -> prefs.updateServer(k.id) { it.copy(token = null) } }
                            state.value = State.Idle
                            passwordFor.value = target.copy(fp = fp)
                        }
                        "wrong_password" -> { state.value = State.Idle; say("Şifre yanlış"); passwordFor.value = target.copy(fp = fp) }
                        "rejected" -> fail("Bilgisayarda reddedildi ya da süre doldu", auto = false)
                        "qr_expired" -> fail("Karekodun süresi dolmuş ya da kullanılmış. Bilgisayarda “Yeni " +
                            "karekod”a basıp tekrar okut.")
                        "wrong_qr" -> fail("Karekod tutmadı. Bilgisayardaki en son karekodu okut.")
                        "too_many_attempts" -> fail("Çok fazla hatalı deneme. 10 dakika sonra tekrar dene.", auto = false)
                        "server_outdated" -> fail("Bilgisayardaki Talk To eski. Güvenli eşleşme için " +
                            "bilgisayardaki uygulamayı güncelle (0.5 ya da daha yeni).", auto = false)
                        "protocol" -> fail("Bilgisayar beklenmeyen bir yanıt verdi; bağlanılmadı.", auto = false)
                        else -> if (res.reason.startsWith("fp_changed:")) fail(fpChanged(res.reason.substringAfter(':')), auto = false)
                            else fail("Bağlantı kurulamadı (${res.reason})")
                    }
                }
            }
        } catch (e: Exception) {
            val cancelled = s.closed
            s.close()
            approvalTarget = null
            when {
                cancelled -> fail("Vazgeçildi", auto = false)
                // Kendiliğinden deneme (bilgisayar kapalı ya da başka ağdayız): her seferinde uyarı çıkmasın.
                e is IOException && target.knownOnly -> state.value = State.Idle
                e is IOException -> fail("${target.name}: bağlanılamadı — ${whyNot(e, target)}")
                else -> fail("Beklenmeyen hata: ${e.message}")
            }
        } finally {
            pending = null
        }
    }

    @Volatile private var approvalTarget: Target? = null
    @Volatile private var byeReceived = false

    /** Bağlanamamanın nedeni, yapılabilecek şeyle (kullanıcı "olmuyor"un nedenini bilsin). */
    internal fun whyNot(e: IOException, target: Target): String {
        val m = e.message.orEmpty()
        if (target.kind != "wifi") return m.ifEmpty { e.javaClass.simpleName }
        return when {
            e is java.net.SocketTimeoutException || "ETIMEDOUT" in m ->
                "bilgisayardan yanıt gelmedi. Aynı Wi-Fi'de olsanız da modem cihazların birbirini görmesini " +
                    "engelliyor olabilir (misafir ağı, “AP izolasyonu”) ya da bilgisayarın güvenlik duvarı " +
                    "${target.port} portunu kapatıyor."
            e is java.net.ConnectException && ("ECONNREFUSED" in m || "refused" in m) ->
                "bilgisayar bu adreste dinlemiyor: Talk To açık mı, Tercihler'de Wi-Fi açık mı, port " +
                    "${target.port} mi?"
            e is java.net.NoRouteToHostException || "EHOSTUNREACH" in m || "ENETUNREACH" in m ->
                "bu adrese ulaşılamıyor: telefon Wi-Fi'ye bağlı mı, adres bilgisayardaki Talk To'da " +
                    "yazanla aynı mı?"
            e is java.net.UnknownHostException -> "adres anlaşılamadı (${target.host})"
            e is javax.net.ssl.SSLException -> "güvenli bağlantı kurulamadı (${m.ifEmpty { "TLS" }})"
            else -> m.ifEmpty { e.javaClass.simpleName }
        }
    }

    private fun fpChanged(name: String) = "$name bilgisayarının güvenlik kodu değişmiş. Talk To yeniden " +
        "kurulduysa bilgisayarı listeden unutup tekrar eşleştir; kurulmadıysa bağlanma."

    private fun fail(text: String, auto: Boolean = true) {
        state.value = State.Idle
        if (!auto) prefs.autoServer = null
        say(text)
    }

    /** Kullanıcı bağlantıyı kesti: otomatik yeniden bağlanma da durur. */
    fun disconnect() {
        prefs.autoServer = null
        cancelConnecting()  // bağlanma ya da onay sürüyorsa o da kesilsin
        val s = session
        session = null
        state.value = State.Idle
        pcMedia.value = null
        profile.value = null
        if (s != null) Thread({ s.close() }, "talkto-kapat").start()
        app.stopService(Intent(app, TalkService::class.java))
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
            if (byeReceived) {
                byeReceived = false  // bilgisayar kendisi kesti; nedeni "bye"da söylendi
            } else if (wasConnected) {
                say("Bağlantı koptu" + (reason?.let { " ($it)" } ?: ""))
                lastAutoAttempt = 0
                // Servis açık kalır ve keşifle yeniden bağlanmayı dener (bkz. TalkService).
            }
        }

        override fun onTransfer(t: ClientSession.Transfer) {
            val key = t.direction + t.tid
            var stale = false
            transfers.update { cur ->
                val old = cur.firstOrNull { it.direction + it.tid == key }
                // Okuyucu ve gönderen iş parçacıkları yarışabilir: bitmiş bir kaydı geç gelen ilerleme ezmesin.
                stale = old != null && old.state in FINISHED && t.state !in FINISHED
                if (stale) cur else (listOf(t) + cur.filter { it.direction + it.tid != key }).take(30)
            }
            if (stale) return
            if (t.direction == "in" && t.state == "done" && t.location != null) {
                Notifs.fileReceived(app, t.name, t.location, app.contentResolver.getType(Uri.parse(t.location)))
            }
            if (t.state == "failed") say("${t.name}: ${t.error ?: "aktarım başarısız"}")
            if (t.state == "rejected") say("${t.name} bilgisayarda reddedildi" + (t.error?.takeIf { it.isNotBlank() }?.let { ": $it" } ?: ""))
        }

        override fun onMessage(msg: JSONObject) {
            when (msg.optString("type")) {
                "media_state" -> pcMedia.value = if (!msg.optBoolean("active")) null else PcMedia(
                    msg.optString("title"), msg.optString("artist"), msg.optString("player"),
                    msg.optBoolean("playing"), msg.optLong("position_ms"), msg.optLong("duration_ms"),
                    if (msg.isNull("volume")) null else msg.optInt("volume"), msg.optBoolean("can_seek"),
                    msg.optString("art_id").ifEmpty { null }.takeUnless { msg.isNull("art_id") },
                    SystemClock.elapsedRealtime())
                "setup_result" -> {
                    val items = msg.optJSONArray("items")
                    val failed = items != null && (0 until items.length()).any {
                        items.optJSONObject(it)?.let { o -> !o.isNull("ok") && !o.optBoolean("ok") } == true
                    }
                    setupRunning.value = false
                    setupResult.value = msg.optString("summary") to (items != null && items.length() > 0 && !failed)
                    say(msg.optString("summary"))
                    main.post {
                        ensureListener()
                        sendPhoneStatus()
                        lab.crucible.talktolinux.ui.UiTick.bump()
                    }
                }
                "bye" -> {
                    // Bilgisayardaki "Bağlantıyı kes" ya da "Unut": kendiliğinden geri bağlanılmaz.
                    byeReceived = true
                    prefs.autoServer = null
                    val id = (state.value as? State.Connected)?.serverId
                    if (msg.optString("reason") == "forgotten") {
                        id?.let { prefs.updateServer(it) { s -> s.copy(token = null) } }
                        say("Bilgisayar bu telefonu unuttu; yeniden bağlanmak için bilgisayarda onay gerekir")
                    } else say("Bilgisayar bağlantıyı kesti")
                }
                "media_art" -> runCatching {
                    val bytes = Base64.decode(msg.getString("data"), Base64.DEFAULT)
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.let { pcArt.value = msg.getString("art_id") to it }
                }
                "media_control" -> if (mediaOn()) {
                    val v = if (msg.isNull("value")) null else msg.optDouble("value").takeUnless { it.isNaN() }
                    main.post { PhoneMedia.control(msg.optString("action"), v) }
                    // Ses ve konum sürüklemesi sürekli gelir: yalnızca düğme gibi komutlarda titreşir.
                    if (msg.optString("action") in setOf("play_pause", "play", "pause", "next", "previous")) tick()
                }
                "profile" -> {
                    vibrate = msg.optBoolean("vibrate", false)
                    val p = msg.optJSONObject("permissions") ?: JSONObject()
                    profile.value = Profile(msg.optString("id"), msg.optString("name"),
                        p.keys().asSequence().associateWith { p.optBoolean(it) })
                }
                "commands" -> {
                    val arr = msg.optJSONArray("items") ?: org.json.JSONArray()
                    commands.value = (0 until arr.length()).map { arr.getJSONObject(it) }.map {
                        Command(it.optString("id"), it.optString("name"), it.optString("icon"), it.optBoolean("power"))
                    }
                }
                "command_result" -> commandResult.value = Triple(
                    msg.optString("name").ifEmpty { "Komut" }, msg.optBoolean("ok"), msg.optString("output"))
                "sysinfo" -> sysinfo.value = SysInfo(
                    msg.optString("host"), msg.optString("os"),
                    if (msg.isNull("cpu")) null else msg.optDouble("cpu"),
                    msg.optLong("mem_used"), msg.optLong("mem_total"), msg.optLong("disk_used"), msg.optLong("disk_total"),
                    msg.optJSONObject("battery")?.let { it.optInt("level") to it.optBoolean("charging") },
                    msg.optLong("uptime"), if (msg.isNull("volume")) null else msg.optInt("volume"), msg.optBoolean("muted"))
                "notify" -> Notifs.fromComputer(app, msg.optString("title"), msg.optString("text"))
                "call_action" -> if (notificationsOn()) {
                    tick()
                    val (title, error) = Calls.press(app, msg.optString("key"), msg.optInt("action", -1))
                    send(JSONObject().put("type", "call_result").put("kind", "action")
                        .put("title", title ?: JSONObject.NULL).put("error", error ?: JSONObject.NULL))
                }
                "call_volume" -> if (notificationsOn()) {
                    tick()
                    send(Calls.volume(app, msg.optInt("dir") > 0).put("type", "call_result"))
                }
                "phone_info_request" -> runCatching { send(PhoneInfo.collect(app)) }
                "ring" -> Notifs.ring(app)
                "timer" -> main.post {
                    tick()
                    Notifs.startTimer(app, msg.optInt("seconds"), msg.optString("label"))
                }
                "timer_cancel" -> main.post { Notifs.cancelTimer(app) }
                "ring_stop" -> Notifs.stopRing(app)
                "clipboard" -> main.post {
                    // Binder sınırı ~1 MB: çok uzun metin setPrimaryClip'te süreci çökertir.
                    val text = msg.optString("text")
                    val clipped = text.length > CLIPBOARD_MAX
                    try {
                        app.getSystemService(ClipboardManager::class.java)
                            .setPrimaryClip(ClipData.newPlainText("Talk To", text.take(CLIPBOARD_MAX)))
                        if (clipped) say("Bilgisayarın panosu çok uzundu; ilk ${CLIPBOARD_MAX / 1000} bin karakter kopyalandı")
                        else if (Build.VERSION.SDK_INT < 33) Toast.makeText(app, "Bilgisayarın panosu kopyalandı", Toast.LENGTH_SHORT).show()
                    } catch (e: RuntimeException) {
                        say("Bilgisayarın panosu telefona sığmadı")
                    }
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

    /** Bağlantı koptuysa ve kendiliğinden yeniden bağlanılacaksa paylaşımlar kısa süre bekletilir. */
    fun willReconnect() = isConnected() || prefs.server(prefs.autoServer)?.token != null

    private val pendingUris = ArrayList<Uri>()
    @Volatile private var pendingText: String? = null
    @Volatile private var pendingUntil = 0L

    private fun queue(uris: List<Uri>, text: String?): Boolean {
        if (!willReconnect()) return false
        synchronized(pendingUris) {
            pendingUris.addAll(uris)
            if (text != null) pendingText = text
            pendingUntil = SystemClock.elapsedRealtime() + 120_000
        }
        say("Bağlantı bekleniyor; bağlanınca gönderilecek")
        return true
    }

    /** Bağlanınca bekleyen paylaşımları gönderir (süresi geçtiyse atar). */
    private fun flushPending() {
        val (uris, text) = synchronized(pendingUris) {
            val fresh = SystemClock.elapsedRealtime() < pendingUntil
            val out = (if (fresh) pendingUris.toList() else emptyList()) to (if (fresh) pendingText else null)
            pendingUris.clear()
            pendingText = null
            out
        }
        if (uris.isNotEmpty()) sendUris(uris)
        text?.let { sendText(it) }
    }

    fun sendUris(uris: List<Uri>) {
        val s = session
        if (s == null || !isConnected()) {
            if (!queue(uris, null)) say("Önce bir bilgisayara bağlan")
            return
        }
        for (uri in uris) {
            fileSender.execute {
                if (s.closed) return@execute
                var src: ClientSession.Source? = null
                try {
                    src = uriSource(app, uri)
                    s.sendFile(src)
                } catch (e: Exception) {
                    // SecurityException (izin geri alındı), sağlayıcı hataları, IOException...
                    say("Dosya gönderilemedi: ${e.message ?: e.javaClass.simpleName}")
                } finally {
                    src?.let { runCatching { it.cleanup() } }
                }
            }
        }
    }

    fun isUrl(text: String) = Regex("^https?://\\S+$", RegexOption.IGNORE_CASE).matches(text.trim())

    fun cancelTransfer(t: ClientSession.Transfer) {
        val s = session ?: return
        sender.execute { runCatching { s.cancelTransfer(t.direction, t.tid) } }
    }

    fun sendText(text: String) {
        if (!isConnected()) {
            if (!queue(emptyList(), text)) say("Önce bir bilgisayara bağlan")
            return
        }
        val t = text.trim()
        val need = if (isUrl(t)) "open_url" else "clipboard"
        if (profile.value?.can(need) == false) {
            say(if (need == "open_url") "Bu bilgisayar bu telefona bağlantı açma izni vermiyor"
                else "Bu bilgisayar bu telefona pano izni vermiyor")
            return
        }
        if (isUrl(t)) {
            send(JSONObject().put("type", "open_url").put("url", t))
            say("Bağlantı bilgisayarda açılıyor")
        } else {
            send(JSONObject().put("type", "clipboard").put("text", text))
            say("Metin bilgisayarın panosuna kopyalandı")
        }
    }

    fun sendClipboard(text: String) {
        if (profile.value?.can("clipboard") == false) {
            say("Bu bilgisayar bu telefona pano izni vermiyor")
            return
        }
        send(JSONObject().put("type", "clipboard").put("text", text))
        say("Pano bilgisayara gönderildi")
    }

    fun runCommand(id: String) = send(JSONObject().put("type", "run_command").put("id", id))

    /** Bilgisayardan (USB + adb) bu uygulamanın izinlerini vermesini ister. */
    fun requestSetup() {
        if (!isConnected()) return
        setupRunning.value = true
        setupResult.value = null
        send(JSONObject().put("type", "setup_request"))
        // Cevap gelmezse (eski bilgisayar sürümü) düğme sonsuza kadar dönmesin.
        main.postDelayed({
            if (setupRunning.value) {
                setupRunning.value = false
                say("Bilgisayar cevap vermedi; bilgisayardaki Talk To'yu güncelle")
            }
        }, 45_000)
    }

    fun requestSysinfo() = send(JSONObject().put("type", "sysinfo_request"))

    fun requestScreenshot() {
        send(JSONObject().put("type", "screenshot_request"))
        say("Ekran görüntüsü isteniyor; dosya olarak gelecek")
    }

    fun pcVolume(value: Int? = null, toggleMute: Boolean = false) {
        send(JSONObject().put("type", "pc_volume").put("value", value ?: JSONObject.NULL).put("toggle_mute", toggleMute))
    }

    /** Bu bilgisayara özel ayar değişikliği. */
    fun updateCurrentServer(change: (Prefs.Server) -> Prefs.Server) {
        val id = (state.value as? State.Connected)?.serverId ?: return
        prefs.updateServer(id, change)
        if (prefs.server(id)?.auto == false) prefs.autoServer = null else prefs.autoServer = id
        if (prefs.server(id)?.media == false) send(JSONObject().put("type", "media_state").put("active", false))
        else PhoneMedia.push()
    }

    fun mediaControl(action: String, value: Long? = null) {
        send(JSONObject().put("type", "media_control").put("action", action).put("value", value ?: JSONObject.NULL))
    }

    // ---- keşif ve otomatik bağlanma -------------------------------------------------

    /** Arayüz ve servis kendi ihtiyaçları için açar/kapatır (sayaçlı). */
    @Synchronized
    fun discoveryAcquire() {
        if (discoveryUsers++ > 0) return
        multicastLock = app.getSystemService(WifiManager::class.java)?.createMulticastLock("talktolinux")?.apply {
            setReferenceCounted(false); acquire()
        }
        discovery = Discovery(
            onFound = { list -> found.value = list; main.post { maybeAutoConnect() } },
            onUsb = { ok -> usbAvailable.value = ok; main.post { maybeAutoConnect() } },
            usbAllowed = { adbEnabled() && state.value !is State.Connected },
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

    fun bluetoothTarget(d: BluetoothLink.Device): Target {
        val known = prefs.servers().firstOrNull { it.kind == "bluetooth" && it.host == d.address }
        return Target(d.address, 0, "bluetooth", known?.id, d.name, known?.fp)
    }

    /** Eşleşmiş Bluetooth bilgisayarlarını yeniden okur (izin verildikten / Bluetooth açıldıktan sonra). */
    fun refreshBluetooth() {
        bluetoothDevices.value = BluetoothLink.bondedComputers(app)
    }

    /**
     * Duyuru ulaşmıyorsa (Tailscale gibi bir VPN'le başka ağdan, istemci yalıtımlı modem) kayıtlı adrese seyrek
     * dene; güvenlik kodu yine kayıtlıyla karşılaştırılır. Ekran açıkken daha da seyrek: deneme sürerken
     * listenin yerinde "bağlanılıyor" görünür.
     */
    private fun savedAddress(auto: Prefs.Server, now: Long): Target? {
        val wait = if (uiVisible) 300_000 else 60_000
        if (auto.kind != "wifi" || auto.host.isEmpty() || now - lastAutoAttempt <= wait) return null
        return Target(auto.host, auto.port, "wifi", auto.id, auto.name, auto.fp, knownOnly = true)
    }

    private fun maybeAutoConnect() {
        if (state.value !is State.Idle || passwordFor.value != null) return
        val auto = prefs.server(prefs.autoServer) ?: return
        if (auto.token == null) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastAutoAttempt < 8_000) return
        val target = when {
            // Başka kayıtlı bir bilgisayar da (ör. iş bilgisayarı) olabilir; yalnızca tanınan güvenlik kodu.
            auto.kind == "usb" && usbAvailable.value && now > autoPausedUntil -> usbTarget().copy(knownOnly = true)
            // Bluetooth'ta yayın yok: kayıtlı adrese, daha seyrek dene (bağlanma denemesi birkaç saniye sürer).
            auto.kind == "bluetooth" && BluetoothLink.enabled(app) && BluetoothLink.hasPermission(app) &&
                now - lastAutoAttempt > 20_000 -> Target(auto.host, 0, "bluetooth", auto.id, auto.name, auto.fp, knownOnly = true)
            // Duyurudaki güvenlik kodu da kayıtlı olanla aynı olmalı (aynı kimlikle sahte duyuru olabilir).
            now > autoPausedUntil -> found.value.firstOrNull { it.id == auto.id && it.fp == auto.fp }
                ?.let { targetOf(it).copy(knownOnly = true) } ?: savedAddress(auto, now)
            else -> null
        }
        if (target != null) {
            lastAutoAttempt = now
            connect(target)
        }
    }
}
