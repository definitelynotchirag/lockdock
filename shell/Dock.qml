import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "components"

// The dock window. Lays out the components in one row; add a feature by
// dropping a component into components/ and placing it in `row` below.
PanelWindow {
    id: dock
    required property var shell
    readonly property var st: shell.state
    readonly property var activeMode: (st.modes || []).find(m => m.id === st.mode) || { id: "", label: "", icon: "", color: "#888", apps: [] }
    readonly property bool offTask: (st.activity || {}).verdict === "off"
    readonly property color accent: activeMode.color || "#f0a04b"

    anchors.bottom: true
    margins.bottom: 10
    exclusiveZone: 0
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "lockdock"
    implicitWidth: card.implicitWidth + 24
    implicitHeight: card.implicitHeight + 12 + 34   // headroom for the nudge
    mask: Region { item: card; Region { item: nudgeBox } }

    // countdown clock
    property real now: Date.now()
    Timer { interval: 100; repeat: true; running: dock.st.pending !== null && dock.st.pending !== undefined; onTriggered: dock.now = Date.now() }

    Rectangle {
        id: card
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        implicitWidth: row.implicitWidth + 20
        implicitHeight: 64
        radius: 22
        color: Qt.rgba(0.11, 0.11, 0.13, 0.86)
        border.width: 1
        border.color: dock.offTask ? Qt.rgba(1, 0.35, 0.3, 0.8) : Qt.rgba(1, 1, 1, 0.12)
        Behavior on border.color { ColorAnimation { duration: 250 } }

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 6

            ModeStrip {
                st: dock.st
                now: dock.now
                offTask: dock.offTask
                onModeClicked: modeId => dock.shell.send(["mode", modeId])
            }

            Rectangle { width: 1; height: 36; color: Qt.rgba(1, 1, 1, 0.14); Layout.leftMargin: 4; Layout.rightMargin: 4 }

            AppStrip {
                activeMode: dock.activeMode
                accent: dock.accent
            }

            Rectangle { visible: agentStrip.visible; width: 1; height: 36; color: Qt.rgba(1, 1, 1, 0.14); Layout.leftMargin: 4; Layout.rightMargin: 4 }

            AgentStrip { id: agentStrip; st: dock.st; shell: dock.shell }

            HeldBadge {
                Layout.leftMargin: 6
                st: dock.st
                accent: dock.accent
                onReleaseClicked: dock.shell.send(["release"])
            }
        }
    }

    // off-task nudge above the dock
    Nudge {
        id: nudgeBox
        visible: dock.offTask
        anchors.bottom: card.top
        anchors.bottomMargin: 6
        anchors.horizontalCenter: card.horizontalCenter
        reason: (dock.st.activity || {}).reason || ""
    }
}
