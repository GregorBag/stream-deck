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
