import QtQuick

// Bell (theme icons.held / held_muted) with the number of held notifications; click releases them.
Pressable {
    id: badgeRoot
    required property var st          // state.json
    required property color accent
    signal releaseClicked()

    // sections report whether they have anything to show through `active` (see Dock.qml)
    readonly property bool active: (st.held_count || 0) > 0
    readonly property int heldCount: st.held_count || 0
    visible: active
    implicitWidth: theme.ipx(40); implicitHeight: theme.ipx(40)
    scale: pressScale
    // icons.held, or icons.held_muted while the active mode holds every notification
    readonly property bool muted: ((st.modes || []).find(m => m.id === st.mode) || {}).notifications === "hold"
    readonly property string glyph: muted ? theme.icon("held_muted", "icona:snooze") : theme.icon("held", "icona:bell")
    // the newest held one names itself in the tip
    readonly property var newest: (st.held || []).length ? st.held[st.held.length - 1] : null
    tip: ({
        icon: glyph,
        title: heldCount + (heldCount === 1 ? " held notification" : " held notifications"),
        detail: "click to release" + (newest && newest.app ? " · latest from " + newest.app : "")
    })
    onClicked: releaseClicked()

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: badgeRoot.theme.alpha(badgeRoot.theme.surfaceHover, 0.6 + 0.4 * badgeRoot.hoverProgress)
    }
    Icon {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: badgeRoot.lift(1.5)
        name: badgeRoot.glyph
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
            id: count; anchors.centerIn: parent; text: badgeRoot.heldCount
            color: badgeRoot.theme.readableOn(badgeRoot.accent)
            font.pixelSize: badgeRoot.theme.fpx(10); font.bold: true
            font.family: badgeRoot.theme.family
        }
    }
}
