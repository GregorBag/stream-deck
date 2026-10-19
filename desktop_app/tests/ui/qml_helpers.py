from PySide6.QtCore import QPointF, Qt
from PySide6.QtQuick import QQuickItem


def find_item(root: QQuickItem, name: str) -> QQuickItem:
    if root.objectName() == name:
        return root
    for child in root.childItems():
        try:
            return find_item(child, name)
        except LookupError:
            pass
    raise LookupError(name)


def click_item(qtbot, widget, item: QQuickItem) -> None:
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    qtbot.mouseClick(widget, Qt.LeftButton, pos=point.toPoint())


def value(root, name):
    result = root.property(name)
    return result.toVariant() if hasattr(result, "toVariant") else result
