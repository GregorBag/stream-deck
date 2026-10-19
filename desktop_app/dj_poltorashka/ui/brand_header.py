"""Шапка Synthwave Panel с аватаркой проекта."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTabBar, QVBoxLayout

from dj_poltorashka.ui.theme import avatar_pixmap


def create_brand_header(navigation: QTabBar) -> QFrame:
    header = QFrame()
    header.setObjectName("brand_header")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(16, 8, 16, 8)
    layout.setSpacing(14)
    avatar = QLabel()
    avatar.setPixmap(avatar_pixmap(56))
    avatar.setFixedSize(56, 56)
    layout.addWidget(avatar)

    titles = QVBoxLayout()
    titles.setSpacing(4)
    title = QLabel('<span style="color:#f448bd">DJ</span> POLTORASHKA')
    title.setObjectName("brand_title")
    titles.addWidget(title)
    status = QLabel("Панель не подключена")
    status.setObjectName("panel_connection_status")
    titles.addWidget(status, alignment=Qt.AlignLeft)
    layout.addLayout(titles)
    layout.addWidget(navigation, 1, Qt.AlignRight | Qt.AlignVCenter)
    return header
