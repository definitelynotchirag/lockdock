import QtQuick
import QtQuick.Layouts

// Agent inbox, compact: one pill for every running coding agent (state.json `agents`): an
// icon (theme.agentIcon), the count, and a dot (danger + "N need you" + a pulsing accent outline when an
// agent waits for you, success while all work, muted when idle / done). Click toggles the
// list (AgentsPanel), which the Dock draws outside the card and opens from this pill's
// centre. The Dock registers the pill (`agentsPill`) and binds `panelHovered`.
Pressable {
    id: pill
    required property var st          // state.json
    property bool open: false
    property bool panelHovered: false  // set by the Dock from the panel

    readonly property var agents: st.agents || []
    readonly property int count: agents.length
    readonly property int needCount: agents.filter(a => a.state === "needs_input").length
    readonly property int workingCount: agents.filter(a => a.state === "working").length
    readonly property bool needs: needCount > 0
    readonly property bool active: count > 0
    // the kind's icon when every agent is the same kind, else the generic icons.agents
    readonly property string glyph: count > 0 && agents.every(a => a.kind === agents[0].kind)
                                    ? theme.agentIcon(agents[0]) : theme.icon("agents", "icona:sparkles")
    readonly property color dotColor: needs ? theme.danger : workingCount > 0 ? theme.success : theme.textMuted
    property real pulse: 1

    visible: active
    onActiveChanged: if (!active) open = false
    implicitHeight: theme.ipx(40)
    implicitWidth: content.implicitWidth + theme.px(26)
    Behavior on implicitWidth { NumberAnimation { duration: pill.theme.dur(220); easing.type: Easing.OutCubic } }
    scale: pressScale
    tip: ({
        icon: glyph,
        title: count + (count === 1 ? " agent" : " agents"),
        detail: (needs ? needCount + (needCount === 1 ? " needs you" : " need you")
                       : workingCount > 0 ? workingCount + " working" : "all idle") + " · click for the list"
    })
    tipEnabled: !open
    onClicked: pill.open = !pill.open

    readonly property real rest: theme.dark ? 0.85 : 0.6
    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: pill.theme.alpha(pill.theme.surfaceHover, pill.open ? 1 : pill.rest + (1 - pill.rest) * pill.hoverProgress)
        border.width: pill.needs ? pill.theme.px(1.5) : 0
        border.color: pill.theme.alpha(pill.theme.paletteAccent, pill.pulse)
    }

    SequentialAnimation on pulse {
        running: pill.needs
        loops: Animation.Infinite
        onRunningChanged: if (!running) pill.pulse = 1
        NumberAnimation { to: 0.2; duration: 900; easing.type: Easing.InOutQuad }
        NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutQuad }
    }

    // pointer away from both the pill and the open panel for 700 ms: close
    Timer {
        interval: 700
        running: pill.open && !pill.hovered && !pill.panelHovered
        onTriggered: pill.open = false
    }

    RowLayout {
        id: content
        anchors.centerIn: parent
        spacing: pill.theme.px(7)
        Icon {
            name: pill.glyph
            size: pill.theme.fpx(17)
            stroke: pill.theme.iconStroke
            family: pill.theme.family
            color: pill.theme.text
            Layout.alignment: Qt.AlignVCenter
            transform: Translate { y: pill.lift(1.5) }
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
            Behavior on color { ColorAnimation { duration: pill.theme.dur(200) } }
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
                Behavior on opacity { NumberAnimation { duration: pill.theme.dur(200) } }
            }
        }
    }
}
