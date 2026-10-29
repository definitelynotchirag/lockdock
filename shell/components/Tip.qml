import QtQuick
import QtQuick.Shapes

// The dock's tooltip: an island-styled bubble with an optional Icona icon, a bold title and an
// optional muted detail (up to 2 lines), and a 4 px tail pointing at the hovered item. The
// Dock owns one Tip per window and places it (x, y, tailX, below); `open` animates it in
// (opacity + 4 px slide, 120 ms OutCubic) and out (80 ms). `visible` stays true until it has
// faded out, so the Dock can add it to the input mask only while it shows.
Item {
    id: tip
    required property var theme
    property string icon: ""
    property string title: ""
    property string detail: ""
    property bool open: false
    property bool below: false          // under the item (dock at the top): the tail points up
    property real tailX: width / 2      // the hovered item's centre, in tip coordinates
    readonly property real tail: theme.px(4)
    readonly property real maxTextWidth: theme.px(240)
    readonly property real padX: theme.px(10)
    readonly property real padY: theme.px(8)
    // the tallest a tip gets (title + 2 detail lines + tail): the Dock keeps this much headroom
    readonly property real maxHeight: 2 * padY + titleText.font.pixelSize * 1.3 + 2 * detailText.font.pixelSize * 1.35
                                      + theme.px(2) + tail

    width: body.width
    height: body.height + tail

    property real progress: 0
    onOpenChanged: {
        anim.stop()
        const d = theme.dur(open ? 120 : 80)
        if (d <= 0) { progress = open ? 1 : 0; return }
        anim.to = open ? 1 : 0
        anim.duration = d
        anim.easing.type = open ? Easing.OutCubic : Easing.InCubic
        anim.start()
    }
    NumberAnimation { id: anim; target: tip; property: "progress" }
    visible: progress > 0
    opacity: progress
    transform: Translate { y: (1 - tip.progress) * tip.theme.px(4) * (tip.below ? -1 : 1) }

    // dark: the elevated surface; light: one step darker than the islands so it reads over a card
    readonly property color fill: theme.dark ? theme.bgElevated : theme.surface
    readonly property color stroke: theme.alpha(theme.outline, theme.dark ? 0.6 : 0.45)

    Island {
        id: body
        theme: tip.theme
        y: tip.below ? tip.tail : 0
        width: content.implicitWidth + 2 * tip.padX
        height: content.implicitHeight + 2 * tip.padY
        radius: tip.theme.px(10)
        fill: tip.fill
        stroke: tip.stroke
    }

    // the tail: a small triangle in the fill colour, stroked on its two outer edges, laid over
    // the bubble's border so the outline runs around it
    Shape {
        id: tailShape
        readonly property real half: tip.tail + tip.theme.px(1)
        x: Math.round(Math.max(tip.theme.px(10), Math.min(tip.width - tip.theme.px(10), tip.tailX)) - half)
        y: tip.below ? 0 : body.height - 1
        width: 2 * half; height: tip.tail + 1
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: tip.fill
            strokeColor: tip.stroke
            strokeWidth: tip.theme.borderWidth
            joinStyle: ShapePath.RoundJoin
            startX: 0; startY: tip.below ? tailShape.height : 0
            PathLine { x: tailShape.half; y: tip.below ? 0 : tailShape.height }
            PathLine { x: tailShape.width; y: tip.below ? tailShape.height : 0 }
        }
    }

    Row {
        id: content
        x: tip.padX
        y: body.y + tip.padY
        spacing: tip.theme.px(7)
        Icon {
            id: glyph
            visible: tip.icon !== ""
            name: tip.icon
            size: tip.theme.fpx(14)
            stroke: tip.theme.iconStroke
            family: tip.theme.family
            color: tip.theme.text
            // centred on the title line
            y: Math.round((titleText.height - height) / 2)
        }
        Column {
            spacing: tip.theme.px(2)
            Text {
                id: titleText
                width: Math.min(implicitWidth, tip.maxTextWidth)
                text: tip.title
                elide: Text.ElideRight
                font.pixelSize: tip.theme.fpx(12.5)
                font.family: tip.theme.family
                font.weight: Font.Bold
                color: tip.theme.text
            }
            Text {
                id: detailText
                visible: tip.detail !== ""
                width: Math.min(implicitWidth, tip.maxTextWidth)
                text: tip.detail
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.pixelSize: tip.theme.fpx(11)
                font.family: tip.theme.family
                color: tip.theme.textMuted
            }
        }
    }
}
