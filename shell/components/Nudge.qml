import QtQuick

// The "off task · reason" bubble shown next to the dock, in the danger role, styled like an
// island. Position it from the parent.
Item {
    id: nudge
    required property string reason
    required property var theme

    width: label.implicitWidth + theme.px(28); height: theme.px(30)

    Island {
        anchors.fill: parent
        theme: nudge.theme
        fill: nudge.theme.danger
        stroke: nudge.theme.alpha(nudge.theme.dangerInk, 0.15)
        radius: height / 2
    }
    Text {
        id: label; anchors.centerIn: parent; color: nudge.theme.dangerInk
        font.pixelSize: nudge.theme.fpx(12)
        font.family: nudge.theme.family
        font.weight: Font.DemiBold
        text: "off task · " + nudge.reason
    }
}
