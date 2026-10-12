import pytest

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
)
from dj_poltorashka.configuration.workspace import ConfigurationWorkspace


def make_panel(volume: float) -> PanelConfiguration:
    channels = tuple(
        MixerChannelConfig(channel_kind="master", volume=volume, muted=False)
        for _ in range(4)
    )
    buttons = tuple(SoundButtonConfig() for _ in range(8))
    return PanelConfiguration(channels=channels, sound_buttons=buttons)


def make_stored_configuration(
    active: PanelConfiguration | None = None,
    baseline: PanelConfiguration | None = None,
    first_preset: PresetConfig | None = None,
) -> StoredConfiguration:
    default_panel = make_panel(0.5)
    return StoredConfiguration(
        active=active or default_panel,
        baseline=baseline or default_panel,
        presets=(first_preset, None, None),
    )


def test_new_workspace_is_clean() -> None:
    workspace = ConfigurationWorkspace(make_stored_configuration())

    assert not workspace.is_dirty


def test_replacing_active_configuration_marks_workspace_dirty() -> None:
    workspace = ConfigurationWorkspace(make_stored_configuration())
    changed_panel = make_panel(0.8)

    changed_workspace = workspace.with_active(changed_panel)

    assert changed_workspace.is_dirty
    assert changed_workspace.stored_configuration.active == changed_panel
    assert not workspace.is_dirty


def test_saving_active_to_preset_returns_new_clean_workspace() -> None:
    initial_panel = make_panel(0.5)
    changed_panel = make_panel(0.8)
    workspace = ConfigurationWorkspace(
        make_stored_configuration(active=changed_panel, baseline=initial_panel)
    )

    saved_workspace = workspace.with_saved_preset(2, "Игры")

    assert not saved_workspace.is_dirty
    assert saved_workspace.stored_configuration.active == changed_panel
    assert saved_workspace.stored_configuration.baseline == changed_panel
    assert saved_workspace.stored_configuration.presets[1] == PresetConfig(
        name="Игры",
        panel=changed_panel,
    )
    assert workspace.is_dirty
    assert workspace.stored_configuration.presets[1] is None


def test_preparing_preset_load_returns_dirty_configuration_as_draft() -> None:
    baseline = make_panel(0.5)
    changed_panel = make_panel(0.8)
    preset_panel = make_panel(0.2)
    workspace = ConfigurationWorkspace(
        make_stored_configuration(
            active=changed_panel,
            baseline=baseline,
            first_preset=PresetConfig(name="Работа", panel=preset_panel),
        )
    )

    prepared = workspace.prepare_preset_load(1)

    assert prepared.draft_to_save == changed_panel
    assert not prepared.workspace.is_dirty
    assert prepared.workspace.stored_configuration.active == preset_panel
    assert prepared.workspace.stored_configuration.baseline == preset_panel
    assert workspace.stored_configuration.active == changed_panel


def test_preparing_preset_load_without_changes_returns_no_draft() -> None:
    active_panel = make_panel(0.5)
    preset_panel = make_panel(0.2)
    workspace = ConfigurationWorkspace(
        make_stored_configuration(
            active=active_panel,
            baseline=active_panel,
            first_preset=PresetConfig(name="Работа", panel=preset_panel),
        )
    )

    prepared = workspace.prepare_preset_load(1)

    assert prepared.draft_to_save is None
    assert prepared.workspace.stored_configuration.active == preset_panel


def test_restoring_draft_returns_new_dirty_workspace() -> None:
    active_panel = make_panel(0.5)
    draft_panel = make_panel(0.8)
    workspace = ConfigurationWorkspace(
        make_stored_configuration(active=active_panel, baseline=active_panel)
    )

    restored_workspace = workspace.with_restored_draft(draft_panel)

    assert restored_workspace.is_dirty
    assert restored_workspace.stored_configuration.active == draft_panel
    assert restored_workspace.stored_configuration.baseline == active_panel
    assert not workspace.is_dirty


def test_preset_slot_outside_one_to_three_changes_nothing() -> None:
    panel = make_panel(0.5)
    workspace = ConfigurationWorkspace(
        make_stored_configuration(
            active=panel,
            baseline=panel,
            first_preset=PresetConfig(name="Работа", panel=panel),
        )
    )
    snapshot = workspace.stored_configuration

    for slot in (0, 4):
        with pytest.raises(IndexError):
            workspace.with_saved_preset(slot, "Недопустимый")
        with pytest.raises(IndexError):
            workspace.prepare_preset_load(slot)

    assert workspace.stored_configuration == snapshot


def test_preparing_empty_preset_slot_is_rejected() -> None:
    workspace = ConfigurationWorkspace(make_stored_configuration())

    with pytest.raises(LookupError):
        workspace.prepare_preset_load(2)
