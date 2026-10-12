import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import Gio from 'gi://Gio';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
// Test sürücüsü: D-Bus'ta test.Cek (/test/Cek): Shot(yol), Click(x, y), Drag(x1, y1, x2, y2), Move(x, y), Scroll(x, y, dy),
// Find(sınıf) → (x, y, w, h): o stil sınıfındaki ilk görünür öğenin ekrandaki yeri (yoksa w = -1).
// Genel bakışı kapatır.
const XML = `<node><interface name="test.Cek">
<method name="Shot"><arg type="s" direction="in"/></method>
<method name="Click"><arg type="d" direction="in"/><arg type="d" direction="in"/></method>
<method name="Drag"><arg type="d" direction="in"/><arg type="d" direction="in"/><arg type="d" direction="in"/><arg type="d" direction="in"/></method>
<method name="Move"><arg type="d" direction="in"/><arg type="d" direction="in"/></method>
<method name="Scroll"><arg type="d" direction="in"/><arg type="d" direction="in"/><arg type="d" direction="in"/></method>
<method name="Find"><arg type="s" direction="in"/><arg type="d" direction="out"/><arg type="d" direction="out"/><arg type="d" direction="out"/><arg type="d" direction="out"/></method>
</interface></node>`;
export default class Cek extends Extension {
    enable() {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => { Main.overview.hide(); return GLib.SOURCE_REMOVE; });
        this._dev = Clutter.get_default_backend().get_default_seat().create_virtual_device(
            Clutter.InputDeviceType.POINTER_DEVICE);
        this._impl = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._impl.export(Gio.DBus.session, '/test/Cek');
        this._own = Gio.bus_own_name(Gio.BusType.SESSION, 'test.Cek', 0, null, null, null);
    }
    _t() { return GLib.get_monotonic_time(); }
    ShotAsync([path], inv) {
        const shot = new Shell.Screenshot();
        const stream = Gio.File.new_for_path(path).replace(null, false, Gio.FileCreateFlags.NONE, null);
        shot.screenshot(false, stream, (o, res) => {
            try { o.screenshot_finish(res); } catch (e) { log('cek hata ' + e); }
            stream.close(null);
            inv.return_value(null);
        });
    }
    Click(x, y) {
        this._dev.notify_absolute_motion(this._t(), x, y);
        this._dev.notify_button(this._t(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.PRESSED);
        this._dev.notify_button(this._t() + 50000, Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
    }
    Drag(x1, y1, x2, y2) {
        this._dev.notify_absolute_motion(this._t(), x1, y1);
        this._dev.notify_button(this._t(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.PRESSED);
        let i = 0;
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 20, () => {
            i++;
            this._dev.notify_absolute_motion(this._t(), x1 + (x2 - x1) * i / 10, y1 + (y2 - y1) * i / 10);
            if (i < 10) return GLib.SOURCE_CONTINUE;
            this._dev.notify_button(this._t(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
            return GLib.SOURCE_REMOVE;
        });
    }
    Move(x, y) {
        this._dev.notify_absolute_motion(this._t(), x, y);
    }
    Scroll(x, y, dy) {  // dy < 0: yukarı
        this._dev.notify_absolute_motion(this._t(), x, y);
        this._dev.notify_discrete_scroll(this._t(), dy < 0 ? Clutter.ScrollDirection.UP : Clutter.ScrollDirection.DOWN,
            Clutter.ScrollSource.WHEEL);
    }
    Find(cls) {
        const walk = a => {
            if (!a.visible)
                return null;
            if (a.has_style_class_name && a.has_style_class_name(cls) && a.is_mapped())
                return a;
            for (const c of a.get_children()) {
                const r = walk(c);
                if (r)
                    return r;
            }
            return null;
        };
        const a = walk(Main.layoutManager.uiGroup);
        if (!a)
            return [0, 0, -1, -1];
        const [x, y] = a.get_transformed_position();
        const [w, h] = a.get_transformed_size();
        return [x, y, w, h];
    }
    disable() { Gio.bus_unown_name(this._own); this._impl.unexport(); }
}
