import QtQuick

// Reads st.theme (published by the daemon from ~/.config/lockdock/theme.json).
// Every property has a fallback equal to the default look, so a missing or
// partial theme never breaks the dock. Use px()/fpx() for sizes so `scale` applies.
QtObject {
    id: th
    property var st: ({})
    property var t: (st && st.theme) ? st.theme : ({})

    function pick(v, fallback) { return (v === undefined || v === null) ? fallback : v }

    readonly property string position: t.position === "top" ? "top" : "bottom"
    readonly property bool atTop: position === "top"
    readonly property real margin: pick(t.margin, 10)
    readonly property real scale: pick(t.scale, 1.0)
    readonly property real radius: pick(t.radius, 22)
    readonly property color background: pick(t.background, "#DB1C1C21")
    readonly property real borderWidth: pick((t.border || {}).width, 1)
    readonly property color borderColor: pick((t.border || {}).color, "#1FFFFFFF")
    readonly property color offTaskBorderColor: pick((t.border || {}).off_task_color, "#CCFF594D")
    readonly property string accentOverride: t.accent_override || ""
    readonly property string fontFamily: pick((t.font || {}).family, "")
    readonly property string family: fontFamily !== "" ? fontFamily : Qt.application.font.family
    readonly property real fontSize: pick((t.font || {}).size, 14)
    readonly property real iconSize: pick(t.icon_size, 36)
    readonly property var sections: Array.isArray(t.sections) ? t.sections : ["pet", "modes", "apps", "agents", "held"]
    readonly property bool showUnpinned: pick(t.show_unpinned, true)
    readonly property bool autohide: pick((t.autohide || {}).enabled, false)
    readonly property real revealPx: pick((t.autohide || {}).reveal_px, 4)
    readonly property int hideDelayMs: pick((t.autohide || {}).hide_delay_ms, 600)
    readonly property bool nudge: pick((t.nudge || {}).enabled, true)
    readonly property real opacity: pick(t.opacity, 1.0)

    // icon_size grows or shrinks everything that wraps an icon by the same delta
    readonly property real iconDelta: iconSize - 36

    // scaled pixel size for a base (scale 1, default icon_size) length
    function px(v) { return Math.round(v * scale) }
    // scaled font pixel size for a base size that is 14 at the default font size
    function fpx(v) { return Math.max(1, Math.round(v * (fontSize / 14) * scale)) }
    // like px() but grows with icon_size (button, pill and card heights)
    function ipx(v) { return Math.round((v + iconDelta) * scale) }
}
