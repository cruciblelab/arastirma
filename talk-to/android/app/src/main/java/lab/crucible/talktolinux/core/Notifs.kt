package lab.crucible.talktolinux.core

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.Ringtone
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import lab.crucible.talktolinux.R
import lab.crucible.talktolinux.service.TalkService
import lab.crucible.talktolinux.ui.MainActivity

@SuppressLint("StaticFieldLeak")  // yalnızca uygulama bağlamı tutulur
object Notifs {
    const val CH_CONNECTION = "baglanti"
    const val CH_FILES = "dosyalar"
    const val CH_RING = "zil"
    const val CH_COMPUTER = "bilgisayar"
    const val ID_SERVICE = 1
    const val ID_RING = 2

    fun createChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_CONNECTION, "Bağlantı durumu", NotificationManager.IMPORTANCE_LOW))
        nm.createNotificationChannel(NotificationChannel(CH_FILES, "Gelen dosyalar", NotificationManager.IMPORTANCE_DEFAULT))
        nm.createNotificationChannel(NotificationChannel(CH_RING, "Telefonu bul", NotificationManager.IMPORTANCE_HIGH))
        nm.createNotificationChannel(NotificationChannel(CH_COMPUTER, "Bilgisayardan gelen bildirimler",
            NotificationManager.IMPORTANCE_DEFAULT))
    }

    private fun openApp(ctx: Context) = PendingIntent.getActivity(
        ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE)

    fun service(ctx: Context, text: String) = NotificationCompat.Builder(ctx, CH_CONNECTION)
        .setSmallIcon(R.drawable.ic_stat_talk)
        .setContentTitle("Talk To Linux")
        .setContentText(text)
        .setOngoing(true)
        .setContentIntent(openApp(ctx))
        .addAction(0, "Bağlantıyı kes", PendingIntent.getService(
            ctx, 1, Intent(ctx, TalkService::class.java).setAction(TalkService.ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE))
        .build()

    private fun canPost(ctx: Context) = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")  // canPost() denetliyor
    fun fileReceived(ctx: Context, name: String, uri: String, mime: String?) {
        if (!canPost(ctx)) return
        val view = Intent(Intent.ACTION_VIEW).setDataAndType(Uri.parse(uri), mime)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        val n = NotificationCompat.Builder(ctx, CH_FILES)
            .setSmallIcon(R.drawable.ic_stat_talk)
            .setContentTitle("Dosya alındı")
            .setContentText("$name · İndirilenler/TalkToLinux")
            .setAutoCancel(true)
            .setContentIntent(PendingIntent.getActivity(ctx, uri.hashCode(), view, PendingIntent.FLAG_IMMUTABLE))
            .build()
        NotificationManagerCompat.from(ctx).notify(uri.hashCode(), n)
    }

    /** Bilgisayardan (ör. terminalde: talk-to-android bildirim "Derleme bitti") gelen bildirim. */
    @SuppressLint("MissingPermission")  // canPost() denetliyor
    fun fromComputer(ctx: Context, title: String, text: String) {
        if (!canPost(ctx) || title.isBlank()) return
        val n = NotificationCompat.Builder(ctx, CH_COMPUTER)
            .setSmallIcon(R.drawable.ic_stat_talk)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setContentIntent(openApp(ctx))
            .build()
        NotificationManagerCompat.from(ctx).notify((title + text).hashCode(), n)
    }

    // ---- Telefonu bul ----------------------------------------------------------

    private var ringtone: Ringtone? = null
    private val main = Handler(Looper.getMainLooper())

    @SuppressLint("MissingPermission")  // canPost() denetliyor
    fun ring(ctx: Context) {
        main.post {
            stopRing(ctx)
            val uri = RingtoneManager.getActualDefaultRingtoneUri(ctx, RingtoneManager.TYPE_RINGTONE)
                ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            ringtone = RingtoneManager.getRingtone(ctx, uri)?.apply {
                // Alarm akışı: telefon sessizdeyken de duyulur.
                audioAttributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
                isLooping = true
                play()
            }
            if (canPost(ctx)) {
                val stop = PendingIntent.getService(ctx, 2,
                    Intent(ctx, TalkService::class.java).setAction(TalkService.ACTION_STOP_RING),
                    PendingIntent.FLAG_IMMUTABLE)
                NotificationManagerCompat.from(ctx).notify(ID_RING, NotificationCompat.Builder(ctx, CH_RING)
                    .setSmallIcon(R.drawable.ic_stat_talk)
                    .setContentTitle("Bilgisayar telefonu arıyor")
                    .setContentText("Durdurmak için dokun")
                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                    // Bildirime dokunmak uygulamayı açar; MainActivity açılınca zil durur.
                    .setContentIntent(openApp(ctx)).setDeleteIntent(stop).setAutoCancel(true)
                    .addAction(0, "Durdur", stop)
                    .build())
            }
            main.postDelayed({ stopRing(ctx) }, 30_000)
        }
    }

    fun stopRing(ctx: Context) {
        main.removeCallbacksAndMessages(null)
        ringtone?.stop()
        ringtone = null
        NotificationManagerCompat.from(ctx).cancel(ID_RING)
    }
}
