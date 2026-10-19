import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: card
    required property int channel_index
    required property var channel
    required property var page
    property color accent: channel ? channel.accent : "#f448bd"
    objectName: "channel_card_" + channel_index
    radius: 8
    border.color: Qt.darker(accent, 1.7)
    Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 10; color: "transparent"; border.width: 2; border.color: card.accent; opacity: 0.07; z: -1 }
    gradient: Gradient {
        GradientStop { position: 0; color: "#182039" }
        GradientStop { position: 0.24; color: "#10182d" }
        GradientStop { position: 1; color: "#0c1225" }
    }
    Rectangle { x: 1; y: 1; width: parent.width - 2; height: 3; radius: 2; color: card.accent; opacity: 0.75 }
    Connections {
        target: card.page
        function onRender_revisionChanged() {
            kind_combo.currentIndex = card.channel ? kind_combo.kinds.indexOf(card.channel.kind) : 0
            fader.sync_value()
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6
        Text { text: "КАНАЛ 0" + (card.channel_index + 1); color: card.accent; font.pixelSize: 10; font.letterSpacing: 2 }
        Text {
            objectName: "channel_name_" + card.channel_index
            Layout.fillWidth: true
            Layout.preferredHeight: 23
            text: card.channel ? card.channel.name : "Не назначен"
            elide: Text.ElideRight
            maximumLineCount: 1
            color: "#edf0ff"
            font.family: "Segoe UI"
            font.pixelSize: 18
            font.weight: Font.DemiBold
            ToolTip.visible: name_hover.hovered && truncated
            ToolTip.text: text
            HoverHandler { id: name_hover }
        }
        ComboBox {
            id: kind_combo
            objectName: "channel_kind_" + card.channel_index
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            property var kinds: ["unassigned", "master", "application", "microphone"]
            model: ["Не назначен", "Общая громкость", "Программа", "Микрофон"]
            currentIndex: card.channel ? kinds.indexOf(card.channel.kind) : 0
            onActivated: card.page.channel_kind_changed(card.channel_index, kinds[currentIndex])
            font.family: "Segoe UI"
            font.pixelSize: 12
            palette.text: "#d9e3fa"
            palette.buttonText: "#d9e3fa"
            palette.base: "#10182d"
            palette.window: "#10182d"
            palette.highlight: card.accent
            background: Rectangle { radius: 4; color: "#0b1124"; border.color: kind_combo.activeFocus ? card.accent : "#36456d" }
            contentItem: Text { leftPadding: 9; rightPadding: 23; text: kind_combo.displayText; color: "#d4dff5"; font: kind_combo.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
            indicator: Text { x: kind_combo.width - 22; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: "#a9badd"; font.pixelSize: 18 }
        }
        NeonButton {
            objectName: "application_button_" + card.channel_index
            Layout.fillWidth: true
            text: "Выбрать программу"
            implicitHeight: 30
            enabled: card.channel ? card.channel.application_enabled : false
            icon_url: card.page.icons.app || ""
            onClicked: card.page.application_requested(card.channel_index)
        }
        Text {
            objectName: "channel_status_" + card.channel_index
            Layout.fillWidth: true
            Layout.preferredHeight: 12
            text: card.channel ? card.channel.availability_text : ""
            color: "#8b9dbf"; font.pixelSize: 10; elide: Text.ElideRight
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 160
            Fader {
                id: fader
                objectName: "volume_slider_" + card.channel_index
                x: (parent.width - width) / 2 + 12
                width: 34
                height: parent.height
                enabled: card.channel ? card.channel.assigned : false
                accent: card.accent
                external_value: card.channel ? card.channel.volume : 0
                onMoved: card.page.volume_changed(card.channel_index, value / 100)
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            color: "#080f20"; radius: 4; border.color: Qt.darker(card.accent, 2.7)
            Text {
                objectName: "volume_value_" + card.channel_index
                anchors.centerIn: parent; text: Math.round(fader.value) + "%"
                color: card.accent; font.family: "Consolas"; font.pixelSize: 22; font.bold: true
            }
        }
        NeonButton {
            objectName: "mute_button_" + card.channel_index
            Layout.fillWidth: true
            implicitHeight: 34
            text: card.channel && card.channel.muted ? "Включить звук" : "Заглушить"
            icon_name: card.channel ? card.channel.icon_name : "speaker"
            icon_url: card.page.icons[icon_name] || ""
            primary: card.channel ? card.channel.muted : false
            accent: "#39d9f4"
            enabled: card.channel ? card.channel.assigned : false
            onClicked: card.page.mute_toggled(card.channel_index)
        }
    }
}
