import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

Rectangle {
    id: screen
    objectName: "configuration_root"
    color: "#090d20"
    property var channels: []
    property var sounds: []
    property var presets: []
    property var icons: ({})
    property int render_revision: 0
    property url background_url
    property string microphone_status: "Виртуальный микрофон: состояние ещё не определено"
    signal channel_kind_changed(int index, string kind)
    signal application_requested(int index)
    signal volume_changed(int index, real volume)
    signal mute_toggled(int index)
    signal sound_import_requested(int index)
    signal sound_clear_requested(int index)
    signal save_preset_requested()
    signal load_preset_requested(int index)
    signal edit_preset_requested(int index)

    function reveal_item(item) {
        if (!item || !scroll.contentItem || !scroll.contentItem.contentItem) return
        const flick = scroll.contentItem
        let ancestor = item
        while (ancestor && ancestor !== flick.contentItem) ancestor = ancestor.parent
        if (!ancestor) return
        const position = item.mapToItem(flick.contentItem, 0, 0)
        let x = flick.contentX
        let y = flick.contentY
        if (position.x < x + 8) x = position.x - 8
        else if (position.x + item.width > x + flick.width - 8) x = position.x + item.width - flick.width + 8
        if (position.y < y + 8) y = position.y - 8
        else if (position.y + item.height > y + flick.height - 8) y = position.y + item.height - flick.height + 8
        flick.contentX = Math.max(0, Math.min(x, flick.contentWidth - flick.width))
        flick.contentY = Math.max(0, Math.min(y, flick.contentHeight - flick.height))
    }
    Connections {
        target: screen.Window.window
        function onActiveFocusItemChanged() { screen.reveal_item(target.activeFocusItem) }
    }

    ScrollView {
        id: scroll
        anchors.fill: parent
        clip: true
        contentWidth: Math.max(1050, availableWidth)
        contentHeight: Math.max(660, availableHeight)
        ScrollBar.horizontal.policy: contentWidth > availableWidth ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: contentHeight > availableHeight ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
        Item {
            width: scroll.contentWidth
            height: scroll.contentHeight
            Image { anchors.fill: parent; source: screen.background_url; opacity: 0.18; fillMode: Image.Tile }
            RowLayout {
                anchors.fill: parent
                anchors.bottomMargin: 12
                spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 4
                            Text { text: "Активная настройка"; font.pixelSize: 20; font.weight: Font.DemiBold; color: "#e9eaff" }
                            Text { objectName: "virtual_microphone_status"; Layout.fillWidth: true; text: screen.microphone_status; color: "#a4b4d5"; font.pixelSize: 11; elide: Text.ElideRight }
                        }
                        NeonButton { objectName: "save_preset_button"; text: "Сохранить в пресет"; icon_url: screen.icons.save || ""; primary: true; accent: "#39d9f4"; onClicked: screen.save_preset_requested() }
                    }
                    RowLayout {
                        objectName: "channels_container"
                        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                        Repeater {
                            model: 4
                            ChannelCard {
                                required property int index
                                channel_index: index
                                channel: screen.channels[index] || null
                                page: screen
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumWidth: 170
                            }
                        }
                    }
                    GridLayout {
                        objectName: "sounds_container"
                        columns: 4; rowSpacing: 10; columnSpacing: 12
                        Layout.fillWidth: true
                        Repeater {
                            model: 8
                            SoundPad {
                                required property int index
                                sound_index: index
                                sound: screen.sounds[index] || null
                                page: screen
                                Layout.fillWidth: true
                                Layout.preferredHeight: 78
                            }
                        }
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 302
                    Layout.fillHeight: true
                    radius: 8; color: "#0c1225"; border.color: "#2c3859"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 12
                        Text { text: "Пресеты"; color: "#e9eaff"; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.bottomMargin: 3 }
                        Repeater {
                            model: 3
                            PresetCard {
                                required property int index
                                preset_index: index
                                preset: screen.presets[index] || null
                                page: screen
                                Layout.fillWidth: true; Layout.fillHeight: true
                                Layout.minimumHeight: 165
                            }
                        }
                    }
                }
            }
        }
    }
}
