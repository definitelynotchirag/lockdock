import QtQuick

// The dock's one interaction language. Use it as the root of a button (or a pill) and draw
// with its progress values instead of a MouseArea's raw flags:
//   hoverProgress  0..1, 180 ms OutCubic in, 240 ms out: fade in a surface_hover background,
//                  lift the icon (lift(px)), brighten dimmed content
//   pressProgress  0..1, 80 ms in, 160 ms OutBack out: pressScale (0.96 while held) springs back
// `tip` ({icon, title, detail}) is shown by the Dock's single Tip (theme.host) after the hover
// delay; it hides on press and stays hidden until the pointer leaves and comes back.
// theme.reduced_motion makes every duration 0. Debug: set `forceHover` / `forcePress`.
Item {
    id: root
    required property var theme
    property var tip: null             // {icon, title, detail}; null or no title = no tooltip
    property bool tipEnabled: true
    property bool forceHover: false
    property bool forcePress: false
    signal clicked()

    readonly property bool hovered: ma.containsMouse || forceHover
    readonly property bool pressed: ma.pressed || forcePress
    property real hoverProgress: 0
    property real pressProgress: 0
    readonly property real pressScale: 1 - 0.04 * pressProgress
    // the icon's hover lift: translate y by -px * hoverProgress
    function lift(px) { return -px * root.theme.scale * hoverProgress }

    NumberAnimation { id: hoverAnim; target: root; property: "hoverProgress" }
    NumberAnimation { id: pressAnim; target: root; property: "pressProgress" }
    function animate(anim, to, ms, easing) {
        anim.stop()
        const d = root.theme.dur(ms)
        if (d <= 0) { root[anim.property] = to; return }
        anim.to = to
        anim.duration = d
        anim.easing.type = easing
        anim.start()
    }
    onHoveredChanged: {
        animate(hoverAnim, hovered ? 1 : 0, hovered ? 180 : 240, Easing.OutCubic)
        if (!hovered) tipSuppressed = false
        syncTip()
    }
    onPressedChanged: {
        animate(pressAnim, pressed ? 1 : 0, pressed ? 80 : 160, pressed ? Easing.OutCubic : Easing.OutBack)
        if (pressed) tipSuppressed = true
        syncTip()
    }

    // ---- tooltip ----
    property bool tipSuppressed: false
    function syncTip() {
        const host = root.theme.host
        if (!host) return
        if (root.hovered && root.visible && root.tipEnabled && !root.tipSuppressed && root.tip && root.tip.title)
            host.showTip(root, root.tip)
        else
            host.hideTip(root)
    }
    onTipChanged: if (hovered) syncTip()
    onTipEnabledChanged: syncTip()
    onVisibleChanged: syncTip()
    Component.onDestruction: if (root.theme.host) root.theme.host.hideTip(root)

    MouseArea {
        id: ma
        anchors.fill: parent
        z: 100
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
