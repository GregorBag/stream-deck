"""Координация пользовательского интерфейса и конфигурации приложения."""

from pathlib import Path

from dj_poltorashka.configuration.models import (
    ChannelKind,
    MixerChannelConfig,
    SoundButtonConfig,
)
from dj_poltorashka.panel.event_router import PanelEventRouter


class AppController:
    """Выполняет пользовательские операции и синхронизирует представления."""

    def __init__(
        self,
        configuration_service,
        editor,
        sound_library,
        main_window,
        simulator,
        dialogs,
        settings_dialog,
        tray,
        quit_application,
    ):
        self._configuration_service = configuration_service
        self._editor = editor
        self._sound_library = sound_library
        self._main_window = main_window
        self._simulator = simulator
        self._dialogs = dialogs
        self._settings_dialog = settings_dialog
        self._tray = tray
        self._quit_application = quit_application
        self._event_router = PanelEventRouter(
            self.set_volume,
            self.toggle_mute,
            self.press_sound,
            self.load_preset,
        )

    def start(self, background: bool, draft_available: bool) -> None:
        if draft_available:
            try:
                if self._dialogs.ask_restore():
                    self._configuration_service.restore_draft()
                else:
                    self._configuration_service.discard_draft()
            except (OSError, ValueError, LookupError) as error:
                self._dialogs.show_error("Восстановление", str(error))

        self._refresh()
        self._tray.show()
        if not background:
            self._main_window.show()

    def show_main_window(self) -> None:
        self._main_window.show()
        self._main_window.activate()

    def show_simulator(self) -> None:
        self._simulator.show()

    def show_settings(self) -> None:
        self._settings_dialog.open()

    def set_volume(self, channel_index: int, volume: float) -> None:
        panel = self._editor.set_volume(
            self._active_configuration,
            channel_index,
            volume,
        )
        self._replace_active(panel, "Конфигурация")

    def toggle_mute(self, channel_index: int) -> None:
        panel = self._editor.toggle_mute(
            self._active_configuration,
            channel_index,
        )
        self._replace_active(panel, "Конфигурация")

    def set_channel(self, channel_index: int, channel_kind: ChannelKind) -> None:
        current = self._active_configuration.channels[channel_index]
        application_path: str | None = None
        display_name: str | None = None
        if channel_kind == "application":
            selected_path = self._dialogs.choose_application_file()
            if selected_path is None:
                return
            application_path = str(selected_path)
            display_name = Path(selected_path).stem

        channel = MixerChannelConfig(
            channel_kind=channel_kind,
            volume=current.volume,
            muted=current.muted,
            application_path=application_path,
            display_name=display_name,
        )
        panel = self._editor.set_channel(
            self._active_configuration,
            channel_index,
            channel,
        )
        self._replace_active(panel, "Конфигурация")

    def import_sound(self, button_index: int) -> None:
        source = self._dialogs.choose_sound_file()
        if source is None:
            return

        try:
            imported = self._sound_library.import_file(source)
            sound = SoundButtonConfig(imported.sound_id, imported.display_name)
            panel = self._editor.set_sound(
                self._active_configuration,
                button_index,
                sound,
            )
            self._configuration_service.replace_active(panel)
        except (OSError, ValueError) as error:
            self._dialogs.show_error("Импорт звука", str(error))
        self._refresh()

    def clear_sound(self, button_index: int) -> None:
        panel = self._editor.clear_sound(
            self._active_configuration,
            button_index,
        )
        self._replace_active(panel, "Конфигурация")

    def load_preset(self, preset_index: int) -> None:
        try:
            self._configuration_service.load_preset(preset_index + 1)
        except (OSError, ValueError, LookupError) as error:
            self._dialogs.show_error("Пресет", str(error))
        self._refresh()

    def save_active_to_preset(self) -> bool:
        selection = self._dialogs.choose_preset(
            self._configuration_service.stored_configuration
        )
        if selection is None:
            return False

        preset_index, name = selection
        current = self._configuration_service.stored_configuration.presets[
            preset_index
        ]
        if current is not None and not self._dialogs.confirm_overwrite(current.name):
            return False

        try:
            self._configuration_service.save_active_to_preset(
                preset_index + 1,
                name,
            )
        except (OSError, ValueError) as error:
            self._dialogs.show_error("Пресет", str(error))
            self._refresh()
            return False
        self._refresh()
        return True

    def press_sound(self, button_index: int) -> None:
        self._simulator.set_status("Воспроизведение будет добавлено позже")

    def handle_panel_event(self, event) -> None:
        self._event_router.route(event)

    def handle_instance_command(self, command: str) -> None:
        if command == "show":
            self.show_main_window()
            return
        if command == "ping":
            return
        raise ValueError("Неизвестная команда экземпляра")

    def request_exit(self) -> None:
        if not self._configuration_service.is_dirty:
            self._finish_exit()
            return

        choice = self._dialogs.ask_exit()
        if choice == "cancel":
            return
        if choice == "save":
            if self.save_active_to_preset():
                self._finish_exit()
            return
        if choice == "discard":
            try:
                self._configuration_service.discard_unsaved_and_exit()
            except (OSError, ValueError) as error:
                self._dialogs.show_error("Конфигурация", str(error))
                self._refresh()
                return
            self._finish_exit()
            return
        raise ValueError("Неизвестный вариант выхода")

    @property
    def _active_configuration(self):
        return self._configuration_service.stored_configuration.active

    def _replace_active(self, panel, error_title: str) -> None:
        try:
            self._configuration_service.replace_active(panel)
        except (OSError, ValueError) as error:
            self._dialogs.show_error(error_title, str(error))
        self._refresh()

    def _refresh(self) -> None:
        stored = self._configuration_service.stored_configuration
        self._main_window.render(stored)
        self._simulator.render(stored.active)

    def _finish_exit(self) -> None:
        self._tray.hide()
        self._quit_application()
