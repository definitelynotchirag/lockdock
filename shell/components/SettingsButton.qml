import QtQuick

// Section "settings" (in the default sections, last): the gear that opens the quick settings
// panel (components/QuickSettings.qml). The Dock (theme.host) owns the one panel per window:
// hovering the gear opens it after the tooltip delay (host.hoverSettings), a click toggles it
// (host.toggleSettings). icons.settings on a soft pill (the accent container while the panel is
// open); a small accent dot while the dock is pinned. Its tooltip hides while the panel shows.
Pressable {
    id: btn
    required property var st          // state.json
    readonly property bool pinned: theme.pinned
    readonly property bool open: theme.host ? theme.host.settingsOpen === true && theme.host.settingsTarget === btn : false

    implicitWidth: theme.ipx(40); implicitHeight: theme.ipx(40)
    scale: pressScale
    tip: ({ icon: theme.icon("settings", "icona:settings"), title: "Quick settings · click or hover",
            detail: pinned ? "the dock is pinned" : "" })
    tipEnabled: !open
    onClicked: if (theme.host && theme.host.toggleSettings) theme.host.toggleSettings(btn)

    Connections {
        target: btn
        function onHoveredChanged() { if (btn.theme.host && btn.theme.host.hoverSettings) btn.theme.host.hoverSettings(btn, btn.hovered) }
        function onVisibleChanged() { if (!btn.visible && btn.theme.host && btn.theme.host.hoverSettings) btn.theme.host.hoverSettings(btn, false) }
    }
    Component.onDestruction: if (btn.theme.host && btn.theme.host.closeSettings) btn.theme.host.closeSettings(btn)

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: btn.open ? btn.theme.accentContainer : btn.theme.alpha(btn.theme.surfaceHover, 0.6 + 0.4 * btn.hoverProgress)
    }
    Icon {
        anchors.centerIn: parent
        name: btn.theme.icon("settings", "icona:settings")
        size: btn.theme.fpx(18)
        stroke: btn.theme.iconStroke
        family: btn.theme.family
        color: btn.open ? btn.theme.accentContainerInk : btn.theme.text
        opacity: btn.open ? 1 : 0.85 + 0.15 * btn.hoverProgress
    }
    // pinned: a small accent dot on the top-right
    Rectangle {
        visible: btn.pinned
        readonly property real s: btn.theme.px(10)
        width: s; height: s; radius: s / 2
        x: btn.width - s - btn.theme.px(2); y: btn.theme.px(2)
        color: btn.theme.paletteAccent
        border.width: btn.theme.px(1.5)
        border.color: btn.theme.background
    }
}
