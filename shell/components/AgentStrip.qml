import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Agent inbox: one chip per running coding agent (state.json `agents`).
// Red pulsing dot = waiting for you, green = working, grey = idle / done. Click focuses its window.
RowLayout {
    id: strip
    required property var st          // state.json
    required property var shell       // for shell.send([...])

    readonly property var agents: st.agents || []
    readonly property bool active: agents.length > 0
    spacing: 6
    visible: agents.length > 0

    function dotColor(state) {
        return state === "needs_input" ? "#ff5a4e" : state === "working" ? "#5fd38d" : Qt.rgba(1, 1, 1, 0.35)
    }

    Repeater {
        model: strip.agents
        Rectangle {
            id: chip
            required property var modelData
            readonly property bool needs: modelData.state === "needs_input"
            readonly property bool quiet: modelData.state === "done" || modelData.state === "idle"

            implicitHeight: 40
            implicitWidth: content.implicitWidth + 24
            radius: 20
            color: needs ? Qt.rgba(1, 0.35, 0.3, ma.containsMouse ? 0.32 : 0.22)
                         : (ma.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.07))
            border.width: needs ? 1 : 0
            border.color: Qt.rgba(1, 0.35, 0.3, 0.7)
            Behavior on color { ColorAnimation { duration: 150 } }

            RowLayout {
                id: content
                anchors.centerIn: parent
                spacing: 7
                Text {
                    text: chip.modelData.glyph || "◆"
                    font.pixelSize: 15
                    color: "#eaeaea"
                    opacity: chip.quiet ? 0.6 : 1
                    Layout.alignment: Qt.AlignVCenter
                }
                Text {
                    text: chip.modelData.label
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: "#eaeaea"
                    opacity: chip.quiet ? 0.6 : 1
                    elide: Text.ElideRight
                    Layout.maximumWidth: 120
                    Layout.alignment: Qt.AlignVCenter
                }
                Rectangle {
                    id: dot
                    width: 8; height: 8; radius: 4
                    color: strip.dotColor(chip.modelData.state)
                    Layout.alignment: Qt.AlignVCenter
                    SequentialAnimation on opacity {
                        running: chip.needs
                        loops: Animation.Infinite
                        onRunningChanged: if (!running) dot.opacity = 1
                        NumberAnimation { to: 0.25; duration: 600; easing.type: Easing.InOutQuad }
                        NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutQuad }
                    }
                }
            }

            MouseArea {
                id: ma
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: strip.shell.send(["agent", "focus", chip.modelData.id])
                ToolTip.visible: containsMouse
                ToolTip.delay: 400
                ToolTip.text: chip.modelData.kind + " · " + chip.modelData.state.replace("_", " ")
                              + (chip.modelData.last_message ? "\n" + chip.modelData.last_message : "")
                              + "\n" + chip.modelData.cwd
            }
        }
    }
}
