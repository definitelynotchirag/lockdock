import QtQuick

// Red "off task · reason" bubble shown above the dock. Position it from the parent.
Rectangle {
    id: nudge
    required property string reason
    required property var theme

    width: label.implicitWidth + theme.px(20); height: theme.px(24); radius: height / 2
    color: Qt.rgba(0.8, 0.2, 0.15, 0.9)
    Text {
        id: label; anchors.centerIn: parent; color: "white"
        font.pixelSize: nudge.theme.fpx(11)
        font.family: nudge.theme.family
        text: "off task · " + nudge.reason
    }
}
