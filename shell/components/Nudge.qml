import QtQuick

// The "off task · reason" bubble shown next to the dock, in the danger role, styled like an
// island. Position it from the parent.
Item {
    id: nudge
    required property string reason
    required property var theme

    width: row.implicitWidth + theme.px(28); height: theme.px(30)

    Island {
        anchors.fill: parent
        theme: nudge.theme
        fill: nudge.theme.danger
        stroke: nudge.theme.alpha(nudge.theme.dangerInk, 0.15)
        radius: height / 2
    }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: nudge.theme.px(6)
        Icon {
            visible: name !== ""
            anchors.verticalCenter: parent.verticalCenter
            name: nudge.theme.icon("nudge", "icona:alert")
            size: nudge.theme.fpx(15)
            stroke: nudge.theme.iconStroke
            family: nudge.theme.family
            color: nudge.theme.dangerInk
        }
        Text {
            id: label; anchors.verticalCenter: parent.verticalCenter; color: nudge.theme.dangerInk
            font.pixelSize: nudge.theme.fpx(12)
            font.family: nudge.theme.family
            font.weight: Font.DemiBold
            text: "off task · " + nudge.reason
        }
    }
}
