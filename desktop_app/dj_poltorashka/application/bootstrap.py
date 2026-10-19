"""Сборка и запуск настольного приложения."""

import argparse
from dataclasses import dataclass, field
import logging
from pathlib import Path
from collections.abc import Callable, Sequence
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
from dj_poltorashka.audio.service import AudioService, UnavailableAudioBackend
from dj_poltorashka.audio.device_registry import QtAudioDeviceRegistry
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.audio.routing_service import AudioRoutingService
from dj_poltorashka.audio.routing_settings import (
    AudioRoutingSettings,
    AudioRoutingSettingsRepository,
)
from dj_poltorashka.audio.windows_backend import WindowsAudioBackend
from dj_poltorashka.audio.worker import AudioCoordinator
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
from dj_poltorashka.sounds.playback import SoundPlaybackService
from dj_poltorashka.sounds.qt_player import QtSoundPlayerFactory
from dj_poltorashka.ui.dialog_service import DialogService
from dj_poltorashka.ui.main_window import MainWindow, MainWindowCallbacks
from dj_poltorashka.ui.panel_simulator import PanelSimulator
from dj_poltorashka.ui.settings_dialog import SettingsDialog
from dj_poltorashka.ui.tray_controller import TrayCallbacks, TrayController


_APPLICATION_NAME = "DJ Poltorashka"
_LOGGER = logging.getLogger(__name__)


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
    audio_coordinator: AudioCoordinator
    sound_playback: SoundPlaybackService
    audio_routing_service: AudioRoutingService
    audio_device_registry: QtAudioDeviceRegistry
    controller: AppController
    single_instance: SingleInstanceController
    draft_available: bool
    startup_errors: tuple[tuple[str, str], ...]
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.sound_playback.close()
        self.audio_routing_service.close()
        self.audio_coordinator.close()
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
    routing_repository = AudioRoutingSettingsRepository(paths.settings_file)
    try:
        routing_settings = routing_repository.load()
    except (OSError, ValueError) as error:
        routing_settings = AudioRoutingSettings()
        startup_errors.append(("Виртуальный микрофон", str(error)))
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
    try:
        audio_backend = WindowsAudioBackend()
    except Exception as error:
        message = str(error).strip() or type(error).__name__
        startup_errors.append(("Аудиосистема", message))
        audio_backend = UnavailableAudioBackend(message)
    audio_service = AudioService(audio_backend)
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
            edit_preset_requested=lambda index: controller().edit_preset(index),
        )
    )
    simulator = PanelSimulator(lambda event: controller().handle_panel_event(event))

    routing_status_consumers: list[Callable[[AudioRoutingStatus], None]] = []

    def report_routing_status(status: AudioRoutingStatus) -> None:
        if status.code == "pipeline_error":
            _LOGGER.error("Ошибка виртуального микрофона: %s", status.message)
        elif status.code != "active":
            _LOGGER.warning("Виртуальный микрофон: %s", status.message)
        for consumer in tuple(routing_status_consumers):
            consumer(status)

    audio_device_registry = QtAudioDeviceRegistry()
    audio_routing_service = AudioRoutingService(
        audio_device_registry,
        routing_settings,
        report_routing_status,
    )

    def report_sound_error(button_index: int, message: str) -> None:
        _LOGGER.error(
            "Ошибка звуковой кнопки %s: %s",
            button_index + 1,
            message,
        )
        simulator.set_status(f"Ошибка воспроизведения: {message}")

    settings_controller_reference: list[SettingsController] = []

    def current_mix_gains() -> tuple[float, float]:
        current = settings_controller_reference[0].routing_settings()
        return current.microphone_gain, current.sound_gain

    sound_player_factory = QtSoundPlayerFactory(
        monitor_device_provider=audio_routing_service.monitor_device,
        cable_device_provider=audio_routing_service.cable_device,
        mix_gains_provider=current_mix_gains,
        on_routing_error=audio_routing_service.report_pipeline_error,
        on_routing_active=audio_routing_service.report_pipeline_active,
    )
    sound_playback = SoundPlaybackService(
        sound_player_factory,
        lambda index, path: simulator.set_status(
            f"Воспроизводится: {path.stem}"
        ),
        lambda index: simulator.set_status("Воспроизведение завершено"),
        report_sound_error,
    )
    dialogs = DialogService(main_window.widget)

    def report_audio_error(message: str) -> None:
        _LOGGER.error("Ошибка аудиосистемы: %s", message)
        dialogs.show_error("Аудиосистема", message)

    audio_coordinator = AudioCoordinator(
        audio_service,
        lambda updates: controller().handle_audio_updates(updates),
        report_audio_error,
    )
    autostart = WindowsAutostart(
        build_background_command(
            Path(sys.executable),
            packaged=bool(getattr(sys, "frozen", False)),
        )
    )
    def apply_routing_settings(settings: AudioRoutingSettings) -> None:
        audio_routing_service.apply(settings)
        sound_player_factory.update_output_devices()
        sound_player_factory.update_mix_gains()

    settings_controller = SettingsController(
        autostart,
        routing_repository,
        audio_device_registry,
        apply_routing_settings,
        routing_settings,
    )
    settings_controller_reference.append(settings_controller)
    settings_dialog = SettingsDialog(
        settings_controller,
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
    routing_status_consumers.extend(
        (
            main_window.set_virtual_microphone_status,
            settings_dialog.set_virtual_microphone_status,
            tray.set_virtual_microphone_status,
        )
    )
    audio_routing_service.start()
    app_controller = AppController(
        configuration_service=configuration_service,
        editor=PanelConfigurationEditor(),
        sound_library=sound_library,
        main_window=main_window,
        simulator=simulator,
        dialogs=dialogs,
        settings_dialog=settings_dialog,
        tray=tray,
        audio_coordinator=audio_coordinator,
        sound_playback=sound_playback,
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
        audio_coordinator=audio_coordinator,
        sound_playback=sound_playback,
        audio_routing_service=audio_routing_service,
        audio_device_registry=audio_device_registry,
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
    except Exception as error:
        if running.single_instance.notify_existing(command):
            running.close()
            return 0
        running.dialogs.show_error("Ошибка запуска", str(error))
        running.close()
        return 1

    try:
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
