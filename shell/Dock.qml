import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland

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

    // running apps (for the dot + for unpinned running apps)
    readonly property var toplevels: ToplevelManager.toplevels.values
    function norm(s) { return (s || "").toLowerCase() }
    function runningFor(appId) {
        const a = norm(appId)
        return toplevels.filter(t => { const i = norm(t.appId); return i === a || i.endsWith("." + a) || a.endsWith("." + i) })
    }
    readonly property var unpinned: {
        const seen = {}
        const pinned = (activeMode.apps || []).map(norm)
        const out = []
        for (const t of toplevels) {
            const id = norm(t.appId)
            if (!id || seen[id]) continue
            if (pinned.some(p => p === id || id.endsWith("." + p) || p.endsWith("." + id))) continue
            seen[id] = true
            out.push(t.appId)
        }
        return out
    }

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

            // ---- modes ----
            Repeater {
                model: dock.st.modes || []
                ModePill {
                    required property var modelData
                    mode: modelData
                    active: modelData.id === dock.st.mode
                    pending: dock.st.pending && dock.st.pending.mode === modelData.id ? dock.st.pending : null
                    now: dock.now
                    offTask: dock.offTask
                    onClicked: dock.shell.send(["mode", modelData.id])
                }
            }

            Rectangle { width: 1; height: 36; color: Qt.rgba(1, 1, 1, 0.14); Layout.leftMargin: 4; Layout.rightMargin: 4 }

            // ---- pinned apps of the mode ----
            Repeater {
                model: dock.activeMode.apps || []
                AppButton {
                    required property var modelData
                    appId: modelData
                    windows: dock.runningFor(modelData)
                    accent: dock.accent
                }
            }
            // ---- running but not pinned ----
            Rectangle { visible: dock.unpinned.length > 0; width: 1; height: 28; color: Qt.rgba(1, 1, 1, 0.1) }
            Repeater {
                model: dock.unpinned
                AppButton {
                    required property var modelData
                    appId: modelData
                    windows: dock.runningFor(modelData)
                    accent: dock.accent
                    dim: true
                }
            }

            // ---- held notifications ----
            Rectangle {
                visible: (dock.st.held_count || 0) > 0
                Layout.leftMargin: 6
                width: 34; height: 34; radius: 17
                color: Qt.rgba(1, 1, 1, 0.08)
                Text { anchors.centerIn: parent; text: "🔕"; font.pixelSize: 15 }
                Rectangle {
                    anchors.top: parent.top; anchors.right: parent.right
                    anchors.topMargin: -3; anchors.rightMargin: -3
                    height: 16; width: Math.max(16, badge.implicitWidth + 8); radius: 8
                    color: dock.accent
                    Text { id: badge; anchors.centerIn: parent; text: dock.st.held_count; color: "#111"; font.pixelSize: 10; font.bold: true }
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true
                    onClicked: dock.shell.send(["release"])
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: ((dock.st.held || []).slice(-6).map(n => n.app + ": " + n.summary).join("\n") || "") + "\n\nclick to release"
                }
            }
        }
    }

    // off-task nudge above the dock
    Rectangle {
        id: nudgeBox
        visible: dock.offTask
        anchors.bottom: card.top
        anchors.bottomMargin: 6
        anchors.horizontalCenter: card.horizontalCenter
        width: nudge.implicitWidth + 20; height: 24; radius: 12
        color: Qt.rgba(0.8, 0.2, 0.15, 0.9)
        Text {
            id: nudge; anchors.centerIn: parent; color: "white"; font.pixelSize: 11
            text: "off task · " + ((dock.st.activity || {}).reason || "")
        }
    }
}
