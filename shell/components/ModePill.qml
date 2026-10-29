import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One mode. Active: a filled pill (accent_container, or the mode's own colour when modes.json
// sets one) with a small accent dot, icon (Icon.qml: icona:<slug> or a glyph) and label.
// Inactive: the icon only, muted; a
// pending switch widens it and fills it left to right as the countdown runs.
Item {
    id: pill
    required property var theme
    property var mode
    property bool active: false
    property var pending: null      // {mode, deadline_ms, total_ms} or null
    property real now: 0
    property bool offTask: false
    signal clicked()

    readonly property bool auto: theme.modeIsAuto(mode)
    readonly property color c: theme.modeColor(mode)
    // active fill and its text: Material container roles for "auto", else the mode's colour
    readonly property color fill: auto ? theme.accentContainer : c
    readonly property color ink: auto ? theme.accentContainerInk : theme.readableOn(c)
    readonly property color dotColor: auto ? theme.paletteAccent : ink
    readonly property real remaining: pending ? Math.max(0, pending.deadline_ms - now) : 0
    readonly property real progress: pending && pending.total_ms > 0 ? 1 - remaining / pending.total_ms : 0
    readonly property bool wide: active || pending !== null

    implicitHeight: theme.ipx(40)
    implicitWidth: wide ? content.implicitWidth + theme.px(30) : implicitHeight
    Behavior on implicitWidth { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: pill.active ? pill.fill
                           : (pill.pending || ma.containsMouse ? pill.theme.surfaceHover : "transparent")
        Behavior on color { ColorAnimation { duration: 150 } }

        // countdown fill while a switch is pending
        Rectangle {
            visible: pill.pending !== null
            anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
            width: Math.max(height, parent.width * pill.progress)
            radius: parent.radius
            color: pill.theme.alpha(pill.c, 0.35)
        }
    }

    RowLayout {
        id: content
        anchors.centerIn: parent
        spacing: pill.theme.px(7)
        Rectangle {
            visible: pill.active
            implicitWidth: pill.theme.px(6); implicitHeight: implicitWidth; radius: implicitWidth / 2
            color: pill.dotColor
            Layout.alignment: Qt.AlignVCenter
            Layout.rightMargin: pill.theme.px(1)
        }
        Icon {
            name: pill.theme.modeIcon(pill.mode)
            size: pill.theme.fpx(18)
            stroke: pill.theme.iconStroke
            family: pill.theme.family
            color: pill.active ? pill.ink : (ma.containsMouse || pill.pending ? pill.theme.text : pill.theme.textMuted)
            Layout.alignment: Qt.AlignVCenter
        }
        Text {
            visible: pill.wide
            text: pill.pending ? (pill.mode.label + " in " + Math.ceil(pill.remaining / 1000) + "s") : pill.mode.label
            font.pixelSize: pill.theme.fpx(14)
            font.family: pill.theme.family
            font.weight: Font.DemiBold
            font.letterSpacing: 0.2
            color: pill.active ? pill.ink : pill.theme.text
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
