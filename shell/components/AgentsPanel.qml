import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The list the agents pill opens: a header ("3 agents · 1 needs you") and one row per agent
// (state.json `agents`, already sorted needs_input -> working -> idle -> done): kind glyph,
// project label, last message, age and a state dot; the cwd is in the tooltip. Clicking a row
// focuses that agent's window and closes the panel. Up to theme.agentsMaxRows rows, then
// it scrolls. The Dock positions it (x, y), adds it to the input mask while `visible`, and
// grows the window by its height. It scales and fades out of `originX` (the pill's centre)
// at the edge facing the dock; rows stagger in.
Item {
    id: panel
    required property var st
    required property var shell
    required property var theme
    property bool open: false
    property bool below: false         // dock at the top: the panel hangs below the pill
    property real originX: width / 2   // the pill's centre, in panel coordinates
    signal closeRequested()

    readonly property var agents: st.agents || []
    readonly property int needCount: agents.filter(a => a.state === "needs_input").length
    readonly property int workingCount: agents.filter(a => a.state === "working").length
    readonly property bool hovered: hover.hovered
    readonly property real rowHeight: theme.px(48)
    readonly property real pad: theme.px(6)
    readonly property int visibleRows: Math.min(agents.length, theme.agentsMaxRows)

    // 0 closed .. 1 open; the panel stays visible until it has faded out
    property real progress: open ? 1 : 0
    Behavior on progress {
        NumberAnimation {
            duration: panel.open ? 180 : 120
            easing.type: panel.open ? Easing.OutCubic : Easing.InCubic
        }
    }
    visible: progress > 0
    opacity: progress * theme.opacity
    transform: Scale {
        origin.x: panel.originX
        origin.y: panel.below ? 0 : panel.height
        xScale: 0.85 + 0.15 * panel.progress
        yScale: xScale
    }

    width: theme.px(320)
    height: header.height + list.height + 2 * pad + theme.px(2)

    // ages tick while open
    property real now: Date.now()
    Timer { interval: 1000; repeat: true; running: panel.visible; triggeredOnStart: true; onTriggered: panel.now = Date.now() }
    function age(ms) {
        const s = Math.max(0, (panel.now - ms) / 1000)
        if (s < 60) return "now"
        if (s < 3600) return Math.floor(s / 60) + "m"
        if (s < 86400) return Math.floor(s / 3600) + "h"
        return Math.floor(s / 86400) + "d"
    }
    function dotColor(state) {
        return state === "needs_input" ? theme.danger : state === "working" ? theme.success : theme.textMuted
    }
    function stateText(state) {
        return state === "needs_input" ? "needs you" : state
    }

    HoverHandler { id: hover }

    Island {
        anchors.fill: parent
        theme: panel.theme
        radius: panel.theme.px(Math.min(panel.theme.radius, 18))
    }

    Text {
        id: header
        x: panel.pad + panel.theme.px(10)
        y: panel.pad + panel.theme.px(2)
        height: panel.theme.px(30)
        verticalAlignment: Text.AlignVCenter
        text: panel.agents.length + (panel.agents.length === 1 ? " agent" : " agents")
              + (panel.needCount > 0 ? " · " + panel.needCount + (panel.needCount === 1 ? " needs you" : " need you")
                                     : panel.workingCount > 0 ? " · " + panel.workingCount + " working" : "")
        font.pixelSize: panel.theme.fpx(12)
        font.family: panel.theme.family
        font.weight: Font.DemiBold
        font.letterSpacing: 0.2
        color: panel.theme.textMuted
    }

    ListView {
        id: list
        x: panel.pad
        y: header.y + header.height
        width: panel.width - 2 * panel.pad
        height: panel.visibleRows * panel.rowHeight
        clip: true
        interactive: count > panel.theme.agentsMaxRows
        boundsBehavior: Flickable.StopAtBounds
        model: panel.agents
        // a slim always-on bar while some rows are out of view
        ScrollBar.vertical: ScrollBar {
            policy: list.interactive ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            padding: panel.theme.px(2)
            background: null
            contentItem: Rectangle {
                implicitWidth: panel.theme.px(4)
                radius: width / 2
                color: panel.theme.alpha(panel.theme.textMuted, parent.pressed ? 0.7 : 0.4)
            }
        }

        delegate: Item {
            id: row
            required property var modelData
            required property int index
            readonly property bool needs: modelData.state === "needs_input"
            readonly property bool quiet: modelData.state === "idle" || modelData.state === "done"
            width: list.width
            height: panel.rowHeight

            // stagger: each row fades and slides in 25 ms after the one above it
            property bool revealed: false
            Timer {
                interval: 30 + 25 * Math.min(row.index, 12)
                running: panel.open && !row.revealed
                onTriggered: row.revealed = true
            }
            Connections {
                target: panel
                function onOpenChanged() { if (!panel.open) row.revealed = false }
            }
            opacity: revealed ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: row.revealed ? 180 : 100; easing.type: Easing.OutCubic } }
            transform: Translate {
                y: row.revealed ? 0 : (panel.below ? -1 : 1) * panel.theme.px(8)
                Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            }

            Rectangle {
                anchors.fill: parent
                anchors.margins: panel.theme.px(1)
                radius: panel.theme.px(12)
                color: rowMa.containsMouse ? panel.theme.surfaceHover
                                           : row.needs ? panel.theme.alpha(panel.theme.danger, 0.10) : "transparent"
                Behavior on color { ColorAnimation { duration: 120 } }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: panel.theme.px(10)
                anchors.rightMargin: panel.theme.px(list.interactive ? 16 : 12)   // clear of the scroll bar
                spacing: panel.theme.px(10)

                // kind glyph on a small round tile
                Rectangle {
                    implicitWidth: panel.theme.px(30); implicitHeight: implicitWidth; radius: implicitWidth / 2
                    color: panel.theme.alpha(panel.theme.surfaceHover, panel.theme.dark ? 0.9 : 0.7)
                    Layout.alignment: Qt.AlignVCenter
                    Text {
                        anchors.centerIn: parent
                        text: row.modelData.glyph || "◆"
                        font.pixelSize: panel.theme.fpx(14)
                        font.family: panel.theme.family
                        color: panel.theme.text
                        opacity: row.quiet ? 0.6 : 1
                    }
                }
                ColumnLayout {
                    spacing: panel.theme.px(1)
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    Text {
                        text: row.modelData.label
                        font.pixelSize: panel.theme.fpx(13)
                        font.family: panel.theme.family
                        font.weight: Font.DemiBold
                        color: panel.theme.text
                        opacity: row.quiet ? 0.7 : 1
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: row.modelData.last_message || (row.modelData.kind + " · " + panel.stateText(row.modelData.state))
                        font.pixelSize: panel.theme.fpx(11)
                        font.family: panel.theme.family
                        color: row.needs ? panel.theme.danger : panel.theme.textMuted
                        maximumLineCount: 1
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
                Text {
                    text: panel.age(row.modelData.since_ms || 0)
                    font.pixelSize: panel.theme.fpx(11)
                    font.family: panel.theme.family
                    color: panel.theme.textMuted
                    Layout.alignment: Qt.AlignVCenter
                }
                Rectangle {
                    implicitWidth: panel.theme.px(8); implicitHeight: implicitWidth; radius: implicitWidth / 2
                    color: panel.dotColor(row.modelData.state)
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            MouseArea {
                id: rowMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    panel.shell.send(["agent", "focus", row.modelData.id])
                    panel.closeRequested()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 600
                ToolTip.text: row.modelData.cwd || row.modelData.id
            }
        }
    }
}
