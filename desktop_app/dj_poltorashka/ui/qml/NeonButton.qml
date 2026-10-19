import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property color accent: "#39d9f4"
    property bool primary: false
    property string icon_name: ""
    property string icon_url: ""
    property string tooltip: ""
    implicitHeight: 36
    implicitWidth: Math.max(36, contentItem.implicitWidth + 22)
    hoverEnabled: true
    leftPadding: text.length ? 9 : 6
    rightPadding: text.length ? 9 : 6
    topPadding: 6
    bottomPadding: 6
    Accessible.name: text.length ? text : tooltip
    ToolTip.visible: hovered && (tooltip.length > 0 || label.truncated)
    ToolTip.text: tooltip.length ? tooltip : text
    contentItem: Item {
        implicitWidth: label.implicitWidth + (glyph.visible ? 25 : 0)
        implicitHeight: Math.max(18, label.implicitHeight)
        clip: true
        opacity: control.enabled ? 1 : 0.35
        Image {
            id: glyph
            visible: control.icon_url.length > 0
            source: control.icon_url
            sourceSize.width: 18
            sourceSize.height: 18
            width: visible ? 18 : 0
            height: 18
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            anchors.left: glyph.visible ? glyph.right : parent.left
            anchors.leftMargin: glyph.visible ? 7 : 0
            anchors.right: parent.right
            text: control.text
            elide: Text.ElideRight
            color: "#8aeafa"
            font.family: "Segoe UI"
            font.pixelSize: 12
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    background: Rectangle {
        radius: 5
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? "#ffffff" : control.accent
        opacity: control.enabled ? 1 : 0.35
        gradient: Gradient {
            GradientStop { position: 0; color: control.down ? "#20546b" : control.hovered ? "#1c4357" : control.primary ? "#153449" : "#14283c" }
            GradientStop { position: 1; color: "#11182d" }
        }
        Rectangle { x: 2; y: 1; width: parent.width - 4; height: 1; color: "#ffffff"; opacity: 0.09 }
    }
}
