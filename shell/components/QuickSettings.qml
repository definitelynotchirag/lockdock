import QtQuick
import QtQuick.Shapes
import Quickshell

// Quick settings, opened from the gear (section "settings", SettingsButton.qml): an island-styled
// panel (Tip's fill and stroke, radius 14) with a "Dock" header (position and pinned state as a
// muted detail) and one row per toggle: an icon, a label and an iOS-style switch (accent when
// on). Rows read the live theme / state, so they follow theme.json as the daemon rewrites it;
// a click sends the CLI verb (`theme set <key> <json>`, `pin toggle`, `pet mute|unmute`).
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
    readonly property real panelW: theme.px(260)
    // the tallest the panel gets (every row, the pet's included, plus the tail): the Dock keeps
    // this much headroom
    readonly property real maxHeight: 2 * pad + headerH + theme.px(9) + (allRows.length + 1) * rowH + theme.px(9) + tail

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

    // ---- the rows: {id, icon, label, on, enabled, shown, note} ----
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
        Item {
            width: parent.width; height: panel.theme.px(9)
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                x: panel.theme.px(10); width: parent.width - 2 * x; height: 1
                color: panel.theme.alpha(panel.theme.outline, panel.theme.dark ? 0.7 : 0.5)
            }
        }

        Repeater {
            model: panel.allRows.filter(r => r.shown)
            delegate: Pressable {
                id: row
                required property var modelData
                theme: panel.theme
                width: content.width; height: panel.rowH
                enabled: modelData.enabled
                onClicked: panel.toggle(row.modelData)

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
                        name: row.modelData.icon
                        size: panel.theme.fpx(16)
                        stroke: panel.theme.iconStroke
                        family: panel.theme.family
                        color: panel.theme.text
                        opacity: 0.85 + 0.15 * row.hoverProgress
                    }
                    Text {
                        anchors.left: rowIcon.right; anchors.leftMargin: panel.theme.px(10)
                        anchors.right: note.left; anchors.rightMargin: panel.theme.px(6)
                        anchors.verticalCenter: parent.verticalCenter
                        text: row.modelData.label
                        elide: Text.ElideRight
                        font.pixelSize: panel.theme.fpx(12.5)
                        font.family: panel.theme.family
                        color: panel.theme.text
                    }
                    Text {
                        id: note
                        anchors.right: sw.left; anchors.rightMargin: panel.theme.px(row.modelData.note ? 8 : 0)
                        anchors.verticalCenter: parent.verticalCenter
                        text: row.modelData.note
                        font.pixelSize: panel.theme.fpx(11)
                        font.family: panel.theme.family
                        color: panel.theme.textMuted
                    }
                    // the switch: a 30x18 pill with a sliding knob, accent when on
                    Rectangle {
                        id: sw
                        readonly property bool on: row.modelData.on
                        anchors.right: parent.right; anchors.rightMargin: panel.theme.px(8)
                        anchors.verticalCenter: parent.verticalCenter
                        width: panel.theme.px(30); height: panel.theme.px(18)
                        radius: height / 2
                        color: on ? panel.theme.paletteAccent : panel.theme.alpha(panel.theme.surfaceHover, panel.theme.dark ? 1 : 0.7)
                        border.width: on ? 0 : panel.theme.borderWidth
                        border.color: panel.theme.alpha(panel.theme.outline, panel.theme.dark ? 1 : 0.8)
                        Behavior on color { ColorAnimation { duration: panel.theme.dur(140); easing.type: Easing.OutCubic } }
                        Rectangle {
                            readonly property real inset: panel.theme.px(3)
                            width: sw.height - 2 * inset; height: width; radius: width / 2
                            y: inset
                            x: sw.on ? sw.width - width - inset : inset
                            color: sw.on ? panel.theme.accentInk : panel.theme.textMuted
                            Behavior on x { NumberAnimation { duration: panel.theme.dur(140); easing.type: Easing.OutCubic } }
                            Behavior on color { ColorAnimation { duration: panel.theme.dur(140); easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }
        }

        Item {
            width: parent.width; height: panel.theme.px(9)
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                x: panel.theme.px(10); width: parent.width - 2 * x; height: 1
                color: panel.theme.alpha(panel.theme.outline, panel.theme.dark ? 0.7 : 0.5)
            }
        }

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
}
