import QtQuick

// Reads st.theme (published by the daemon from ~/.config/lockdock/theme.json plus the
// desktop palette). Every property has a fallback, so a missing or partial theme never
// breaks the dock. Use px()/fpx() for sizes so `scale` applies, and the colour roles
// below (never literal colours) so the dock follows the wallpaper and light/dark.
QtObject {
    id: th
    property var st: ({})
    property var t: (st && st.theme) ? st.theme : ({})
    readonly property var c: t.colors || ({})

    function pick(v, fallback) { return (v === undefined || v === null) ? fallback : v }
    function role(name, fallback) { return c[name] ? c[name] : fallback }
    // a colour with its alpha multiplied by a (0..1)
    function alpha(col, a) { return Qt.rgba(col.r, col.g, col.b, col.a * a) }
    // readable text (black or white) on an arbitrary fill, e.g. an explicit mode colour
    function readableOn(col) { return (0.2126 * col.r + 0.7152 * col.g + 0.0722 * col.b) > 0.55 ? "#161616" : "#ffffff" }

    // ---- palette roles (fallbacks: the built-in dark palette, core/palette.py DARK) ----
    readonly property color bg: role("bg", "#1D2024")
    readonly property color bgElevated: role("bg_elevated", "#272A2F")
    readonly property color surface: role("surface", "#32353A")
    readonly property color surfaceHover: role("surface_hover", "#3E4146")
    readonly property color text: role("text", "#E0E2E8")
    readonly property color textMuted: role("text_muted", "#C2C7CE")
    readonly property color outline: role("outline", "#42474E")
    readonly property color paletteAccent: role("accent", "#99CCFA")
    readonly property color accentInk: role("on_accent", "#003350")
    readonly property color accentContainer: role("accent_container", "#084B72")
    readonly property color accentContainerInk: role("on_accent_container", "#CDE5FF")
    readonly property color secondary: role("secondary", "#B8C8DA")
    readonly property color tertiary: role("tertiary", "#D2BFE7")
    readonly property color danger: role("danger", "#FFB4AB")
    readonly property color dangerInk: role("on_danger", "#690005")
    readonly property color success: role("success", "#8FD5A6")
    readonly property color warning: role("warning", "#F2C46B")
    readonly property color bubble: role("bubble", "#E0E2E8")
    readonly property color bubbleText: role("bubble_text", "#2D3135")
    readonly property color shadowColor: role("shadow", "#000000")
    readonly property bool dark: (0.2126 * bg.r + 0.7152 * bg.g + 0.0722 * bg.b) < 0.5

    // ---- layout ----
    readonly property string layout: t.layout === "slab" ? "slab" : "islands"
    readonly property bool islands: layout === "islands"
    readonly property string position: t.position === "top" ? "top" : "bottom"
    readonly property bool atTop: position === "top"
    readonly property real margin: pick(t.margin, 10)
    readonly property real scale: pick(t.scale, 1.0)
    readonly property real radius: pick(t.radius, 20)
    readonly property real gap: pick(t.gap, 8)
    readonly property real fillOpacity: pick(t.fill_opacity, 1.0)
    readonly property bool shadow: pick((t.shadow || {}).enabled, true)
    readonly property real shadowOpacity: pick((t.shadow || {}).opacity, 0.28)

    // ---- island / card surface: explicit legacy keys win over the palette ----
    readonly property color background: t.background ? t.background : alpha(islands ? bg : bgElevated, fillOpacity)
    readonly property real borderWidth: pick((t.border || {}).width, 1)
    readonly property color borderColor: (t.border || {}).color ? t.border.color : alpha(outline, dark ? 0.55 : 0.35)
    readonly property color offTaskBorderColor: (t.border || {}).off_task_color ? t.border.off_task_color : alpha(danger, 0.7)

    readonly property string accentOverride: t.accent_override || ""
    // a mode's colour: "auto" (or none) follows the palette accent; accent_override beats both
    function modeColor(mode) {
        if (accentOverride !== "") return accentOverride
        const col = mode ? mode.color : ""
        return (!col || col === "auto") ? paletteAccent : col
    }
    function modeIsAuto(mode) { return accentOverride === "" && (!mode || !mode.color || mode.color === "auto") }

    // ---- type ----
    readonly property string fontFamily: pick((t.font || {}).family, "Inter Display")
    readonly property string family: fontFamily !== "" && Qt.fontFamilies().indexOf(fontFamily) >= 0 ? fontFamily : Qt.application.font.family
    readonly property real fontSize: pick((t.font || {}).size, 14)
    readonly property real iconSize: pick(t.icon_size, 34)
    readonly property var sections: Array.isArray(t.sections) ? t.sections : ["pet", "modes", "apps", "agents", "held"]
    readonly property bool showUnpinned: pick(t.show_unpinned, true)
    readonly property bool autohide: pick((t.autohide || {}).enabled, false)
    readonly property real revealPx: pick((t.autohide || {}).reveal_px, 4)
    readonly property int hideDelayMs: pick((t.autohide || {}).hide_delay_ms, 600)
    readonly property bool nudge: pick((t.nudge || {}).enabled, true)
    readonly property real opacity: pick(t.opacity, 1.0)
    // agent inbox: "pill" (one pill + pop-over list) or "chips" (one chip per agent)
    readonly property string agentsStyle: (t.agents || {}).style === "chips" ? "chips" : "pill"
    readonly property int agentsMaxRows: Math.max(1, pick((t.agents || {}).max_rows, 8))
    // decision cards (state.json `prompts`) above the dock
    readonly property bool promptsEnabled: pick((t.prompts || {}).enabled, true)
    readonly property int promptsMaxVisible: Math.max(1, pick((t.prompts || {}).max_visible, 3))
    readonly property real promptsWidth: pick((t.prompts || {}).width, 360)
    // a Stay (cancel) pill next to the countdown pill while a switch is pending
    readonly property bool stayButton: pick((t.mode_strip || {}).stay_button, true)

    // ---- icons (theme.json `icons`, core/theme.py IconsTheme): names for components/Icon.qml ----
    readonly property var icons: t.icons || ({})
    readonly property real iconStroke: pick(icons.stroke, 1.75)
    // the icon for a key ("held", "timer", ...); "" (set in theme.json) means none
    function icon(key, fallback) { const v = icons[key]; return (v === undefined || v === null) ? fallback : v }
    // a mode's icon (modes.json `icon`, emoji or icona:<slug>), else icons.mode_fallback
    function modeIcon(mode) { return (mode && mode.icon) ? mode.icon : icon("mode_fallback", "icona:target") }
    // an agent's icon: an icona glyph from modes.json agents.kinds, else icons.agent_kinds[kind],
    // else its own glyph, else the generic icons.agents
    function agentIcon(a) {
        if (!a) return icon("agents", "icona:sparkles")
        const g = a.glyph || ""
        if (g.indexOf("icona:") === 0) return g
        const k = (icons.agent_kinds || {})[a.kind]
        if (k) return k
        return g && g !== "◆" ? g : icon("agents", "icona:sparkles")
    }

    // icon_size grows or shrinks everything that wraps an icon by the same delta
    readonly property real iconDelta: iconSize - 34

    // scaled pixel size for a base (scale 1, default icon_size) length
    function px(v) { return Math.round(v * scale) }
    // scaled font pixel size for a base size that is 14 at the default font size
    function fpx(v) { return Math.max(1, Math.round(v * (fontSize / 14) * scale)) }
    // like px() but grows with icon_size (button, pill and island heights)
    function ipx(v) { return Math.round((v + iconDelta) * scale) }
}
