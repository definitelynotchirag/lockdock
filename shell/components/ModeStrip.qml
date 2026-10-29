import QtQuick
import QtQuick.Layouts

// One pill per mode; the active one is wide, a pending one shows the countdown.
RowLayout {
    id: strip
    required property var st          // state.json
    required property real now        // ms clock for the countdown
    required property bool offTask
    required property var theme
    signal modeClicked(string modeId)

    spacing: theme.px(6)

    Repeater {
        model: strip.st.modes || []
        ModePill {
            required property var modelData
            theme: strip.theme
            mode: modelData
            active: modelData.id === strip.st.mode
            pending: strip.st.pending && strip.st.pending.mode === modelData.id ? strip.st.pending : null
            now: strip.now
            offTask: strip.offTask
            onClicked: strip.modeClicked(modelData.id)
        }
    }
}
