"""Шапка приложения с аватаркой проекта и клубным баннером."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from dj_poltorashka.ui.theme import asset_path, avatar_pixmap


def create_brand_header() -> QFrame:
    header = QFrame()
    header.setObjectName("brand_header")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(18, 10, 0, 10)
    layout.setSpacing(18)
    avatar = QLabel()
    avatar.setPixmap(avatar_pixmap(72))
    avatar.setFixedSize(72, 72)
    layout.addWidget(avatar)

    titles = QVBoxLayout()
    titles.setSpacing(4)
    title = QLabel('DJ <span style="color:#ed58c5">POLTORASHKA</span>')
    title.setObjectName("brand_title")
    titles.addWidget(title)
    subtitle = QLabel("C A T   C L U B")
    subtitle.setObjectName("brand_subtitle")
    titles.addWidget(subtitle)
    status = QLabel("Панель не подключена · доступен симулятор")
    status.setObjectName("panel_connection_status")
    titles.addWidget(status, alignment=Qt.AlignLeft)
    layout.addLayout(titles)

    banner = QLabel()
    banner.setObjectName("club_banner")
    banner.setFixedHeight(80)
    banner.setMaximumWidth(360)
    banner.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    banner.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    image = QPixmap(str(asset_path("club_banner.png")))
    image = image.scaled(360, 120, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    banner.setPixmap(image.copy(0, (image.height() - 80) // 2, 360, 80))
    layout.addWidget(banner, 1)
    return header
