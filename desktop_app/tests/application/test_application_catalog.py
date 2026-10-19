from pathlib import Path

from dj_poltorashka.application.application_catalog import ApplicationCatalog


def test_installed_catalog_combines_shortcuts_and_app_paths(tmp_path: Path) -> None:
    start_menu = tmp_path / "Start"
    start_menu.mkdir()
    (start_menu / "Audacity.lnk").touch()
    (start_menu / "Broken.lnk").touch()
    executable = tmp_path / "Audacity.exe"
    executable.touch()

    def resolve(shortcut: Path) -> Path | None:
        return executable if shortcut.stem == "Audacity" else None

    catalog = ApplicationCatalog(
        start_menu_paths=(start_menu,),
        resolve_shortcut=resolve,
        app_paths=lambda: (("Audacity.exe", executable),),
    )

    assert tuple((item.name, item.path) for item in catalog.installed()) == (
        ("Audacity", executable),
    )
