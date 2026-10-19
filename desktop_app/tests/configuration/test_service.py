import pytest

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
)
from dj_poltorashka.configuration.service import ConfigurationService
from dj_poltorashka.configuration.workspace import ConfigurationWorkspace


class InMemoryRepository:
    def __init__(
        self,
        stored: StoredConfiguration | None = None,
        draft: PanelConfiguration | None = None,
    ):
        self.saved_configuration = stored
        self.draft = draft
        self.fail_draft_save = False
        self.fail_draft_clear = False
        self.fail_save = False
        self.operations: list[tuple[str, object | None]] = []

    def save(self, stored: StoredConfiguration) -> None:
        self.operations.append(("save", stored))
        if self.fail_save:
            raise OSError("configuration save failed")
        self.saved_configuration = stored

    def load_draft(self) -> PanelConfiguration | None:
        self.operations.append(("load_draft", None))
        return self.draft

    def save_draft(self, panel: PanelConfiguration) -> None:
        self.operations.append(("save_draft", panel))
        if self.fail_draft_save:
            raise OSError("draft save failed")
        self.draft = panel

    def clear_draft(self) -> None:
        self.operations.append(("clear_draft", None))
        if self.fail_draft_clear:
            raise PermissionError("draft clear failed")
        self.draft = None


class InMemorySoundLibrary:
    pass


def make_panel(
    volume: float,
    sound_ids: tuple[str, ...] = (),
) -> PanelConfiguration:
    buttons = [
        SoundButtonConfig(sound_id=sound_id, display_name=sound_id)
        for sound_id in sound_ids
    ]
    buttons.extend(SoundButtonConfig() for _ in range(8 - len(buttons)))
    return PanelConfiguration(
        channels=(
            MixerChannelConfig("master", volume, False),
            *(
                MixerChannelConfig("unassigned", volume, False)
                for _ in range(3)
            ),
        ),
        sound_buttons=tuple(buttons),
    )


def make_stored_configuration(
    active: PanelConfiguration,
    baseline: PanelConfiguration,
    first_preset: PresetConfig | None = None,
) -> StoredConfiguration:
    return StoredConfiguration(
        active=active,
        baseline=baseline,
        presets=(first_preset, None, None),
    )


def make_service(
    stored: StoredConfiguration,
    repository: InMemoryRepository,
) -> ConfigurationService:
    return ConfigurationService(
        workspace=ConfigurationWorkspace(stored),
        repository=repository,
        sound_library=InMemorySoundLibrary(),
    )


def test_replace_active_persists_recovery_draft() -> None:
    initial = make_panel(0.5)
    changed = make_panel(0.8)
    stored = make_stored_configuration(initial, initial)
    repository = InMemoryRepository(stored=stored)
    service = make_service(stored, repository)

    service.replace_active(changed)

    assert service.stored_configuration.active == changed
    assert service.is_dirty
    assert repository.draft == changed
    assert repository.operations == [("save_draft", changed)]


def test_save_to_preset_persists_state_and_clears_draft() -> None:
    baseline = make_panel(0.5)
    changed = make_panel(0.8)
    stored = make_stored_configuration(changed, baseline)
    repository = InMemoryRepository(stored=stored, draft=changed)
    service = make_service(stored, repository)

    saved_preset = service.save_active_to_preset(2, "Игры")

    assert saved_preset == PresetConfig("Игры", changed)
    assert repository.saved_configuration == service.stored_configuration
    assert repository.draft is None
    assert not service.is_dirty
    assert [operation[0] for operation in repository.operations] == [
        "save",
        "clear_draft",
    ]


def test_replace_preset_persists_without_touching_draft() -> None:
    baseline = make_panel(0.5)
    active = make_panel(0.8)
    original = PresetConfig("Работа", make_panel(0.2))
    replacement = PresetConfig("Игры", make_panel(0.3))
    stored = make_stored_configuration(active, baseline, original)
    repository = InMemoryRepository(stored=stored, draft=active)
    service = make_service(stored, repository)

    service.replace_preset(1, replacement)

    assert service.stored_configuration.presets[0] == replacement
    assert service.stored_configuration.active == active
    assert service.stored_configuration.baseline == baseline
    assert service.is_dirty
    assert repository.draft == active
    assert [operation[0] for operation in repository.operations] == ["save"]


def test_replace_preset_save_failure_keeps_workspace() -> None:
    panel = make_panel(0.5)
    original = PresetConfig("Работа", panel)
    stored = make_stored_configuration(panel, panel, original)
    repository = InMemoryRepository(stored=stored)
    repository.fail_save = True
    service = make_service(stored, repository)

    with pytest.raises(OSError, match="configuration save failed"):
        service.replace_preset(1, PresetConfig("Игры", make_panel(0.3)))

    assert service.stored_configuration == stored
    assert repository.saved_configuration == stored


def test_load_dirty_preset_saves_draft_before_persisting_loaded_state() -> None:
    baseline = make_panel(0.5)
    changed = make_panel(0.8)
    preset_panel = make_panel(0.2)
    stored = make_stored_configuration(
        changed,
        baseline,
        PresetConfig("Работа", preset_panel),
    )
    repository = InMemoryRepository(stored=stored)
    service = make_service(stored, repository)

    loaded_panel = service.load_preset(1)

    assert loaded_panel == preset_panel
    assert repository.draft == changed
    assert repository.saved_configuration == service.stored_configuration
    assert service.stored_configuration.active == preset_panel
    assert not service.is_dirty
    assert [operation[0] for operation in repository.operations] == [
        "save_draft",
        "save",
    ]


def test_failed_draft_save_prevents_preset_load_and_preserves_active_state() -> None:
    baseline = make_panel(0.5)
    changed = make_panel(0.8)
    preset_panel = make_panel(0.2)
    stored = make_stored_configuration(
        changed,
        baseline,
        PresetConfig("Работа", preset_panel),
    )
    repository = InMemoryRepository(stored=stored)
    repository.fail_draft_save = True
    service = make_service(stored, repository)

    with pytest.raises(OSError, match="draft save failed"):
        service.load_preset(1)

    assert service.stored_configuration == stored
    assert repository.saved_configuration == stored
    assert repository.draft is None
    assert [operation[0] for operation in repository.operations] == ["save_draft"]


def test_restore_draft_makes_it_active_without_persisting_main_state() -> None:
    baseline = make_panel(0.5)
    draft = make_panel(0.8)
    stored = make_stored_configuration(baseline, baseline)
    repository = InMemoryRepository(stored=stored, draft=draft)
    service = make_service(stored, repository)

    restored_panel = service.restore_draft()

    assert restored_panel == draft
    assert service.stored_configuration.active == draft
    assert service.is_dirty
    assert repository.saved_configuration == stored
    assert repository.draft == draft
    assert repository.operations == [("load_draft", None)]


def test_discard_draft_removes_recovery_copy_without_changing_workspace() -> None:
    baseline = make_panel(0.5)
    draft = make_panel(0.8)
    stored = make_stored_configuration(baseline, baseline)
    repository = InMemoryRepository(stored=stored, draft=draft)
    service = make_service(stored, repository)

    service.discard_draft()

    assert service.stored_configuration == stored
    assert repository.draft is None
    assert repository.operations == [("clear_draft", None)]


def test_exit_without_saving_clears_draft_and_restores_baseline() -> None:
    baseline = make_panel(0.5)
    changed = make_panel(0.8)
    stored = make_stored_configuration(changed, baseline)
    repository = InMemoryRepository(stored=stored, draft=changed)
    service = make_service(stored, repository)

    service.discard_unsaved_and_exit()

    assert service.stored_configuration.active == baseline
    assert not service.is_dirty
    assert repository.saved_configuration == service.stored_configuration
    assert repository.draft is None
    assert [operation[0] for operation in repository.operations] == [
        "save",
        "clear_draft",
    ]


def test_referenced_sound_ids_include_active_presets_and_draft() -> None:
    active = make_panel(0.5, ("active.mp3",))
    preset_panel = make_panel(0.2, ("preset.wav",))
    draft = make_panel(0.8, ("draft.mp3", "active.mp3"))
    stored = make_stored_configuration(
        active,
        active,
        PresetConfig("Работа", preset_panel),
    )
    repository = InMemoryRepository(stored=stored, draft=draft)
    service = make_service(stored, repository)

    sound_ids = service.referenced_sound_ids()

    assert sound_ids == {"active.mp3", "preset.wav", "draft.mp3"}


def test_failed_draft_clear_keeps_saved_preset_in_service_state() -> None:
    baseline = make_panel(0.5)
    changed = make_panel(0.8)
    stored = make_stored_configuration(changed, baseline)
    repository = InMemoryRepository(stored=stored, draft=changed)
    repository.fail_draft_clear = True
    service = make_service(stored, repository)

    with pytest.raises(PermissionError, match="draft clear failed"):
        service.save_active_to_preset(1, "Первый")

    assert service.stored_configuration == repository.saved_configuration
    assert service.stored_configuration.presets[0] == PresetConfig("Первый", changed)

    repository.fail_draft_clear = False
    service.save_active_to_preset(2, "Второй")

    assert repository.saved_configuration is not None
    assert repository.saved_configuration.presets[0] == PresetConfig("Первый", changed)
    assert repository.saved_configuration.presets[1] == PresetConfig("Второй", changed)


def test_failed_draft_clear_after_discard_keeps_service_in_sync() -> None:
    baseline = make_panel(0.5)
    changed = make_panel(0.8)
    stored = make_stored_configuration(changed, baseline)
    repository = InMemoryRepository(stored=stored, draft=changed)
    repository.fail_draft_clear = True
    service = make_service(stored, repository)

    with pytest.raises(PermissionError, match="draft clear failed"):
        service.discard_unsaved_and_exit()

    assert service.stored_configuration == repository.saved_configuration
    assert service.stored_configuration.active == baseline
    assert not service.is_dirty
