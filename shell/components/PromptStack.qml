import QtQuick

// The decision cards (state.json `prompts`, newest last) stacked next to the dock: newest
// nearest the dock, at most theme.promptsMaxVisible, theme.px(8) apart. state.json is re-parsed
// on every write, so the cards live in a ListModel synced by prompt id: a new id slides in
// (opacity 0 -> 1, 12 px toward the dock, its slot growing open), a gone id fades and shrinks
// (0.95) and then its slot closes, so nothing jumps. A prompt past `expires_ms` hides on its
// own; clicking an action sends ["prompt", id, action] and hides the card at once.
// The Dock positions the stack, adds it to the input mask and reserves headroom for it.
Column {
    id: stack
    required property var st
    required property var shell
    required property var theme
    property bool below: false            // dock at the top: newest first, cards hang below it

    readonly property var prompts: theme.promptsEnabled && Array.isArray(st.prompts) ? st.prompts : []
    readonly property real gap: theme.px(8)
    readonly property int count: cards.count
    // the widest card (verdict toasts can be wider than full cards)
    readonly property real cardWidth: theme.px(theme.promptsWidth)

    // ids hidden here before the daemon dropped them (clicked or expired)
    property var dismissed: ({})
    property real now: Date.now()

    spacing: 0
    width: maxSlotWidth > 0 ? maxSlotWidth : cardWidth
    property real maxSlotWidth: 0

    ListModel { id: cards }   // {pid, payload (JSON of the prompt), leaving}

    function wanted() {
        const out = []
        for (const p of stack.prompts) {
            if (!p || !p.id || stack.dismissed[p.id]) continue
            if (p.expires_ms && p.expires_ms <= stack.now) continue
            out.push(p)
        }
        return out.slice(-theme.promptsMaxVisible)
    }

    function sync() {
        // forget dismissals the daemon has caught up with
        const live = {}
        for (const p of stack.prompts) if (p && p.id) live[p.id] = true
        let changed = false
        const d = {}
        for (const k in stack.dismissed) { if (live[k]) d[k] = true; else changed = true }
        if (changed) stack.dismissed = d

        const want = wanted()
        const byId = {}
        for (const p of want) byId[p.id] = p
        for (let i = 0; i < cards.count; i++) {
            const row = cards.get(i)
            if (row.leaving) continue
            if (!byId[row.pid]) cards.setProperty(i, "leaving", true)
            else {
                const payload = JSON.stringify(byId[row.pid])
                if (payload !== row.payload) cards.setProperty(i, "payload", payload)
            }
        }
        // visual order, top to bottom: newest nearest the dock (last at the bottom, first when
        // the dock is at the top). A new card goes right before the next card in that order.
        const order = stack.below ? want.slice().reverse() : want
        const rowOf = id => {
            for (let i = 0; i < cards.count; i++) if (cards.get(i).pid === id && !cards.get(i).leaving) return i
            return -1
        }
        for (let k = 0; k < order.length; k++) {
            const p = order[k]
            if (rowOf(p.id) >= 0) continue
            let at = cards.count
            for (let j = k + 1; j < order.length; j++) {
                const r = rowOf(order[j].id)
                if (r >= 0) { at = r; break }
            }
            cards.insert(at, { pid: p.id, payload: JSON.stringify(p), leaving: false })
        }
        // the next expiry: re-check then
        let next = 0
        for (const p of stack.prompts)
            if (p && p.expires_ms && p.expires_ms > stack.now && (!next || p.expires_ms < next)) next = p.expires_ms
        expiry.interval = next ? Math.max(50, next - Date.now()) : 1000
        expiry.running = next > 0
    }
    function removeLeft(pid) {
        for (let i = 0; i < cards.count; i++)
            if (cards.get(i).pid === pid && cards.get(i).leaving) { cards.remove(i); break }
    }
    function act(pid, actionId) {
        stack.shell.send(["prompt", pid, actionId])
        const d = Object.assign({}, stack.dismissed)
        d[pid] = true
        stack.dismissed = d
        sync()
    }

    onPromptsChanged: { now = Date.now(); sync() }
    onBelowChanged: { cards.clear(); sync() }
    Component.onCompleted: sync()
    Timer {
        id: expiry
        repeat: false
        onTriggered: { stack.now = Date.now(); stack.sync() }
    }

    function refreshWidth() {
        let w = 0
        for (let i = 0; i < rep.count; i++) { const it = rep.itemAt(i); if (it) w = Math.max(w, it.cardWidth) }
        stack.maxSlotWidth = w
    }

    Repeater {
        id: rep
        model: cards
        onItemRemoved: Qt.callLater(stack.refreshWidth)
        delegate: Item {
            id: slot
            required property string pid
            required property string payload
            required property bool leaving
            readonly property var prompt: JSON.parse(payload)

            // 0..1: how far the card is in (opacity, slide) and how open its slot is
            property real shown: 0
            property real open: 0
            width: stack.width
            height: (card.height + stack.gap) * open

            readonly property real cardWidth: card.width
            onCardWidthChanged: Qt.callLater(stack.refreshWidth)
            Component.onCompleted: { enter.start(); Qt.callLater(stack.refreshWidth) }
            onLeavingChanged: if (leaving) { enter.stop(); leave.start() }

            ParallelAnimation {
                id: enter
                NumberAnimation { target: slot; property: "open"; to: 1; duration: 180; easing.type: Easing.OutCubic }
                NumberAnimation { target: slot; property: "shown"; to: 1; duration: 180; easing.type: Easing.OutCubic }
            }
            SequentialAnimation {
                id: leave
                NumberAnimation { target: slot; property: "shown"; to: 0; duration: 120; easing.type: Easing.InCubic }
                NumberAnimation { target: slot; property: "open"; to: 0; duration: 140; easing.type: Easing.InOutCubic }
                ScriptAction { script: stack.removeLeft(slot.pid) }
            }

            PromptCard {
                id: card
                theme: stack.theme
                prompt: slot.prompt
                maxWidth: stack.cardWidth
                x: Math.round((slot.width - width) / 2)
                // pinned to the dock-facing edge of the slot; the gap is on that side too
                y: stack.below ? stack.gap * slot.open : slot.height - stack.gap * slot.open - height
                opacity: slot.shown * stack.theme.opacity
                scale: slot.leaving ? 0.95 + 0.05 * slot.shown : 1
                transform: Translate {
                    y: slot.leaving ? 0 : (stack.below ? -1 : 1) * stack.theme.px(12) * (1 - slot.shown)
                }
                onActionClicked: actionId => { if (!slot.leaving) stack.act(slot.pid, actionId) }
            }
        }
    }
}
