"""Сборка и запуск настольного приложения."""

import argparse
from dataclasses import dataclass, field, replace
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
from dj_poltorashka.panel.lighting import LightingSettings, LightingSettingsRepository
from dj_poltorashka.panel.lighting_frame import build_lighting_frame
from dj_poltorashka.panel.protocol import LedUpdate
from dj_poltorashka.panel.events import MutePressed, PresetPressed, SoundPressed
from dj_poltorashka.panel.transport import EMULATOR_PORT
from dj_poltorashka.panel.worker import PanelCoordinator
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
    panel_coordinator: PanelCoordinator
    controller: AppController
    single_instance: SingleInstanceController
    draft_available: bool
    startup_errors: tuple[tuple[str, str], ...]
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.panel_coordinator.close()
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
    lighting_repository = LightingSettingsRepository(paths.root / "lighting.json")
    try:
        lighting_settings = lighting_repository.load()
    except (OSError, ValueError) as error:
        lighting_settings = LightingSettings()
        startup_errors.append(("Подсветка панели", str(error)))
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
    panel_reference: list[PanelCoordinator] = []

    def handle_simulator_event(event) -> None:
        if panel_reference and panel_reference[0].selected_port == EMULATOR_PORT:
            if isinstance(event, SoundPressed):
                panel_reference[0].press_emulated_button(event.button_index)
                return
            if isinstance(event, MutePressed):
                panel_reference[0].press_emulated_button(event.channel_index + 8)
                return
            if isinstance(event, PresetPressed):
                panel_reference[0].press_emulated_button(event.preset_index + 12)
                return
        controller().handle_panel_event(event)

    simulator = PanelSimulator(handle_simulator_event)
    panel_status_consumers = []

    def receive_panel_events(events) -> None:
        for event in events:
            controller().handle_panel_event(event)

    def report_panel_status(status) -> None:
        for consumer in tuple(panel_status_consumers):
            consumer(status)

    panel_coordinator = PanelCoordinator(receive_panel_events, report_panel_status)
    panel_reference.append(panel_coordinator)
    settings_controller_reference: list[SettingsController] = []
    playing_buttons: set[int] = set()

    def refresh_panel_lighting(stored=None) -> None:
        if not settings_controller_reference:
            return
        current = settings_controller_reference[0].lighting_settings()
        brightness = round(current.brightness * 100)
        frame = build_lighting_frame(
            stored or configuration_service.stored_configuration,
            replace(current, brightness=brightness / 100),
            connected=True,
            playing_buttons=frozenset(playing_buttons),
        )
        panel_coordinator.set_lighting(LedUpdate(brightness, frame.perimeter + frame.buttons))

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
        playing_buttons.discard(button_index)
        refresh_panel_lighting()

    def report_sound_started(index: int, path: Path) -> None:
        simulator.set_status(f"Воспроизводится: {path.stem}")
        playing_buttons.add(index)
        refresh_panel_lighting()

    def report_sound_finished(index: int) -> None:
        simulator.set_status("Воспроизведение завершено")
        playing_buttons.discard(index)
        refresh_panel_lighting()

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
        report_sound_started,
        report_sound_finished,
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
        lighting_repository=lighting_repository,
        initial_lighting_settings=lighting_settings,
        panel_coordinator=panel_coordinator,
        on_lighting_change=lambda settings: refresh_panel_lighting(),
    )
    settings_controller_reference.append(settings_controller)
    settings_dialog = SettingsDialog(
        settings_controller,
        dialogs.show_error,
        main_window.widget,
    )
    panel_status_consumers.append(settings_dialog.set_panel_connection_status)
    panel_coordinator.on_ports_changed = settings_dialog.refresh_panel_ports
    main_window.add_panel_pages(
        simulator.widget,
        settings_dialog.widget,
        settings_dialog.refresh,
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
        on_configuration_change=refresh_panel_lighting,
    )
    controller_reference.append(app_controller)
    refresh_panel_lighting()

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
        panel_coordinator=panel_coordinator,
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
