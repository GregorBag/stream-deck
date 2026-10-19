from pathlib import Path
import tomllib

import pytest


def test_package_data_covers_qml_components():
    project = Path(__file__).parents[1]
    metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = metadata["tool"]["setuptools"]["package-data"]["dj_poltorashka.ui"]
    covered = {path.name for pattern in patterns for path in (project / "dj_poltorashka/ui").glob(pattern)}
    assert {"ConfigurationPage.qml", "ChannelCard.qml", "Fader.qml", "SoundPad.qml", "PresetCard.qml", "NeonButton.qml"} <= covered


def test_pyinstaller_collects_qml_components():
    collect_data_files = pytest.importorskip("PyInstaller.utils.hooks").collect_data_files
    data = collect_data_files("dj_poltorashka.ui", includes=["assets/*", "qml/*.qml"])
    names = {Path(source).name for source, _ in data}
    assert {"ConfigurationPage.qml", "Fader.qml", "avatar.png", "synthwave_grid.svg"} <= names
