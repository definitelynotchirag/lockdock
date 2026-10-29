import QtQuick
import Quickshell
import Quickshell.Wayland

// The grown pet: a full-screen, click-through overlay (empty input mask, no keyboard
// focus) that shows the pet at st.pet.scale x its sprite size, capped at
// max_screen_fraction of the screen, standing just above the dock. Shown only
// while scale > 1.05; it animates back down before hiding.
PanelWindow {
    id: overlay
    required property var st
    readonly property var info: st.pet || {}
    readonly property real base: info.size || 48
    readonly property real cap: (info.max_screen_fraction || 0.9) * (screen ? screen.height : 1080)
    readonly property bool grown: (info.scale || 1) > 1.05 && !!info.pack_dir
    readonly property real target: grown ? Math.min(cap, (info.scale || 1) * base) : base

    visible: grown || sprite.height > base + 1
    anchors.bottom: true
    anchors.left: true
    anchors.right: true
    implicitHeight: screen ? screen.height : 1080
    exclusiveZone: 0
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "lockdock-pet"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}   // empty input region: every click goes to the window underneath

    PetSprite {
        id: sprite
        pet: overlay.info
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 84     // just above the dock
        height: overlay.target
        width: height
        Behavior on height { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
    }

    // big speech bubble beside the pet's head
    Item {
        id: bubble
        visible: overlay.grown && !!overlay.info.line
        width: Math.min(overlay.width * 0.4, label.implicitWidth + 44)
        height: label.implicitHeight + 28 + 16
        x: Math.min(overlay.width - width - 24, sprite.x + sprite.width * 0.82)
        y: Math.max(24, sprite.y + sprite.height * 0.3 - height)

        Rectangle {
            id: bubbleRect
            width: parent.width
            height: parent.height - 16
            radius: 22
            color: "#fbf7ff"
            border.width: 3
            border.color: "#3a2e3f"
        }
        // tail toward the pet
        Rectangle {
            width: 22; height: 22
            rotation: 45
            x: 26; y: bubbleRect.height - 13
            color: bubbleRect.color
            border.width: 3
            border.color: "#3a2e3f"
            z: -1
        }
        Text {
            id: label
            x: 22; y: 14
            width: Math.min(overlay.width * 0.4 - 44, implicitWidth)
            text: overlay.info.line || ""
            wrapMode: Text.Wrap
            color: "#3a2e3f"
            font.pixelSize: Math.max(20, Math.min(40, sprite.height / 14))
            font.weight: Font.Black
        }
    }
}
