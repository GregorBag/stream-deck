"""Шапка Synthwave Panel с аватаркой проекта."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from dj_poltorashka.ui.theme import avatar_pixmap


def create_brand_header() -> QFrame:
    header = QFrame()
    header.setObjectName("brand_header")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(18, 10, 18, 10)
    layout.setSpacing(18)
    avatar = QLabel()
    avatar.setPixmap(avatar_pixmap(72))
    avatar.setFixedSize(72, 72)
    layout.addWidget(avatar)

    titles = QVBoxLayout()
    titles.setSpacing(4)
    title = QLabel('<span style="color:#f448bd">DJ</span> POLTORASHKA')
    title.setObjectName("brand_title")
    titles.addWidget(title)
    subtitle = QLabel("S Y N T H W A V E   P A N E L")
    subtitle.setObjectName("brand_subtitle")
    titles.addWidget(subtitle)
    status = QLabel("Панель не подключена · доступен симулятор")
    status.setObjectName("panel_connection_status")
    titles.addWidget(status, alignment=Qt.AlignLeft)
    layout.addLayout(titles)
    layout.addStretch()
    return header
