import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "components"

// The dock window. Lays out the components in one row; add a feature by
// dropping a component into components/ and placing it in `row` below.
PanelWindow {
    id: dock
    required property var shell
    readonly property var st: shell.state
    readonly property var activeMode: (st.modes || []).find(m => m.id === st.mode) || { id: "", label: "", icon: "", color: "#888", apps: [] }
    readonly property bool offTask: (st.activity || {}).verdict === "off"
    readonly property color accent: activeMode.color || "#f0a04b"
    readonly property bool petRight: (st.pet || {}).position === "right"
    readonly property var pet: petRight ? petRightLoader.item : petLeft
    // the pet sits 10 px below the card's top; its bubble clears the nudge row when off task
    readonly property real petLift: offTask ? 42 : 8

    anchors.bottom: true
    margins.bottom: 10
    exclusiveZone: 0
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "lockdock"
    implicitWidth: card.implicitWidth + 24
    // headroom for the nudge, more while the pet's speech bubble shows
    implicitHeight: card.implicitHeight + Math.max(12 + 34, (pet ? pet.headroom : 0) - 10 + 6)
    mask: Region {
        item: card
        Region { item: nudgeBox }
        Region { item: dock.pet && dock.pet.bubbleShown ? dock.pet.bubble : null }
    }

    // countdown clock
    property real now: Date.now()
    Timer { interval: 100; repeat: true; running: dock.st.pending !== null && dock.st.pending !== undefined; onTriggered: dock.now = Date.now() }

    Rectangle {
        id: card
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        implicitWidth: row.implicitWidth + 20
        implicitHeight: 64
        radius: 22
        color: Qt.rgba(0.11, 0.11, 0.13, 0.86)
        border.width: 1
        border.color: dock.offTask ? Qt.rgba(1, 0.35, 0.3, 0.8) : Qt.rgba(1, 1, 1, 0.12)
        Behavior on border.color { ColorAnimation { duration: 250 } }

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 6

            Pet { id: petLeft; st: dock.st; shell: dock.shell; shown: !dock.petRight; bubbleLift: dock.petLift; Layout.rightMargin: 2 }

            ModeStrip {
                st: dock.st
                now: dock.now
                offTask: dock.offTask
                onModeClicked: modeId => dock.shell.send(["mode", modeId])
            }

            Rectangle { width: 1; height: 36; color: Qt.rgba(1, 1, 1, 0.14); Layout.leftMargin: 4; Layout.rightMargin: 4 }

            AppStrip {
                activeMode: dock.activeMode
                accent: dock.accent
            }

            HeldBadge {
                Layout.leftMargin: 6
                st: dock.st
                accent: dock.accent
                onReleaseClicked: dock.shell.send(["release"])
            }

            // the pet again when pet.json says "position": "right"
            Loader {
                id: petRightLoader
                active: dock.petRight
                visible: active
                sourceComponent: Pet { st: dock.st; shell: dock.shell; bubbleLift: dock.petLift; bubbleLeftward: true }
            }
        }
    }

    // off-task nudge above the dock
    Nudge {
        id: nudgeBox
        visible: dock.offTask
        anchors.bottom: card.top
        anchors.bottomMargin: 6
        anchors.horizontalCenter: card.horizontalCenter
        reason: (dock.st.activity || {}).reason || ""
    }
}
