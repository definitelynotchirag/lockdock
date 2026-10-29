import QtQuick

// The pet's current mood from its sprite pack, looping the mood's frames at its fps.
// Size it from the parent; pixel packs stay crisp at any size (smooth: false).
Image {
    id: sprite
    required property var pet          // st.pet: {mood, pack_dir, manifest, ...}
    property int renderSize: pet.size || 48   // rasterise at this size, then scale without smoothing

    readonly property string mood: pet.mood || "content"
    readonly property var moodDef: ((pet.manifest || {}).moods || {})[mood] || ({ frames: [], fps: 1 })
    readonly property var frames: moodDef.frames || []
    property int frame: 0
    onMoodChanged: frame = 0

    source: pet.pack_dir && frames.length > 0 ? "file://" + pet.pack_dir + "/" + frames[frame % frames.length] : ""
    sourceSize: Qt.size(renderSize, renderSize)
    fillMode: Image.PreserveAspectFit
    smooth: false

    Timer {
        interval: Math.round(1000 / Math.max(0.5, sprite.moodDef.fps || 2))
        repeat: true
        running: sprite.visible && sprite.frames.length > 1
        onTriggered: sprite.frame = (sprite.frame + 1) % sprite.frames.length
    }
}
