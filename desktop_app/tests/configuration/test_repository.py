from pathlib import Path

import pytest

import dj_poltorashka.configuration.repository as repository_module
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
    StoredConfiguration,
)
from dj_poltorashka.configuration.repository import (
    ConfigurationPaths,
    ConfigurationRepository,
)


def make_panel(volume: float) -> PanelConfiguration:
    return PanelConfiguration(
        channels=(
            MixerChannelConfig("master", volume, False),
            *(
                MixerChannelConfig("unassigned", volume, False)
                for _ in range(3)
            ),
        ),
        sound_buttons=tuple(SoundButtonConfig() for _ in range(8)),
    )


def make_stored_configuration(volume: float) -> StoredConfiguration:
    panel = make_panel(volume)
    return StoredConfiguration(
        active=panel,
        baseline=panel,
        presets=(None, None, None),
    )


def make_repository(root: Path) -> ConfigurationRepository:
    return ConfigurationRepository(ConfigurationPaths.under(root))


def test_save_and_load_configuration(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    stored = make_stored_configuration(0.7)

    repository.save(stored)

    assert repository.load(make_stored_configuration(0.1)) == stored


def test_save_and_load_draft(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    panel = make_panel(0.8)

    repository.save_draft(panel)

    assert repository.load_draft() == panel


def test_clear_draft_is_idempotent(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.save_draft(make_panel(0.8))

    repository.clear_draft()
    repository.clear_draft()

    assert repository.load_draft() is None


def test_missing_configuration_returns_supplied_default(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    default = make_stored_configuration(0.3)

    loaded = repository.load(default)

    assert loaded is default


def test_invalid_json_raises_format_error_without_modifying_file(
    tmp_path: Path,
) -> None:
    paths = ConfigurationPaths.under(tmp_path)
    paths.configuration_file.write_text("{invalid", encoding="utf-8")
    original_contents = paths.configuration_file.read_bytes()
    repository = ConfigurationRepository(paths)

    with pytest.raises(ValueError, match="configuration.json"):
        repository.load(make_stored_configuration(0.1))

    assert paths.configuration_file.read_bytes() == original_contents


def test_first_write_after_corrupt_draft_preserves_original_backup(
    tmp_path: Path,
) -> None:
    paths = ConfigurationPaths.under(tmp_path)
    invalid_contents = b"[invalid"
    paths.draft_file.write_bytes(invalid_contents)
    repository = ConfigurationRepository(paths)

    with pytest.raises(ValueError, match="draft.json"):
        repository.load_draft()
    repository.save_draft(make_panel(0.4))

    assert (tmp_path / "draft.json.corrupt").read_bytes() == invalid_contents
    assert repository.load_draft() == make_panel(0.4)


def test_failed_replace_keeps_previous_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = ConfigurationPaths.under(tmp_path)
    repository = ConfigurationRepository(paths)
    first = make_stored_configuration(0.2)
    second = make_stored_configuration(0.9)
    repository.save(first)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        repository.save(second)

    assert repository.load(make_stored_configuration(0.1)) == first
    assert not tuple(tmp_path.glob("*.tmp"))


def test_successful_save_leaves_no_temporary_file(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)

    repository.save(make_stored_configuration(0.6))

    assert not tuple(tmp_path.glob("*.tmp"))
