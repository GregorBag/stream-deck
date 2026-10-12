"""Операции над активной конфигурацией и слотами пресетов."""

from dataclasses import dataclass

from dj_poltorashka.configuration.models import (
    PanelConfiguration,
    PresetConfig,
    StoredConfiguration,
)


@dataclass(frozen=True)
class PresetLoad:
    """Результат подготовки загрузки пресета."""

    workspace: "ConfigurationWorkspace"
    draft_to_save: PanelConfiguration | None


class ConfigurationWorkspace:
    """Неизменяемое рабочее состояние конфигурации панели."""

    def __init__(self, stored: StoredConfiguration):
        if not isinstance(stored, StoredConfiguration):
            raise ValueError("Рабочее состояние требует StoredConfiguration")
        self._stored_configuration = stored

    @property
    def stored_configuration(self) -> StoredConfiguration:
        return self._stored_configuration

    @property
    def is_dirty(self) -> bool:
        return self._stored_configuration.active != self._stored_configuration.baseline

    def with_active(self, panel: PanelConfiguration) -> "ConfigurationWorkspace":
        stored = StoredConfiguration(
            active=panel,
            baseline=self._stored_configuration.baseline,
            presets=self._stored_configuration.presets,
        )
        return ConfigurationWorkspace(stored)

    def with_saved_preset(self, slot: int, name: str) -> "ConfigurationWorkspace":
        preset_index = self._preset_index(slot)
        presets = list(self._stored_configuration.presets)
        presets[preset_index] = PresetConfig(
            name=name,
            panel=self._stored_configuration.active,
        )
        stored = StoredConfiguration(
            active=self._stored_configuration.active,
            baseline=self._stored_configuration.active,
            presets=tuple(presets),
        )
        return ConfigurationWorkspace(stored)

    def prepare_preset_load(self, slot: int) -> PresetLoad:
        preset_index = self._preset_index(slot)
        preset = self._stored_configuration.presets[preset_index]
        if preset is None:
            raise LookupError("Выбранный слот пресета пуст")

        draft = self._stored_configuration.active if self.is_dirty else None
        stored = StoredConfiguration(
            active=preset.panel,
            baseline=preset.panel,
            presets=self._stored_configuration.presets,
        )
        return PresetLoad(
            workspace=ConfigurationWorkspace(stored),
            draft_to_save=draft,
        )

    def with_restored_draft(self, panel: PanelConfiguration) -> "ConfigurationWorkspace":
        return self.with_active(panel)

    @staticmethod
    def _preset_index(slot: int) -> int:
        if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= 3:
            raise IndexError("Номер слота пресета должен быть от 1 до 3")
        return slot - 1
