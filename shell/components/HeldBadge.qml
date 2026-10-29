import QtQuick
import QtQuick.Controls

// Bell with the number of held notifications; click releases them.
Rectangle {
    id: badgeRoot
    required property var st          // state.json
    required property color accent
    required property var theme
    signal releaseClicked()

    // sections report whether they have anything to show through `active` (see Dock.qml)
    readonly property bool active: (st.held_count || 0) > 0
    visible: active
    implicitWidth: theme.px(34); implicitHeight: theme.px(34); radius: height / 2
    color: Qt.rgba(1, 1, 1, 0.08)
    Text { anchors.centerIn: parent; text: "🔕"; font.pixelSize: badgeRoot.theme.fpx(15) }
    Rectangle {
        anchors.top: parent.top; anchors.right: parent.right
        anchors.topMargin: -badgeRoot.theme.px(3); anchors.rightMargin: -badgeRoot.theme.px(3)
        height: badgeRoot.theme.px(16); width: Math.max(height, count.implicitWidth + badgeRoot.theme.px(8)); radius: height / 2
        color: badgeRoot.accent
        Text {
            id: count; anchors.centerIn: parent; text: badgeRoot.st.held_count; color: "#111"
            font.pixelSize: badgeRoot.theme.fpx(10); font.bold: true
            font.family: badgeRoot.theme.family
        }
    }
    MouseArea {
        anchors.fill: parent; hoverEnabled: true
        onClicked: badgeRoot.releaseClicked()
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: ((badgeRoot.st.held || []).slice(-6).map(n => n.app + ": " + n.summary).join("\n") || "") + "\n\nclick to release"
    }
}
