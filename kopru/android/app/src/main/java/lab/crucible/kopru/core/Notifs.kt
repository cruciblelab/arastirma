package lab.crucible.kopru.core

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
import lab.crucible.kopru.R
import lab.crucible.kopru.service.KopruService
import lab.crucible.kopru.ui.MainActivity

@SuppressLint("StaticFieldLeak")  // yalnızca uygulama bağlamı tutulur
object Notifs {
    const val CH_CONNECTION = "baglanti"
    const val CH_FILES = "dosyalar"
    const val CH_RING = "zil"
    const val ID_SERVICE = 1
    const val ID_RING = 2

    fun createChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_CONNECTION, "Bağlantı durumu", NotificationManager.IMPORTANCE_LOW))
        nm.createNotificationChannel(NotificationChannel(CH_FILES, "Gelen dosyalar", NotificationManager.IMPORTANCE_DEFAULT))
        nm.createNotificationChannel(NotificationChannel(CH_RING, "Telefonu bul", NotificationManager.IMPORTANCE_HIGH))
    }

    private fun openApp(ctx: Context) = PendingIntent.getActivity(
        ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE)

    fun service(ctx: Context, text: String) = NotificationCompat.Builder(ctx, CH_CONNECTION)
        .setSmallIcon(R.drawable.ic_stat_kopru)
        .setContentTitle("Köprü")
        .setContentText(text)
        .setOngoing(true)
        .setContentIntent(openApp(ctx))
        .addAction(0, "Bağlantıyı kes", PendingIntent.getService(
            ctx, 1, Intent(ctx, KopruService::class.java).setAction(KopruService.ACTION_STOP),
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
            .setSmallIcon(R.drawable.ic_stat_kopru)
            .setContentTitle("Dosya alındı")
            .setContentText("$name · İndirilenler/Kopru")
            .setAutoCancel(true)
            .setContentIntent(PendingIntent.getActivity(ctx, uri.hashCode(), view, PendingIntent.FLAG_IMMUTABLE))
            .build()
        NotificationManagerCompat.from(ctx).notify(uri.hashCode(), n)
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
                    Intent(ctx, KopruService::class.java).setAction(KopruService.ACTION_STOP_RING),
                    PendingIntent.FLAG_IMMUTABLE)
                NotificationManagerCompat.from(ctx).notify(ID_RING, NotificationCompat.Builder(ctx, CH_RING)
                    .setSmallIcon(R.drawable.ic_stat_kopru)
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
