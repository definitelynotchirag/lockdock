import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets

// One decision card (an entry of state.json `prompts`), drawn on an Island:
//   [icon] title                 (bold)
//          subtitle              (muted)
//   body (up to 3 lines)
//   [! tag label · detail]       (tinted by tag.level: urgent danger, info accent, ok success)
//                 [plain] [primary]
// Icons come from theme `icons` (card_<kind> when the prompt has no desktop icon, tag_<level>).
// kind "verdict" is a compact one-line toast with no buttons. `actionClicked(actionId)` fires
// on a button; the stack sends the command and hides the card.
Item {
    id: card
    required property var theme
    required property var prompt
    property real maxWidth: theme.px(theme.promptsWidth)
    signal actionClicked(string actionId)

    readonly property bool toast: prompt.kind === "verdict"
    readonly property var tag: prompt.tag || null
    readonly property var actions: prompt.actions || []
    readonly property bool urgent: tag !== null && tag.level === "urgent"
    readonly property string fallbackGlyph: prompt.kind === "notification" ? theme.icon("card_notification", "icona:bell")
                                          : prompt.kind === "site" ? theme.icon("card_site", "icona:compass")
                                          : theme.icon("card_verdict", "icona:check-circle")
    readonly property string iconSource: prompt.icon ? Quickshell.iconPath(prompt.icon, true) : ""
    readonly property real pad: theme.px(16)

    function tagColor(level) {
        return level === "urgent" ? theme.danger : level === "ok" ? theme.success : theme.paletteAccent
    }
    function tagGlyph(level) {
        return level === "urgent" ? theme.icon("tag_urgent", "icona:alert")
             : level === "ok" ? theme.icon("tag_ok", "icona:check-circle") : theme.icon("tag_info", "icona:info")
    }
    function tagText(t) { return t ? (t.label || "") + (t.detail ? " · " + t.detail : "") : "" }

    implicitWidth: toast ? Math.min(toastRow.implicitWidth + 2 * theme.px(14), maxWidth * 1.45) : maxWidth
    implicitHeight: toast ? theme.px(38) : full.implicitHeight + 2 * pad
    width: implicitWidth; height: implicitHeight

    Island {
        anchors.fill: parent
        theme: card.theme
        radius: card.toast ? height / 2 : card.theme.px(Math.min(card.theme.radius, 18))
    }

    // ---- the icon: the desktop icon, else a glyph by kind ----
    component Badge: Item {
        id: badge
        property real size: card.theme.px(36)
        implicitWidth: size; implicitHeight: size
        Rectangle {
            anchors.fill: parent
            radius: badge.size * 0.3
            visible: card.iconSource === ""
            color: card.theme.alpha(card.theme.surfaceHover, card.theme.dark ? 0.9 : 0.7)
            Icon {
                anchors.centerIn: parent
                name: card.fallbackGlyph
                size: Math.max(card.theme.px(14), Math.round(badge.size * 0.56))
                stroke: card.theme.iconStroke
                family: card.theme.family
                color: card.theme.text
            }
        }
        IconImage {
            anchors.fill: parent
            visible: card.iconSource !== ""
            implicitSize: badge.size
            source: card.iconSource
        }
    }

    // ---- verdict toast: one line ----
    RowLayout {
        id: toastRow
        visible: card.toast
        anchors.verticalCenter: parent.verticalCenter
        x: card.theme.px(10)
        width: card.width - card.theme.px(10) - card.theme.px(14)
        spacing: card.theme.px(8)
        Badge { size: card.theme.px(22); Layout.alignment: Qt.AlignVCenter }
        Text {
            id: toastText
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            textFormat: Text.StyledText
            elide: Text.ElideRight
            maximumLineCount: 1
            font.pixelSize: card.theme.fpx(12)
            font.family: card.theme.family
            color: card.theme.textMuted
            readonly property string sep: "  ·  "
            function esc(s) { return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
            text: "<b><font color='" + card.theme.text + "'>" + esc(card.prompt.title) + "</font></b>"
                  + (card.prompt.subtitle ? sep + esc(card.prompt.subtitle) : "")
        }
        // the tag: icon + label (· detail), tinted by level
        Icon {
            visible: card.tag !== null && name !== ""
            name: card.tag ? card.tagGlyph(card.tag.level) : ""
            size: card.theme.fpx(15)
            stroke: card.theme.iconStroke
            family: card.theme.family
            color: card.tag ? card.tagColor(card.tag.level) : card.theme.text
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: card.theme.px(2)
        }
        Text {
            visible: card.tag !== null
            Layout.alignment: Qt.AlignVCenter
            Layout.maximumWidth: card.maxWidth * 0.6
            textFormat: Text.StyledText
            elide: Text.ElideRight
            maximumLineCount: 1
            font.pixelSize: card.theme.fpx(12)
            font.family: card.theme.family
            color: card.tag ? card.tagColor(card.tag.level) : card.theme.text
            text: card.tag ? "<b>" + toastText.esc(card.tag.label) + "</b>"
                             + (card.tag.detail ? toastText.sep + toastText.esc(card.tag.detail) : "") : ""
        }
    }

    // ---- full card ----
    ColumnLayout {
        id: full
        visible: !card.toast
        x: card.pad; y: card.pad
        width: card.width - 2 * card.pad
        spacing: card.theme.px(10)

        RowLayout {
            spacing: card.theme.px(12)
            Layout.fillWidth: true
            Badge { Layout.alignment: Qt.AlignVCenter }
            ColumnLayout {
                spacing: card.theme.px(1)
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                Text {
                    text: card.prompt.title || ""
                    font.pixelSize: card.theme.fpx(15)
                    font.family: card.theme.family
                    font.weight: Font.Bold
                    color: card.theme.text
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Text {
                    visible: text !== ""
                    text: card.prompt.subtitle || ""
                    font.pixelSize: card.theme.fpx(12)
                    font.family: card.theme.family
                    color: card.theme.textMuted
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }

        Text {
            visible: text !== ""
            text: card.prompt.body || ""
            font.pixelSize: card.theme.fpx(13)
            font.family: card.theme.family
            color: card.theme.text
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
            lineHeight: 1.1
            Layout.fillWidth: true
        }

        // tag row: tinted by level
        Rectangle {
            visible: card.tag !== null
            readonly property color tint: card.tag ? card.tagColor(card.tag.level) : card.theme.paletteAccent
            implicitHeight: tagRow.implicitHeight + card.theme.px(12)
            radius: card.theme.px(9)
            color: card.theme.alpha(tint, card.theme.dark ? 0.16 : 0.12)
            Layout.fillWidth: true
            RowLayout {
                id: tagRow
                anchors.verticalCenter: parent.verticalCenter
                x: card.theme.px(10)
                width: parent.width - card.theme.px(20)
                spacing: card.theme.px(6)
                Icon {
                    visible: name !== ""
                    name: card.tag ? card.tagGlyph(card.tag.level) : ""
                    size: card.theme.fpx(16)
                    stroke: card.theme.iconStroke
                    family: card.theme.family
                    color: parent.parent.tint
                    Layout.alignment: Qt.AlignVCenter
                }
                Text {
                    text: card.tag ? card.tag.label || "" : ""
                    font.pixelSize: card.theme.fpx(12)
                    font.family: card.theme.family
                    font.weight: Font.DemiBold
                    color: parent.parent.tint
                }
                Text {
                    visible: card.tag !== null && !!card.tag.detail
                    text: card.tag && card.tag.detail ? "· " + card.tag.detail : ""
                    font.pixelSize: card.theme.fpx(12)
                    font.family: card.theme.family
                    color: parent.parent.tint
                    opacity: 0.85
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }

        // actions, right-aligned
        RowLayout {
            visible: card.actions.length > 0
            spacing: card.theme.px(8)
            Layout.fillWidth: true
            Layout.topMargin: card.theme.px(2)
            Item { Layout.fillWidth: true }
            Repeater {
                model: card.actions
                delegate: Pressable {
                    id: btn
                    theme: card.theme
                    required property var modelData
                    readonly property bool primary: modelData.style === "primary"
                    readonly property color fill: !primary ? card.theme.surfaceHover
                                                  : card.urgent ? card.theme.danger : card.theme.paletteAccent
                    readonly property color ink: !primary ? card.theme.text
                                                 : card.urgent ? card.theme.dangerInk : card.theme.accentInk
                    implicitHeight: card.theme.px(34)
                    implicitWidth: label.implicitWidth + card.theme.px(32)
                    Layout.maximumWidth: full.width
                    scale: pressScale
                    onClicked: card.actionClicked(btn.modelData.id)
                    Rectangle {
                        anchors.fill: parent
                        radius: height / 2
                        color: Qt.tint(btn.fill, card.theme.alpha(btn.ink, 0.10 * btn.hoverProgress))
                    }
                    Text {
                        id: label
                        anchors.centerIn: parent
                        width: Math.min(implicitWidth, btn.width - card.theme.px(20))
                        elide: Text.ElideRight
                        text: btn.modelData.label || btn.modelData.id
                        font.pixelSize: card.theme.fpx(13)
                        font.family: card.theme.family
                        font.weight: btn.primary ? Font.DemiBold : Font.Medium
                        color: btn.ink
                        transform: Translate { y: btn.lift(1) }
                    }
                }
            }
        }
    }
}
