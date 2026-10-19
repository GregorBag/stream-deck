import QtQuick
import QtQuick.Controls.Basic

Slider {
    id: control
    property real external_value: 0
    property color accent: "#f448bd"
    property bool pending_update: false
    from: 0
    to: 100
    stepSize: 1
    orientation: Qt.Vertical
    padding: 0
    implicitWidth: 34
    implicitHeight: 270
    focusPolicy: Qt.StrongFocus
    function sync_value() {
        if (pressed) pending_update = true
        else value = external_value
    }
    onExternal_valueChanged: sync_value()
    onPressedChanged: {
        if (!pressed && pending_update) {
            pending_update = false
            value = external_value
        }
    }
    Component.onCompleted: value = external_value
    Accessible.name: "Громкость канала"
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
            const target = event.key === Qt.Key_Home ? from : to
            if (value !== target) { value = target; moved() }
            event.accepted = true
        }
    }
    background: Item {
        Rectangle {
            x: (control.width - width) / 2
            y: 0
            width: 12
            height: control.height
            color: "#050916"
            border.color: control.activeFocus ? "#d6e7ff" : "#33416b"
            radius: 6
            Rectangle {
                x: 3; width: 6
                y: control.handle.y + control.handle.height / 2
                height: Math.max(0, parent.height - y - 1)
                radius: 3
                color: control.enabled ? control.accent : "#48516a"
                opacity: 0.85
            }
        }
        Repeater {
            model: 21
            delegate: Item {
                required property int index
                x: -61
                y: 12 + index / 20 * (control.height - 24)
                width: 51; height: 1
                Rectangle {
                    anchors.right: parent.right
                    width: index % 5 === 0 ? 17 : 8
                    height: index % 5 === 0 ? 2 : 1
                    color: index % 5 === 0 ? "#889bc6" : "#526993"
                }
                Text {
                    visible: index % 5 === 0
                    text: 100 - index * 5
                    width: 30
                    horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#aebddd"
                    font.family: "Consolas"
                    font.pixelSize: 11
                }
            }
        }
        Column {
            x: control.width + 17
            y: 12
            spacing: 2
            Repeater {
                model: 40
                delegate: Rectangle {
                    required property int index
                    width: 12
                    height: Math.max(1, (control.height - 24 - 39 * 2) / 40)
                    color: control.enabled && (40 - index) * 2.5 <= control.value ? control.accent : "#1b2540"
                    opacity: control.enabled ? 0.9 : 0.4
                }
            }
        }
    }
    handle: Rectangle {
        objectName: "fader_handle"
        x: (control.width - width) / 2
        y: control.visualPosition * (control.height - height)
        width: 32
        height: 24
        radius: 4
        border.color: control.enabled ? Qt.lighter(control.accent, 1.45) : "#7c88a3"
        border.width: control.hovered || control.pressed ? 2 : 1
        gradient: Gradient {
            GradientStop { position: 0; color: control.enabled ? Qt.lighter(control.accent, 1.15) : "#5c6985" }
            GradientStop { position: 0.45; color: control.enabled ? control.accent : "#49536b" }
            GradientStop { position: 1; color: control.enabled ? Qt.darker(control.accent, 1.8) : "#354056" }
        }
        Rectangle { x: 1; y: parent.height / 2 - 1; width: parent.width - 2; height: 2; color: "#f3fcff"; opacity: control.enabled ? 0.95 : 0.3 }
    }
}
