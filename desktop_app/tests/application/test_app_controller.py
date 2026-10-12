from pathlib import Path

import pytest

from dj_poltorashka.application.app_controller import AppController
from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.editor import PanelConfigurationEditor
from dj_poltorashka.configuration.models import (
    PanelConfiguration,
    PresetConfig,
    StoredConfiguration,
)
from dj_poltorashka.configuration.service import ConfigurationService
from dj_poltorashka.configuration.workspace import ConfigurationWorkspace
from dj_poltorashka.panel.events import (
    MutePressed,
    PresetPressed,
    SliderChanged,
    SoundPressed,
)
from dj_poltorashka.sounds.library import SoundLibrary


class InMemoryRepository:
    def __init__(
        self,
        stored: StoredConfiguration,
        draft: PanelConfiguration | None = None,
    ) -> None:
        self.saved = stored
        self.draft = draft
        self.fail_draft_save = False
        self.fail_draft_clear = False

    def save(self, stored: StoredConfiguration) -> None:
        self.saved = stored

    def load_draft(self) -> PanelConfiguration | None:
        return self.draft

    def save_draft(self, panel: PanelConfiguration) -> None:
        if self.fail_draft_save:
            raise OSError("draft denied")
        self.draft = panel

    def clear_draft(self) -> None:
        if self.fail_draft_clear:
            raise PermissionError("draft clear failed")
        self.draft = None


class RecordingMainWindow:
    def __init__(self) -> None:
        self.rendered: list[StoredConfiguration] = []
        self.show_count = 0
        self.hide_count = 0
        self.activate_count = 0

    def render(self, stored: StoredConfiguration) -> None:
        self.rendered.append(stored)

    def show(self) -> None:
        self.show_count += 1

    def hide(self) -> None:
        self.hide_count += 1

    def activate(self) -> None:
        self.activate_count += 1


class RecordingSimulator:
    def __init__(self) -> None:
        self.rendered: list[PanelConfiguration] = []
        self.show_count = 0
        self.statuses: list[str] = []

    def render(self, panel: PanelConfiguration) -> None:
        self.rendered.append(panel)

    def show(self) -> None:
        self.show_count += 1

    def set_status(self, message: str) -> None:
        self.statuses.append(message)


class FakeDialogs:
    def __init__(self) -> None:
        self.sound_path: Path | None = None
        self.application_path: Path | None = None
        self.preset_selection: tuple[int, str] | None = None
        self.overwrite_answer = False
        self.exit_choice = "cancel"
        self.restore_answer = False
        self.errors: list[tuple[str, str]] = []

    def choose_sound_file(self) -> Path | None:
        return self.sound_path

    def choose_application_file(self) -> Path | None:
        return self.application_path

    def choose_preset(
        self,
        stored: StoredConfiguration,
    ) -> tuple[int, str] | None:
        return self.preset_selection

    def confirm_overwrite(self, name: str) -> bool:
        return self.overwrite_answer

    def ask_exit(self) -> str:
        return self.exit_choice

    def ask_restore(self) -> bool:
        return self.restore_answer

    def show_error(self, title: str, message: str) -> None:
        self.errors.append((title, message))


class FakeSettingsDialog:
    def __init__(self) -> None:
        self.open_count = 0

    def open(self) -> None:
        self.open_count += 1


class FakeTray:
    def __init__(self) -> None:
        self.show_count = 0
        self.hide_count = 0

    def show(self) -> None:
        self.show_count += 1

    def hide(self) -> None:
        self.hide_count += 1


class ControllerContext:
    def __init__(self, tmp_path: Path, stored: StoredConfiguration | None = None):
        initial = stored or create_default_stored_configuration()
        self.repository = InMemoryRepository(initial)
        self.sound_library = SoundLibrary(tmp_path / "sounds", lambda: "sound-id")
        self.service = ConfigurationService(
            ConfigurationWorkspace(initial),
            self.repository,
            self.sound_library,
        )
        self.main_window = RecordingMainWindow()
        self.simulator = RecordingSimulator()
        self.dialogs = FakeDialogs()
        self.settings = FakeSettingsDialog()
        self.tray = FakeTray()
        self.quit_count = 0
        self.controller = AppController(
            configuration_service=self.service,
            editor=PanelConfigurationEditor(),
            sound_library=self.sound_library,
            main_window=self.main_window,
            simulator=self.simulator,
            dialogs=self.dialogs,
            settings_dialog=self.settings,
            tray=self.tray,
            quit_application=self.quit_application,
        )

    def quit_application(self) -> None:
        self.quit_count += 1

    def clear_renders(self) -> None:
        self.main_window.rendered.clear()
        self.simulator.rendered.clear()


def assert_views_show_service_state(context: ControllerContext) -> None:
    stored = context.service.stored_configuration
    assert context.main_window.rendered == [stored]
    assert context.simulator.rendered == [stored.active]


def test_volume_mute_and_channel_changes_update_service_and_both_views(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)

    context.controller.set_volume(0, 0.3)
    assert context.service.stored_configuration.active.channels[0].volume == 0.3
    assert_views_show_service_state(context)

    context.clear_renders()
    context.controller.toggle_mute(0)
    assert context.service.stored_configuration.active.channels[0].muted
    assert_views_show_service_state(context)

    context.clear_renders()
    context.controller.set_channel(1, "microphone")
    assert context.service.stored_configuration.active.channels[1].channel_kind == (
        "microphone"
    )
    assert_views_show_service_state(context)


def test_import_and_clear_sound_update_service_and_both_views(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    source = tmp_path / "intro.mp3"
    source.write_bytes(b"audio")
    context.dialogs.sound_path = source

    context.controller.import_sound(2)

    imported = context.service.stored_configuration.active.sound_buttons[2]
    assert imported.sound_id == "sound-id.mp3"
    assert imported.display_name == "intro"
    assert_views_show_service_state(context)

    context.clear_renders()
    context.controller.clear_sound(2)

    assert context.service.stored_configuration.active.sound_buttons[2].sound_id is None
    assert_views_show_service_state(context)


def test_load_preset_uses_zero_based_index_and_refreshes_views(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    preset_panel = PanelConfigurationEditor.set_volume(initial.active, 0, 0.2)
    stored = StoredConfiguration(
        active=initial.active,
        baseline=initial.baseline,
        presets=(None, PresetConfig("Игры", preset_panel), None),
    )
    context = ControllerContext(tmp_path, stored)

    context.controller.load_preset(1)

    assert context.service.stored_configuration.active == preset_panel
    assert_views_show_service_state(context)


def test_failed_draft_save_reports_error_and_renders_unchanged_state(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    original = context.service.stored_configuration
    context.repository.fail_draft_save = True

    context.controller.set_volume(0, 0.2)

    assert context.service.stored_configuration == original
    assert context.dialogs.errors == [("Конфигурация", "draft denied")]
    assert_views_show_service_state(context)


def test_failed_sound_import_reports_error_and_keeps_state(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    unsupported = tmp_path / "intro.txt"
    unsupported.write_text("not audio", encoding="utf-8")
    context.dialogs.sound_path = unsupported
    original = context.service.stored_configuration

    context.controller.import_sound(0)

    assert context.service.stored_configuration == original
    assert context.dialogs.errors == [
        ("Импорт звука", "Поддерживаются только файлы MP3 и WAV")
    ]
    assert_views_show_service_state(context)


def test_cancelled_application_selection_restores_actual_view_state(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    original = context.service.stored_configuration
    context.dialogs.application_path = None

    context.controller.set_channel(1, "application")

    assert context.service.stored_configuration == original
    assert_views_show_service_state(context)


@pytest.mark.parametrize(
    ("background", "expected_window_count"),
    ((False, 1), (True, 0)),
)
def test_start_always_shows_tray_and_only_opens_window_when_requested(
    tmp_path: Path,
    background: bool,
    expected_window_count: int,
) -> None:
    context = ControllerContext(tmp_path)

    context.controller.start(background=background, draft_available=False)

    assert context.tray.show_count == 1
    assert context.main_window.show_count == expected_window_count
    assert_views_show_service_state(context)


@pytest.mark.parametrize("restore", (False, True))
def test_start_resolves_recovery_draft_before_rendering(
    tmp_path: Path,
    restore: bool,
) -> None:
    context = ControllerContext(tmp_path)
    draft = PanelConfigurationEditor.set_volume(
        context.service.stored_configuration.active,
        0,
        0.25,
    )
    context.repository.draft = draft
    context.dialogs.restore_answer = restore

    context.controller.start(background=True, draft_available=True)

    expected = draft if restore else context.service.stored_configuration.baseline
    assert context.service.stored_configuration.active == expected
    assert context.repository.draft == (draft if restore else None)
    assert_views_show_service_state(context)


def test_panel_events_route_to_configuration_and_sound_status(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    preset_panel = PanelConfigurationEditor.set_volume(initial.active, 0, 0.4)
    stored = StoredConfiguration(
        active=initial.active,
        baseline=initial.baseline,
        presets=(PresetConfig("Работа", preset_panel), None, None),
    )
    context = ControllerContext(tmp_path, stored)

    context.controller.handle_panel_event(SliderChanged(0, 0.7))
    context.controller.handle_panel_event(MutePressed(0))
    context.controller.handle_panel_event(SoundPressed(3))
    context.controller.handle_panel_event(PresetPressed(0))

    assert context.service.stored_configuration.active == preset_panel
    assert context.simulator.statuses == ["Воспроизведение будет добавлено позже"]


def test_saving_to_occupied_preset_requires_confirmation(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    occupied = PresetConfig("Старый", initial.active)
    stored = StoredConfiguration(
        active=initial.active,
        baseline=initial.baseline,
        presets=(occupied, None, None),
    )
    context = ControllerContext(tmp_path, stored)
    context.dialogs.preset_selection = (0, "Новый")

    context.controller.save_active_to_preset()

    assert context.service.stored_configuration.presets[0] == occupied
    assert context.main_window.rendered == []

    context.dialogs.overwrite_answer = True
    context.controller.save_active_to_preset()

    assert context.service.stored_configuration.presets[0] == PresetConfig(
        "Новый",
        initial.active,
    )
    assert_views_show_service_state(context)


def test_show_commands_open_requested_surfaces(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)

    context.controller.show_main_window()
    context.controller.show_simulator()
    context.controller.show_settings()
    context.controller.handle_instance_command("show")
    context.controller.handle_instance_command("ping")

    assert context.main_window.show_count == 2
    assert context.main_window.activate_count == 2
    assert context.simulator.show_count == 1
    assert context.settings.open_count == 1

    with pytest.raises(ValueError, match="Неизвестная команда экземпляра"):
        context.controller.handle_instance_command("invalid")


def test_clean_exit_hides_tray_and_quits_immediately(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)

    context.controller.request_exit()

    assert context.tray.hide_count == 1
    assert context.quit_count == 1


def test_dirty_exit_can_save_active_configuration_before_quitting(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    context.controller.set_volume(0, 0.6)
    context.dialogs.exit_choice = "save"
    context.dialogs.preset_selection = (1, "Стрим")

    context.controller.request_exit()

    assert context.service.stored_configuration.presets[1] == PresetConfig(
        "Стрим",
        context.service.stored_configuration.active,
    )
    assert context.tray.hide_count == 1
    assert context.quit_count == 1


def test_dirty_exit_can_discard_changes_before_quitting(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    baseline = context.service.stored_configuration.baseline
    context.controller.set_volume(0, 0.6)
    context.dialogs.exit_choice = "discard"

    context.controller.request_exit()

    assert context.service.stored_configuration.active == baseline
    assert context.repository.draft is None
    assert context.tray.hide_count == 1
    assert context.quit_count == 1


def test_dirty_exit_cancel_keeps_application_running(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    context.controller.set_volume(0, 0.6)
    context.dialogs.exit_choice = "cancel"

    context.controller.request_exit()

    assert context.tray.hide_count == 0
    assert context.quit_count == 0


def test_dirty_exit_does_not_quit_when_preset_save_fails(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    context.controller.set_volume(0, 0.6)
    context.dialogs.exit_choice = "save"
    context.dialogs.preset_selection = (0, "Стрим")
    context.repository.fail_draft_clear = True

    context.controller.request_exit()

    assert context.dialogs.errors == [("Пресет", "draft clear failed")]
    assert context.tray.hide_count == 0
    assert context.quit_count == 0
