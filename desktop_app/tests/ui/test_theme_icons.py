import pytest
from PySide6.QtWidgets import QApplication

from dj_poltorashka.ui.theme import make_icon


@pytest.mark.parametrize("name", ("speaker", "microphone"))
def test_muted_icon_preserves_original_shape_and_adds_slash(qapp: QApplication, name: str) -> None:
    original = make_icon(name, size=64).pixmap(64, 64).toImage()
    muted = make_icon(f"{name}_muted", size=64).pixmap(64, 64).toImage()

    assert muted != original
    assert muted.size() == original.size()
    for row in range(original.height()):
        for column in range(original.width()):
            assert muted.pixelColor(column, row).alpha() >= original.pixelColor(column, row).alpha()
