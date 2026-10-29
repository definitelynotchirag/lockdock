import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "components"

// The dock window. Everything visual comes from st.theme (theme.json + the desktop
// palette) through components/Theme.qml. The row is built from theme.sections: each id
// is looked up in `sectionMap` below. To add a feature's component (Pet, AgentStrip, ...):
//   1. add a Component for it under "section components",
//   2. add one entry to `sectionMap`.
// A section component may expose `readonly property bool active` (default true)
// to say whether it has anything to show; hidden sections get no divider / island.
//
// layout "islands" (default): sections are grouped (`groups`) and each group is drawn
// on its own Island; the pet shares the island of the section next to it.
// layout "slab": one Island (the card) holds every section, with dividers between them.
PanelWindow {
    id: dock
    required property var shell
    readonly property var st: shell.state
    readonly property var theme: Theme { st: dock.st }
    readonly property var activeMode: (st.modes || []).find(m => m.id === st.mode) || { id: "", label: "", icon: "", color: "auto", apps: [] }
    readonly property bool offTask: (st.activity || {}).verdict === "off"
    readonly property bool nudgeShown: offTask && theme.nudge
    readonly property color accent: theme.modeColor(activeMode)
    // the pet registers itself here when its section is loaded (see components/Pet.qml)
    property Item petItem: null
    readonly property bool petAfterModes: theme.sections.indexOf("pet") > theme.sections.indexOf("modes")
    // the pet's bubble clears the nudge row while off task
    readonly property real petLift: theme.px(nudgeShown ? 48 : 12)
    readonly property real islandHeight: theme.ipx(theme.islands ? 56 : 62)

    // section id -> component. Unknown ids in theme.sections are skipped.
    readonly property var sectionMap: ({
        pet: petComp,
        modes: modeStripComp,
        apps: appStripComp,
        agents: agentStripComp,
        held: heldBadgeComp,
    })
    // slab: sections drawn right after their neighbour with no divider (like the held badge)
    readonly property var inlineSections: ({ held: true })
    // islands: sections that share the island of their neighbour (the next one, or the previous when last)
    readonly property var joinSections: ({ pet: true })

    // theme.sections -> list of groups (lists of ids); one group per island
    readonly property var groups: {
        const secs = theme.sections
        if (!theme.islands) return [secs]
        const out = []
        for (let i = 0; i < secs.length; i++) {
            const id = secs[i]
            const last = out.length ? out[out.length - 1] : null
            const prevJoins = last && last.length === 1 && dock.joinSections[last[0]] && i === secs.indexOf(last[0]) + 1
            if (prevJoins || (dock.joinSections[id] && i === secs.length - 1 && last)) last.push(id)
            else out.push([id])
        }
        return out
    }

    anchors.bottom: !theme.atTop
    anchors.top: theme.atTop
    exclusiveZone: theme.autohide ? -1 : 0   // autohide: sit at the physical edge so the reveal strip is reachable
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "lockdock"
    // room around the card for the islands' shadows
    implicitWidth: card.implicitWidth + theme.px(56)
    // card, gap to the edge, headroom for the nudge; more while the pet's speech bubble shows
    implicitHeight: card.implicitHeight + theme.margin
                    + Math.max(theme.px(14 + 28 + 12), (petItem ? petItem.headroom : 0) - 4)
    mask: Region {
        item: cardHit
        Region { item: nudgeBox }
        Region { item: edge }
        Region { item: dock.petItem && dock.petItem.bubbleShown ? dock.petItem.bubble : null }
    }

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

    // input region of the card (every island and the gaps between them): none while slid away
    Item {
        id: cardHit
        x: card.x; y: card.y; width: card.width
        height: dock.shown ? card.height : 0
    }

    // the bounding box of all islands (or the slab card)
    Item {
        id: card
        anchors.horizontalCenter: parent.horizontalCenter
        y: dock.theme.atTop ? dock.theme.margin : dock.height - height - dock.theme.margin
        implicitWidth: groupRow.implicitWidth
        implicitHeight: dock.islandHeight
        width: implicitWidth; height: implicitHeight
        opacity: dock.theme.opacity
        HoverHandler { id: cardHover }

        transform: Translate {
            y: dock.shown ? 0 : (dock.theme.atTop ? -1 : 1) * (card.height + dock.theme.margin + dock.theme.px(12))
            Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        }

        Row {
            id: groupRow
            spacing: dock.theme.islands ? dock.theme.px(dock.theme.gap) : 0

            Repeater {
                model: dock.groups
                delegate: Item {
                    id: grp
                    required property var modelData     // section ids on this island
                    readonly property real pad: dock.theme.px(dock.theme.islands ? 8 : 10)
                    visible: modelData.some(id => dock.shownSections[id] === true)
                    implicitWidth: secRow.implicitWidth + 2 * pad
                    implicitHeight: dock.islandHeight
                    width: implicitWidth; height: implicitHeight

                    Island {
                        anchors.fill: parent
                        theme: dock.theme
                        alert: dock.offTask
                    }

                    RowLayout {
                        id: secRow
                        anchors.centerIn: parent
                        spacing: dock.theme.px(6)

                        Repeater {
                            model: grp.modelData
                            delegate: RowLayout {
                                id: sec
                                required property string modelData
                                required property int index
                                readonly property bool shown: loader.item ? (loader.item.active !== undefined ? loader.item.active : true) : false
                                readonly property bool inlineSection: dock.inlineSections[modelData] === true
                                visible: shown
                                spacing: dock.theme.px(6)
                                Layout.leftMargin: inlineSection && !dock.theme.islands ? dock.theme.px(6) : 0

                                onShownChanged: dock.markShown(modelData, shown)
                                Component.onCompleted: dock.markShown(modelData, shown)
                                Component.onDestruction: dock.markShown(modelData, false)

                                // slab only: a hairline between sections
                                Rectangle {
                                    visible: sec.shown && !sec.inlineSection && !dock.theme.islands
                                             && grp.modelData.slice(0, sec.index).some(id => dock.shownSections[id] === true)
                                    implicitWidth: 1; implicitHeight: dock.theme.px(32)
                                    color: dock.theme.alpha(dock.theme.text, 0.14)
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
            }
        }
    }

    // which section ids currently have something to show (drives the dividers and islands)
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
        id: petComp
        Pet {
            st: dock.st
            shell: dock.shell
            theme: dock.theme
            bubbleLift: dock.petLift
            bubbleLeftward: dock.petAfterModes
            bubbleBelow: dock.theme.atTop
            Layout.leftMargin: dock.theme.px(2)
            Layout.rightMargin: dock.theme.px(2)
            Component.onCompleted: dock.petItem = this
            Component.onDestruction: if (dock.petItem === this) dock.petItem = null
        }
    }
    Component {
        id: agentStripComp
        AgentStrip { st: dock.st; shell: dock.shell; theme: dock.theme }
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
        y: dock.theme.atTop ? card.y + card.height + dock.theme.px(8) : card.y - height - dock.theme.px(8)
        anchors.horizontalCenter: card.horizontalCenter
        reason: (dock.st.activity || {}).reason || ""
    }
}
