import QtQuick
import QtQuick.Controls

// The mascot in the dock: its mood sprite, plus a speech bubble that pops up when
// st.pet.line changes and hides after 6 s. Click to calm it. The Dock adds `bubble`
// to its input mask and grows its headroom by `headroom` while the bubble shows.
Item {
    id: pet
    required property var st           // state.json
    required property var shell        // for shell.send
    property bool shown: true          // the Dock hides the copy that is not in the configured position
    property real bubbleLift: 14       // gap between the pet's top and the bubble's bottom
    property bool bubbleLeftward: false // grow the bubble to the left (pet at the right end of the dock)
    readonly property var info: st.pet || {}
    readonly property Item bubble: bubbleBox
    readonly property bool bubbleShown: bubbleBox.visible
    readonly property real headroom: bubbleShown ? bubbleBox.height + bubbleLift : 0
    readonly property bool active: shown && !!info.pack_dir

    visible: shown && !!info.pack_dir
    implicitWidth: 44
    implicitHeight: 44

    PetSprite {
        anchors.fill: parent
        pet: pet.info
        renderSize: 44
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
        width: Math.min(260, label.implicitWidth + 20)
        height: label.implicitHeight + 12 + 6
        x: pet.bubbleLeftward ? pet.width + 6 - width : -6
        y: -(height + pet.bubbleLift)

        Rectangle {
            id: bubbleRect
            width: parent.width
            height: parent.height - 6
            radius: 12
            color: "#fbf7ff"
            border.width: 1
            border.color: Qt.rgba(0.23, 0.18, 0.25, 0.35)
        }
        // little tail pointing down at the pet
        Rectangle {
            width: 10; height: 10
            rotation: 45
            color: bubbleRect.color
            x: pet.width / 2 - bubbleBox.x - 5
            y: bubbleRect.height - 6
        }
        Text {
            id: label
            x: 10; y: 6
            width: Math.min(240, implicitWidth)
            text: pet.info.line || ""
            wrapMode: Text.Wrap
            color: "#3a2e3f"
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
        scale: visible ? 1 : 0.6
        transformOrigin: pet.bubbleLeftward ? Item.BottomRight : Item.BottomLeft
        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack } }
    }
}
