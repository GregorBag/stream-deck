"""Сценарии конфигурации, предназначенные для вызова из интерфейса."""

from dj_poltorashka.configuration.models import (
    PanelConfiguration,
    PresetConfig,
    StoredConfiguration,
)
from dj_poltorashka.configuration.repository import ConfigurationRepository
from dj_poltorashka.configuration.workspace import ConfigurationWorkspace
from dj_poltorashka.sounds.library import SoundLibrary


class ConfigurationService:
    """Связывает рабочее состояние, хранилище и библиотеку звуков."""

    def __init__(
        self,
        workspace: ConfigurationWorkspace,
        repository: ConfigurationRepository,
        sound_library: SoundLibrary,
    ):
        self._workspace = workspace
        self._repository = repository
        self._sound_library = sound_library

    @property
    def stored_configuration(self) -> StoredConfiguration:
        return self._workspace.stored_configuration

    @property
    def is_dirty(self) -> bool:
        return self._workspace.is_dirty

    def replace_active(self, panel: PanelConfiguration) -> None:
        candidate = self._workspace.with_active(panel)
        self._repository.save_draft(panel)
        self._workspace = candidate

    def save_active_to_preset(self, slot: int, name: str) -> PresetConfig:
        candidate = self._workspace.with_saved_preset(slot, name)
        self._repository.save(candidate.stored_configuration)
        self._workspace = candidate
        self._repository.clear_draft()

        preset = candidate.stored_configuration.presets[slot - 1]
        if preset is None:
            raise RuntimeError("Сохранённый пресет отсутствует")
        return preset

    def load_preset(self, slot: int) -> PanelConfiguration:
        prepared = self._workspace.prepare_preset_load(slot)
        if prepared.draft_to_save is not None:
            self._repository.save_draft(prepared.draft_to_save)
        self._repository.save(prepared.workspace.stored_configuration)
        self._workspace = prepared.workspace
        return prepared.workspace.stored_configuration.active

    def restore_draft(self) -> PanelConfiguration:
        draft = self._repository.load_draft()
        if draft is None:
            raise LookupError("Черновик отсутствует")

        candidate = self._workspace.with_restored_draft(draft)
        self._repository.save(candidate.stored_configuration)
        self._workspace = candidate
        return draft

    def discard_draft(self) -> None:
        self._repository.clear_draft()

    def discard_unsaved_and_exit(self) -> None:
        baseline = self._workspace.stored_configuration.baseline
        candidate = self._workspace.with_active(baseline)
        self._repository.save(candidate.stored_configuration)
        self._workspace = candidate
        self._repository.clear_draft()

    def referenced_sound_ids(self) -> set[str]:
        stored = self._workspace.stored_configuration
        panels = [stored.active, stored.baseline]
        panels.extend(
            preset.panel for preset in stored.presets if preset is not None
        )
        draft = self._repository.load_draft()
        if draft is not None:
            panels.append(draft)

        sound_ids: set[str] = set()
        for panel in panels:
            sound_ids.update(
                button.sound_id
                for button in panel.sound_buttons
                if button.sound_id is not None
            )
        return sound_ids
