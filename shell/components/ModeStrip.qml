import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One pill per mode; the active one is wide. While a switch is pending, a timer pill follows
// the modes (target glyph + label + m:ss, filling as the wait runs; click = press again, which
// shortens the wait) and, with theme.stayButton, a Stay pill that cancels the switch. The
// target mode's own pill then stays a plain inactive pill so the countdown shows once.
RowLayout {
    id: strip
    required property var st          // state.json
    required property real now        // ms clock for the countdown
    required property bool offTask
    required property var theme
    signal modeClicked(string modeId)
    signal stayClicked()

    readonly property var pending: st.pending || null
    readonly property var pendingMode: pending ? ((st.modes || []).find(m => m.id === pending.mode)
                                                  || { id: pending.mode, label: pending.mode, icon: "", color: "auto" }) : null

    spacing: theme.px(6)

    Repeater {
        model: strip.st.modes || []
        ModePill {
            required property var modelData
            theme: strip.theme
            mode: modelData
            active: modelData.id === strip.st.mode
            // the timer pill below shows the countdown; this pill stays plain
            pending: null
            now: strip.now
            offTask: strip.offTask
            onClicked: strip.modeClicked(modelData.id)
        }
    }

    // ---- timer pill: "<glyph> Social 0:10" ----
    Item {
        id: timer
        visible: strip.pending !== null
        property real clock: Date.now()
        Timer {
            interval: 250; repeat: true; running: timer.visible; triggeredOnStart: true
            onTriggered: timer.clock = Date.now()
        }
        readonly property color c: strip.theme.modeColor(strip.pendingMode)
        readonly property real remaining: strip.pending ? Math.max(0, strip.pending.deadline_ms - clock) : 0
        readonly property real progress: strip.pending && strip.pending.total_ms > 0
                                         ? Math.min(1, 1 - remaining / strip.pending.total_ms) : 0
        function mmss(ms) {
            const s = Math.ceil(ms / 1000)
            return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0")
        }

        implicitHeight: strip.theme.ipx(40)
        implicitWidth: timerRow.implicitWidth + strip.theme.px(30)
        Layout.leftMargin: strip.theme.px(2)
        scale: tma.pressed ? 0.96 : 1
        Behavior on scale { NumberAnimation { duration: 100 } }

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: tma.containsMouse ? Qt.tint(strip.theme.surfaceHover, strip.theme.alpha(timer.c, 0.10)) : strip.theme.surfaceHover
            Behavior on color { ColorAnimation { duration: 150 } }
            // the wait so far, rising left to right
            Rectangle {
                anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                width: Math.max(height, parent.width * timer.progress)
                radius: parent.radius
                color: strip.theme.alpha(timer.c, 0.35)
                Behavior on width { NumberAnimation { duration: 250 } }
            }
        }
        RowLayout {
            id: timerRow
            anchors.centerIn: parent
            spacing: strip.theme.px(7)
            Text {
                text: strip.pendingMode ? (strip.pendingMode.icon || "●") : ""
                font.pixelSize: strip.theme.fpx(16)
                font.family: strip.theme.family
                color: strip.theme.text
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: strip.pendingMode ? strip.pendingMode.label : ""
                font.pixelSize: strip.theme.fpx(14)
                font.family: strip.theme.family
                font.weight: Font.DemiBold
                font.letterSpacing: 0.2
                color: strip.theme.text
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: timer.mmss(timer.remaining)
                font.pixelSize: strip.theme.fpx(14)
                font.family: strip.theme.family
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
                color: strip.theme.textMuted
                Layout.alignment: Qt.AlignVCenter
            }
        }
        MouseArea {
            id: tma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (strip.pending) strip.modeClicked(strip.pending.mode)
            ToolTip.visible: containsMouse
            ToolTip.delay: 400
            ToolTip.text: "press again to shorten the wait"
        }
    }

    // ---- Stay: cancel the pending switch ----
    Rectangle {
        visible: strip.pending !== null && strip.theme.stayButton
        implicitHeight: strip.theme.ipx(40)
        implicitWidth: stayLabel.implicitWidth + strip.theme.px(30)
        radius: height / 2
        color: sma.containsMouse ? Qt.tint(strip.theme.surfaceHover, strip.theme.alpha(strip.theme.text, 0.08))
                                 : strip.theme.surfaceHover
        Behavior on color { ColorAnimation { duration: 150 } }
        scale: sma.pressed ? 0.96 : 1
        Behavior on scale { NumberAnimation { duration: 100 } }
        Text {
            id: stayLabel
            anchors.centerIn: parent
            text: "Stay"
            font.pixelSize: strip.theme.fpx(14)
            font.family: strip.theme.family
            font.weight: Font.DemiBold
            color: strip.theme.text
        }
        MouseArea {
            id: sma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: strip.stayClicked()
            ToolTip.visible: containsMouse
            ToolTip.delay: 400
            ToolTip.text: "cancel the switch and stay in this mode"
        }
    }
}
