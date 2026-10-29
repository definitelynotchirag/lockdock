import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: pill
    required property var theme
    property var mode
    property bool active: false
    property var pending: null      // {mode, deadline_ms, total_ms} or null
    property real now: 0
    property bool offTask: false
    signal clicked()

    readonly property color c: theme.accentOverride !== "" ? theme.accentOverride : (mode.color || "#f0a04b")
    readonly property real remaining: pending ? Math.max(0, pending.deadline_ms - now) : 0
    readonly property real progress: pending && pending.total_ms > 0 ? 1 - remaining / pending.total_ms : 0
    readonly property bool wide: active || pending !== null

    implicitHeight: theme.ipx(40)
    implicitWidth: wide ? content.implicitWidth + theme.px(26) : implicitHeight
    Behavior on implicitWidth { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: pill.active ? pill.c : (pill.pending ? Qt.rgba(1, 1, 1, 0.14) : (ma.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.07)))
        Behavior on color { ColorAnimation { duration: 150 } }

        // countdown fill while a switch is pending
        Rectangle {
            visible: pill.pending !== null
            anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
            width: parent.width * pill.progress
            radius: parent.radius
            color: Qt.rgba(pill.c.r, pill.c.g, pill.c.b, 0.55)
        }
    }

    RowLayout {
        id: content
        anchors.centerIn: parent
        spacing: pill.theme.px(7)
        Text {
            text: pill.mode.icon || "●"
            font.pixelSize: pill.theme.fpx(17)
            font.family: pill.theme.family
            color: pill.active ? "#161616" : "#eaeaea"
            Layout.alignment: Qt.AlignVCenter
        }
        Text {
            visible: pill.wide
            text: pill.pending ? (pill.mode.label + " in " + Math.ceil(pill.remaining / 1000) + "s") : pill.mode.label
            font.pixelSize: pill.theme.fpx(14)
            font.family: pill.theme.family
            font.weight: Font.DemiBold
            color: pill.active ? "#161616" : "#eaeaea"
            Layout.alignment: Qt.AlignVCenter
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pill.clicked()
        ToolTip.visible: containsMouse
        ToolTip.delay: 400
        ToolTip.text: pill.pending ? "press again to shorten the wait" : (pill.mode.description || pill.mode.label)
    }
}
