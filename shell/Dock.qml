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
    readonly property var theme: Theme { st: dock.st; host: dock }
    readonly property var activeMode: (st.modes || []).find(m => m.id === st.mode) || { id: "", label: "", icon: "", color: "auto", apps: [] }
    readonly property bool offTask: (st.activity || {}).verdict === "off"
    readonly property bool nudgeShown: offTask && theme.nudge
    readonly property color accent: theme.modeColor(activeMode)
    // the pet registers itself here when its section is loaded (see components/Pet.qml)
    property Item petItem: null
    // the agents pill registers itself here (theme.agents.style "pill"); its list is agentsPanel
    property Item agentsPill: null
    readonly property bool agentsOpen: agentsPill !== null && agentsPill.open
    readonly property bool petAfterModes: theme.sections.indexOf("pet") > theme.sections.indexOf("modes")
    // the pet's bubble clears the nudge row while off task
    readonly property real petLift: theme.px(nudgeShown ? 48 : 12)
    readonly property real islandHeight: theme.ipx(theme.islands ? 56 : 62)

    // section id -> component. Unknown ids in theme.sections are skipped.
    readonly property var sectionMap: ({
        pet: petComp,
        modes: modeStripComp,
        apps: appStripComp,
        agents: theme.agentsStyle === "chips" ? agentStripComp : agentsPillComp,
        held: heldBadgeComp,
        pin: pinComp,
        settings: settingsComp,
    })
    // slab: sections drawn right after their neighbour with no divider (like the held badge)
    readonly property var inlineSections: ({ held: true, pin: true, settings: true })
    // islands: sections that share the island of their neighbour (the next one, or the previous when last)
    readonly property var joinSections: ({ pet: true, pin: true, settings: true })

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
    // pinned: reserve the island row and the margin (not the transparent headroom above it) so
    // maximised and tiled windows stop at the dock. Unpinned: an overlay; autohide sits at the
    // physical edge so the reveal strip is reachable. Pinned never hides.
    readonly property bool autohide: theme.autohide && !theme.pinned
    readonly property int reservedZone: Math.ceil(islandHeight + theme.margin)
    exclusiveZone: theme.pinned ? reservedZone : (autohide ? -1 : 0)
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "lockdock"
    // room around the card for the islands' shadows
    // (wide enough for the agents list to sit centred on its pill)
    implicitWidth: Math.max(card.implicitWidth + theme.px(56),
                            theme.tooltips ? tip.maxTextWidth + theme.px(60) : 0,
                            agentsPill ? 2 * (Math.abs(agentsPanel.pillOffset) + agentsPanel.width / 2 + theme.px(12)) : 0,
                            promptStack.count > 0 ? promptStack.width + theme.px(48) : 0,
                            previewsHeadroom > 0 ? previews.widthFor(previewsMaxCards, previewsMaxMore) + theme.px(24) : 0,
                            settingsHeadroom > 0 ? 2 * (Math.abs(quickSettings.btnOffset) + quickSettings.width / 2 + theme.px(12)) : 0)
    // card, gap to the edge, headroom for the nudge; more while the pet's speech bubble, the
    // agents list or decision cards show
    implicitHeight: card.implicitHeight + theme.margin
                    + Math.max(theme.px(14 + 28 + 12), (petItem ? petItem.headroom : 0) - 4, agentsHeadroom, promptsHeadroom,
                               tipHeadroom, previewsHeadroom, settingsHeadroom)
    readonly property real panelGap: theme.px(10) + (nudgeShown ? nudgeBox.height + theme.px(8) : 0)
    // reserved while the pill shows, not only while the list is open: resizing the layer surface
    // on every open makes Hyprland redraw the whole dock squashed for a frame
    // (plus a tooltip's height, so a row's tip fits above the list)
    readonly property real agentsHeadroom: agentsPill && agentsPill.visible
        ? agentsPanel.height + panelGap + theme.px(14) + (theme.tooltips ? tipHeadroom : 0) : 0
    // a tooltip over the islands: always reserved while tooltips are on (no resize on hover)
    readonly property real tipHeadroom: theme.tooltips ? Math.ceil(tip.maxHeight) + theme.px(16) : 0
    // window previews: reserved while previews are on and any app runs (not only while open, so
    // hovering never resizes the layer surface); wide enough for the app with the most windows
    readonly property var toplevels: ToplevelManager.toplevels.values
    readonly property int mostWindows: {
        const n = {}
        let most = 0
        for (const t of toplevels) {
            const id = (t.appId || "").toLowerCase()
            n[id] = (n[id] || 0) + 1
            most = Math.max(most, n[id])
        }
        return most
    }
    readonly property int previewsMaxCards: Math.min(mostWindows, theme.previewsMax)
    readonly property bool previewsMaxMore: mostWindows > theme.previewsMax
    readonly property real previewsHeadroom: theme.previews && mostWindows > 0 && theme.sections.indexOf("apps") >= 0
        ? Math.ceil(previews.maxHeight) + theme.px(16) : 0
    // quick settings: reserved while the "settings" section is listed (not only while open, so
    // hovering the gear never resizes the layer surface)
    readonly property real settingsHeadroom: theme.sections.indexOf("settings") >= 0
        ? Math.ceil(quickSettings.maxHeight) + theme.px(16) : 0
    // decision cards: while any card is up, reserve room for max_visible tall cards (or the real
    // stack, if taller) so the surface does not resize as cards come and go
    readonly property real promptCardReserve: theme.px(14 + 32 + 10 + 3 * 17 + 10 + 28 + 12 + 32 + 14 + 8)
    readonly property real promptsHeadroom: promptStack.count > 0
        ? Math.max(promptStack.height, theme.promptsMaxVisible * promptCardReserve) + panelGap + theme.px(14) : 0
    mask: Region {
        item: cardHit
        Region { item: nudgeBox }
        Region { item: edge }
        Region { item: dock.petItem && dock.petItem.bubbleShown ? dock.petItem.bubble : null }
        Region { item: agentsPanel.visible ? agentsPanel : null }
        Region { item: promptStack.count > 0 ? promptStack : null }
        Region { item: tip.visible ? tip : null }
        Region { item: previews.visible ? previews : null }
        Region { item: quickSettings.visible ? quickSettings : null }
    }

    // countdown clock
    property real now: Date.now()
    Timer { interval: 100; repeat: true; running: dock.st.pending !== null && dock.st.pending !== undefined; onTriggered: dock.now = Date.now() }

    // ---- autohide ----
    property bool shown: true
    readonly property bool busy: (st.pending !== null && st.pending !== undefined) || nudgeShown
                                 || ((st.held_count || 0) > 0 && !(st.notifications || {}).dnd)
                                 || agentsOpen || promptStack.count > 0 || previews.visible
                                 || quickSettings.visible
    readonly property bool wantShown: !autohide || cardHover.hovered || edgeHover.hovered || busy
    onWantShownChanged: { if (wantShown) { hideTimer.stop(); shown = true } else hideTimer.restart() }
    Component.onCompleted: if (!wantShown) hideTimer.start()
    Timer { id: hideTimer; interval: dock.theme.hideDelayMs; onTriggered: dock.shown = false }

    // thin strip at the screen edge that reveals a hidden dock (also bridges the margin while shown)
    Item {
        id: edge
        anchors.horizontalCenter: parent.horizontalCenter
        width: card.width
        height: dock.autohide ? (dock.shown ? Math.max(dock.theme.revealPx, dock.theme.margin) : dock.theme.revealPx) : 0
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
            Behavior on y { NumberAnimation { duration: dock.theme.dur(200); easing.type: Easing.OutCubic } }
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
            onStayClicked: dock.shell.send(["cancel"])
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
        id: agentsPillComp
        AgentsPill {
            st: dock.st
            theme: dock.theme
            panelHovered: agentsPanel.hovered
            Component.onCompleted: dock.agentsPill = this
            Component.onDestruction: if (dock.agentsPill === this) dock.agentsPill = null
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

    Component {
        id: pinComp
        PinButton { st: dock.st; shell: dock.shell; theme: dock.theme }
    }
    Component {
        id: settingsComp
        SettingsButton {
            st: dock.st
            theme: dock.theme
            Component.onCompleted: dock.settingsBtn = this
            Component.onDestruction: if (dock.settingsBtn === this) dock.settingsBtn = null
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

    // the agents list, opened from the pill: above the dock (below it at the top), centred on
    // the pill, clear of the nudge
    AgentsPanel {
        id: agentsPanel
        st: dock.st
        shell: dock.shell
        theme: dock.theme
        open: dock.agentsOpen
        below: dock.theme.atTop
        z: 10
        // the pill's centre relative to the card's centre (the card is centred in the window)
        readonly property real pillOffset: {
            const p = dock.agentsPill
            card.width; open
            if (!p || !p.visible) return 0
            return p.mapToItem(card, p.width / 2, 0).x - card.width / 2
        }
        x: Math.round(dock.width / 2 + pillOffset - width / 2)
        originX: dock.width / 2 + pillOffset - x
        y: dock.theme.atTop ? card.y + card.height + dock.panelGap : card.y - height - dock.panelGap
        onCloseRequested: if (dock.agentsPill) dock.agentsPill.open = false
    }

    // decision cards (state.json `prompts`): above the dock (below it at the top), centred,
    // clear of the nudge; newest nearest the dock
    PromptStack {
        id: promptStack
        st: dock.st
        shell: dock.shell
        theme: dock.theme
        below: dock.theme.atTop
        z: 11
        x: Math.round((dock.width - width) / 2)
        // the slot nearest the dock carries one card gap of its own
        y: dock.theme.atTop ? card.y + card.height + dock.panelGap - promptStack.gap
                            : card.y - height - dock.panelGap + promptStack.gap
    }

    // ---- the tooltip: one per window, shown for whichever Pressable is hovered ----
    // showTip(item, {icon, title, detail}) after theme.tooltips.delay_ms; moving from one item to
    // the next while a tip shows (or just faded) switches at once. hideTip(item) only hides the
    // tip that item owns.
    property Item tipTarget: null
    property var tipContent: ({})
    property bool tipOpen: false
    function showTip(item, content) {
        if (!theme.tooltips || !content || !content.title) return
        const switching = tipOpen || tipGrace.running
        tipGrace.stop()
        tipTarget = item
        tipContent = content
        if (switching) { tipDelay.stop(); tipOpen = true }
        else if (!tipOpen) tipDelay.restart()
    }
    function hideTip(item) {
        if (item !== tipTarget) return
        tipDelay.stop()
        if (tipOpen) { tipOpen = false; tipGrace.restart() }
    }
    onTipTargetChanged: if (!tipTarget) { tipDelay.stop(); tipOpen = false }
    Timer { id: tipDelay; interval: dock.theme.tooltipDelayMs; onTriggered: dock.tipOpen = dock.tipTarget !== null }
    Timer { id: tipGrace; interval: 300 }

    Tip {
        id: tip
        theme: dock.theme
        z: 20
        open: dock.tipOpen && dock.tipTarget !== null && dock.shown
        icon: dock.tipContent.icon || ""
        title: dock.tipContent.title || ""
        detail: dock.tipContent.detail || ""
        readonly property real gap: dock.theme.px(6)
        // the target's top centre and bottom, in window coordinates (re-read as the card moves)
        readonly property rect anchorRect: {
            const t = dock.tipTarget
            card.width; card.x; dock.width; dock.height; agentsPanel.y; tip.open
            if (!t) return Qt.rect(0, 0, 0, 0)
            const p = t.mapToItem(tip.parent, 0, 0)
            const w = t.width * t.scale, h = t.height * t.scale
            // an item on the islands: point at the island edge, not at the item itself
            const cy = p.y + h / 2
            if (cy >= card.y && cy <= card.y + card.height) return Qt.rect(p.x, card.y, w, card.height)
            return Qt.rect(p.x, p.y, w, h)
        }
        readonly property bool wantBelow: dock.theme.atTop
        readonly property real yAbove: anchorRect.y - height - gap
        readonly property real yBelow: anchorRect.y + anchorRect.height + gap
        below: wantBelow ? yBelow + height <= dock.height : yAbove < 0
        x: Math.round(Math.max(dock.theme.px(4), Math.min(dock.width - width - dock.theme.px(4),
                                                         anchorRect.x + anchorRect.width / 2 - width / 2)))
        y: Math.round(below ? yBelow : yAbove)
        tailX: anchorRect.x + anchorRect.width / 2 - x
    }

    // ---- window previews: one per window, for whichever running AppButton is hovered ----
    // showPreviews(item, windows) after theme.previewsDelayMs (switching at once while open);
    // they stay open while the pointer is on the button or the panel and close 250 ms after it
    // has left both. hidePreviews(item, immediate) only acts for the item that owns them.
    property Item previewTarget: null
    property bool previewsOpen: false
    property bool previewBtnHovered: false
    function showPreviews(item, windows) {
        if (!theme.previews || !theme.hoverOpens || !windows || windows.length === 0) return
        previewClose.stop()
        previewTarget = item
        previewBtnHovered = true
        if (previewsOpen) return
        previewDelay.restart()
    }
    // popups.open_on_hover false: a click on a running app opens / closes its previews
    function togglePreviews(item, windows) {
        if (!theme.previews || !windows || windows.length === 0) return
        previewDelay.stop(); previewClose.stop()
        const same = previewTarget === item
        previewTarget = item
        previewsOpen = !(same && previewsOpen)
    }
    function hidePreviews(item, immediate) {
        if (item !== previewTarget) return
        if (!theme.hoverOpens && !immediate) return   // click-opened: stays until a click or a card
        previewBtnHovered = false
        previewDelay.stop()
        if (immediate) { previewClose.stop(); previewsOpen = false }
        else if (previewsOpen && !previews.hovered) previewClose.restart()
    }
    onPreviewTargetChanged: if (!previewTarget) { previewDelay.stop(); previewClose.stop(); previewsOpen = false; previewBtnHovered = false }
    Timer { id: previewDelay; interval: dock.theme.previewsDelayMs; onTriggered: dock.previewsOpen = dock.previewTarget !== null && dock.previewBtnHovered }
    Timer {
        id: previewClose
        interval: 250
        onTriggered: if (!dock.previewBtnHovered && !previews.hovered) dock.previewsOpen = false
    }

    WindowPreviews {
        id: previews
        theme: dock.theme
        z: 19
        windows: dock.previewTarget ? dock.previewTarget.windows : []
        iconSource: dock.previewTarget ? dock.previewTarget.iconSource : ""
        open: dock.previewsOpen && dock.previewTarget !== null && dock.shown && windows.length > 0 && dock.theme.previews
        readonly property real gap: dock.theme.px(6)
        onHoveredChanged: {
            if (hovered) previewClose.stop()
            else if (!dock.previewBtnHovered && dock.previewsOpen) previewClose.restart()
        }
        onActivated: { previewClose.stop(); dock.previewsOpen = false }
        // the target's horizontal span and the island edge, in window coordinates
        readonly property rect anchorRect: {
            const t = dock.previewTarget
            card.width; card.x; dock.width; dock.height; previews.open
            if (!t) return Qt.rect(0, 0, 0, 0)
            const p = t.mapToItem(previews.parent, 0, 0)
            return Qt.rect(p.x, card.y, t.width * t.scale, card.height)
        }
        below: dock.theme.atTop
        x: Math.round(Math.max(dock.theme.px(4), Math.min(dock.width - width - dock.theme.px(4),
                                                         anchorRect.x + anchorRect.width / 2 - width / 2)))
        y: Math.round(below ? anchorRect.y + anchorRect.height + gap : anchorRect.y - height - gap)
        tailX: anchorRect.x + anchorRect.width / 2 - x
    }

    // ---- quick settings: one panel per window, opened from the gear (section "settings") ----
    // hoverSettings(item, hovered): open after theme.tooltipDelayMs of hover; it stays open while
    // the pointer is on the gear or the panel and closes 250 ms after it has left both.
    // toggleSettings(item): a click opens / closes it at once. closeSettings(item) closes it.
    property Item settingsBtn: null      // the gear registers itself here
    property Item settingsTarget: null
    property bool settingsOpen: false
    property bool settingsBtnHovered: false
    function hoverSettings(item, hovered) {
        if (hovered) {
            if (!theme.hoverOpens) return
            settingsTarget = item
            settingsBtnHovered = true
            settingsClose.stop()
            if (!settingsOpen) settingsDelay.restart()
            return
        }
        if (item !== settingsTarget) return
        settingsBtnHovered = false
        settingsDelay.stop()
        if (settingsOpen && !quickSettings.hovered) settingsClose.restart()
    }
    function toggleSettings(item) {
        settingsTarget = item
        settingsDelay.stop()
        settingsClose.stop()
        settingsOpen = !settingsOpen
    }
    function closeSettings(item) {
        if (item !== settingsTarget) return
        settingsDelay.stop(); settingsClose.stop()
        settingsOpen = false
        settingsTarget = null
    }
    Timer { id: settingsDelay; interval: dock.theme.tooltipDelayMs; onTriggered: dock.settingsOpen = dock.settingsTarget !== null && dock.settingsBtnHovered }
    Timer {
        id: settingsClose
        interval: 250
        onTriggered: if (!dock.settingsBtnHovered && !quickSettings.hovered) dock.settingsOpen = false
    }

    QuickSettings {
        id: quickSettings
        theme: dock.theme
        st: dock.st
        shell: dock.shell
        z: 19
        open: dock.settingsOpen && dock.settingsTarget !== null && dock.settingsTarget.visible && dock.shown
        readonly property real gap: dock.theme.px(6)
        onHoveredChanged: {
            if (hovered) settingsClose.stop()
            else if (!dock.settingsBtnHovered && dock.settingsOpen) settingsClose.restart()
        }
        onCloseRequested: { settingsClose.stop(); dock.settingsOpen = false }
        // the gear's centre relative to the card's centre (wide enough a window to centre the
        // panel on it; known from the start, so the first hover does not resize the surface)
        readonly property real btnOffset: {
            const b = dock.settingsBtn
            card.width; dock.shownSections
            if (!b || !b.visible) return 0
            return b.mapToItem(card, b.width / 2, 0).x - card.width / 2
        }
        // the gear's horizontal span and the island edge, in window coordinates
        readonly property rect anchorRect: {
            const t = dock.settingsTarget || dock.settingsBtn
            card.width; card.x; dock.width; dock.height; quickSettings.open; dock.shownSections
            if (!t || !t.visible) return Qt.rect(0, 0, 0, 0)
            const p = t.mapToItem(quickSettings.parent, 0, 0)
            return Qt.rect(p.x, card.y, t.width * t.scale, card.height)
        }
        below: dock.theme.atTop
        x: Math.round(Math.max(dock.theme.px(4), Math.min(dock.width - width - dock.theme.px(4),
                                                         anchorRect.x + anchorRect.width / 2 - width / 2)))
        y: Math.round(below ? anchorRect.y + anchorRect.height + gap : anchorRect.y - height - gap)
        tailX: anchorRect.x + anchorRect.width / 2 - x
    }
}
