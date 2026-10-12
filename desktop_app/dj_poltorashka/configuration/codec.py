"""Преобразование конфигурации в JSON-совместимые значения и обратно."""

from typing import cast

from dj_poltorashka.configuration.models import (
    ChannelKind,
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
)


_SCHEMA_VERSION = 1
_CHANNEL_KINDS = ("unassigned", "master", "application", "microphone")


def encode_panel_configuration(panel: PanelConfiguration) -> dict[str, object]:
    return {
        "channels": [
            {
                "channel_kind": channel.channel_kind,
                "volume": channel.volume,
                "muted": channel.muted,
                "application_path": channel.application_path,
                "display_name": channel.display_name,
            }
            for channel in panel.channels
        ],
        "sound_buttons": [
            {
                "sound_id": button.sound_id,
                "display_name": button.display_name,
            }
            for button in panel.sound_buttons
        ],
    }


def decode_panel_configuration(data: object) -> PanelConfiguration:
    return _decode_panel_configuration(data, "panel")


def encode_stored_configuration(stored: StoredConfiguration) -> dict[str, object]:
    presets: list[object] = []
    for preset in stored.presets:
        if preset is None:
            presets.append(None)
        else:
            presets.append(
                {
                    "name": preset.name,
                    "panel": encode_panel_configuration(preset.panel),
                }
            )

    return {
        "schema_version": _SCHEMA_VERSION,
        "active": encode_panel_configuration(stored.active),
        "baseline": encode_panel_configuration(stored.baseline),
        "presets": presets,
    }


def decode_stored_configuration(data: object) -> StoredConfiguration:
    root = _require_mapping(data, "root")
    schema_version = _required(root, "schema_version", "")
    if isinstance(schema_version, bool) or schema_version != _SCHEMA_VERSION:
        raise ValueError(
            f"schema_version: поддерживается только версия {_SCHEMA_VERSION}"
        )

    active = _decode_panel_configuration(_required(root, "active", ""), "active")
    baseline = _decode_panel_configuration(
        _required(root, "baseline", ""),
        "baseline",
    )
    preset_values = _require_list(_required(root, "presets", ""), "presets")
    presets: list[PresetConfig | None] = []
    for index, preset_value in enumerate(preset_values):
        preset_path = f"presets[{index}]"
        if preset_value is None:
            presets.append(None)
        else:
            presets.append(_decode_preset(preset_value, preset_path))

    try:
        return StoredConfiguration(
            active=active,
            baseline=baseline,
            presets=tuple(presets),
        )
    except ValueError as error:
        raise ValueError(f"root: {error}") from error


def _decode_panel_configuration(data: object, path: str) -> PanelConfiguration:
    panel = _require_mapping(data, path)
    channel_values = _require_list(
        _required(panel, "channels", path),
        _join(path, "channels"),
    )
    button_values = _require_list(
        _required(panel, "sound_buttons", path),
        _join(path, "sound_buttons"),
    )
    channels = tuple(
        _decode_channel(channel, f"{path}.channels[{index}]")
        for index, channel in enumerate(channel_values)
    )
    buttons = tuple(
        _decode_sound_button(button, f"{path}.sound_buttons[{index}]")
        for index, button in enumerate(button_values)
    )

    try:
        return PanelConfiguration(channels=channels, sound_buttons=buttons)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _decode_channel(data: object, path: str) -> MixerChannelConfig:
    channel = _require_mapping(data, path)
    channel_kind = _required(channel, "channel_kind", path)
    if channel_kind not in _CHANNEL_KINDS:
        raise ValueError(f"{path}.channel_kind: неизвестный вид аудиоканала")

    try:
        return MixerChannelConfig(
            channel_kind=cast(ChannelKind, channel_kind),
            volume=_required(channel, "volume", path),
            muted=_required(channel, "muted", path),
            application_path=_required(channel, "application_path", path),
            display_name=_required(channel, "display_name", path),
        )
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _decode_sound_button(data: object, path: str) -> SoundButtonConfig:
    button = _require_mapping(data, path)
    try:
        return SoundButtonConfig(
            sound_id=_required(button, "sound_id", path),
            display_name=_required(button, "display_name", path),
        )
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _decode_preset(data: object, path: str) -> PresetConfig:
    preset = _require_mapping(data, path)
    name = _required(preset, "name", path)
    panel = _decode_panel_configuration(
        _required(preset, "panel", path),
        _join(path, "panel"),
    )
    try:
        return PresetConfig(name=name, panel=panel)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _require_mapping(data: object, path: str) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ValueError(f"{path}: ожидался объект")
    if not all(isinstance(key, str) for key in data):
        raise ValueError(f"{path}: имена полей должны быть строками")
    return cast(dict[str, object], data)


def _require_list(data: object, path: str) -> list[object]:
    if not isinstance(data, list):
        raise ValueError(f"{path}: ожидался массив")
    return data


def _required(data: dict[str, object], key: str, path: str) -> object:
    if key not in data:
        raise ValueError(f"{_join(path, key)}: обязательное поле отсутствует")
    return data[key]


def _join(path: str, field: str) -> str:
    if not path:
        return field
    return f"{path}.{field}"
