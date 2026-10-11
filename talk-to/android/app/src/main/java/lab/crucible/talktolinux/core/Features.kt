package lab.crucible.talktolinux.core

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Basit mod: ekranda yalnızca temel işler (bağlantı durumu, bildirimler, çalan müzik) görünür; diğerleri
 * "Görünüm ve özellikler"den tek tek eklenir. Hafif sürümden farklıdır: hafif sürümde bildirim özelliği
 * hiç yoktur, basit mod yalnızca ekranı sadeleştirir. Neye izin verildiğini bilgisayardaki profil belirler.
 */
object Features {
    /** Eklenebilir özellikler: anahtar → (başlık, açıklama). */
    val EXTRAS: Map<String, Pair<String, String>> = linkedMapOf(
        "files" to ("Dosya ve pano" to "Dosyalar sekmesi; bilgisayara dosya ve pano gönderme"),
        "pc" to ("Bilgisayar komutları ve durumu" to "Kilitleme, ekran görüntüsü, özel komutlar; işlemci, bellek, disk"),
    )

    private val _simple = MutableStateFlow(true)
    private val _extras = MutableStateFlow<Set<String>>(emptySet())
    private val _enabled = MutableStateFlow<Set<String>>(emptySet())
    val simple: StateFlow<Boolean> = _simple
    val enabled: StateFlow<Set<String>> = _enabled

    fun compute(simple: Boolean, extras: Set<String>): Set<String> =
        if (simple) extras.filter { it in EXTRAS }.toSet() else EXTRAS.keys.toSet()

    fun load(p: Prefs) = show(p.simpleMode, p.extras)

    /** Ekrandaki durumu ayarlar (kaydetmeden; ekran görüntüsü testleri de bunu kullanır). */
    fun show(simple: Boolean, extras: Set<String>) {
        _simple.value = simple
        _extras.value = extras
        _enabled.value = compute(simple, extras)
    }

    fun setSimple(p: Prefs, on: Boolean) {
        p.simpleMode = on
        show(on, _extras.value)
    }

    fun setExtra(p: Prefs, key: String, on: Boolean) {
        val extras = if (on) _extras.value + key else _extras.value - key
        p.extras = extras
        show(_simple.value, extras)
    }
}
