"""Сборка и запуск настольного приложения."""

import argparse
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from dj_poltorashka.application.app_controller import AppController
from dj_poltorashka.application.app_paths import resolve_configuration_paths
from dj_poltorashka.application.autostart import (
    WindowsAutostart,
    build_background_command,
)
from dj_poltorashka.application.logging_setup import configure_logging
from dj_poltorashka.application.settings_controller import SettingsController
from dj_poltorashka.application.single_instance import SingleInstanceController
from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.editor import PanelConfigurationEditor
from dj_poltorashka.configuration.repository import (
    ConfigurationPaths,
    ConfigurationRepository,
)
from dj_poltorashka.configuration.service import ConfigurationService
from dj_poltorashka.configuration.workspace import ConfigurationWorkspace
from dj_poltorashka.sounds.library import SoundLibrary
from dj_poltorashka.ui.dialog_service import DialogService
from dj_poltorashka.ui.main_window import MainWindow, MainWindowCallbacks
from dj_poltorashka.ui.panel_simulator import PanelSimulator
from dj_poltorashka.ui.settings_dialog import SettingsDialog
from dj_poltorashka.ui.tray_controller import TrayCallbacks, TrayController


_APPLICATION_NAME = "DJ Poltorashka"


@dataclass(frozen=True)
class StartupOptions:
    background: bool


@dataclass
class RunningApplication:
    application: QApplication
    paths: ConfigurationPaths
    repository: ConfigurationRepository
    configuration_service: ConfigurationService
    sound_library: SoundLibrary
    main_window: MainWindow
    simulator: PanelSimulator
    dialogs: DialogService
    settings_dialog: SettingsDialog
    tray: TrayController
    controller: AppController
    single_instance: SingleInstanceController
    draft_available: bool
    startup_errors: tuple[tuple[str, str], ...]

    def close(self) -> None:
        self.tray.hide()
        self.main_window.hide()
        self.simulator.hide()
        self.single_instance.close()


def parse_arguments(arguments: Sequence[str]) -> StartupOptions:
    parser = argparse.ArgumentParser(prog="dj-poltorashka")
    parser.add_argument("--background", action="store_true")
    namespace = parser.parse_args(arguments)
    return StartupOptions(background=namespace.background)


def build_application(data_root: Path | None = None) -> RunningApplication:
    _set_qt_identity()
    application = _ensure_application()
    paths = resolve_configuration_paths(data_root)
    configure_logging(paths.logs_dir)

    repository = ConfigurationRepository(paths)
    default = create_default_stored_configuration()
    startup_errors: list[tuple[str, str]] = []
    try:
        stored = repository.load(default)
    except (OSError, ValueError) as error:
        stored = default
        startup_errors.append(("Конфигурация", str(error)))

    draft_available = False
    try:
        draft_available = repository.load_draft() is not None
    except (OSError, ValueError) as error:
        startup_errors.append(("Черновик", str(error)))

    sound_library = SoundLibrary(paths.sounds_dir)
    configuration_service = ConfigurationService(
        ConfigurationWorkspace(stored),
        repository,
        sound_library,
    )
    controller_reference: list[AppController] = []

    def controller() -> AppController:
        if not controller_reference:
            raise RuntimeError("Контроллер приложения ещё не создан")
        return controller_reference[0]

    main_window = MainWindow(
        MainWindowCallbacks(
            channel_kind_changed=lambda index, kind: controller().set_channel(
                index,
                kind,
            ),
            application_requested=lambda index: controller().set_channel(
                index,
                "application",
            ),
            volume_changed=lambda index, volume: controller().set_volume(
                index,
                volume,
            ),
            mute_toggled=lambda index: controller().toggle_mute(index),
            sound_import_requested=lambda index: controller().import_sound(index),
            sound_clear_requested=lambda index: controller().clear_sound(index),
            save_preset_requested=lambda: controller().save_active_to_preset(),
            load_preset_requested=lambda index: controller().load_preset(index),
        )
    )
    simulator = PanelSimulator(lambda event: controller().handle_panel_event(event))
    dialogs = DialogService(main_window.widget)
    autostart = WindowsAutostart(
        build_background_command(
            Path(sys.executable),
            packaged=bool(getattr(sys, "frozen", False)),
        )
    )
    settings_dialog = SettingsDialog(
        SettingsController(autostart),
        dialogs.show_error,
        main_window.widget,
    )
    tray = TrayController(
        TrayCallbacks(
            open_main=lambda: controller().show_main_window(),
            open_simulator=lambda: controller().show_simulator(),
            open_settings=lambda: controller().show_settings(),
            exit_application=lambda: controller().request_exit(),
        )
    )
    app_controller = AppController(
        configuration_service=configuration_service,
        editor=PanelConfigurationEditor(),
        sound_library=sound_library,
        main_window=main_window,
        simulator=simulator,
        dialogs=dialogs,
        settings_dialog=settings_dialog,
        tray=tray,
        quit_application=application.quit,
    )
    controller_reference.append(app_controller)

    return RunningApplication(
        application=application,
        paths=paths,
        repository=repository,
        configuration_service=configuration_service,
        sound_library=sound_library,
        main_window=main_window,
        simulator=simulator,
        dialogs=dialogs,
        settings_dialog=settings_dialog,
        tray=tray,
        controller=app_controller,
        single_instance=SingleInstanceController(),
        draft_available=draft_available,
        startup_errors=tuple(startup_errors),
    )


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    _set_qt_identity()
    _ensure_application()
    try:
        running = build_application()
    except Exception as error:
        QMessageBox.critical(None, "Ошибка запуска", str(error))
        return 1

    command = "ping" if options.background else "show"
    if running.single_instance.notify_existing(command):
        running.close()
        return 0
    if not running.tray.is_available():
        running.dialogs.show_error("Системный трей", "Системный трей недоступен")
        running.close()
        return 1

    try:
        running.single_instance.listen(
            running.controller.handle_instance_command
        )
        for title, message in running.startup_errors:
            running.dialogs.show_error(title, message)
        running.controller.start(
            background=options.background,
            draft_available=running.draft_available,
        )
        return running.application.exec()
    except Exception as error:
        running.dialogs.show_error("Ошибка запуска", str(error))
        return 1
    finally:
        running.close()


def _set_qt_identity() -> None:
    QCoreApplication.setOrganizationName(_APPLICATION_NAME)
    QCoreApplication.setApplicationName(_APPLICATION_NAME)


def _ensure_application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application
