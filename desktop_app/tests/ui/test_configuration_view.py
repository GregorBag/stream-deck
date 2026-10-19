from dataclasses import replace

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtQuickWidgets import QQuickWidget

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.ui.configuration_view import ConfigurationView
from qml_helpers import click_item, find_item, value
from test_main_window import CallbackRecorder, make_stored_configuration


def make_view(qtbot):
    recorder = CallbackRecorder()
    view = ConfigurationView(recorder.callbacks())
    qtbot.addWidget(view.widget)
    view.widget.resize(1240, 740)
    view.render(make_stored_configuration())
    view.widget.show()
    qtbot.waitUntil(lambda: view.widget.status() == QQuickWidget.Ready)
    qtbot.wait(40)
    return view, recorder


def test_render_does_not_emit_commands(qtbot):
    view, recorder = make_view(qtbot)
    root = view.widget.rootObject()
    assert len(value(root, "channels")) == 4
    assert len(value(root, "sounds")) == 8
    assert len(value(root, "presets")) == 3
    assert find_item(root, "volume_slider_1").property("value") == 65
    assert find_item(root, "channel_name_2").property("text") == "Player"
    assert value(root, "channels")[1]["muted"]
    assert value(root, "sounds")[0]["name"] == "Заставка"
    assert value(root, "presets")[0]["name"] == "Работа"
    assert recorder.calls == []
    view.render(make_stored_configuration(), (ChannelAudioUpdate(1, 0.65, True, "active", "Динамики", False),))
    assert find_item(root, "channel_name_1").property("text") == "Динамики"
    assert recorder.calls == []


@pytest.mark.parametrize("name, expected", [
    ("application_button_2", ("application", 2)),
    ("mute_button_1", ("mute", 1)),
    ("sound_import_0", ("sound_import", 0)),
    ("sound_clear_0", ("sound_clear", 0)),
    ("save_preset_button", ("save_preset",)),
    ("preset_load_0", ("load_preset", 0)),
    ("preset_edit_0", ("edit_preset", 0)),
])
def test_actions_dispatch_once(qtbot, name, expected):
    view, recorder = make_view(qtbot)
    click_item(qtbot, view.widget, find_item(view.widget.rootObject(), name))
    assert recorder.calls == [expected]


def test_unassigned_controls_and_empty_presets_are_disabled(qtbot):
    view, recorder = make_view(qtbot)
    root = view.widget.rootObject()
    for name in ("volume_slider_0", "mute_button_0", "application_button_1", "sound_clear_1", "preset_load_1", "preset_edit_1"):
        item = find_item(root, name)
        assert not item.isEnabled()
        click_item(qtbot, view.widget, item)
    assert recorder.calls == []


def test_render_updates_existing_delegate_and_long_name_preserves_fader(qtbot):
    view, recorder = make_view(qtbot)
    root = view.widget.rootObject()
    slider = find_item(root, "volume_slider_1")
    previous_height = slider.height()
    stored = make_stored_configuration()
    channels = list(stored.active.channels)
    long_name = "Очень длинное название устройства " * 8
    channels[1] = replace(channels[1], display_name=long_name.strip(), volume=0.2)
    view.render(replace(stored, active=replace(stored.active, channels=tuple(channels))))
    qtbot.wait(20)
    assert find_item(root, "volume_slider_1") is slider
    assert slider.height() == previous_height
    assert slider.property("value") == 20
    label = find_item(root, "channel_name_1")
    assert label.property("text") == long_name.strip()
    assert label.property("truncated")
    assert recorder.calls == []


@pytest.mark.parametrize("channel_index, icon", [(1, "speaker"), (3, "microphone")])
def test_microphone_and_speaker_mute_icons(qtbot, channel_index, icon):
    view, _ = make_view(qtbot)
    stored = make_stored_configuration()
    channels = list(stored.active.channels)
    for muted in (False, True, False):
        channels[channel_index] = replace(channels[channel_index], muted=muted)
        view.render(replace(stored, active=replace(stored.active, channels=tuple(channels))))
        button = find_item(view.widget.rootObject(), f"mute_button_{channel_index}")
        assert button.property("icon_name") == (f"{icon}_muted" if muted else icon)


@pytest.mark.parametrize("key, expected", [(Qt.Key_Home, 0), (Qt.Key_End, 100)])
def test_fader_endpoints_and_keyboard(qtbot, key, expected):
    view, recorder = make_view(qtbot)
    slider = find_item(view.widget.rootObject(), "volume_slider_1")
    slider.forceActiveFocus()
    qtbot.keyClick(view.widget, key)
    assert slider.property("value") == expected
    assert recorder.calls == [("volume", 1, expected / 100)]
    handle = find_item(slider, "fader_handle")
    if expected == 100:
        assert handle.y() == 0
    else:
        assert handle.y() + handle.height() == slider.height()


def test_silent_render_restores_fader_and_readout_after_user_change(qtbot):
    view, recorder = make_view(qtbot)
    root = view.widget.rootObject()
    slider = find_item(root, "volume_slider_1")
    slider.forceActiveFocus()
    qtbot.keyClick(view.widget, Qt.Key_Home)
    assert find_item(root, "volume_value_1").property("text") == "0%"
    view.render(make_stored_configuration())
    assert slider.property("value") == 65
    assert find_item(root, "volume_value_1").property("text") == "65%"
    assert recorder.calls == [("volume", 1, 0.0)]


@pytest.mark.parametrize("start, target", [("sound_import_3", "sound_import_4"), ("preset_load_0", "preset_edit_0")])
def test_keyboard_focus_scrolls_into_view_in_small_window(qtbot, start, target):
    view, _ = make_view(qtbot)
    view.widget.resize(852, 470)
    root = view.widget.rootObject()
    find_item(root, start).forceActiveFocus()
    qtbot.keyClick(view.widget, Qt.Key_Tab)
    qtbot.wait(30)
    item = find_item(root, target)
    assert item.hasActiveFocus()
    point = item.mapToScene(QPointF(0, 0))
    assert point.x() >= 0 and point.y() >= 0
    assert point.x() + item.width() <= view.widget.width()
    assert point.y() + item.height() <= view.widget.height()


@pytest.mark.parametrize("name", ("sound_clear_0", "sound_import_0", "application_button_2"))
def test_button_icons_fit_inside_content_without_clipping(qtbot, name):
    view, _ = make_view(qtbot)
    button = find_item(view.widget.rootObject(), name)
    content = button.property("contentItem")
    glyph = content.childItems()[0]
    assert glyph.x() >= 0 and glyph.y() >= 0
    assert glyph.x() + glyph.width() <= content.width()
    assert glyph.y() + glyph.height() <= content.height()


def test_drag_survives_external_render(qtbot):
    view, recorder = make_view(qtbot)
    root = view.widget.rootObject()
    slider = find_item(root, "volume_slider_1")
    point = slider.mapToScene(QPointF(slider.width() / 2, slider.height() / 2)).toPoint()
    qtbot.mousePress(view.widget, Qt.LeftButton, pos=point)
    qtbot.wait(20)
    assert slider.property("pressed")
    dragging_value = slider.property("value")
    view.render(make_stored_configuration())
    qtbot.wait(20)
    assert find_item(root, "volume_slider_1") is slider
    assert slider.property("pressed")
    assert slider.property("value") == dragging_value
    destination = slider.mapToScene(QPointF(slider.width() / 2, slider.height() / 4)).toPoint()
    qtbot.mouseMove(view.widget, pos=destination)
    qtbot.wait(20)
    assert slider.property("value") > dragging_value
    confirmed = slider.property("value")
    stored = make_stored_configuration()
    channels = list(stored.active.channels)
    channels[1] = replace(channels[1], volume=confirmed / 100)
    view.render(replace(stored, active=replace(stored.active, channels=tuple(channels))))
    qtbot.mouseRelease(view.widget, Qt.LeftButton, pos=destination)
    assert not slider.property("pressed")
    assert slider.property("value") == confirmed
    assert recorder.calls[-1] == ("volume", 1, confirmed / 100)


def test_virtual_microphone_status_has_single_compact_label(qtbot):
    view, _ = make_view(qtbot)
    view.set_virtual_microphone_status(AudioRoutingStatus("active", "Виртуальный микрофон активен"))
    assert find_item(view.widget.rootObject(), "virtual_microphone_status").property("text") == "Виртуальный микрофон: активен"


def test_qml_load_errors_are_reported(qtbot, tmp_path):
    invalid = tmp_path / "invalid.qml"
    invalid.write_text("import QtQuick\nThisIsNotAType {}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="QML"):
        ConfigurationView(CallbackRecorder().callbacks(), source_path=invalid)


def test_qml_loads_and_renders_without_warnings(qtbot, qtlog):
    view, _ = make_view(qtbot)
    view.render(make_stored_configuration())
    qtbot.wait(20)
    assert qtlog.records == []


def test_kind_combo_activates_and_silent_render_restores_selection(qtbot):
    view, recorder = make_view(qtbot)
    combo = find_item(view.widget.rootObject(), "channel_kind_1")
    combo.forceActiveFocus()
    qtbot.keyClick(view.widget, Qt.Key_Down)
    assert recorder.calls == [("channel_kind", 1, "application")]
    view.render(make_stored_configuration())
    assert combo.property("currentIndex") == 1
    assert recorder.calls == [("channel_kind", 1, "application")]


@pytest.mark.parametrize("at_top, expected", [(True, 100), (False, 0)])
def test_fader_mouse_reaches_endpoints(qtbot, at_top, expected):
    view, recorder = make_view(qtbot)
    slider = find_item(view.widget.rootObject(), "volume_slider_1")
    point = slider.mapToScene(QPointF(slider.width() / 2, 0 if at_top else slider.height() - 1)).toPoint()
    qtbot.mouseClick(view.widget, Qt.LeftButton, pos=point)
    assert slider.property("value") == expected
    assert recorder.calls == [("volume", 1, expected / 100)]
