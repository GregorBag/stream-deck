"""Операции окна настроек над системными параметрами."""

from dj_poltorashka.application.autostart import WindowsAutostart


class SettingsController:
    """Предоставляет настройкам проверенное фактическое состояние системы."""

    def __init__(self, autostart: WindowsAutostart):
        self._autostart = autostart

    def autostart_enabled(self) -> bool:
        return self._autostart.is_enabled()

    def set_autostart_enabled(self, enabled: bool) -> bool:
        self._autostart.set_enabled(enabled)
        return self._autostart.is_enabled()
