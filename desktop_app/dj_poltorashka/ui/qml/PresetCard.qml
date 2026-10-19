import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property int preset_index
    required property var preset
    required property var page
    property color accent: preset ? preset.accent : "#a16aff"
    radius: 7
    border.color: Qt.darker(accent, 1.5)
    gradient: Gradient {
        GradientStop { position: 0; color: "#1d2039" }
        GradientStop { position: 1; color: "#101528" }
    }
    Rectangle { x: 1; y: 14; width: 2; height: parent.height - 28; color: card.accent; opacity: 0.7 }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 16; spacing: 10
        RowLayout {
            Text { Layout.fillWidth: true; text: "ПРЕСЕТ 0" + (card.preset_index + 1); color: card.accent; font.pixelSize: 10; font.letterSpacing: 2 }
            Image { source: card.page.icons.panel || ""; sourceSize.width: 24; sourceSize.height: 24; Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
        }
        Text { objectName: "preset_name_" + card.preset_index; Layout.fillWidth: true; text: card.preset ? card.preset.name : "Пусто"; color: "#f0ebff"; font.pixelSize: 20; font.weight: Font.DemiBold; elide: Text.ElideRight }
        Text { objectName: "preset_summary_" + card.preset_index; Layout.fillWidth: true; text: card.preset ? card.preset.summary : "Нет сохранённой настройки"; color: "#96a8ca"; font.pixelSize: 11; wrapMode: Text.WordWrap }
        Item { Layout.fillHeight: true }
        RowLayout {
            spacing: 7
            NeonButton { objectName: "preset_load_" + card.preset_index; text: "Загрузить"; icon_url: card.page.icons.download || ""; primary: true; accent: "#39d9f4"; enabled: card.preset ? card.preset.assigned : false; onClicked: card.page.load_preset_requested(card.preset_index) }
            NeonButton { objectName: "preset_edit_" + card.preset_index; text: "Редактировать"; icon_url: card.page.icons.edit || ""; enabled: card.preset ? card.preset.assigned : false; onClicked: card.page.edit_preset_requested(card.preset_index) }
        }
    }
}
