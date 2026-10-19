import QtQuick
import QtQuick.Layouts

Rectangle {
    id: pad
    required property int sound_index
    required property var sound
    required property var page
    property color accent: sound ? sound.accent : "#39d9f4"
    objectName: "sound_button_" + sound_index
    radius: 6
    border.color: Qt.darker(accent, 2)
    gradient: Gradient {
        GradientStop { position: 0; color: "#1c2541" }
        GradientStop { position: 1; color: "#10182c" }
    }
    Rectangle { x: 10; y: 0; width: parent.width - 20; height: 2; color: pad.accent; opacity: 0.65 }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 8
        RowLayout {
            Text { objectName: "sound_name_" + pad.sound_index; Layout.fillWidth: true; text: pad.sound ? pad.sound.name : "Пусто"; color: "#e4eaff"; font.pixelSize: 14; font.bold: true; elide: Text.ElideRight }
            Image { source: pad.page.icons.music || ""; sourceSize.width: 18; sourceSize.height: 18; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
        }
        RowLayout {
            spacing: 5
            NeonButton {
                objectName: "sound_import_" + pad.sound_index
                Layout.fillWidth: true
                implicitHeight: 30
                text: pad.sound && pad.sound.assigned ? "Заменить" : "Импортировать"
                icon_url: pad.page.icons.plus || ""
                onClicked: pad.page.sound_import_requested(pad.sound_index)
            }
            NeonButton {
                objectName: "sound_clear_" + pad.sound_index
                implicitWidth: 32; implicitHeight: 30
                tooltip: "Очистить звук"
                icon_url: pad.page.icons.close || ""
                enabled: pad.sound ? pad.sound.assigned : false
                onClicked: pad.page.sound_clear_requested(pad.sound_index)
            }
        }
    }
}
