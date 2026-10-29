import QtQuick
import QtQuick.Controls

// The mascot in the dock: its mood sprite, plus a speech bubble that pops up when
// st.pet.line changes and hides after 6 s. Click to calm it. The Dock adds `bubble`
// to its input mask and grows its headroom by `headroom` while the bubble shows.
Item {
    id: pet
    required property var st           // state.json
    required property var shell        // for shell.send
    required property var theme        // components/Theme.qml (bubble colours, sizes)
    property bool shown: true          // the Dock hides the copy that is not in the configured position
    property real bubbleLift: 14       // gap between the pet's top and the bubble's bottom
    property bool bubbleLeftward: false // grow the bubble to the left (pet at the right end of the dock)
    property bool bubbleBelow: false    // dock at the top: the bubble hangs below the pet
    readonly property var info: st.pet || {}
    readonly property Item bubble: bubbleBox
    readonly property bool bubbleShown: bubbleBox.visible
    readonly property real headroom: bubbleShown ? bubbleBox.height + bubbleLift : 0
    readonly property bool active: shown && !!info.pack_dir

    visible: shown && !!info.pack_dir
    implicitWidth: theme.ipx(40)
    implicitHeight: theme.ipx(40)

    PetSprite {
        anchors.fill: parent
        pet: pet.info
        renderSize: pet.theme.ipx(40)
        scale: ma.pressed ? 0.9 : (ma.containsMouse ? 1.08 : 1)
        Behavior on scale { NumberAnimation { duration: 120 } }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pet.shell.send(["pet", "calm"])
        ToolTip.visible: containsMouse
        ToolTip.delay: 500
        ToolTip.text: (pet.info.name || "pet") + " is " + (pet.info.mood || "content")
                      + (pet.info.off_seconds ? " · " + pet.info.off_seconds + "s off task" : "") + "\nclick to calm"
    }

    // ---- speech bubble: pops when the line changes ----
    property bool talking: false
    readonly property string lineKey: (info.line_id || 0) + "|" + (info.line || "")
    onLineKeyChanged: {
        talking = !!info.line
        if (talking) hideTimer.restart()
    }
    Timer { id: hideTimer; interval: 6000; onTriggered: pet.talking = false }

    Item {
        id: bubbleBox
        // the full-screen overlay shows its own big bubble while the pet is grown
        visible: pet.visible && pet.talking && !!pet.info.line && (pet.info.scale || 1) <= 1.05
        width: Math.min(pet.theme.px(260), label.implicitWidth + pet.theme.px(24))
        height: label.implicitHeight + pet.theme.px(14) + 6
        x: pet.bubbleLeftward ? pet.width + 6 - width : -6
        y: pet.bubbleBelow ? pet.height + pet.bubbleLift : -(height + pet.bubbleLift)

        Rectangle {
            id: bubbleRect
            width: parent.width
            height: parent.height - 6
            y: pet.bubbleBelow ? 6 : 0
            radius: pet.theme.px(14)
            color: pet.theme.bubble
            border.width: 1
            border.color: pet.theme.alpha(pet.theme.bubbleText, 0.18)
        }
        // little tail pointing at the pet
        Rectangle {
            width: 10; height: 10
            rotation: 45
            color: bubbleRect.color
            x: pet.width / 2 - bubbleBox.x - 5
            y: pet.bubbleBelow ? 1 : bubbleRect.height - 6
        }
        Text {
            id: label
            x: pet.theme.px(12); y: bubbleRect.y + pet.theme.px(7)
            width: Math.min(pet.theme.px(236), implicitWidth)
            text: pet.info.line || ""
            wrapMode: Text.Wrap
            color: pet.theme.bubbleText
            font.pixelSize: pet.theme.fpx(12)
            font.family: pet.theme.family
            font.weight: Font.DemiBold
        }
        scale: visible ? 1 : 0.6
        transformOrigin: pet.bubbleBelow ? (pet.bubbleLeftward ? Item.TopRight : Item.TopLeft)
                                         : (pet.bubbleLeftward ? Item.BottomRight : Item.BottomLeft)
        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack } }
    }
}
