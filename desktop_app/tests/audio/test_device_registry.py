from dj_poltorashka.audio.device_registry import QtAudioDeviceRegistry


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self.callbacks.append(callback)

    def disconnect(self, callback: object) -> None:
        self.callbacks.remove(callback)

    def emit(self) -> None:
        for callback in tuple(self.callbacks):
            callback()  # type: ignore[operator]


class FakeDevice:
    def __init__(self, device_id: bytes, description: str) -> None:
        self._device_id = device_id
        self._description = description

    def id(self) -> bytes:
        return self._device_id

    def description(self) -> str:
        return self._description

    def preferredFormat(self) -> None:
        return None

    def isFormatSupported(self, audio_format: object) -> bool:
        return True


class FakeMediaDevices:
    def __init__(
        self,
        inputs: list[FakeDevice],
        outputs: list[FakeDevice],
    ) -> None:
        self.audioInputsChanged = FakeSignal()
        self.audioOutputsChanged = FakeSignal()
        self.input_devices = inputs
        self.output_devices = outputs
        self.default_input = inputs[0] if inputs else None
        self.default_output = outputs[0] if outputs else None

    def audioInputs(self) -> list[FakeDevice]:
        return list(self.input_devices)

    def audioOutputs(self) -> list[FakeDevice]:
        return list(self.output_devices)

    def defaultAudioInput(self) -> FakeDevice | None:
        return self.default_input

    def defaultAudioOutput(self) -> FakeDevice | None:
        return self.default_output


def test_descriptors_keep_stable_ids_duplicate_names_and_cyrillic() -> None:
    media = FakeMediaDevices(
        [
            FakeDevice(b"\x02", "Микрофон"),
            FakeDevice(b"\x01", "Микрофон"),
        ],
        [FakeDevice(b"\xff\x10", "Наушники")],
    )
    registry = QtAudioDeviceRegistry(media)

    assert [(item.device_id, item.description) for item in registry.inputs()] == [
        ("01", "Микрофон"),
        ("02", "Микрофон"),
    ]
    assert [(item.device_id, item.description) for item in registry.outputs()] == [
        ("ff10", "Наушники")
    ]


def test_default_resolution_follows_changed_windows_default() -> None:
    first = FakeDevice(b"first", "Первый")
    second = FakeDevice(b"second", "Второй")
    media = FakeMediaDevices([first, second], [first, second])
    registry = QtAudioDeviceRegistry(media)

    assert registry.resolve_input(None) is first
    assert registry.resolve_monitor(None) is first

    media.default_input = second
    media.default_output = second

    assert registry.resolve_input(None) is second
    assert registry.resolve_monitor(None) is second


def test_explicit_resolution_uses_id_and_missing_device_stays_missing() -> None:
    selected = FakeDevice(b"\x10\x20", "Одинаковое имя")
    duplicate = FakeDevice(b"\x30\x40", "Одинаковое имя")
    media = FakeMediaDevices([selected, duplicate], [selected, duplicate])
    registry = QtAudioDeviceRegistry(media)

    assert registry.resolve_input("1020") is selected
    assert registry.resolve_monitor("3040") is duplicate
    assert registry.resolve_input("ffff") is None
    assert registry.resolve_monitor("ffff") is None


def test_cable_input_recognition_is_case_insensitive_and_rejects_output() -> None:
    wrong = FakeDevice(b"wrong", "CABLE Output (VB-Audio Virtual Cable)")
    cable = FakeDevice(b"right", "cable input (vb-audio virtual cable)")
    media = FakeMediaDevices([], [wrong, cable])
    registry = QtAudioDeviceRegistry(media)

    assert registry.resolve_cable_input() is cable


def test_device_change_signals_share_callback_path_and_close_disconnects() -> None:
    media = FakeMediaDevices([], [])
    registry = QtAudioDeviceRegistry(media)
    calls: list[str] = []
    registry.on_devices_changed(lambda: calls.append("changed"))

    media.audioInputsChanged.emit()
    media.audioOutputsChanged.emit()
    registry.close()
    media.audioInputsChanged.emit()

    assert calls == ["changed", "changed"]
