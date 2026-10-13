"""Правила формирования и проверки Windows-сборки."""

from collections.abc import Iterable
from pathlib import Path
import sys


BinaryEntry = tuple[str, str, str]


def _is_external_icu_dll(name: str) -> bool:
    normalized = name.casefold()
    return normalized.startswith("icu") and normalized.endswith(".dll")


def filter_windows_binaries(
    binaries: Iterable[BinaryEntry],
) -> list[BinaryEntry]:
    """Исключает ICU DLL, которые должны загружаться из Windows."""

    return [
        entry
        for entry in binaries
        if not _is_external_icu_dll(Path(entry[0]).name)
    ]


def verify_windows_bundle(bundle_root: Path) -> None:
    """Проверяет ICU и обязательные плагины Qt Multimedia."""

    forbidden = sorted(
        path.relative_to(bundle_root)
        for path in bundle_root.rglob("*")
        if path.is_file() and _is_external_icu_dll(path.name)
    )
    if forbidden:
        names = ", ".join(str(path) for path in forbidden)
        raise RuntimeError(f"Сборка содержит внешние ICU DLL: {names}")

    available_names = {
        path.name.casefold()
        for path in bundle_root.rglob("*.dll")
        if path.is_file()
    }
    required_plugins = (
        "ffmpegmediaplugin.dll",
        "windowsmediaplugin.dll",
    )
    missing = tuple(
        plugin for plugin in required_plugins if plugin not in available_names
    )
    if missing:
        raise RuntimeError(
            "В сборке отсутствуют плагины Qt Multimedia: "
            + ", ".join(missing)
        )


def main(arguments: list[str] | None = None) -> int:
    actual_arguments = sys.argv[1:] if arguments is None else arguments
    if len(actual_arguments) != 1:
        print("Укажите каталог Windows-сборки", file=sys.stderr)
        return 2
    try:
        verify_windows_bundle(Path(actual_arguments[0]))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
