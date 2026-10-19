from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from dj_poltorashka.ui.elided_label import ElidedLabel


def test_elision_recomputes_after_shrinking_and_expanding(qtbot: QtBot) -> None:
    label = ElidedLabel("test_label")
    qtbot.addWidget(label.widget)
    text = "Микрофон подключённого аудиоустройства"
    label.set_text(text)
    label.widget.resize(110, label.widget.height())
    label.widget.show()
    QApplication.processEvents()

    assert label.widget.text().endswith("…")
    original_height = label.widget.height()
    label.widget.resize(label.widget.fontMetrics().horizontalAdvance(text) + 10, original_height)
    QApplication.processEvents()
    assert label.widget.text() == text
    assert label.widget.height() == original_height

    label.widget.resize(110, original_height)
    QApplication.processEvents()
    assert label.widget.text().endswith("…")
    assert label.widget.toolTip() == text
    assert label.widget.accessibleName() == text


def test_line_breaks_in_name_do_not_create_extra_lines(qtbot: QtBot) -> None:
    label = ElidedLabel("test_label")
    qtbot.addWidget(label.widget)
    label.widget.resize(600, label.widget.height())
    label.set_text("USB\nМикрофон\t<input>")
    label.widget.show()
    QApplication.processEvents()

    assert label.widget.text() == "USB Микрофон <input>"
    assert label.widget.toolTip() == "USB\nМикрофон\t<input>"
