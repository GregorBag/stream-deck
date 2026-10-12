from pathlib import Path

import pytest
from PySide6.QtCore import QStandardPaths

from dj_poltorashka.application.app_paths import resolve_configuration_paths


def test_explicit_root_bypasses_qstandardpaths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args: object) -> str:
        raise AssertionError("QStandardPaths не должен вызываться")

    monkeypatch.setattr(QStandardPaths, "writableLocation", fail_if_called)

    paths = resolve_configuration_paths(tmp_path / "custom")

    assert paths.root == tmp_path / "custom"
    assert paths.configuration_file == tmp_path / "custom" / "configuration.json"
    assert paths.draft_file == tmp_path / "custom" / "draft.json"
    assert paths.sounds_dir == tmp_path / "custom" / "sounds"
    assert paths.logs_dir == tmp_path / "custom" / "logs"


def test_default_root_uses_qstandardpaths_app_data_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_data = tmp_path / "appdata"
    requested_locations: list[QStandardPaths.StandardLocation] = []

    def writable_location(location: QStandardPaths.StandardLocation) -> str:
        requested_locations.append(location)
        return str(app_data)

    monkeypatch.setattr(QStandardPaths, "writableLocation", writable_location)

    paths = resolve_configuration_paths()

    assert paths.root == app_data
    assert requested_locations == [QStandardPaths.AppDataLocation]


def test_empty_qstandardpaths_location_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(QStandardPaths, "writableLocation", lambda location: "")

    with pytest.raises(RuntimeError, match="каталог данных"):
        resolve_configuration_paths()
