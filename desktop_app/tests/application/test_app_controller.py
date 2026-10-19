from pathlib import Path

import pytest

from dj_poltorashka.application.app_controller import AppController
from dj_poltorashka.audio.models import AudioTarget, ChannelAudioUpdate
from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.editor import PanelConfigurationEditor
from dj_poltorashka.configuration.models import (
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
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
from dj_poltorashka.ui.preset_edit_dialog import PresetEditResult


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
        self.fail_save = False

    def save(self, stored: StoredConfiguration) -> None:
        if self.fail_save:
            raise OSError("configuration save failed")
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
        self.audio_states: list[tuple[ChannelAudioUpdate, ...]] = []
        self.show_count = 0
        self.hide_count = 0
        self.activate_count = 0
        self.selected_pages: list[str] = []

    def render(
        self,
        stored: StoredConfiguration,
        audio_states: tuple[ChannelAudioUpdate, ...] = (),
    ) -> None:
        self.rendered.append(stored)
        self.audio_states.append(audio_states)

    def show(self) -> None:
        self.show_count += 1

    def hide(self) -> None:
        self.hide_count += 1

    def activate(self) -> None:
        self.activate_count += 1

    def show_page(self, page: str) -> None:
        self.selected_pages.append(page)
        self.show()
        self.activate()


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
        self.preset_edit_result: PresetEditResult | None = None
        self.edited_presets: list[PresetConfig] = []

    def choose_sound_file(self) -> Path | None:
        return self.sound_path

    def choose_application_file(self) -> Path | None:
        return self.application_path

    def choose_preset(
        self,
        stored: StoredConfiguration,
    ) -> tuple[int, str] | None:
        return self.preset_selection

    def edit_preset(self, preset: PresetConfig, on_save) -> None:
        self.edited_presets.append(preset)
        if self.preset_edit_result is not None:
            on_save(self.preset_edit_result)

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


class FakeAudioCoordinator:
    def __init__(self) -> None:
        self.started: list[PanelConfiguration] = []
        self.applied: list[PanelConfiguration] = []
        self.adopted: list[tuple[PanelConfiguration, int]] = []
        self.revision = 0

    def start(self, panel: PanelConfiguration) -> int:
        self.started.append(panel)
        self.revision += 1
        return self.revision

    def apply_configuration(self, panel: PanelConfiguration) -> int:
        self.applied.append(panel)
        self.revision += 1
        return self.revision

    def adopt_channel(
        self,
        panel: PanelConfiguration,
        channel_index: int,
    ) -> int:
        self.adopted.append((panel, channel_index))
        self.revision += 1
        return self.revision


class FakeSoundPlayback:
    def __init__(self) -> None:
        self.played: list[tuple[int, Path]] = []
        self.play_error: RuntimeError | None = None

    def play(self, button_index: int, path: Path) -> bool:
        if self.play_error is not None:
            raise self.play_error
        self.played.append((button_index, path))
        return True


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
        self.audio = FakeAudioCoordinator()
        self.playback = FakeSoundPlayback()
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
            audio_coordinator=self.audio,
            sound_playback=self.playback,
            quit_application=self.quit_application,
        )

    def quit_application(self) -> None:
        self.quit_count += 1

    def clear_renders(self) -> None:
        self.main_window.rendered.clear()
        self.main_window.audio_states.clear()
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
    assert context.audio.applied[-1] == context.service.stored_configuration.active
    assert_views_show_service_state(context)

    context.clear_renders()
    context.controller.toggle_mute(0)
    assert context.service.stored_configuration.active.channels[0].muted
    assert context.audio.applied[-1] == context.service.stored_configuration.active
    assert_views_show_service_state(context)

    context.clear_renders()
    context.controller.set_channel(1, "microphone")
    assert context.service.stored_configuration.active.channels[1].channel_kind == (
        "microphone"
    )
    assert context.audio.applied[-1] == context.service.stored_configuration.active
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
    assert context.audio.applied == [preset_panel]
    assert_views_show_service_state(context)


def test_edit_preset_changes_only_selected_slot_without_audio_or_draft(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    active = PanelConfigurationEditor.set_volume(initial.active, 0, 0.8)
    old = PresetConfig("Работа", initial.active)
    stored = StoredConfiguration(active, initial.baseline, (old, None, None))
    context = ControllerContext(tmp_path, stored)
    context.repository.draft = active
    edited_panel = PanelConfigurationEditor.set_volume(initial.active, 0, 0.2)
    context.dialogs.preset_edit_result = PresetEditResult("Игры", edited_panel, (None,) * 8)

    context.controller.edit_preset(0)

    updated = context.service.stored_configuration
    assert updated.presets[0] == PresetConfig("Игры", edited_panel)
    assert updated.active == active
    assert updated.baseline == initial.baseline
    assert context.service.is_dirty
    assert context.repository.draft == active
    assert context.audio.applied == context.audio.adopted == []
    assert context.dialogs.edited_presets == [old]
    assert_views_show_service_state(context)


def test_cancelled_preset_edit_changes_nothing(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    stored = StoredConfiguration(initial.active, initial.baseline, (PresetConfig("Работа", initial.active), None, None))
    context = ControllerContext(tmp_path, stored)

    context.controller.edit_preset(0)

    assert context.service.stored_configuration == stored
    assert context.repository.saved == stored
    assert context.audio.applied == []


def test_replaced_sound_imports_only_final_source(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    stored = StoredConfiguration(initial.active, initial.baseline, (PresetConfig("Работа", initial.active), None, None))
    context = ControllerContext(tmp_path, stored)
    final_source = tmp_path / "final.mp3"
    final_source.write_bytes(b"final")
    sources = (final_source,) + (None,) * 7
    context.dialogs.preset_edit_result = PresetEditResult("Работа", initial.active, sources)

    context.controller.edit_preset(0)

    sound = context.service.stored_configuration.presets[0].panel.sound_buttons[0]
    assert sound == SoundButtonConfig("sound-id.mp3", "final")
    assert sorted(path.name for path in (tmp_path / "sounds").iterdir()) == ["sound-id.mp3"]


def test_save_failure_removes_new_sound_and_preserves_state(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    stored = StoredConfiguration(initial.active, initial.baseline, (PresetConfig("Работа", initial.active), None, None))
    context = ControllerContext(tmp_path, stored)
    source = tmp_path / "new.mp3"
    source.write_bytes(b"audio")
    context.dialogs.preset_edit_result = PresetEditResult("Новый", initial.active, (source,) + (None,) * 7)
    context.repository.fail_save = True

    context.controller.edit_preset(0)

    assert context.service.stored_configuration == stored
    assert list((tmp_path / "sounds").iterdir()) == []
    assert context.dialogs.errors == [("Пресет", "configuration save failed")]


def test_second_sound_import_failure_removes_first_import(tmp_path: Path) -> None:
    initial = create_default_stored_configuration()
    stored = StoredConfiguration(initial.active, initial.baseline, (PresetConfig("Работа", initial.active), None, None))
    context = ControllerContext(tmp_path, stored)
    first = tmp_path / "first.mp3"
    first.write_bytes(b"audio")
    missing = tmp_path / "missing.mp3"
    context.dialogs.preset_edit_result = PresetEditResult("Работа", initial.active, (first, missing) + (None,) * 6)

    context.controller.edit_preset(0)

    assert context.service.stored_configuration == stored
    assert list((tmp_path / "sounds").iterdir()) == []
    assert "не найден" in context.dialogs.errors[0][1]


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


def test_application_assignment_adopts_only_selected_channel(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    context.dialogs.application_path = Path("C:/Apps/Player.exe")

    context.controller.set_channel(2, "application")

    panel = context.service.stored_configuration.active
    assert context.audio.applied == []
    assert context.audio.adopted == [(panel, 2)]


@pytest.mark.parametrize("channel_kind", ("master", "microphone", "application"))
def test_duplicate_channel_assignment_is_reported_and_reverted(
    tmp_path: Path,
    channel_kind: str,
) -> None:
    context = ControllerContext(tmp_path)
    if channel_kind == "microphone":
        context.controller.set_channel(1, "microphone")
        duplicate_index = 2
    elif channel_kind == "application":
        context.dialogs.application_path = Path("C:/Apps/Player.exe")
        context.controller.set_channel(1, "application")
        duplicate_index = 2
    else:
        duplicate_index = 1
    context.dialogs.errors.clear()
    context.clear_renders()

    context.controller.set_channel(duplicate_index, channel_kind)

    assert context.dialogs.errors
    assert "уже назначен" in context.dialogs.errors[-1][1]
    assert context.service.stored_configuration.active.channels[
        duplicate_index
    ].channel_kind == "unassigned"
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
    assert context.audio.started == [context.service.stored_configuration.active]
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
    assert context.audio.started == [expected]
    assert_views_show_service_state(context)


def test_external_audio_change_updates_draft_without_echo(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    update = ChannelAudioUpdate(0, 0.25, True, "active", "Динамики", True)

    context.controller.handle_audio_updates((update,))

    active = context.service.stored_configuration.active
    assert active.channels[0].volume == 0.25
    assert active.channels[0].muted
    assert context.service.is_dirty
    assert context.repository.draft == active
    assert context.audio.applied == []
    assert context.main_window.audio_states == [(update,)]
    assert_views_show_service_state(context)


def test_status_only_audio_update_does_not_change_configuration(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    original = context.service.stored_configuration
    update = ChannelAudioUpdate(
        0,
        1.0,
        False,
        "unavailable",
        "Динамики",
        False,
    )

    context.controller.handle_audio_updates((update,))

    assert context.service.stored_configuration == original
    assert not context.service.is_dirty
    assert context.repository.draft is None
    assert context.audio.applied == []
    assert context.main_window.audio_states == [(update,)]
    assert_views_show_service_state(context)


def test_stale_audio_update_is_ignored_after_channel_reassignment(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    context.controller.set_channel(1, "microphone")
    current = context.service.stored_configuration.active.channels[1]
    stale = ChannelAudioUpdate(
        1,
        0.2,
        True,
        "active",
        "Старое устройство",
        True,
        AudioTarget("master"),
    )

    context.controller.handle_audio_updates((stale,))

    assert context.service.stored_configuration.active.channels[1] == current
    assert context.main_window.audio_states[-1] == ()


def test_stale_audio_update_is_ignored_after_local_volume_change(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    context.controller.start(background=True, draft_available=False)
    stale_revision = context.audio.revision
    context.controller.set_volume(0, 0.4)
    stale = ChannelAudioUpdate(
        0,
        0.9,
        False,
        "active",
        "Динамики",
        True,
        AudioTarget("master"),
        revision=stale_revision,
    )

    context.controller.handle_audio_updates((stale,))

    assert context.service.stored_configuration.active.channels[0].volume == 0.4
    assert context.main_window.audio_states[-1] == ()


def test_unassigning_channel_clears_its_runtime_state(tmp_path: Path) -> None:
    context = ControllerContext(tmp_path)
    state = ChannelAudioUpdate(
        0,
        1.0,
        False,
        "active",
        "Динамики",
        False,
        AudioTarget("master"),
    )
    context.controller.handle_audio_updates((state,))

    context.controller.set_channel(0, "unassigned")

    assert context.main_window.audio_states[-1] == ()


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
    assert context.simulator.statuses == ["Кнопка 4 не настроена"]


def test_press_sound_resolves_library_copy_and_starts_playback(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)
    source = tmp_path / "intro.wav"
    source.write_bytes(b"wave")
    context.dialogs.sound_path = source
    context.controller.import_sound(0)
    context.simulator.statuses.clear()

    context.controller.press_sound(0)

    sound = context.service.stored_configuration.active.sound_buttons[0]
    path = context.sound_library.resolve(sound.sound_id or "")
    assert path is not None
    assert context.playback.played == [(0, path)]
    assert context.simulator.statuses == ["Воспроизводится: intro"]


def test_press_sound_handles_empty_button_missing_file_and_player_error(
    tmp_path: Path,
) -> None:
    context = ControllerContext(tmp_path)

    context.controller.press_sound(1)
    assert context.simulator.statuses[-1] == "Кнопка 2 не настроена"
    assert context.playback.played == []

    source = tmp_path / "intro.mp3"
    source.write_bytes(b"mp3")
    context.dialogs.sound_path = source
    context.controller.import_sound(0)
    sound = context.service.stored_configuration.active.sound_buttons[0]
    imported_path = context.sound_library.resolve(sound.sound_id or "")
    assert imported_path is not None
    imported_path.unlink()

    context.controller.press_sound(0)
    assert context.simulator.statuses[-1] == "Звуковой файл не найден: intro"

    source.write_bytes(b"mp3")
    context.dialogs.sound_path = source
    context.controller.import_sound(0)
    context.playback.play_error = RuntimeError("декодер недоступен")
    context.controller.press_sound(0)
    assert context.simulator.statuses[-1] == (
        "Ошибка воспроизведения: декодер недоступен"
    )


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

    assert context.main_window.selected_pages == [
        "configuration", "simulator", "settings", "configuration",
    ]
    assert context.main_window.show_count == 4
    assert context.main_window.activate_count == 4
    assert context.simulator.show_count == 0
    assert context.settings.open_count == 0

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
