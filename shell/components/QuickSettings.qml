import QtQuick
import QtQuick.Shapes
import Quickshell

// Quick settings, opened from the gear (section "settings", SettingsButton.qml): an island-styled
// panel (Tip's fill and stroke, radius 14) with a "Dock" header (position and pinned state as a
// muted detail) and one row per toggle: an icon, a label and an iOS-style switch (accent when
// on). Below the switches, two groups under a small muted header: "Notifications" (a Do not
// disturb switch and a "Release held after" stepper over st.notifications) and "Pet" (steppers
// over st.pet.config: the mood thresholds, growth, nag interval; hidden without a pet). A stepper
// is a "−" / "+" pair of 24 px round buttons (theme icons step_down / step_up: muted, accent on
// hover) around the value. Rows read the live theme / state, so they follow the files as the
// daemon rewrites them; a click sends the CLI verb (`theme set <key> <json>`, `pin toggle`,
// `pet mute|unmute`, `pet set <key> <n>`, `dnd on|off`, `held timeout <min>`).
// The Dock owns one per window and places it (x, y, tailX, below); `open` animates it in
// (opacity + 6 px slide, 140 ms OutCubic) and out (100 ms). `visible` stays true until it has
// faded out (the Dock masks it only while visible).
Item {
    id: panel
    required property var theme
    required property var st            // state.json
    required property var shell         // for shell.send([...])
    property bool open: false
    property bool below: false          // under the gear (dock at the top): the tail points up
    property real tailX: width / 2      // the gear's centre, in panel coordinates
    readonly property bool hovered: hover.hovered
    signal closeRequested()

    readonly property real tail: theme.px(4)
    readonly property real pad: theme.px(6)
    readonly property real rowH: theme.px(34)
    readonly property real headerH: theme.px(34)
    readonly property real groupH: theme.px(26)
    readonly property real sepH: theme.px(9)
    readonly property real panelW: theme.px(280)
    // the tallest the panel gets (every row and group, the pet's included, plus the tail): the
    // Dock keeps this much headroom
    readonly property real maxHeight: 2 * pad + headerH + 4 * sepH + (allRows.length + 1) * rowH
                                      + 2 * groupH + (1 + notifSteppers.length + petSteppers.length) * rowH + tail

    width: panelW
    height: body.height + tail

    property real progress: 0
    onOpenChanged: {
        anim.stop()
        const d = theme ? theme.dur(open ? 140 : 100) : 0
        if (d <= 0) { progress = open ? 1 : 0; return }
        anim.to = open ? 1 : 0
        anim.duration = d
        anim.easing.type = open ? Easing.OutCubic : Easing.InCubic
        anim.start()
    }
    NumberAnimation { id: anim; target: panel; property: "progress" }
    visible: progress > 0
    opacity: progress
    transform: Translate { y: (1 - panel.progress) * panel.theme.px(6) * (panel.below ? -1 : 1) }

    readonly property color fill: theme.dark ? theme.bgElevated : theme.surface
    readonly property color stroke: theme.alpha(theme.outline, theme.dark ? 0.6 : 0.45)
    readonly property color hairline: theme.alpha(theme.outline, theme.dark ? 0.7 : 0.5)

    // ---- the switch rows: {id, icon, label, on, enabled, shown, note} ----
    readonly property var pet: st.pet || ({})
    readonly property bool hasPet: !!pet.pack_dir
    readonly property var allRows: [
        { id: "pin", icon: theme.pinned ? theme.icon("pin", "icona:map-pin-fill") : theme.icon("pin_off", "icona:map-pin"),
          label: "Pin dock", on: theme.pinned, enabled: true, shown: true, note: "" },
        { id: "autohide", icon: "icona:eye-off", label: "Auto-hide", on: theme.autohide, enabled: !theme.pinned,
          shown: true, note: theme.pinned ? "pinned" : "" },
        { id: "position", icon: "icona:scroll-to-top", label: "Position: Top", on: theme.atTop, enabled: true, shown: true, note: "" },
        { id: "tooltips", icon: "icona:tooltip", label: "Tooltips", on: theme.tooltips, enabled: true, shown: true, note: "" },
        { id: "previews", icon: "icona:picture-in-picture", label: "Window previews", on: theme.previews, enabled: true,
          shown: true, note: "" },
        { id: "unpinned", icon: "icona:layers", label: "Show other running apps", on: theme.showUnpinned, enabled: true,
          shown: true, note: "" },
        { id: "motion", icon: "icona:reduce-motion", label: "Reduce motion", on: theme.reducedMotion, enabled: true,
          shown: true, note: "" },
        { id: "pet", icon: "icona:sketch-cat", label: "Mute the pet", on: !!pet.muted, enabled: true, shown: hasPet, note: "" },
    ]
    function themeSet(key, value) { panel.shell.send(["theme", "set", key, JSON.stringify(value)]) }
    function toggle(row) {
        switch (row.id) {
        case "pin": panel.shell.send(["pin", "toggle"]); break
        case "autohide": themeSet("autohide.enabled", !row.on); break
        case "position": themeSet("position", row.on ? "bottom" : "top"); break
        case "tooltips": themeSet("tooltips.enabled", !row.on); break
        case "previews": themeSet("previews.enabled", !row.on); break
        case "unpinned": themeSet("show_unpinned", !row.on); break
        case "motion": themeSet("reduced_motion", !row.on); break
        case "pet": panel.shell.send(["pet", row.on ? "unmute" : "mute"]); break
        }
    }

    // ---- the Notifications group (st.notifications) ----
    readonly property var notif: st.notifications || ({})
    readonly property bool dnd: !!notif.dnd
    readonly property real releaseAfter: notif.release_after_min === undefined ? 15 : notif.release_after_min
    readonly property var releaseSteps: [0, 5, 10, 15, 30, 60, 120]
    function minutesText(m) { return m <= 0 ? "never" : m % 60 === 0 ? (m / 60) + " h" : m + " min" }
    // the next / previous entry of releaseSteps from m (null at either end)
    function releaseUp(m) { const n = releaseSteps.find(x => x > m); return n === undefined ? null : n }
    function releaseDown(m) { const l = releaseSteps.filter(x => x < m); return l.length ? l[l.length - 1] : null }

    // ---- the Pet group (st.pet.config, in seconds) ----
    readonly property var petCfg: pet.config || ({})
    readonly property var thresholds: petCfg.thresholds || ({})
    function thresholdOf(m, fallback) { return thresholds[m] === undefined ? fallback : thresholds[m] }
    readonly property real suspicious: thresholdOf("suspicious", 45)
    readonly property real annoyed: thresholdOf("annoyed", 120)
    readonly property real furious: thresholdOf("furious", 300)
    // "45 s", "2 min", "2.5 min", "1 h"
    function secondsText(s) {
        if (s < 120) return Math.round(s) + " s"
        if (s % 3600 === 0) return (s / 3600) + " h"
        const m = s / 60
        return (Number.isInteger(m) ? m : m.toFixed(1)) + " min"
    }
    // v moved one step along a grid of `step`, clamped to [lo, hi]; null when it cannot move
    function snapStep(v, dir, step, lo, hi) {
        const n = dir > 0 ? Math.floor(v / step + 1e-6) * step + step : Math.ceil(v / step - 1e-6) * step - step
        const c = Math.max(lo, Math.min(hi, n))
        return Math.abs(c - v) < 1e-6 ? null : c
    }
    // thresholds: 15 s steps below 2 min, 30 s up to 10 min, 1 min above
    function thresholdMove(v, dir, lo, hi) {
        const at = dir > 0 ? v : v - 1e-6
        return snapStep(v, dir, at < 120 ? 15 : at < 600 ? 30 : 60, lo, hi)
    }
    function petSet(key, v) { panel.shell.send(["pet", "set", key, String(v)]) }

    // ---- the stepper rows: {icon, label, value, text(v), up(v), down(v), send(v)} ----
    readonly property var notifSteppers: [
        { icon: "icona:clock", label: "Release held after", value: releaseAfter,
          text: v => minutesText(v), up: v => releaseUp(v), down: v => releaseDown(v),
          send: v => panel.shell.send(["held", "timeout", String(v)]) },
    ]
    // a lower threshold never passes a higher one
    readonly property var petSteppers: [
        { icon: "icona:eye", label: "Suspicious after", value: suspicious, text: v => secondsText(v),
          up: v => thresholdMove(v, 1, 15, annoyed), down: v => thresholdMove(v, -1, 15, annoyed),
          send: v => petSet("thresholds.suspicious", v) },
        { icon: "icona:alert", label: "Annoyed after", value: annoyed, text: v => secondsText(v),
          up: v => thresholdMove(v, 1, suspicious, furious), down: v => thresholdMove(v, -1, suspicious, furious),
          send: v => petSet("thresholds.annoyed", v) },
        { icon: "icona:flame", label: "Furious after", value: furious, text: v => secondsText(v),
          up: v => thresholdMove(v, 1, annoyed, 3600), down: v => thresholdMove(v, -1, annoyed, 3600),
          send: v => petSet("thresholds.furious", v) },
        { icon: "icona:hourglass", label: "Grows to full in", value: petCfg.grow_s === undefined ? 240 : petCfg.grow_s,
          text: v => secondsText(v), up: v => snapStep(v, 1, 30, 30, 3600), down: v => snapStep(v, -1, 30, 30, 3600),
          send: v => petSet("grow_s", v) },
        { icon: "icona:message", label: "Nags every", value: petCfg.nag_every_s === undefined ? 60 : petCfg.nag_every_s,
          text: v => secondsText(v), up: v => snapStep(v, 1, 15, 15, 1800), down: v => snapStep(v, -1, 15, 15, 1800),
          send: v => petSet("nag_every_s", v) },
    ]
    // a colour between a and b (t 0..1), for hover tints that follow hoverProgress
    function mix(a, b, t) { return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t) }

    // ~/.config/lockdock[-<instance>]/theme.json (paths.py THEME_FILE)
    readonly property string themePath: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config")
                                        + "/lockdock" + (panel.shell.instance ? "-" + panel.shell.instance : "") + "/theme.json"

    HoverHandler { id: hover }

    Island {
        id: body
        theme: panel.theme
        y: panel.below ? panel.tail : 0
        width: panel.width
        height: content.implicitHeight + 2 * panel.pad
        radius: panel.theme.px(14)
        fill: panel.fill
        stroke: panel.stroke
    }

    // the tail (as in Tip.qml): a triangle in the fill colour laid over the border
    Shape {
        id: tailShape
        readonly property real half: panel.tail + panel.theme.px(1)
        x: Math.round(Math.max(panel.theme.px(14), Math.min(panel.width - panel.theme.px(14), panel.tailX)) - half)
        y: panel.below ? 0 : body.height - 1
        width: 2 * half; height: panel.tail + 1
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: panel.fill
            strokeColor: panel.stroke
            strokeWidth: panel.theme.borderWidth
            joinStyle: ShapePath.RoundJoin
            startX: 0; startY: panel.below ? tailShape.height : 0
            PathLine { x: tailShape.half; y: panel.below ? 0 : tailShape.height }
            PathLine { x: tailShape.width; y: panel.below ? tailShape.height : 0 }
        }
    }

    Column {
        id: content
        x: panel.pad
        y: body.y + panel.pad
        width: panel.width - 2 * panel.pad

        // header: "Dock" and the position / pinned state
        Item {
            width: parent.width; height: panel.headerH
            Text {
                x: panel.theme.px(10)
                anchors.verticalCenter: parent.verticalCenter
                text: "Dock"
                font.pixelSize: panel.theme.fpx(13.5)
                font.family: panel.theme.family
                font.weight: Font.Bold
                color: panel.theme.text
            }
            Text {
                anchors.right: parent.right; anchors.rightMargin: panel.theme.px(10)
                anchors.verticalCenter: parent.verticalCenter
                text: (panel.theme.atTop ? "Top" : "Bottom") + " · "
                      + (panel.theme.pinned ? "pinned" : panel.theme.autohide ? "auto-hides" : "overlay")
                font.pixelSize: panel.theme.fpx(11.5)
                font.family: panel.theme.family
                color: panel.theme.textMuted
            }
        }
        Separator {}

        Repeater {
            model: panel.allRows.filter(r => r.shown)
            delegate: SwitchRow {
                required property var modelData
                icon: modelData.icon
                label: modelData.label
                note: modelData.note
                on: modelData.on
                enabled: modelData.enabled
                onClicked: panel.toggle(modelData)
            }
        }

        // ---- Notifications ----
        Separator {}
        GroupHeader { label: "Notifications" }
        SwitchRow {
            icon: panel.dnd ? panel.theme.icon("dnd", "icona:moon-fill") : "icona:moon"
            label: "Do not disturb"
            note: panel.dnd && (panel.st.held_count || 0) > 0 ? panel.st.held_count + " held" : ""
            on: panel.dnd
            onClicked: panel.shell.send(["dnd", panel.dnd ? "off" : "on"])
        }
        Repeater {
            model: panel.notifSteppers
            delegate: StepperRow { required property var modelData; spec: modelData }
        }

        // ---- Pet ----
        Separator { visible: panel.hasPet }
        GroupHeader { label: "Pet"; visible: panel.hasPet }
        Repeater {
            model: panel.hasPet ? panel.petSteppers : []
            delegate: StepperRow { required property var modelData; spec: modelData }
        }

        Separator {}

        // footer: open theme.json in the default editor
        Pressable {
            id: edit
            theme: panel.theme
            width: content.width; height: panel.rowH
            onClicked: { Quickshell.execDetached(["xdg-open", panel.themePath]); panel.closeRequested() }
            Rectangle {
                anchors.fill: parent
                radius: panel.theme.px(9)
                color: panel.theme.surfaceHover
                opacity: edit.hoverProgress
                visible: opacity > 0
            }
            Icon {
                id: editIcon
                x: panel.theme.px(10)
                anchors.verticalCenter: parent.verticalCenter
                name: "icona:edit"
                size: panel.theme.fpx(16)
                stroke: panel.theme.iconStroke
                family: panel.theme.family
                color: panel.theme.textMuted
            }
            Text {
                anchors.left: editIcon.right; anchors.leftMargin: panel.theme.px(10)
                anchors.verticalCenter: parent.verticalCenter
                text: "Edit theme.json"
                font.pixelSize: panel.theme.fpx(12.5)
                font.family: panel.theme.family
                color: panel.theme.textMuted
            }
            Icon {
                anchors.right: parent.right; anchors.rightMargin: panel.theme.px(12)
                anchors.verticalCenter: parent.verticalCenter
                name: "icona:external-link"
                size: panel.theme.fpx(14)
                stroke: panel.theme.iconStroke
                family: panel.theme.family
                color: panel.theme.textMuted
            }
        }
    }

    // ---- building blocks ----
    // a hairline between groups
    component Separator: Item {
        width: content.width; height: panel.sepH
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            x: panel.theme.px(10); width: parent.width - 2 * x; height: 1
            color: panel.hairline
        }
    }

    // a small muted group title ("Notifications", "Pet")
    component GroupHeader: Item {
        id: gh
        property string label
        width: content.width; height: panel.groupH
        Text {
            x: panel.theme.px(10)
            anchors.bottom: parent.bottom; anchors.bottomMargin: panel.theme.px(5)
            text: gh.label
            font.pixelSize: panel.theme.fpx(11)
            font.family: panel.theme.family
            font.weight: Font.DemiBold
            color: panel.theme.textMuted
        }
    }

    // an icon, a label, an optional muted note and an iOS-style switch (accent when on)
    component SwitchRow: Pressable {
        id: row
        property string icon
        property string label
        property string note
        property bool on
        theme: panel.theme
        width: content.width; height: panel.rowH

        Rectangle {
            anchors.fill: parent
            radius: panel.theme.px(9)
            color: panel.theme.surfaceHover
            opacity: row.hoverProgress
            visible: opacity > 0
        }
        Item {
            anchors.fill: parent
            opacity: row.enabled ? 1 : 0.45
            Icon {
                id: rowIcon
                x: panel.theme.px(10)
                anchors.verticalCenter: parent.verticalCenter
                name: row.icon
                size: panel.theme.fpx(16)
                stroke: panel.theme.iconStroke
                family: panel.theme.family
                color: panel.theme.text
                opacity: 0.85 + 0.15 * row.hoverProgress
            }
            Text {
                anchors.left: rowIcon.right; anchors.leftMargin: panel.theme.px(10)
                anchors.right: noteText.left; anchors.rightMargin: panel.theme.px(6)
                anchors.verticalCenter: parent.verticalCenter
                text: row.label
                elide: Text.ElideRight
                font.pixelSize: panel.theme.fpx(12.5)
                font.family: panel.theme.family
                color: panel.theme.text
            }
            Text {
                id: noteText
                anchors.right: sw.left; anchors.rightMargin: panel.theme.px(row.note ? 8 : 0)
                anchors.verticalCenter: parent.verticalCenter
                text: row.note
                font.pixelSize: panel.theme.fpx(11)
                font.family: panel.theme.family
                color: panel.theme.textMuted
            }
            // the switch: a 30x18 pill with a sliding knob, accent when on
            Rectangle {
                id: sw
                anchors.right: parent.right; anchors.rightMargin: panel.theme.px(8)
                anchors.verticalCenter: parent.verticalCenter
                width: panel.theme.px(30); height: panel.theme.px(18)
                radius: height / 2
                color: row.on ? panel.theme.paletteAccent : panel.theme.alpha(panel.theme.surfaceHover, panel.theme.dark ? 1 : 0.7)
                border.width: row.on ? 0 : panel.theme.borderWidth
                border.color: panel.theme.alpha(panel.theme.outline, panel.theme.dark ? 1 : 0.8)
                Behavior on color { ColorAnimation { duration: panel.theme.dur(140); easing.type: Easing.OutCubic } }
                Rectangle {
                    readonly property real inset: panel.theme.px(3)
                    width: sw.height - 2 * inset; height: width; radius: width / 2
                    y: inset
                    x: row.on ? sw.width - width - inset : inset
                    color: row.on ? panel.theme.accentInk : panel.theme.textMuted
                    Behavior on x { NumberAnimation { duration: panel.theme.dur(140); easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: panel.theme.dur(140); easing.type: Easing.OutCubic } }
                }
            }
        }
    }

    // an icon, a label and "−  value  +"; `spec` is a notifSteppers / petSteppers entry. A press
    // shows the new value at once (`pending`) until the state file catches up (or 3 s pass).
    component StepperRow: Item {
        id: sr
        required property var spec
        property var pending: null
        readonly property real value: pending === null ? spec.value : pending
        readonly property var upTo: spec.up(value)
        readonly property var downTo: spec.down(value)
        function go(v) {
            if (v === null) return
            pending = v
            settle.restart()
            spec.send(v)
        }
        onSpecChanged: if (pending !== null && Math.abs(spec.value - pending) < 1e-6) pending = null
        Timer { id: settle; interval: 3000; onTriggered: sr.pending = null }
        width: content.width; height: panel.rowH

        Icon {
            id: stepIcon
            x: panel.theme.px(10)
            anchors.verticalCenter: parent.verticalCenter
            name: sr.spec.icon
            size: panel.theme.fpx(16)
            stroke: panel.theme.iconStroke
            family: panel.theme.family
            color: panel.theme.text
            opacity: 0.85
        }
        Text {
            anchors.left: stepIcon.right; anchors.leftMargin: panel.theme.px(10)
            anchors.right: stepper.left; anchors.rightMargin: panel.theme.px(6)
            anchors.verticalCenter: parent.verticalCenter
            text: sr.spec.label
            elide: Text.ElideRight
            font.pixelSize: panel.theme.fpx(12.5)
            font.family: panel.theme.family
            color: panel.theme.text
        }
        Row {
            id: stepper
            anchors.right: parent.right; anchors.rightMargin: panel.theme.px(8)
            anchors.verticalCenter: parent.verticalCenter
            spacing: panel.theme.px(2)
            StepButton {
                glyph: panel.theme.icon("step_down", "icona:minus")
                enabled: sr.downTo !== null
                onClicked: sr.go(sr.downTo)
            }
            Text {
                width: panel.theme.px(52)
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignHCenter
                text: sr.spec.text(sr.value)
                font.pixelSize: panel.theme.fpx(12)
                font.family: panel.theme.family
                color: panel.theme.text
            }
            StepButton {
                glyph: panel.theme.icon("step_up", "icona:plus")
                enabled: sr.upTo !== null
                onClicked: sr.go(sr.upTo)
            }
        }
    }

    // a 24 px round glyph button: muted, an accent glyph, ring and faint fill on hover
    component StepButton: Pressable {
        id: sb
        property string glyph
        theme: panel.theme
        width: panel.theme.px(24); height: width
        scale: pressScale
        opacity: enabled ? 1 : 0.3
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: panel.theme.alpha(panel.theme.paletteAccent, 0.16 * sb.hoverProgress)
            border.width: panel.theme.borderWidth
            border.color: panel.mix(panel.hairline, panel.theme.paletteAccent, sb.hoverProgress)
        }
        Icon {
            anchors.centerIn: parent
            name: sb.glyph
            size: panel.theme.fpx(13)
            stroke: panel.theme.iconStroke
            family: panel.theme.family
            color: panel.mix(panel.theme.textMuted, panel.theme.paletteAccent, sb.hoverProgress)
        }
    }
}
