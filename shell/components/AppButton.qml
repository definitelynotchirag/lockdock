import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Widgets

Item {
    id: btn
    required property var theme
    property string appId
    property var windows: []
    property color accent: theme.paletteAccent
    property bool dim: false

    // DesktopEntries loads asynchronously; depending on .applications re-runs the lookup when it lands
    readonly property var entry: { const _ = DesktopEntries.applications.values; return DesktopEntries.heuristicLookup(appId) }
    readonly property bool running: windows.length > 0
    readonly property bool focused: windows.some(w => w.activated)

    implicitWidth: theme.ipx(44)
    implicitHeight: theme.ipx(48)

    Rectangle {
        anchors.fill: parent
        radius: btn.theme.px(12)
        color: ma.containsMouse ? btn.theme.surfaceHover : "transparent"
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    // the app's theme icon; none found: theme icons.app_fallback on a soft tile
    readonly property string iconSource: Quickshell.iconPath(btn.entry?.icon ?? btn.appId, true)
    IconImage {
        id: icon
        visible: btn.iconSource !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: btn.theme.px(4)
        implicitSize: btn.theme.px(btn.theme.iconSize)
        source: btn.iconSource
        opacity: btn.dim ? 0.7 : 1
        scale: ma.pressed ? 0.9 : (ma.containsMouse ? 1.08 : 1)
        Behavior on scale { NumberAnimation { duration: 120 } }
    }
    Rectangle {
        visible: btn.iconSource === ""
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: btn.theme.px(4) + Math.round(btn.theme.px(btn.theme.iconSize) * 0.1)
        width: Math.round(btn.theme.px(btn.theme.iconSize) * 0.8); height: width
        radius: width * 0.28
        color: btn.theme.alpha(btn.theme.surfaceHover, btn.theme.dark ? 0.9 : 0.8)
        opacity: btn.dim ? 0.7 : 1
        scale: icon.scale
        Icon {
            anchors.centerIn: parent
            name: btn.theme.icon("app_fallback", "icona:layers")
            size: Math.round(parent.width * 0.62)
            stroke: btn.theme.iconStroke
            family: btn.theme.family
            color: btn.theme.textMuted
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
        Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 140 } }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (btn.windows.length > 0) {
                // cycle: focus the first non-active window, else the first
                const w = btn.windows.find(x => !x.activated) || btn.windows[0]
                w.activate()
            } else if (btn.entry) {
                btn.entry.execute()
            }
        }
        ToolTip.visible: containsMouse
        ToolTip.delay: 500
        ToolTip.text: (btn.entry?.name ?? btn.appId) + (btn.running ? " · " + btn.windows.length + " window" + (btn.windows.length > 1 ? "s" : "") : "")
    }
}
