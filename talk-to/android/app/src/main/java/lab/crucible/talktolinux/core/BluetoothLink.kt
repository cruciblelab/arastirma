package lab.crucible.talktolinux.core

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import java.io.IOException
import java.util.UUID

/**
 * Bluetooth RFCOMM bağlantısı. Bilgisayardaki Talk To Android, BlueZ'e bu
 * UUID ile bir profil kaydeder (linux/talkto/bluetooth.py). Telefon ve
 * bilgisayar önce sistem Bluetooth ayarlarından eşleştirilmiş olmalıdır.
 */
object BluetoothLink {
    val SERVICE_UUID: UUID = UUID.fromString("a3c5e9d4-7b1f-4c6e-9d2a-5f8b3e1c7a90")

    data class Device(val name: String, val address: String, val computer: Boolean)

    fun hasPermission(ctx: Context) = Build.VERSION.SDK_INT < 31 ||
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED

    fun enabled(ctx: Context): Boolean = runCatching {
        ctx.getSystemService(BluetoothManager::class.java)?.adapter?.isEnabled == true
    }.getOrDefault(false)

    /** Eşleşmiş cihazlar: önce bilgisayarlar; kulaklık, saat, telefon gibi olanlar elenir. */
    @SuppressLint("MissingPermission")  // hasPermission() denetleniyor
    fun bondedComputers(ctx: Context): List<Device> {
        if (!hasPermission(ctx)) return emptyList()
        val adapter = ctx.getSystemService(BluetoothManager::class.java)?.adapter ?: return emptyList()
        if (!adapter.isEnabled) return emptyList()
        return try {
            adapter.bondedDevices.mapNotNull { d ->
                val major = d.bluetoothClass?.majorDeviceClass
                val skip = major in setOf(BluetoothClass.Device.Major.AUDIO_VIDEO, BluetoothClass.Device.Major.PHONE,
                    BluetoothClass.Device.Major.WEARABLE, BluetoothClass.Device.Major.HEALTH,
                    BluetoothClass.Device.Major.TOY, BluetoothClass.Device.Major.PERIPHERAL,
                    BluetoothClass.Device.Major.IMAGING)
                if (skip) null else Device(d.name ?: d.address, d.address, major == BluetoothClass.Device.Major.COMPUTER)
            }.sortedWith(compareBy({ !it.computer }, { it.name }))
        } catch (_: SecurityException) {
            emptyList()
        }
    }

    /** Engelleyen bağlantı (birkaç saniye sürebilir); ana iş parçacığında çağırma. */
    @SuppressLint("MissingPermission")
    fun connect(ctx: Context, address: String): BluetoothSocket {
        if (!hasPermission(ctx)) throw IOException("Bluetooth izni verilmedi")
        val adapter = ctx.getSystemService(BluetoothManager::class.java)?.adapter
            ?: throw IOException("Bu telefonda Bluetooth yok")
        if (!adapter.isEnabled) throw IOException("Bluetooth kapalı")
        val socket = adapter.getRemoteDevice(address).createRfcommSocketToServiceRecord(SERVICE_UUID)
        try {
            socket.connect()
        } catch (e: IOException) {
            runCatching { socket.close() }
            throw IOException("Bilgisayardaki Talk To Android'e Bluetooth ile ulaşılamadı " +
                "(açık mı, Bluetooth ayarı açık mı?)", e)
        }
        return socket
    }
}
