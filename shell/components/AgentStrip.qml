import QtQuick
import QtQuick.Layouts

// Agent inbox: one chip per running coding agent (state.json `agents`).
// State dot: danger = waiting for you (the chip's outline pulses in the accent), success =
// working, muted = idle / done. Click focuses its window.
RowLayout {
    id: strip
    required property var st          // state.json
    required property var shell       // for shell.send([...])
    required property var theme

    readonly property var agents: st.agents || []
    readonly property bool active: agents.length > 0
    spacing: theme.px(6)
    visible: agents.length > 0

    function dotColor(state) {
        return state === "needs_input" ? theme.danger : state === "working" ? theme.success : theme.textMuted
    }

    Repeater {
        model: strip.agents
        Pressable {
            id: chip
            theme: strip.theme
            required property var modelData
            readonly property bool needs: modelData.state === "needs_input"
            readonly property bool quiet: modelData.state === "done" || modelData.state === "idle"
            property real pulse: 1

            implicitHeight: strip.theme.ipx(40)
            implicitWidth: content.implicitWidth + strip.theme.px(28)
            scale: pressScale
            tip: ({
                icon: strip.theme.agentIcon(modelData),
                title: modelData.label + " · " + modelData.state.replace("_", " "),
                detail: (modelData.last_message || modelData.cwd || "")
            })
            onClicked: strip.shell.send(["agent", "focus", chip.modelData.id])
            readonly property real rest: strip.theme.dark ? 0.85 : 0.6
            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: strip.theme.alpha(strip.theme.surfaceHover, chip.rest + (1 - chip.rest) * chip.hoverProgress)
                border.width: chip.needs ? strip.theme.px(1.5) : 0
                border.color: strip.theme.alpha(strip.theme.paletteAccent, chip.pulse)
            }
            SequentialAnimation on pulse {
                running: chip.needs
                loops: Animation.Infinite
                onRunningChanged: if (!running) chip.pulse = 1
                NumberAnimation { to: 0.2; duration: 700; easing.type: Easing.InOutQuad }
                NumberAnimation { to: 1; duration: 700; easing.type: Easing.InOutQuad }
            }

            RowLayout {
                id: content
                anchors.centerIn: parent
                spacing: strip.theme.px(7)
                Icon {
                    name: strip.theme.agentIcon(chip.modelData)
                    size: strip.theme.fpx(17)
                    stroke: strip.theme.iconStroke
                    family: strip.theme.family
                    color: strip.theme.text
                    opacity: chip.quiet ? 0.6 + 0.4 * chip.hoverProgress : 1
                    Layout.alignment: Qt.AlignVCenter
                }
                Text {
                    text: chip.modelData.label
                    font.pixelSize: strip.theme.fpx(13)
                    font.family: strip.theme.family
                    font.weight: Font.Medium
                    color: strip.theme.text
                    opacity: chip.quiet ? 0.65 : 1
                    elide: Text.ElideRight
                    Layout.maximumWidth: strip.theme.px(120)
                    Layout.alignment: Qt.AlignVCenter
                }
                Rectangle {
                    implicitWidth: strip.theme.px(7); implicitHeight: implicitWidth; radius: implicitWidth / 2
                    color: strip.dotColor(chip.modelData.state)
                    opacity: chip.needs ? Math.max(0.35, chip.pulse) : 1
                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }
    }
}
