import QtQuick
import QtQuick.Controls

// Bell with the number of held notifications; click releases them.
Rectangle {
    id: badgeRoot
    required property var st          // state.json
    required property color accent
    signal releaseClicked()

    visible: (st.held_count || 0) > 0
    width: 34; height: 34; radius: 17
    color: Qt.rgba(1, 1, 1, 0.08)
    Text { anchors.centerIn: parent; text: "🔕"; font.pixelSize: 15 }
    Rectangle {
        anchors.top: parent.top; anchors.right: parent.right
        anchors.topMargin: -3; anchors.rightMargin: -3
        height: 16; width: Math.max(16, count.implicitWidth + 8); radius: 8
        color: badgeRoot.accent
        Text { id: count; anchors.centerIn: parent; text: badgeRoot.st.held_count; color: "#111"; font.pixelSize: 10; font.bold: true }
    }
    MouseArea {
        anchors.fill: parent; hoverEnabled: true
        onClicked: badgeRoot.releaseClicked()
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: ((badgeRoot.st.held || []).slice(-6).map(n => n.app + ": " + n.summary).join("\n") || "") + "\n\nclick to release"
    }
}
