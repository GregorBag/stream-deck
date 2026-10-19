"""Редактор сохранённого пресета без изменения активной настройки."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from dj_poltorashka.configuration.editor import PanelConfigurationEditor
from dj_poltorashka.configuration.models import (
    ChannelKind, MixerChannelConfig, PanelConfiguration, PresetConfig,
    SoundButtonConfig,
)
from dj_poltorashka.ui.channel_card import ChannelCard
from dj_poltorashka.ui.sound_button import SoundButton


@dataclass(frozen=True)
class PresetEditResult:
    name: str
    panel: PanelConfiguration
    sound_sources: tuple[Path | None, ...]


class PresetEditDialog:
    def __init__(
        self,
        choose_application: Callable[[], Path | None],
        choose_sound: Callable[[], Path | None],
        show_error: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        self._choose_application = choose_application
        self._choose_sound = choose_sound
        self._show_error = show_error
        self._panel: PanelConfiguration | None = None
        self._sound_sources: list[Path | None] = [None] * 8
        self._on_save: Callable[[PresetEditResult], bool] | None = None

        self._widget = QDialog(parent)
        self._widget.setWindowTitle("Изменить пресет")
        self._widget.resize(1100, 700)
        root = QVBoxLayout(self._widget)
        root.addWidget(QLabel("Название"))
        self._name = QLineEdit()
        self._name.setObjectName("preset_edit_name")
        root.addWidget(self._name)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(QLabel("Каналы"))
        channels_row = QWidget()
        channels_layout = QHBoxLayout(channels_row)
        self._channels = tuple(
            ChannelCard(
                index,
                self._set_channel_kind,
                self._choose_channel_application,
                self._set_volume,
                self._toggle_mute,
            )
            for index in range(4)
        )
        for card in self._channels:
            channels_layout.addWidget(card.widget)
        content_layout.addWidget(channels_row)

        content_layout.addWidget(QLabel("Звуковые кнопки"))
        sounds_grid = QGridLayout()
        self._sounds = tuple(
            SoundButton(index, self._import_sound, self._clear_sound)
            for index in range(8)
        )
        for index, button in enumerate(self._sounds):
            sounds_grid.addWidget(button.widget, index // 4, index % 4)
        content_layout.addLayout(sounds_grid)
        scroll.setWidget(content)
        root.addWidget(scroll)

        actions = QHBoxLayout()
        save = QPushButton("Сохранить")
        save.setObjectName("preset_edit_save")
        save.setProperty("role", "primary")
        save.clicked.connect(self._save)
        actions.addWidget(save)
        cancel = QPushButton("Отмена")
        cancel.setObjectName("preset_edit_cancel")
        cancel.clicked.connect(self._widget.reject)
        actions.addWidget(cancel)
        root.addLayout(actions)

    @property
    def widget(self) -> QDialog:
        return self._widget

    def prepare(
        self,
        preset: PresetConfig,
        on_save: Callable[[PresetEditResult], bool],
    ) -> None:
        self._panel = preset.panel
        self._sound_sources = [None] * 8
        self._on_save = on_save
        self._name.setText(preset.name)
        self._render()

    def edit(
        self,
        preset: PresetConfig,
        on_save: Callable[[PresetEditResult], bool],
    ) -> None:
        self.prepare(preset, on_save)
        self._widget.exec()

    def _render(self) -> None:
        if self._panel is None:
            return
        for card, channel in zip(self._channels, self._panel.channels, strict=True):
            card.render(channel)
        for index, (button, sound) in enumerate(
            zip(self._sounds, self._panel.sound_buttons, strict=True)
        ):
            source = self._sound_sources[index]
            if source is not None:
                sound = SoundButtonConfig("pending.mp3", source.stem)
            button.render(sound)

    def _set_channel(self, index: int, channel: MixerChannelConfig) -> None:
        assert self._panel is not None
        try:
            self._panel = PanelConfigurationEditor.set_channel(self._panel, index, channel)
        except ValueError as error:
            self._show_error("Пресет", str(error))
        self._render()

    def _set_channel_kind(self, index: int, kind: ChannelKind) -> None:
        assert self._panel is not None
        current = self._panel.channels[index]
        path: str | None = None
        name: str | None = None
        if kind == "application":
            selected = self._choose_application()
            if selected is None:
                self._render()
                return
            path = str(selected)
            name = selected.stem
        self._set_channel(
            index,
            MixerChannelConfig(kind, current.volume, current.muted, path, name),
        )

    def _choose_channel_application(self, index: int) -> None:
        assert self._panel is not None
        selected = self._choose_application()
        if selected is None:
            return
        current = self._panel.channels[index]
        self._set_channel(
            index,
            MixerChannelConfig(
                "application", current.volume, current.muted,
                str(selected), selected.stem,
            ),
        )

    def _set_volume(self, index: int, volume: float) -> None:
        assert self._panel is not None
        self._panel = PanelConfigurationEditor.set_volume(self._panel, index, volume)
        self._render()

    def _toggle_mute(self, index: int) -> None:
        assert self._panel is not None
        self._panel = PanelConfigurationEditor.toggle_mute(self._panel, index)
        self._render()

    def _import_sound(self, index: int) -> None:
        source = self._choose_sound()
        if source is not None:
            self._sound_sources[index] = source
            self._render()

    def _clear_sound(self, index: int) -> None:
        assert self._panel is not None
        self._sound_sources[index] = None
        self._panel = PanelConfigurationEditor.clear_sound(self._panel, index)
        self._render()

    def _save(self) -> None:
        if self._panel is None or self._on_save is None:
            return
        name = self._name.text().strip()
        if not name:
            self._show_error("Пресет", "Название пресета не должно быть пустым")
            return
        result = PresetEditResult(name, self._panel, tuple(self._sound_sources))
        if self._on_save(result):
            self._widget.accept()
