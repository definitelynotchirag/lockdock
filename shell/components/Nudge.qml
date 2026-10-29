import QtQuick

// Red "off task · reason" bubble shown above the dock. Position it from the parent.
Rectangle {
    id: nudge
    required property string reason

    width: label.implicitWidth + 20; height: 24; radius: 12
    color: Qt.rgba(0.8, 0.2, 0.15, 0.9)
    Text {
        id: label; anchors.centerIn: parent; color: "white"; font.pixelSize: 11
        text: "off task · " + nudge.reason
    }
}
