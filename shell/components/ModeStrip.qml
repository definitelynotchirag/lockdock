import QtQuick
import QtQuick.Layouts

// One pill per mode; the active one is wide. While a switch is pending, a timer pill follows
// the modes (icons.timer + target label + m:ss, filling as the wait runs; click = press again,
// which shortens the wait) and, with theme.stayButton, a Stay pill (icons.stay) that cancels the switch. The
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
    Pressable {
        id: timer
        theme: strip.theme
        visible: strip.pending !== null
        tip: ({
            icon: strip.theme.icon("timer", "icona:hourglass"),
            title: strip.pendingMode ? "Switching to " + strip.pendingMode.label : "Switching",
            detail: "press again to shorten the wait"
        })
        onClicked: if (strip.pending) strip.modeClicked(strip.pending.mode)
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
        scale: pressScale

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: Qt.tint(strip.theme.surfaceHover, strip.theme.alpha(timer.c, 0.10 * timer.hoverProgress))
            // the wait so far, rising left to right
            Rectangle {
                anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                width: Math.max(height, parent.width * timer.progress)
                radius: parent.radius
                color: strip.theme.alpha(timer.c, 0.35)
                Behavior on width { NumberAnimation { duration: strip.theme.dur(250) } }
            }
        }
        RowLayout {
            id: timerRow
            anchors.centerIn: parent
            spacing: strip.theme.px(7)
            // icons.timer; "" (pack "text") shows the target mode's own icon as before
            Icon {
                name: strip.theme.icon("timer", "icona:hourglass") || strip.theme.modeIcon(strip.pendingMode)
                size: strip.theme.fpx(17)
                stroke: strip.theme.iconStroke
                family: strip.theme.family
                color: strip.theme.text
                Layout.alignment: Qt.AlignVCenter
                transform: Translate { y: timer.lift(1.5) }
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
    }

    // ---- Stay: cancel the pending switch ----
    Pressable {
        id: stay
        theme: strip.theme
        visible: strip.pending !== null && strip.theme.stayButton
        implicitHeight: strip.theme.ipx(40)
        implicitWidth: stayRow.implicitWidth + strip.theme.px(30)
        scale: pressScale
        tip: ({
            icon: strip.theme.icon("stay", "icona:target"),
            title: "Cancel the switch",
            detail: "stay in " + ((strip.st.modes || []).find(m => m.id === strip.st.mode) || { label: "this mode" }).label
        })
        onClicked: strip.stayClicked()
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: Qt.tint(strip.theme.surfaceHover, strip.theme.alpha(strip.theme.text, 0.08 * stay.hoverProgress))
        }
        Row {
            id: stayRow
            anchors.centerIn: parent
            spacing: strip.theme.px(6)
            Icon {
                visible: name !== ""
                anchors.verticalCenter: parent.verticalCenter
                name: strip.theme.icon("stay", "icona:target")
                size: strip.theme.fpx(17)
                stroke: strip.theme.iconStroke
                family: strip.theme.family
                color: strip.theme.text
                transform: Translate { y: stay.lift(1.5) }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Stay"
                font.pixelSize: strip.theme.fpx(14)
                font.family: strip.theme.family
                font.weight: Font.DemiBold
                color: strip.theme.text
            }
        }
    }
}
