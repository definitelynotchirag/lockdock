import QtQuick
import QtQuick.Effects

// A rounded surface with a hairline border and a soft drop shadow (theme.shadow). Fill it
// with `anchors.fill: parent` behind a section's content; the dock's islands, the slab
// card and the nudge all use it.
Item {
    id: island
    required property var theme
    property bool alert: false        // off task: the border turns to the danger role
    property color fill: theme.background
    property color stroke: alert ? theme.offTaskBorderColor : theme.borderColor
    property real radius: theme.px(theme.radius)

    Rectangle {
        id: shape
        anchors.fill: parent
        radius: island.radius
        color: island.fill
        border.width: island.theme.borderWidth
        border.color: island.stroke
        Behavior on border.color { ColorAnimation { duration: 250 } }
        Behavior on color { ColorAnimation { duration: 300 } }

        layer.enabled: island.theme.shadow
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: island.theme.alpha(island.theme.shadowColor, island.theme.shadowOpacity)
            shadowBlur: 0.9
            blurMax: 24
            shadowVerticalOffset: island.theme.px(3)
            autoPaddingEnabled: true
        }
    }
}
