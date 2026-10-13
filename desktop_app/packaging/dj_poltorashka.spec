"""PyInstaller-конфигурация one-folder сборки Windows."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PySide6.QtCore import QLibraryInfo


project_root = Path(SPECPATH).parent
entry_point = project_root / "dj_poltorashka" / "__main__.py"

datas = []
binaries = []
hidden_imports = []
for package_name in ("pycaw", "comtypes"):
    package_datas, package_binaries, package_hidden = collect_all(package_name)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hidden_imports.extend(package_hidden)

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
