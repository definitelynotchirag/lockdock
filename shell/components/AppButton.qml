import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Widgets

Item {
    id: btn
    required property var theme
    property string appId
    property var windows: []
    property color accent: "#f0a04b"
    property bool dim: false

    // DesktopEntries loads asynchronously; depending on .applications re-runs the lookup when it lands
    readonly property var entry: { const _ = DesktopEntries.applications.values; return DesktopEntries.heuristicLookup(appId) }
    readonly property bool running: windows.length > 0
    readonly property bool focused: windows.some(w => w.activated)

    implicitWidth: theme.ipx(48)
    implicitHeight: theme.ipx(52)

    Rectangle {
        anchors.fill: parent
        radius: btn.theme.px(12)
        color: ma.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
    }

    IconImage {
        id: icon
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: btn.theme.px(5)
        implicitSize: btn.theme.px(btn.theme.iconSize)
        source: Quickshell.iconPath(btn.entry?.icon ?? btn.appId, "application-x-executable")
        opacity: btn.dim ? 0.75 : 1
        scale: ma.pressed ? 0.9 : (ma.containsMouse ? 1.08 : 1)
        Behavior on scale { NumberAnimation { duration: 120 } }
    }

    // running / focused dot
    Rectangle {
        visible: btn.running
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: btn.theme.px(3)
        width: btn.theme.px(btn.focused ? 14 : 5); height: btn.theme.px(5); radius: height / 2
        color: btn.focused ? btn.accent : Qt.rgba(1, 1, 1, 0.7)
        Behavior on width { NumberAnimation { duration: 120 } }
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
