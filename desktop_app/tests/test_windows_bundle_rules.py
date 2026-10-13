from pathlib import Path

import pytest

from dj_poltorashka.build_rules import (
    filter_windows_binaries,
    verify_windows_bundle,
)


def test_filter_removes_external_icu_dlls() -> None:
    binaries = [
        ("PySide6/Qt6Core.dll", "qt/Qt6Core.dll", "BINARY"),
        ("icuuc.dll", "poppler/icuuc.dll", "BINARY"),
        ("icudt78.dll", "poppler/icudt78.dll", "BINARY"),
    ]

    assert filter_windows_binaries(binaries) == [binaries[0]]


def test_verifier_rejects_external_icu_dlls(tmp_path: Path) -> None:
    (tmp_path / "icuuc.dll").touch()

    with pytest.raises(RuntimeError, match="icuuc.dll"):
        verify_windows_bundle(tmp_path)


@pytest.mark.parametrize(
    "missing_plugin",
    ("ffmpegmediaplugin.dll", "windowsmediaplugin.dll"),
)
def test_verifier_requires_both_qt_multimedia_plugins(
    tmp_path: Path,
    missing_plugin: str,
) -> None:
    plugin_dir = tmp_path / "PySide6" / "plugins" / "multimedia"
    plugin_dir.mkdir(parents=True)
    for plugin in ("ffmpegmediaplugin.dll", "windowsmediaplugin.dll"):
        if plugin != missing_plugin:
            (plugin_dir / plugin).touch()

    with pytest.raises(RuntimeError, match=missing_plugin):
        verify_windows_bundle(tmp_path)


def test_verifier_accepts_complete_multimedia_bundle(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "PySide6" / "plugins" / "multimedia"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "ffmpegmediaplugin.dll").touch()
    (plugin_dir / "windowsmediaplugin.dll").touch()

    verify_windows_bundle(tmp_path)
