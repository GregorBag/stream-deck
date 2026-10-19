"""PyInstaller-конфигурация one-folder сборки Windows."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PySide6.QtCore import QLibraryInfo

from dj_poltorashka.build_rules import filter_windows_binaries


project_root = Path(SPECPATH).parent
entry_point = project_root / "dj_poltorashka" / "__main__.py"

datas = collect_data_files("dj_poltorashka.ui", includes=["assets/*"])
binaries = []
hidden_imports = collect_submodules("pycaw")
hidden_imports.extend(
    collect_submodules(
        "comtypes",
        filter=lambda name: not name.startswith("comtypes.test"),
    )
)

qt_plugins_root = Path(
    QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
)
for plugin_group in ("platforms", "multimedia"):
    plugin_root = qt_plugins_root / plugin_group
    binaries.extend(
        (str(plugin_path), f"PySide6/plugins/{plugin_group}")
        for plugin_path in plugin_root.glob("*.dll")
    )

analysis = Analysis(
    [str(entry_point)],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
analysis.binaries = filter_windows_binaries(analysis.binaries)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="DJ Poltorashka",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DJ Poltorashka",
)
