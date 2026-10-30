import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Quickshell.Wayland
import Quickshell.Widgets

// Live window thumbnails for a hovered running app: an island-styled panel (Tip's fill and
// stroke, radius 14) with one card per window (at most theme.previewsMax, then "+N more"), and a
// tail pointing at the app. A card is a ScreencopyView of the Toplevel fitted into
// previews.width x previews.height, the window title (bold while activated) and the app icon;
// click activates the window, the corner x closes it. The Dock owns one per window and places it
// (x, y, tailX, below); `open` animates it in (opacity + 6 px slide, 140 ms OutCubic) and out
// (100 ms). `visible` stays true until it has faded out (the Dock masks it only while visible).
// Capture runs only while the panel is visible.
Item {
    id: panel
    required property var theme
    property var windows: []            // Toplevel objects (ToplevelManager)
    property string iconSource: ""      // the app's icon path ("" = theme icons.app_fallback)
    property bool open: false
    property bool below: false          // under the app (dock at the top): the tail points up
    property real tailX: width / 2      // the hovered app's centre, in panel coordinates
    readonly property bool hovered: hover.hovered
    signal activated()                  // a card was clicked (its window is focused)

    readonly property real tail: theme.px(4)
    readonly property real pad: theme.px(6)
    readonly property real cardPad: theme.px(6)
    readonly property real boxW: theme.px(theme.previewsWidth)
    readonly property real boxH: theme.px(theme.previewsHeight)
    readonly property real titleH: Math.ceil(theme.fpx(11.5) * 1.35)
    readonly property real cardW: boxW + 2 * cardPad
    readonly property real cardH: cardPad + boxH + theme.px(6) + titleH + cardPad
    readonly property real spacing: theme.px(4)
    readonly property int shownCount: Math.min(windows.length, theme.previewsMax)
    readonly property int moreCount: Math.max(0, windows.length - theme.previewsMax)
    // the panel's full height (tail included): the Dock keeps this much headroom
    readonly property real maxHeight: cardH + 2 * pad + tail
    // the panel's width for n cards (plus the "+N more" label when more is true)
    function widthFor(n, more) {
        return 2 * pad + n * cardW + Math.max(0, n - 1) * spacing + (more ? spacing + moreLabel.implicitWidth : 0)
    }

    width: widthFor(shownCount, moreCount > 0)
    height: body.height + tail

    property real progress: 0
    onOpenChanged: {
        anim.stop()
        const d = theme.dur(open ? 140 : 100)
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

    HoverHandler { id: hover }

    Island {
        id: body
        theme: panel.theme
        y: panel.below ? panel.tail : 0
        width: panel.width
        height: panel.cardH + 2 * panel.pad
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

    Row {
        x: panel.pad
        y: body.y + panel.pad
        spacing: panel.spacing

        Repeater {
            model: panel.windows.slice(0, panel.shownCount)
            delegate: Pressable {
                id: card
                required property var modelData     // a Toplevel
                theme: panel.theme
                width: panel.cardW; height: panel.cardH
                scale: pressScale
                onClicked: { card.modelData.activate(); panel.activated() }

                Rectangle {
                    anchors.fill: parent
                    radius: card.theme.px(10)
                    color: card.theme.surfaceHover
                    opacity: card.hoverProgress
                    visible: opacity > 0
                }

                // the thumbnail box: the capture fitted inside, centred, with rounded corners
                Item {
                    id: box
                    x: panel.cardPad; y: panel.cardPad
                    width: panel.boxW; height: panel.boxH

                    ScreencopyView {
                        id: view
                        anchors.centerIn: parent
                        captureSource: panel.visible ? card.modelData : null
                        live: true
                        paintCursor: false
                        constraintSize: Qt.size(box.width, box.height)
                        width: hasContent ? implicitWidth : box.width
                        height: hasContent ? implicitHeight : box.height
                        layer.enabled: true
                        layer.effect: MultiEffect {
                            maskEnabled: true
                            maskSource: viewMask
                            maskThresholdMin: 0.5
                            maskSpreadAtMin: 1.0
                        }
                    }
                    Item {
                        id: viewMask
                        width: view.width; height: view.height
                        anchors.centerIn: parent
                        layer.enabled: true
                        visible: false
                        Rectangle { anchors.fill: parent; radius: card.theme.px(8); color: "black" }
                    }
                    Rectangle {
                        visible: !view.hasContent
                        anchors.fill: parent
                        radius: card.theme.px(8)
                        color: card.theme.alpha(card.theme.surfaceHover, 0.5)
                        Text {
                            anchors.centerIn: parent
                            text: "no preview"
                            font.pixelSize: card.theme.fpx(11.5)
                            font.family: card.theme.family
                            color: card.theme.textMuted
                        }
                    }
                }

                // the app icon and the window title
                Row {
                    x: panel.cardPad
                    y: box.y + box.height + card.theme.px(6)
                    width: panel.boxW
                    spacing: card.theme.px(5)
                    Item {
                        id: appIcon
                        readonly property real s: card.theme.px(14)
                        width: s; height: s
                        y: Math.round((title.height - s) / 2)
                        IconImage {
                            visible: panel.iconSource !== ""
                            anchors.fill: parent
                            implicitSize: appIcon.s
                            source: panel.iconSource
                        }
                        Icon {
                            visible: panel.iconSource === ""
                            anchors.centerIn: parent
                            name: card.theme.icon("app_fallback", "icona:layers")
                            size: appIcon.s
                            stroke: card.theme.iconStroke
                            family: card.theme.family
                            color: card.theme.textMuted
                        }
                    }
                    Text {
                        id: title
                        width: panel.boxW - appIcon.width - parent.spacing
                        height: panel.titleH
                        verticalAlignment: Text.AlignVCenter
                        text: card.modelData.title || card.modelData.appId || ""
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        font.pixelSize: card.theme.fpx(11.5)
                        font.family: card.theme.family
                        font.weight: card.modelData.activated ? Font.Bold : Font.Normal
                        color: card.theme.text
                    }
                }

                // close: a small round button on the top-right corner, shown while the card is hovered
                Pressable {
                    id: closeBtn
                    theme: card.theme
                    z: 101                                // over the card's own MouseArea (z 100)
                    readonly property real s: card.theme.px(20)
                    width: s; height: s
                    x: card.width - s - card.theme.px(2)
                    y: card.theme.px(2)
                    scale: pressScale
                    opacity: Math.max(card.hoverProgress, closeBtn.hoverProgress)
                    visible: opacity > 0
                    onClicked: card.modelData.close()
                    Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        color: closeBtn.hovered ? card.theme.surfaceHover : panel.fill
                        border.width: card.theme.borderWidth
                        border.color: panel.stroke
                    }
                    Icon {
                        anchors.centerIn: parent
                        name: card.theme.icon("close", "icona:x")
                        size: card.theme.px(12)
                        stroke: card.theme.iconStroke
                        family: card.theme.family
                        color: card.theme.text
                    }
                }
            }
        }

        Text {
            id: moreLabel
            visible: panel.moreCount > 0
            height: panel.cardH
            leftPadding: panel.theme.px(4); rightPadding: panel.theme.px(4)
            verticalAlignment: Text.AlignVCenter
            text: "+" + panel.moreCount + " more"
            font.pixelSize: panel.theme.fpx(11.5)
            font.family: panel.theme.family
            color: panel.theme.textMuted
        }
    }
}
