import QtQuick
import Quickshell
import Quickshell.Io
import "components"

ShellRoot {
    id: root

    // ---- state from the daemon ----
    property var state: ({ mode: "", modes: [], pending: null, activity: {}, held: [], held_count: 0, agents: [], pet: {}, theme: {} })
    property string bin: Quickshell.shellDir + "/../bin/lockdock"
    readonly property string instance: Quickshell.env("LOCKDOCK_INSTANCE") || ""
    readonly property string statePath: Quickshell.env("XDG_RUNTIME_DIR") + "/lockdock" + (instance ? "-" + instance : "") + "/state.json"

    function send(args) { Quickshell.execDetached([root.bin].concat(args)) }

    FileView {
        id: stateFile
        path: root.statePath
        watchChanges: true
        blockLoading: true
        onFileChanged: reload()
        onLoaded: {
            try { root.state = JSON.parse(text()) } catch (e) { console.log("lockdock: bad state.json", e) }
        }
        onLoadFailed: retry.start()
    }
    Timer { id: retry; interval: 1500; onTriggered: stateFile.reload() }

    Variants {
        model: Quickshell.screens
        Dock {
            required property var modelData
            screen: modelData
            shell: root
        }
    }

    // the pet grown past the dock: a click-through overlay per screen
    Variants {
        model: Quickshell.screens
        PetOverlay {
            required property var modelData
            screen: modelData
            st: root.state
        }
    }
}
