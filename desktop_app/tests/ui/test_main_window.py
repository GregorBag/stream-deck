from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSlider,
    QStatusBar,
    QStyle,
    QStyleOptionSlider,
    QWidget,
)
from pytestqt.qtbot import QtBot
from PySide6.QtQuickWidgets import QQuickWidget
from qml_helpers import find_item, click_item

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
)
from dj_poltorashka.ui.main_window import MainWindow, MainWindowCallbacks
from dj_poltorashka.ui.panel_simulator import PanelSimulator
from dj_poltorashka.ui.theme import make_icon


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
        edit_preset_requested=one_argument,
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
            edit_preset_requested=lambda index: self.calls.append(
                ("edit_preset", index)
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


def test_closing_main_window_hides_it_without_quitting(qtbot: QtBot) -> None:
    main_window = MainWindow(make_callbacks())
    qtbot.addWidget(main_window.widget)
    main_window.show()

    assert main_window.is_visible()
    assert not QApplication.quitOnLastWindowClosed()

    main_window.widget.close()

    assert not main_window.is_visible()


def test_activate_raises_and_activates_visible_window(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    main_window = MainWindow(make_callbacks())
    qtbot.addWidget(main_window.widget)
    calls: list[str] = []
    monkeypatch.setattr(main_window.widget, "raise_", lambda: calls.append("raise"))
    monkeypatch.setattr(
        main_window.widget,
        "activateWindow",
        lambda: calls.append("activate"),
    )

    main_window.activate()

    assert main_window.is_visible()
    assert calls == ["raise", "activate"]


def test_activate_restores_minimized_window(qtbot: QtBot) -> None:
    main_window = MainWindow(make_callbacks())
    qtbot.addWidget(main_window.widget)
    main_window.show()
    main_window.widget.showMinimized()
    assert main_window.widget.isMinimized()

    main_window.activate()

    assert not main_window.widget.isMinimized()



def test_main_window_embeds_configuration_and_renders_silently(qtbot):
    recorder = CallbackRecorder()
    window = MainWindow(recorder.callbacks())
    qtbot.addWidget(window.widget)
    window.render(make_stored_configuration())
    page = window.widget.findChild(QQuickWidget, "configuration_page")
    assert page is not None
    assert page.status() == QQuickWidget.Ready
    root = page.rootObject()
    assert find_item(root, "volume_slider_1").property("value") == 65
    assert find_item(root, "channel_name_2").property("text") == "Player"
    assert recorder.calls == []
    window.show()
    QApplication.processEvents()
    click_item(qtbot, page, find_item(root, "save_preset_button"))
    assert recorder.calls == [("save_preset",)]


def test_main_window_displays_status_once(qtbot):
    window = MainWindow(make_callbacks())
    qtbot.addWidget(window.widget)
    page = window.widget.findChild(QQuickWidget)
    label = find_item(page.rootObject(), "virtual_microphone_status")
    for state, expected in (
        (AudioRoutingStatus("active", "Виртуальный микрофон активен"), "активен"),
        (AudioRoutingStatus("cable_missing", "VB-CABLE не найден"), "VB-CABLE не найден"),
    ):
        window.set_virtual_microphone_status(state)
        assert label.property("text") == f"Виртуальный микрофон: {expected}"
    assert window.widget.findChild(QStatusBar) is None


def test_header_does_not_claim_a_physical_panel_is_connected(qtbot):
    window = MainWindow(make_callbacks())
    qtbot.addWidget(window.widget)
    badge = window.widget.findChild(QLabel, "panel_connection_status")
    assert "не подключена" in badge.text().lower()


@pytest.mark.parametrize("channel_index", (1, 3))
def test_simulator_mute_icon_follows_rendered_state(qtbot, channel_index):
    view = PanelSimulator(lambda event: None)
    qtbot.addWidget(view.widget)
    stored = make_stored_configuration()
    channels = list(stored.active.channels)
    icon_name = "microphone" if channel_index == 3 else "speaker"
    for muted in (True, False, True):
        channels[channel_index] = replace(channels[channel_index], muted=muted)
        view.render(replace(stored.active, channels=tuple(channels)))
        button = view.widget.findChild(QPushButton, f"simulator_mute_{channel_index}")
        expected = make_icon(f"{icon_name}_muted" if muted else icon_name, size=18).pixmap(18, 18).toImage()
        assert button.icon().pixmap(18, 18).toImage() == expected
        assert button.text() == ("Включить звук" if muted else "Заглушить")


@pytest.mark.parametrize("value", (0, 100))
def test_simulator_fader_reaches_visible_track_ends(qtbot, value):
    view = PanelSimulator(lambda event: None)
    qtbot.addWidget(view.widget)
    view.render(make_stored_configuration().active)
    view.show()
    QApplication.processEvents()
    slider = view.widget.findChild(QSlider, "simulator_slider_1")
    slider.setValue(value)
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    groove = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, slider)
    handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
    assert handle.top() <= groove.top() if value == 100 else handle.bottom() >= groove.bottom()
