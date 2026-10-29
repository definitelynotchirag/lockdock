import QtQuick

// Section "pin" (not in the default sections): pins or unpins the dock (theme `pinned`; click
// sends `lockdock pin toggle`). Pinned: the filled icons.pin on the accent container (windows
// stop at the dock); unpinned: the outline icons.pin_off, muted.
Pressable {
    id: btn
    required property var st          // state.json
    required property var shell       // for shell.send([...])
    readonly property bool pinned: theme.pinned

    implicitWidth: theme.ipx(40); implicitHeight: theme.ipx(40)
    scale: pressScale
    tip: pinned ? { icon: theme.icon("pin", "icona:map-pin-fill"), title: "Pinned · windows stop at the dock", detail: "click to unpin" }
                : { icon: theme.icon("pin_off", "icona:map-pin"), title: "Click to pin the dock", detail: "windows then stop at it instead of covering it" }
    onClicked: shell.send(["pin", "toggle"])

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: btn.pinned ? btn.theme.accentContainer : btn.theme.alpha(btn.theme.surfaceHover, 0.6 + 0.4 * btn.hoverProgress)
    }
    Icon {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: btn.lift(1.5)
        name: btn.pinned ? btn.theme.icon("pin", "icona:map-pin-fill") : btn.theme.icon("pin_off", "icona:map-pin")
        size: btn.theme.fpx(18)
        stroke: btn.theme.iconStroke
        family: btn.theme.family
        color: btn.pinned ? btn.theme.accentContainerInk : btn.theme.text
        opacity: btn.pinned ? 1 : 0.85 + 0.15 * btn.hoverProgress
    }
}
