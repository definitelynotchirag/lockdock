import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Widgets

// One icon, by name:
//   "icona:<slug>"  an Icona SVG from shell/icons/icona/ (see INDEX.md there), tinted with `color`
//   "brand:<slug>"  a logo from shell/icons/brand/ (claude, openai, gemini, copilot, opencode), tinted
//   a theme icon    a freedesktop icon name ("firefox", "dialog-warning"), drawn as is
//   anything else   a text glyph or emoji ("☕", "✻"), drawn as Text in `color`
// The Icona SVGs stroke with currentColor: the file is read once, currentColor replaced by the
// colour, and the result handed to an Image as a data: URL, so the tint is exact (no shader).
// An unknown icona slug draws a small dot and logs once.
Item {
    id: icon
    property string name: ""
    property color color: "white"
    property real size: 16
    property string family: ""        // font for text glyphs ("" = default)
    property real stroke: 1.75         // line width on the 24 px grid (Icona draws 1.5); theme.iconStroke

    readonly property bool isBrand: name.indexOf("brand:") === 0
    readonly property bool isIcona: name.indexOf("icona:") === 0 || isBrand   // both are tinted SVG files
    readonly property string slug: isIcona ? name.slice(6) : ""
    readonly property string svgDir: isBrand ? "brand" : "icona"
    // a bare freedesktop icon name (letters, digits, - _ .; 3+ chars) that the icon theme has
    readonly property string themePath: !isIcona && /^[A-Za-z0-9][A-Za-z0-9._-]{2,}$/.test(name)
                                        ? Quickshell.iconPath(name, true) : ""
    property string svg: ""
    property bool missing: false

    implicitWidth: glyph.visible ? Math.max(size, glyph.implicitWidth) : size
    implicitHeight: size

    // opaque #rrggbb for the SVG; the colour's alpha goes to `opacity` of the image
    readonly property string hex: Qt.rgba(color.r, color.g, color.b, 1).toString()

    FileView {
        id: file
        path: icon.isIcona ? Quickshell.shellDir + "/icons/" + icon.svgDir + "/" + icon.slug + ".svg" : ""
        blockLoading: true
        printErrors: false
        onLoaded: { icon.svg = text(); icon.missing = false }
        onLoadFailed: {
            icon.svg = ""
            icon.missing = true
            console.log("lockdock: unknown icon " + icon.name + " (no " + path + ")")
        }
    }

    Image {
        anchors.centerIn: parent
        visible: icon.isIcona && icon.svg !== ""
        width: icon.size; height: icon.size
        // rasterised at the drawn size: sharper at 16-20 px than 2x + downscale (tested)
        sourceSize: Qt.size(Math.round(icon.size), Math.round(icon.size))
        smooth: true
        opacity: icon.color.a
        source: visible ? "data:image/svg+xml;utf8," + encodeURIComponent(icon.svg.replace(/currentColor/g, icon.hex).replace(/stroke-width="1.5"/g, "stroke-width=\"" + icon.stroke + "\"")) : ""
    }

    IconImage {
        anchors.centerIn: parent
        visible: icon.themePath !== ""
        implicitSize: icon.size
        source: icon.themePath
    }

    Rectangle {
        visible: icon.isIcona && icon.missing
        anchors.centerIn: parent
        width: Math.round(icon.size * 0.35); height: width; radius: width / 2
        color: icon.color
    }

    Text {
        id: glyph
        visible: !icon.isIcona && icon.themePath === "" && icon.name !== ""
        anchors.centerIn: parent
        text: icon.name
        font.pixelSize: Math.round(icon.size * 0.88)   // a glyph at the old text sizes (16 in an 18 px slot)
        font.family: icon.family !== "" ? icon.family : Qt.application.font.family
        color: icon.color
    }
}
