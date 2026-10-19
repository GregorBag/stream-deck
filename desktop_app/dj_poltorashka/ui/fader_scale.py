"""Числа и штрихи шкалы, выровненные по ходу ручки ползунка."""

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QSlider, QStyle, QStyleOptionSlider


class FaderScale:
    def __init__(self, slider: QSlider):
        self._slider = slider
        self._widget = QLabel()
        self._widget.setProperty("role", "muted")
        self._widget.setFixedWidth(54)
        self._widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        self._widget.setAccessibleName("Шкала громкости от 0 до 100")
        self._observer = QObject(self._widget)
        self._observer.eventFilter = self._handle_event
        self._widget.installEventFilter(self._observer)
        slider.installEventFilter(self._observer)

    @property
    def widget(self) -> QLabel:
        return self._widget

    def _handle_event(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Resize, QEvent.Show, QEvent.FontChange,
            QEvent.StyleChange, QEvent.EnabledChange,
        ):
            self._refresh()
        return False

    def _refresh(self) -> None:
        if self._widget.height() <= 0:
            return
        option = QStyleOptionSlider()
        self._slider.initStyleOption(option)
        option.sliderPosition = option.minimum
        low = self._slider.style().subControlRect(
            QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self._slider,
        ).center().y()
        option.sliderPosition = option.maximum
        high = self._slider.style().subControlRect(
            QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self._slider,
        ).center().y()
        ratio = self._widget.devicePixelRatioF()
        pixmap = QPixmap(round(54 * ratio), round(self._widget.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self._widget.font())
        text_height = self._widget.fontMetrics().height()
        offset = (self._widget.height() - self._slider.height()) / 2
        for value in range(0, 101, 5):
            position = offset + low + (high - low) * value / 100
            major = value % 25 == 0
            painter.setPen(QColor("#8197c3" if major else "#4e648e"))
            painter.drawLine(QPointF(40 if major else 46, position), QPointF(53, position))
            if major:
                painter.setPen(QColor("#b6c7eb"))
                painter.drawText(
                    QRectF(0, position - text_height / 2, 33, text_height),
                    Qt.AlignRight | Qt.AlignVCenter, str(value),
                )
        painter.end()
        self._widget.setPixmap(pixmap)
