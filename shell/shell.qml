import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    // ---- state from the daemon ----
    property var state: ({ mode: "", modes: [], pending: null, activity: {}, held: [], held_count: 0 })
    property string bin: Quickshell.shellDir + "/../bin/lockdock"
    readonly property string statePath: Quickshell.env("XDG_RUNTIME_DIR") + "/lockdock/state.json"

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
}
