"""Операции над активной конфигурацией и слотами пресетов."""

from dataclasses import dataclass

from dj_poltorashka.configuration.models import (
    PanelConfiguration,
    PresetConfig,
    PRESET_COUNT,
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
            active_preset_slot=self._stored_configuration.active_preset_slot,
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
            active_preset_slot=slot,
        )
        return ConfigurationWorkspace(stored)

    def with_replaced_preset(
        self,
        slot: int,
        preset: PresetConfig,
    ) -> "ConfigurationWorkspace":
        preset_index = self._preset_index(slot)
        if self._stored_configuration.presets[preset_index] is None:
            raise LookupError("Выбранный слот пресета пуст")
        if not isinstance(preset, PresetConfig):
            raise ValueError("Требуется PresetConfig")
        presets = list(self._stored_configuration.presets)
        presets[preset_index] = preset
        return ConfigurationWorkspace(
            StoredConfiguration(
                active=self._stored_configuration.active,
                baseline=self._stored_configuration.baseline,
                presets=tuple(presets),
                active_preset_slot=self._stored_configuration.active_preset_slot,
            )
        )

    def prepare_preset_load(self, slot: int) -> PresetLoad:
        preset_index = self._preset_index(slot)
        preset = self._stored_configuration.presets[preset_index]
        if preset is None:
            raise LookupError("Выбранный слот пресета пуст")

        current_slot = self._stored_configuration.active_preset_slot
        if current_slot == slot:
            preset = self._stored_configuration.presets[preset_index]
            return PresetLoad(
                workspace=self.with_saved_preset(slot, preset.name),
                draft_to_save=None,
            )

        presets = list(self._stored_configuration.presets)
        if current_slot is not None:
            previous = presets[current_slot - 1]
            presets[current_slot - 1] = PresetConfig(
                previous.name, self._stored_configuration.active
            )
        draft = self._stored_configuration.active if self.is_dirty and current_slot is None else None
        stored = StoredConfiguration(
            active=preset.panel,
            baseline=preset.panel,
            presets=tuple(presets),
            active_preset_slot=slot,
        )
        return PresetLoad(
            workspace=ConfigurationWorkspace(stored),
            draft_to_save=draft,
        )

    def with_restored_draft(self, panel: PanelConfiguration) -> "ConfigurationWorkspace":
        return self.with_active(panel)

    @staticmethod
    def _preset_index(slot: int) -> int:
        if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= PRESET_COUNT:
            raise IndexError("Номер слота пресета должен быть от 1 до 4")
        return slot - 1
