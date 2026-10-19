"""Экран конфигурации Qt Quick с подключением к Python-контроллерам."""

from dataclasses import fields
from pathlib import Path, PureWindowsPath
from urllib.parse import quote
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.configuration.defaults import create_default_stored_configuration
from dj_poltorashka.configuration.models import StoredConfiguration
from dj_poltorashka.ui.theme import asset_path, icon_svg

if TYPE_CHECKING:
    from dj_poltorashka.ui.main_window import MainWindowCallbacks


class ConfigurationView:
    def __init__(self, callbacks: "MainWindowCallbacks", parent: QWidget | None = None, *, source_path: Path | None = None):
        self.widget_ = QQuickWidget(parent)
        self.widget_.setObjectName("configuration_page")
        self.widget_.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.widget_.setClearColor(QColor("#090d20"))
        source = source_path or Path(__file__).parent / "qml" / "ConfigurationPage.qml"
        self.widget_.setSource(QUrl.fromLocalFile(str(source)))
        if self.widget_.status() != QQuickWidget.Ready or self.widget_.rootObject() is None:
            message = "; ".join(error.toString() for error in self.widget_.errors())
            self.widget_.deleteLater()
            raise RuntimeError(f"Не удалось загрузить QML: {message}")
        self.root_ = self.widget_.rootObject()
        self.root_.setProperty("background_url", QUrl.fromLocalFile(str(asset_path("synthwave_grid.svg"))))
        icons = {
            name: self._icon_url(name)
            for name in ("speaker", "speaker_muted", "microphone", "microphone_muted", "app", "music", "download", "save", "edit", "plus", "close", "panel")
        }
        self.root_.setProperty("icons", icons)
        for field in fields(callbacks):
            getattr(self.root_, field.name).connect(getattr(callbacks, field.name))
        self.render(create_default_stored_configuration())

    @property
    def widget(self) -> QQuickWidget:
        return self.widget_

    def render(self, stored: StoredConfiguration, audio_states: tuple[ChannelAudioUpdate, ...] = ()) -> None:
        states = {state.channel_index: state for state in audio_states}
        channels = []
        names = {"unassigned": "Не назначен", "master": "Общая громкость", "microphone": "Микрофон"}
        statuses = {"active": "Активно", "waiting": "Ожидание программы", "unavailable": "Временно недоступно"}
        for index, channel in enumerate(stored.active.channels):
            name = channel.display_name or (PureWindowsPath(channel.application_path).stem if channel.application_path else names.get(channel.channel_kind, "Программа"))
            state = states.get(index)
            if state is not None and state.display_name is not None:
                name = state.display_name
            base_icon = "microphone" if channel.channel_kind == "microphone" else "speaker"
            channels.append({
                "index": index, "name": name, "kind": channel.channel_kind,
                "volume": round(channel.volume * 100), "muted": channel.muted,
                "assigned": channel.channel_kind != "unassigned",
                "application_enabled": channel.channel_kind == "application",
                "availability_text": statuses[state.availability] if state else "",
                "accent": "#f448bd",
                "icon_name": f"{base_icon}_muted" if channel.muted else base_icon,
            })
        self.root_.setProperty("channels", channels)
        self.root_.setProperty("sounds", [
            {"index": index, "name": sound.display_name or "Пусто", "assigned": sound.sound_id is not None, "accent": "#39d9f4"}
            for index, sound in enumerate(stored.active.sound_buttons)
        ])
        presets = []
        for index, preset in enumerate(stored.presets):
            summary = "Нет сохранённой настройки"
            if preset is not None:
                channel_count = sum(channel.channel_kind != "unassigned" for channel in preset.panel.channels)
                sound_count = sum(sound.sound_id is not None for sound in preset.panel.sound_buttons)
                summary = f"Каналов: {channel_count}; звуков: {sound_count}"
            presets.append({"index": index, "name": preset.name if preset else "Пусто", "summary": summary, "assigned": preset is not None, "accent": "#a16aff"})
        self.root_.setProperty("presets", presets)
        self.root_.setProperty("render_revision", self.root_.property("render_revision") + 1)

    def set_virtual_microphone_status(self, state: AudioRoutingStatus) -> None:
        message = "активен" if state.code == "active" else state.message
        prefix = "Виртуальный микрофон"
        if message.casefold().startswith(prefix.casefold()):
            message = message[len(prefix):].lstrip(" :—–-")
        self.root_.setProperty("microphone_status", f"Виртуальный микрофон: {message}")

    @staticmethod
    def _icon_url(name: str) -> str:
        return "data:image/svg+xml;charset=utf-8," + quote(icon_svg(name, "#d5dcf6"))
