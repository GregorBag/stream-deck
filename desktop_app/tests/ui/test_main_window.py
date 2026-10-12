from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)
from pytestqt.qtbot import QtBot

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
)
from dj_poltorashka.ui.main_window import MainWindow, MainWindowCallbacks


def no_arguments() -> None:
    return None


def one_argument(value: object) -> None:
    return None


def two_arguments(first: object, second: object) -> None:
    return None


def make_callbacks() -> MainWindowCallbacks:
    return MainWindowCallbacks(
        channel_kind_changed=two_arguments,
        application_requested=one_argument,
        volume_changed=two_arguments,
        mute_toggled=one_argument,
        sound_import_requested=one_argument,
        sound_clear_requested=one_argument,
        save_preset_requested=no_arguments,
        load_preset_requested=one_argument,
    )


class CallbackRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def callbacks(self) -> MainWindowCallbacks:
        return MainWindowCallbacks(
            channel_kind_changed=lambda index, kind: self.calls.append(
                ("channel_kind", index, kind)
            ),
            application_requested=lambda index: self.calls.append(
                ("application", index)
            ),
            volume_changed=lambda index, volume: self.calls.append(
                ("volume", index, volume)
            ),
            mute_toggled=lambda index: self.calls.append(("mute", index)),
            sound_import_requested=lambda index: self.calls.append(
                ("sound_import", index)
            ),
            sound_clear_requested=lambda index: self.calls.append(
                ("sound_clear", index)
            ),
            save_preset_requested=lambda: self.calls.append(("save_preset",)),
            load_preset_requested=lambda index: self.calls.append(
                ("load_preset", index)
            ),
        )


def make_stored_configuration() -> StoredConfiguration:
    panel = PanelConfiguration(
        channels=(
            MixerChannelConfig("unassigned", 0.0, False),
            MixerChannelConfig("master", 0.65, True, display_name="Система"),
            MixerChannelConfig(
                "application",
                0.4,
                False,
                application_path=r"C:\Apps\Player.exe",
                display_name="Player",
            ),
            MixerChannelConfig(
                "microphone",
                0.8,
                False,
                display_name="Микрофон",
            ),
        ),
        sound_buttons=(
            SoundButtonConfig("intro.mp3", "Заставка"),
            *(SoundButtonConfig() for _ in range(7)),
        ),
    )
    return StoredConfiguration(
        active=panel,
        baseline=panel,
        presets=(PresetConfig("Работа", panel), None, None),
    )


def widgets_with_prefix(window: QWidget, prefix: str) -> list[QWidget]:
    return [
        widget
        for widget in window.findChildren(QWidget)
        if widget.objectName().startswith(prefix)
    ]


def test_main_window_builds_approved_editor_layout(qtbot: QtBot) -> None:
    main_window = MainWindow(make_callbacks())
    qtbot.addWidget(main_window.widget)

    title = main_window.widget.findChild(QGroupBox, "active_configuration")
    save_button = main_window.widget.findChild(QPushButton, "save_preset_button")
    channels = main_window.widget.findChild(QWidget, "channels_container")
    presets = main_window.widget.findChild(QWidget, "presets_container")

    assert title is not None
    assert title.title() == "Активная настройка"
    assert save_button is not None
    assert save_button.text() == "Сохранить в пресет"
    assert "..." not in save_button.text()
    assert channels is not None
    assert isinstance(channels.layout(), QHBoxLayout)
    assert channels.layout().count() == 4
    assert len(widgets_with_prefix(main_window.widget, "sound_button_")) == 8
    assert presets is not None
    assert presets.layout().count() == 3


def test_closing_main_window_hides_it_without_quitting(qtbot: QtBot) -> None:
    main_window = MainWindow(make_callbacks())
    qtbot.addWidget(main_window.widget)
    main_window.show()

    assert main_window.is_visible()
    assert not QApplication.quitOnLastWindowClosed()

    main_window.widget.close()

    assert not main_window.is_visible()


def test_render_displays_channels_sounds_and_presets_without_callbacks(
    qtbot: QtBot,
) -> None:
    recorder = CallbackRecorder()
    main_window = MainWindow(recorder.callbacks())
    qtbot.addWidget(main_window.widget)

    main_window.render(make_stored_configuration())

    kinds = [
        main_window.widget.findChild(QComboBox, f"channel_kind_{index}").currentData()
        for index in range(4)
    ]
    assert kinds == ["unassigned", "master", "application", "microphone"]
    assert not main_window.widget.findChild(QSlider, "volume_slider_0").isEnabled()
    assert not main_window.widget.findChild(QPushButton, "mute_button_0").isEnabled()
    assert main_window.widget.findChild(QSlider, "volume_slider_1").value() == 65
    assert main_window.widget.findChild(QPushButton, "mute_button_1").isChecked()
    assert main_window.widget.findChild(QLabel, "channel_name_2").text() == "Player"
    assert main_window.widget.findChild(QPushButton, "application_button_2").isEnabled()
    assert main_window.widget.findChild(QLabel, "sound_name_0").text() == "Заставка"
    assert main_window.widget.findChild(QPushButton, "sound_clear_0").isEnabled()
    assert not main_window.widget.findChild(QPushButton, "sound_clear_1").isEnabled()
    assert main_window.widget.findChild(QLabel, "preset_name_0").text() == "Работа"
    assert main_window.widget.findChild(QPushButton, "preset_load_0").isEnabled()
    assert not main_window.widget.findChild(QPushButton, "preset_load_1").isEnabled()
    assert recorder.calls == []


def test_editor_controls_forward_zero_based_actions(qtbot: QtBot) -> None:
    recorder = CallbackRecorder()
    main_window = MainWindow(recorder.callbacks())
    qtbot.addWidget(main_window.widget)
    main_window.render(make_stored_configuration())

    channel_kind = main_window.widget.findChild(QComboBox, "channel_kind_1")
    channel_kind.setCurrentIndex(channel_kind.findData("microphone"))
    qtbot.mouseClick(
        main_window.widget.findChild(QPushButton, "application_button_2"),
        Qt.LeftButton,
    )
    main_window.widget.findChild(QSlider, "volume_slider_1").setValue(45)
    qtbot.mouseClick(
        main_window.widget.findChild(QPushButton, "mute_button_1"),
        Qt.LeftButton,
    )
    qtbot.mouseClick(
        main_window.widget.findChild(QPushButton, "sound_import_0"),
        Qt.LeftButton,
    )
    qtbot.mouseClick(
        main_window.widget.findChild(QPushButton, "sound_clear_0"),
        Qt.LeftButton,
    )
    qtbot.mouseClick(
        main_window.widget.findChild(QPushButton, "save_preset_button"),
        Qt.LeftButton,
    )
    qtbot.mouseClick(
        main_window.widget.findChild(QPushButton, "preset_load_0"),
        Qt.LeftButton,
    )

    assert recorder.calls == [
        ("channel_kind", 1, "microphone"),
        ("application", 2),
        ("volume", 1, 0.45),
        ("mute", 1),
        ("sound_import", 0),
        ("sound_clear", 0),
        ("save_preset",),
        ("load_preset", 0),
    ]
