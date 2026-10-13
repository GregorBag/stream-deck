from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)
import pytest
from pytestqt.qtbot import QtBot

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
)
from dj_poltorashka.panel.events import (
    MutePressed,
    PanelEvent,
    PanelPauseChanged,
    PresetPressed,
    SliderChanged,
    SoundPressed,
)
from dj_poltorashka.ui.panel_simulator import PanelSimulator


def make_panel() -> PanelConfiguration:
    return PanelConfiguration(
        channels=(
            MixerChannelConfig("master", 0.6, False),
            MixerChannelConfig("unassigned", 0.0, False),
            MixerChannelConfig("microphone", 0.4, True),
            MixerChannelConfig("unassigned", 0.0, False),
        ),
        sound_buttons=(
            SoundButtonConfig("intro.mp3", "Заставка"),
            *(SoundButtonConfig() for _ in range(7)),
        ),
    )


def widgets_with_prefix(window: QWidget, prefix: str) -> list[QWidget]:
    return [
        widget
        for widget in window.findChildren(QWidget)
        if widget.objectName().startswith(prefix)
    ]


def test_simulator_builds_all_physical_controls(qtbot: QtBot) -> None:
    simulator = PanelSimulator(lambda event: None)
    qtbot.addWidget(simulator.widget)

    assert len(widgets_with_prefix(simulator.widget, "simulator_slider_")) == 4
    assert len(widgets_with_prefix(simulator.widget, "simulator_mute_")) == 4
    assert len(widgets_with_prefix(simulator.widget, "simulator_sound_")) == 8
    assert len(widgets_with_prefix(simulator.widget, "simulator_preset_")) == 3
    assert simulator.widget.findChild(QCheckBox, "simulator_pause") is not None


def test_render_updates_controls_without_emitting_events(qtbot: QtBot) -> None:
    events: list[PanelEvent] = []
    simulator = PanelSimulator(events.append)
    qtbot.addWidget(simulator.widget)

    simulator.render(make_panel())

    assert simulator.widget.findChild(QSlider, "simulator_slider_0").value() == 60
    assert simulator.widget.findChild(QSlider, "simulator_slider_0").isEnabled()
    assert not simulator.widget.findChild(QSlider, "simulator_slider_1").isEnabled()
    assert simulator.widget.findChild(QPushButton, "simulator_mute_2").isChecked()
    assert simulator.widget.findChild(QPushButton, "simulator_sound_0").isEnabled()
    assert simulator.widget.findChild(QPushButton, "simulator_sound_0").text() == "Заставка"
    assert not simulator.widget.findChild(QPushButton, "simulator_sound_1").isEnabled()
    assert events == []


def test_controls_emit_zero_based_panel_events(qtbot: QtBot) -> None:
    events: list[PanelEvent] = []
    simulator = PanelSimulator(events.append)
    qtbot.addWidget(simulator.widget)
    simulator.render(make_panel())

    simulator.widget.findChild(QSlider, "simulator_slider_0").setValue(25)
    qtbot.mouseClick(
        simulator.widget.findChild(QPushButton, "simulator_mute_0"),
        Qt.LeftButton,
    )
    qtbot.mouseClick(
        simulator.widget.findChild(QPushButton, "simulator_sound_0"),
        Qt.LeftButton,
    )
    qtbot.mouseClick(
        simulator.widget.findChild(QPushButton, "simulator_preset_2"),
        Qt.LeftButton,
    )

    assert events == [
        SliderChanged(0, 0.25),
        MutePressed(0),
        SoundPressed(0),
        PresetPressed(2),
    ]
    assert "Кнопка 1" in simulator.widget.findChild(
        QLabel,
        "simulator_status",
    ).text()


def test_pause_emits_event_and_disables_all_other_controls(qtbot: QtBot) -> None:
    events: list[PanelEvent] = []
    simulator = PanelSimulator(events.append)
    qtbot.addWidget(simulator.widget)
    simulator.render(make_panel())
    pause = simulator.widget.findChild(QCheckBox, "simulator_pause")

    pause.setChecked(True)

    assert events == [PanelPauseChanged(True)]
    assert not simulator.widget.findChild(QSlider, "simulator_slider_0").isEnabled()
    assert not simulator.widget.findChild(QPushButton, "simulator_mute_0").isEnabled()
    assert not simulator.widget.findChild(QPushButton, "simulator_sound_0").isEnabled()
    assert not simulator.widget.findChild(QPushButton, "simulator_preset_0").isEnabled()
    assert pause.isEnabled()

    pause.setChecked(False)

    assert events[-1] == PanelPauseChanged(False)
    assert simulator.widget.findChild(QSlider, "simulator_slider_0").isEnabled()


@pytest.mark.parametrize(
    "message",
    (
        "Воспроизводится: Заставка",
        "Ошибка воспроизведения: файл не найден",
    ),
)
def test_set_status_shows_playback_result(
    qtbot: QtBot,
    message: str,
) -> None:
    simulator = PanelSimulator(lambda event: None)
    qtbot.addWidget(simulator.widget)

    simulator.set_status(message)

    assert simulator.widget.findChild(QLabel, "simulator_status").text() == message
