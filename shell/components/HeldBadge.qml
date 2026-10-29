import QtQuick
import QtQuick.Controls

// Bell (theme icons.held / held_muted) with the number of held notifications; click releases them.
Rectangle {
    id: badgeRoot
    required property var st          // state.json
    required property color accent
    required property var theme
    signal releaseClicked()

    // sections report whether they have anything to show through `active` (see Dock.qml)
    readonly property bool active: (st.held_count || 0) > 0
    visible: active
    implicitWidth: theme.ipx(40); implicitHeight: theme.ipx(40); radius: height / 2
    color: ma.containsMouse ? theme.surfaceHover : theme.alpha(theme.surfaceHover, 0.6)
    // icons.held, or icons.held_muted while the active mode holds every notification
    readonly property bool muted: ((st.modes || []).find(m => m.id === st.mode) || {}).notifications === "hold"
    Icon {
        anchors.centerIn: parent
        name: badgeRoot.muted ? badgeRoot.theme.icon("held_muted", "icona:snooze") : badgeRoot.theme.icon("held", "icona:bell")
        size: badgeRoot.theme.fpx(18)
        stroke: badgeRoot.theme.iconStroke
        family: badgeRoot.theme.family
        color: badgeRoot.theme.text
    }
    Rectangle {
        anchors.top: parent.top; anchors.right: parent.right
        anchors.topMargin: -badgeRoot.theme.px(3); anchors.rightMargin: -badgeRoot.theme.px(3)
        height: badgeRoot.theme.px(16); width: Math.max(height, count.implicitWidth + badgeRoot.theme.px(8)); radius: height / 2
        color: badgeRoot.accent
        border.width: badgeRoot.theme.px(2)
        border.color: badgeRoot.theme.bg
        Text {
            id: count; anchors.centerIn: parent; text: badgeRoot.st.held_count
            color: badgeRoot.theme.readableOn(badgeRoot.accent)
            font.pixelSize: badgeRoot.theme.fpx(10); font.bold: true
            font.family: badgeRoot.theme.family
        }
    }
    MouseArea {
        id: ma
        anchors.fill: parent; hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: badgeRoot.releaseClicked()
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: ((badgeRoot.st.held || []).slice(-6).map(n => n.app + ": " + n.summary).join("\n") || "") + "\n\nclick to release"
    }
}
