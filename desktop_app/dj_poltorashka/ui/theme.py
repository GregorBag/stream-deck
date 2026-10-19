"""Общее оформление Cat Club и векторные значки интерфейса."""

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget


_ASSETS = Path(__file__).parent / "assets"
_ACCENTS = ("pink", "violet", "pink", "blue")
_ICON_PATHS = {
    "sliders": '<path d="M4 6h16M4 12h16M4 18h16"/><path d="M8 3v6m8 0v6M10 15v6"/>',
    "panel": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "settings": '<path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
    "speaker": '<path d="M4 9h4l5-4v14l-5-4H4Z"/><path d="M17 8q5 4 0 8m3-11q7 7 0 14"/>',
    "microphone": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M6 10v2a6 6 0 0 0 12 0v-2m-6 8v3m-4 0h8"/>',
    "music": '<path d="M10 17V5l10-2v12M10 8l10-2"/><ellipse cx="7" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
    "app": '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8m-4-3v3M3 8h18"/>',
    "save": '<path d="M4 3h13l4 4v14H3V3Zm3 0v6h10V3M7 21v-8h10v8"/>',
    "play": '<path d="m8 4 12 8-12 8Z"/>',
    "edit": '<path d="m4 16 12-12 4 4L8 20l-5 1Zm10-10 4 4"/>',
    "plus": '<path d="M12 4v16M4 12h16"/>',
    "close": '<path d="m6 6 12 12M6 18 18 6"/>',
    "paw": '<ellipse cx="7" cy="7" rx="2" ry="3"/><ellipse cx="17" cy="7" rx="2" ry="3"/><ellipse cx="3" cy="12" rx="1.5" ry="2.5"/><ellipse cx="21" cy="12" rx="1.5" ry="2.5"/><path d="M6 18c0-3 3-6 6-6s6 3 6 6c0 4-4 2-6 2s-6 2-6-2Z"/>',
}


def asset_path(name: str) -> Path:
    return _ASSETS / name


def apply_theme(application: QApplication) -> None:
    if application.property("cat_club_theme"):
        return
    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    for role, color in (
        (QPalette.Window, "#100c1c"), (QPalette.WindowText, "#f4efff"),
        (QPalette.Base, "#151126"), (QPalette.AlternateBase, "#1c1631"),
        (QPalette.Text, "#f4efff"), (QPalette.Button, "#241b39"),
        (QPalette.ButtonText, "#f4efff"), (QPalette.Highlight, "#9736c7"),
        (QPalette.HighlightedText, "#ffffff"), (QPalette.ToolTipBase, "#291d3f"),
        (QPalette.ToolTipText, "#f4efff"), (QPalette.PlaceholderText, "#a296bb"),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#80748f"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#80748f"))
    application.setPalette(palette)
    stylesheet = asset_path("cat_club.qss").read_text(encoding="utf-8")
    stylesheet = stylesheet.replace("__DOWN_ARROW__", f'"{asset_path("chevron_down.svg").as_posix()}"')
    stylesheet = stylesheet.replace("__CHECK_MARK__", f'"{asset_path("check_mark.svg").as_posix()}"')
    application.setStyleSheet(stylesheet)
    application.setWindowIcon(QIcon(str(asset_path("avatar.png"))))
    application.setProperty("cat_club_theme", True)


def set_accent(widget: QWidget, index: int) -> None:
    widget.setProperty("accent", _ACCENTS[index % len(_ACCENTS)])


def make_icon(name: str, color: str = "#ddc6ff", size: int = 24) -> QIcon:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{_ICON_PATHS[name]}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def avatar_pixmap(size: int = 80) -> QPixmap:
    source = QPixmap(str(asset_path("avatar.png")))
    result = QPixmap(size * 2, size * 2)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(QRectF(3, 3, size * 2 - 6, size * 2 - 6))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, source.scaled(size * 2, size * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
    painter.setClipping(False)
    painter.setPen(QColor("#e555cc"))
    painter.drawEllipse(QRectF(3, 3, size * 2 - 6, size * 2 - 6))
    painter.end()
    result.setDevicePixelRatio(2)
    return result
