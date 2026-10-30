import QtQuick
import Quickshell
import Quickshell.Widgets

// One app: its icon on a soft halo that grows in on hover (Pressable: hoverProgress);
// press scales it to 0.96. Running dot (text_muted) / focused pill (accent) below.
// Click focuses a window (cycling) or launches the app.
Pressable {
    id: btn
    property string appId
    property var windows: []
    property color accent: theme.paletteAccent

    // DesktopEntries loads asynchronously; depending on .applications re-runs the lookup when it lands
    readonly property var entry: { const _ = DesktopEntries.applications.values; return DesktopEntries.heuristicLookup(appId) }
    readonly property bool running: windows.length > 0
    readonly property bool focused: windows.some(w => w.activated)
    readonly property string appName: entry?.name ?? appId

    implicitWidth: theme.ipx(44)
    implicitHeight: theme.ipx(48)
    scale: pressScale

    tip: ({
        title: appName,
        detail: running ? windows.length + (windows.length === 1 ? " window" : " windows") + " · click to focus"
                        : "click to launch"
    })
    // a running app shows live window previews (theme.previews) instead of its tooltip
    readonly property bool previewsOn: running && theme.previews
    tipEnabled: !previewsOn

    // ---- window previews: the Dock (theme.host) owns one WindowPreviews per window ----
    // a press hides them until the pointer leaves and comes back (like the tip)
    property bool previewsSuppressed: false
    function syncPreviews(immediate) {
        const host = btn.theme.host
        if (!host || !host.showPreviews) return
        if (btn.hovered && btn.visible && btn.previewsOn && !btn.previewsSuppressed)
            host.showPreviews(btn, btn.windows)
        else
            host.hidePreviews(btn, immediate === true)
    }
    Connections {
        target: btn
        function onHoveredChanged() { if (!btn.hovered) btn.previewsSuppressed = false; btn.syncPreviews(false) }
        function onPressedChanged() { if (btn.pressed) { btn.previewsSuppressed = true; btn.syncPreviews(true) } }
        function onPreviewsOnChanged() { btn.syncPreviews(false) }
        function onVisibleChanged() { btn.syncPreviews(true) }
    }
    Component.onCompleted: syncPreviews(false)
    Component.onDestruction: if (btn.theme.host && btn.theme.host.hidePreviews) btn.theme.host.hidePreviews(btn, true)

    onClicked: {
        if (btn.windows.length > 0) {
            // cycle: focus the first non-active window, else the first
            const w = btn.windows.find(x => !x.activated) || btn.windows[0]
            w.activate()
        } else if (btn.entry) {
            btn.entry.execute()
        }
    }

    readonly property real iconPx: theme.px(theme.iconSize)
    readonly property real iconTop: theme.px(4)

    // the halo: a surface_hover rounded square behind the icon, 0.9 -> 1 scale as it fades in
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: btn.iconTop - btn.theme.px(4)
        width: btn.iconPx + btn.theme.px(8); height: width
        radius: btn.theme.px(12)
        color: btn.theme.surfaceHover
        opacity: btn.hoverProgress
        scale: 0.9 + 0.1 * btn.hoverProgress
        visible: opacity > 0
    }

    // the app's theme icon; none found: theme icons.app_fallback on a soft tile
    readonly property string iconSource: Quickshell.iconPath(btn.entry?.icon ?? btn.appId, true)
    Item {
        id: art
        anchors.horizontalCenter: parent.horizontalCenter
        y: btn.iconTop
        width: btn.iconPx; height: width

        IconImage {
            visible: btn.iconSource !== ""
            anchors.fill: parent
            implicitSize: btn.iconPx
            source: btn.iconSource
        }
        Rectangle {
            visible: btn.iconSource === ""
            anchors.centerIn: parent
            width: Math.round(btn.iconPx * 0.8); height: width
            radius: width * 0.28
            color: btn.theme.alpha(btn.theme.surfaceHover, btn.theme.dark ? 0.9 : 0.8)
            Icon {
                anchors.centerIn: parent
                name: btn.theme.icon("app_fallback", "icona:layers")
                size: Math.round(parent.width * 0.62)
                stroke: btn.theme.iconStroke
                family: btn.theme.family
                color: btn.theme.textMuted
            }
        }
    }

    // running dot (text_muted) / focused pill (accent)
    Rectangle {
        visible: btn.running
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: btn.theme.px(3)
        width: btn.theme.px(btn.focused ? 14 : 4); height: btn.theme.px(4); radius: height / 2
        color: btn.focused ? btn.accent : btn.theme.textMuted
        Behavior on width { NumberAnimation { duration: btn.theme.dur(140); easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: btn.theme.dur(140) } }
    }
}
