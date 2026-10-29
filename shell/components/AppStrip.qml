import QtQuick
import QtQuick.Layouts
import Quickshell.Wayland

// The mode's pinned apps, then anything else running (dimmed) after a thin divider.
RowLayout {
    id: strip
    required property var activeMode
    required property color accent

    spacing: 6
    visible: (activeMode.apps || []).length + unpinned.length > 0

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

    // ---- pinned apps of the mode ----
    Repeater {
        model: strip.activeMode.apps || []
        AppButton {
            required property var modelData
            appId: modelData
            windows: strip.runningFor(modelData)
            accent: strip.accent
        }
    }
    // ---- running but not pinned ----
    Rectangle { visible: strip.unpinned.length > 0; width: 1; height: 28; color: Qt.rgba(1, 1, 1, 0.1) }
    Repeater {
        model: strip.unpinned
        AppButton {
            required property var modelData
            appId: modelData
            windows: strip.runningFor(modelData)
            accent: strip.accent
            dim: true
        }
    }
}
