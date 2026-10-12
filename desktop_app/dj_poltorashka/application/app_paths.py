"""Определение постоянных путей настольного приложения."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths

from dj_poltorashka.configuration.repository import ConfigurationPaths


def resolve_configuration_paths(root: Path | None = None) -> ConfigurationPaths:
    """Вернуть пути конфигурации из явно заданного или системного каталога."""
    if root is not None:
        return ConfigurationPaths.under(Path(root))

    location = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not location:
        raise RuntimeError("Не удалось определить каталог данных приложения")
    return ConfigurationPaths.under(Path(location))
