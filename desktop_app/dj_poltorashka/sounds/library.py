"""Импорт и обслуживание управляемых копий звуковых файлов."""

from collections.abc import Callable
from dataclasses import dataclass
import ntpath
import os
from pathlib import Path
import shutil
import tempfile
import uuid


_SUPPORTED_EXTENSIONS = (".mp3", ".wav")
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


@dataclass(frozen=True)
class ImportedSound:
    """Результат импорта звука в библиотеку приложения."""

    sound_id: str
    display_name: str
    path: Path


class SoundLibrary:
    """Управляет копиями поддерживаемых звуков в одном каталоге."""

    def __init__(
        self,
        sounds_dir: Path,
        id_factory: Callable[[], str] | None = None,
    ):
        self._sounds_dir = Path(sounds_dir)
        self._id_factory = id_factory or self._generate_id

    def import_file(self, source: Path) -> ImportedSound:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(f"Звуковой файл не найден: {source_path}")

        extension = source_path.suffix.lower()
        if extension not in _SUPPORTED_EXTENSIONS:
            raise ValueError("Поддерживаются только файлы MP3 и WAV")

        generated_id = self._id_factory()
        if not isinstance(generated_id, str) or not generated_id:
            raise ValueError("Генератор должен вернуть непустой строковый идентификатор")
        sound_id = f"{generated_id}{extension}"
        if not self._is_valid_filename(sound_id):
            raise ValueError("Сгенерирован недопустимый идентификатор звука")

        self._sounds_dir.mkdir(parents=True, exist_ok=True)
        destination = self._sounds_dir / sound_id
        if destination.exists():
            raise FileExistsError(f"Звук с идентификатором {sound_id} уже существует")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self._sounds_dir,
                prefix=f".{sound_id}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            shutil.copyfile(source_path, temporary_path)
            os.replace(temporary_path, destination)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

        return ImportedSound(
            sound_id=sound_id,
            display_name=source_path.stem,
            path=destination,
        )

    def resolve(self, sound_id: str) -> Path | None:
        if not self._is_valid_sound_id(sound_id):
            return None
        path = self._sounds_dir / sound_id
        if not path.is_file():
            return None
        return path

    def remove_unused(self, referenced_ids: set[str]) -> tuple[str, ...]:
        if not self._sounds_dir.is_dir():
            return ()

        normalized_references = {
            ntpath.normcase(sound_id) for sound_id in referenced_ids
        }
        removed_ids: list[str] = []
        for path in sorted(self._sounds_dir.iterdir(), key=lambda item: item.name):
            sound_id = path.name
            if (
                path.is_file()
                and self._is_valid_sound_id(sound_id)
                and ntpath.normcase(sound_id) not in normalized_references
            ):
                path.unlink()
                removed_ids.append(sound_id)
        return tuple(removed_ids)

    @staticmethod
    def _generate_id() -> str:
        return uuid.uuid4().hex

    @classmethod
    def _is_valid_sound_id(cls, sound_id: object) -> bool:
        if not isinstance(sound_id, str) or not cls._is_valid_filename(sound_id):
            return False
        return Path(sound_id).suffix.lower() in _SUPPORTED_EXTENSIONS

    @staticmethod
    def _is_valid_filename(filename: str) -> bool:
        if not filename or filename in (".", ".."):
            return False
        if filename.endswith((" ", ".")):
            return False
        if any(character in _WINDOWS_FORBIDDEN_CHARACTERS for character in filename):
            return False
        if any(ord(character) < 32 for character in filename):
            return False
        stem = filename.split(".", maxsplit=1)[0].upper()
        return stem not in _WINDOWS_RESERVED_NAMES
