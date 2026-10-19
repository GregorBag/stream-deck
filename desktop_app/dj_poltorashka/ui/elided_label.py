"""Однострочная подпись с сокращением по доступной ширине."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel:
    def __init__(self, object_name: str):
        self._widget = QLabel()
        self._widget.setObjectName(object_name)
        self._widget.setProperty("role", "card_name")
        self._widget.setTextFormat(Qt.PlainText)
        self._widget.setWordWrap(False)
        self._widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._observer = QObject(self._widget)
        self._observer.eventFilter = self._handle_event
        self._widget.installEventFilter(self._observer)
        self.set_text("Не назначен")

    @property
    def widget(self) -> QLabel:
        return self._widget

    def set_text(self, text: str) -> None:
        self._widget.setToolTip(text)
        self._widget.setAccessibleName(text)
        self._refresh()

    def _handle_event(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Resize, QEvent.Show, QEvent.FontChange,
            QEvent.StyleChange, QEvent.ContentsRectChange,
        ):
            self._refresh()
        return False

    def _refresh(self) -> None:
        metrics = self._widget.fontMetrics()
        self._widget.setFixedHeight(metrics.height())
        text = " ".join(self._widget.toolTip().split())
        self._widget.setText(metrics.elidedText(
            text, Qt.ElideRight, self._widget.contentsRect().width(),
        ))
