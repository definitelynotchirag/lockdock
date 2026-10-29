import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "components"

// The dock window. Everything visual comes from st.theme (theme.json) through
// components/Theme.qml. The row is built from theme.sections: each id is looked
// up in `sectionMap` below. To add a feature's component (Pet, AgentStrip, ...):
//   1. add a Component for it under "section components",
//   2. add one entry to `sectionMap`.
// A section component may expose `readonly property bool active` (default true)
// to say whether it has anything to show; hidden sections get no divider.
PanelWindow {
    id: dock
    required property var shell
    readonly property var st: shell.state
    readonly property var theme: Theme { st: dock.st }
    readonly property var activeMode: (st.modes || []).find(m => m.id === st.mode) || { id: "", label: "", icon: "", color: "#888", apps: [] }
    readonly property bool offTask: (st.activity || {}).verdict === "off"
    readonly property bool nudgeShown: offTask && theme.nudge
    readonly property color accent: theme.accentOverride !== "" ? theme.accentOverride : (activeMode.color || "#f0a04b")

    // section id -> component. Unknown ids in theme.sections are skipped.
    readonly property var sectionMap: ({
        modes: modeStripComp,
        apps: appStripComp,
        held: heldBadgeComp,
    })
    // sections drawn right after their neighbour with no divider (like the held badge)
    readonly property var inlineSections: ({ held: true })

    anchors.bottom: !theme.atTop
    anchors.top: theme.atTop
    exclusiveZone: theme.autohide ? -1 : 0   // autohide: sit at the physical edge so the reveal strip is reachable
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "lockdock"
    implicitWidth: card.implicitWidth + 24
    implicitHeight: card.implicitHeight + theme.margin + theme.px(12 + 34)   // card, gap to the edge, headroom for the nudge
    mask: Region { item: cardHit; Region { item: nudgeBox } Region { item: edge } }

    // countdown clock
    property real now: Date.now()
    Timer { interval: 100; repeat: true; running: dock.st.pending !== null && dock.st.pending !== undefined; onTriggered: dock.now = Date.now() }

    // ---- autohide ----
    property bool shown: true
    readonly property bool busy: (st.pending !== null && st.pending !== undefined) || nudgeShown || (st.held_count || 0) > 0
    readonly property bool wantShown: !theme.autohide || cardHover.hovered || edgeHover.hovered || busy
    onWantShownChanged: { if (wantShown) { hideTimer.stop(); shown = true } else hideTimer.restart() }
    Component.onCompleted: if (!wantShown) hideTimer.start()
    Timer { id: hideTimer; interval: dock.theme.hideDelayMs; onTriggered: dock.shown = false }

    // thin strip at the screen edge that reveals a hidden dock (also bridges the margin while shown)
    Item {
        id: edge
        anchors.horizontalCenter: parent.horizontalCenter
        width: card.width
        height: dock.theme.autohide ? (dock.shown ? Math.max(dock.theme.revealPx, dock.theme.margin) : dock.theme.revealPx) : 0
        y: dock.theme.atTop ? 0 : dock.height - height
        HoverHandler { id: edgeHover }
    }

    // input region of the card: none while it is slid away
    Item {
        id: cardHit
        x: card.x; y: card.y; width: card.width
        height: dock.shown ? card.height : 0
    }

    Rectangle {
        id: card
        anchors.horizontalCenter: parent.horizontalCenter
        y: dock.theme.atTop ? dock.theme.margin : dock.height - height - dock.theme.margin
        implicitWidth: row.implicitWidth + dock.theme.px(20)
        implicitHeight: dock.theme.ipx(64)
        radius: dock.theme.px(dock.theme.radius)
        color: dock.theme.background
        opacity: dock.theme.opacity
        border.width: dock.theme.borderWidth
        border.color: dock.offTask ? dock.theme.offTaskBorderColor : dock.theme.borderColor
        Behavior on border.color { ColorAnimation { duration: 250 } }
        HoverHandler { id: cardHover }

        transform: Translate {
            y: dock.shown ? 0 : (dock.theme.atTop ? -1 : 1) * (card.height + dock.theme.margin + 4)
            Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        }

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: dock.theme.px(6)

            Repeater {
                model: dock.theme.sections
                delegate: RowLayout {
                    id: sec
                    required property string modelData
                    required property int index
                    readonly property bool shown: loader.item ? (loader.item.active !== undefined ? loader.item.active : true) : false
                    readonly property bool inlineSection: dock.inlineSections[modelData] === true
                    visible: shown
                    spacing: dock.theme.px(6)
                    Layout.leftMargin: inlineSection ? dock.theme.px(6) : 0

                    onShownChanged: dock.markShown(modelData, shown)
                    Component.onCompleted: dock.markShown(modelData, shown)
                    Component.onDestruction: dock.markShown(modelData, false)

                    Rectangle {
                        visible: sec.shown && !sec.inlineSection
                                 && dock.theme.sections.slice(0, sec.index).some(id => dock.shownSections[id] === true)
                        implicitWidth: 1; implicitHeight: dock.theme.px(36)
                        color: Qt.rgba(1, 1, 1, 0.14)
                        Layout.leftMargin: dock.theme.px(4); Layout.rightMargin: dock.theme.px(4)
                    }
                    Loader {
                        id: loader
                        sourceComponent: dock.sectionMap[sec.modelData]
                    }
                }
            }
        }
    }

    // which section ids currently have something to show (drives the dividers)
    property var shownSections: ({})
    function markShown(id, v) {
        if (dock.shownSections[id] === v) return
        const next = Object.assign({}, dock.shownSections)
        next[id] = v
        dock.shownSections = next
    }

    // ---- section components ----
    Component {
        id: modeStripComp
        ModeStrip {
            st: dock.st
            now: dock.now
            offTask: dock.offTask
            theme: dock.theme
            onModeClicked: modeId => dock.shell.send(["mode", modeId])
        }
    }
    Component {
        id: appStripComp
        AppStrip {
            activeMode: dock.activeMode
            accent: dock.accent
            theme: dock.theme
        }
    }
    Component {
        id: heldBadgeComp
        HeldBadge {
            st: dock.st
            accent: dock.accent
            theme: dock.theme
            onReleaseClicked: dock.shell.send(["release"])
        }
    }

    // off-task nudge next to the dock (above it at the bottom, below it at the top)
    Nudge {
        id: nudgeBox
        visible: dock.nudgeShown
        theme: dock.theme
        opacity: dock.theme.opacity
        y: dock.theme.atTop ? card.y + card.height + dock.theme.px(6) : card.y - height - dock.theme.px(6)
        anchors.horizontalCenter: card.horizontalCenter
        reason: (dock.st.activity || {}).reason || ""
    }
}
