import QtQuick
import QtQuick.Layouts
import Quickshell.Wayland

// The mode's pinned apps, then anything else running (dimmed) after a thin divider.
RowLayout {
    id: strip
    required property var activeMode
    required property color accent
    required property var theme

    spacing: theme.px(6)
    // sections report whether they have anything to show through `active` (see Dock.qml)
    readonly property bool active: (activeMode.apps || []).length + shownUnpinned.length > 0
    visible: active

    readonly property var toplevels: ToplevelManager.toplevels.values
    function norm(s) { return (s || "").toLowerCase() }
    function runningFor(appId) {
        const a = norm(appId)
        return toplevels.filter(t => { const i = norm(t.appId); return i === a || i.endsWith("." + a) || a.endsWith("." + i) })
    }
    readonly property var unpinned: {
        const seen = {}
        const pinned = (activeMode.apps || []).map(norm)
        const out = []
        for (const t of toplevels) {
            const id = norm(t.appId)
            if (!id || seen[id]) continue
            if (pinned.some(p => p === id || id.endsWith("." + p) || p.endsWith("." + id))) continue
            seen[id] = true
            out.push(t.appId)
        }
        return out
    }

    readonly property var shownUnpinned: theme.showUnpinned ? unpinned : []

    // ---- pinned apps of the mode ----
    Repeater {
        model: strip.activeMode.apps || []
        AppButton {
            required property var modelData
            appId: modelData
            windows: strip.runningFor(modelData)
            accent: strip.accent
            theme: strip.theme
        }
    }
    // ---- running but not pinned ----
    Rectangle { visible: strip.shownUnpinned.length > 0; width: 1; height: strip.theme.px(28); color: Qt.rgba(1, 1, 1, 0.1) }
    Repeater {
        model: strip.shownUnpinned
        AppButton {
            required property var modelData
            appId: modelData
            windows: strip.runningFor(modelData)
            accent: strip.accent
            theme: strip.theme
            dim: true
        }
    }
}
