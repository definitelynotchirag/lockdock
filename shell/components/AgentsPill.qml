import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Agent inbox, compact: one pill for every running coding agent (state.json `agents`): a
// glyph, the count, and a dot (danger + "N need you" + a pulsing accent outline when an
// agent waits for you, success while all work, muted when idle / done). Click toggles the
// list (AgentsPanel), which the Dock draws outside the card and opens from this pill's
// centre. The Dock registers the pill (`agentsPill`) and binds `panelHovered`.
Rectangle {
    id: pill
    required property var st          // state.json
    required property var theme
    property bool open: false
    property bool panelHovered: false  // set by the Dock from the panel

    readonly property var agents: st.agents || []
    readonly property int count: agents.length
    readonly property int needCount: agents.filter(a => a.state === "needs_input").length
    readonly property int workingCount: agents.filter(a => a.state === "working").length
    readonly property bool needs: needCount > 0
    readonly property bool active: count > 0
    // the first agent's glyph when every agent is the same kind, else the generic mark
    readonly property string glyph: count > 0 && agents.every(a => a.kind === agents[0].kind) && agents[0].glyph
                                    ? agents[0].glyph : "◆"
    readonly property color dotColor: needs ? theme.danger : workingCount > 0 ? theme.success : theme.textMuted
    property real pulse: 1

    visible: active
    onActiveChanged: if (!active) open = false
    implicitHeight: theme.ipx(40)
    implicitWidth: content.implicitWidth + theme.px(26)
    Behavior on implicitWidth { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    radius: height / 2
    color: open || ma.containsMouse ? theme.surfaceHover : theme.alpha(theme.surfaceHover, theme.dark ? 0.85 : 0.6)
    border.width: needs ? theme.px(1.5) : 0
    border.color: theme.alpha(theme.paletteAccent, pulse)
    Behavior on color { ColorAnimation { duration: 150 } }
    scale: ma.pressed ? 0.96 : 1
    Behavior on scale { NumberAnimation { duration: 100 } }

    SequentialAnimation on pulse {
        running: pill.needs
        loops: Animation.Infinite
        onRunningChanged: if (!running) pill.pulse = 1
        NumberAnimation { to: 0.2; duration: 900; easing.type: Easing.InOutQuad }
        NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutQuad }
    }

    // pointer away from both the pill and the open panel for 700 ms: close
    readonly property bool hovered: ma.containsMouse || panelHovered
    Timer {
        interval: 700
        running: pill.open && !pill.hovered
        onTriggered: pill.open = false
    }

    RowLayout {
        id: content
        anchors.centerIn: parent
        spacing: pill.theme.px(7)
        Text {
            text: pill.glyph
            font.pixelSize: pill.theme.fpx(15)
            font.family: pill.theme.family
            color: pill.theme.text
            Layout.alignment: Qt.AlignVCenter
        }
        Text {
            text: pill.count
            font.pixelSize: pill.theme.fpx(13)
            font.family: pill.theme.family
            font.weight: Font.DemiBold
            color: pill.theme.text
            Layout.alignment: Qt.AlignVCenter
        }
        Rectangle {
            implicitWidth: pill.theme.px(7); implicitHeight: implicitWidth; radius: implicitWidth / 2
            color: pill.dotColor
            opacity: pill.needs ? Math.max(0.45, pill.pulse) : 1
            Behavior on color { ColorAnimation { duration: 200 } }
            Layout.alignment: Qt.AlignVCenter
        }
        // "2 need you": slides open (the pill's width animates with it)
        Item {
            implicitWidth: pill.needs ? needLabel.implicitWidth : 0
            implicitHeight: needLabel.implicitHeight
            clip: true
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: pill.needs ? 0 : -content.spacing
            Text {
                id: needLabel
                text: pill.needCount + (pill.needCount === 1 ? " needs you" : " need you")
                font.pixelSize: pill.theme.fpx(12)
                font.family: pill.theme.family
                font.weight: Font.DemiBold
                color: pill.theme.danger
                opacity: pill.needs ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 200 } }
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pill.open = !pill.open
        ToolTip.visible: containsMouse && !pill.open
        ToolTip.delay: 600
        ToolTip.text: pill.count + (pill.count === 1 ? " agent" : " agents")
                      + (pill.needs ? " · " + needLabel.text : "") + "\nclick for the list"
    }
}
