from pathlib import Path

import pytest

from dj_poltorashka.sounds.library import SoundLibrary


def write_sound(path: Path, contents: bytes = b"sound-data") -> Path:
    path.write_bytes(contents)
    return path


def test_import_mp3_copies_file_and_returns_internal_id(tmp_path: Path) -> None:
    source = write_sound(tmp_path / "Заставка.mp3", b"mp3-data")
    sounds_dir = tmp_path / "library"
    library = SoundLibrary(sounds_dir, id_factory=lambda: "sound-1")

    imported = library.import_file(source)

    assert imported.sound_id == "sound-1.mp3"
    assert imported.display_name == "Заставка"
    assert imported.path == sounds_dir / "sound-1.mp3"
    assert imported.path.read_bytes() == b"mp3-data"
    assert imported.path.parent == sounds_dir


def test_import_wav_is_case_insensitive(tmp_path: Path) -> None:
    source = write_sound(tmp_path / "Signal.WAV", b"wav-data")
    sounds_dir = tmp_path / "library"
    library = SoundLibrary(sounds_dir, id_factory=lambda: "sound-2")

    imported = library.import_file(source)

    assert imported.sound_id == "sound-2.wav"
    assert imported.path.read_bytes() == b"wav-data"


def test_each_import_gets_a_distinct_id(tmp_path: Path) -> None:
    source = write_sound(tmp_path / "effect.mp3")
    generated_ids = iter(("first", "second"))
    library = SoundLibrary(tmp_path / "library", id_factory=generated_ids.__next__)

    first = library.import_file(source)
    second = library.import_file(source)

    assert first.sound_id == "first.mp3"
    assert second.sound_id == "second.mp3"
    assert first.path != second.path


def test_missing_source_is_rejected_without_partial_copy(tmp_path: Path) -> None:
    sounds_dir = tmp_path / "library"
    library = SoundLibrary(sounds_dir, id_factory=lambda: "missing")

    with pytest.raises(FileNotFoundError):
        library.import_file(tmp_path / "missing.mp3")

    assert not sounds_dir.exists() or not tuple(sounds_dir.iterdir())


def test_unsupported_extension_is_rejected_without_partial_copy(
    tmp_path: Path,
) -> None:
    source = write_sound(tmp_path / "notes.txt")
    sounds_dir = tmp_path / "library"
    library = SoundLibrary(sounds_dir, id_factory=lambda: "unsupported")

    with pytest.raises(ValueError, match="MP3|WAV"):
        library.import_file(source)

    assert not sounds_dir.exists() or not tuple(sounds_dir.iterdir())


def test_resolve_rejects_path_traversal_id(tmp_path: Path) -> None:
    outside = write_sound(tmp_path / "outside.mp3")
    library = SoundLibrary(tmp_path / "library")

    assert library.resolve(f"../{outside.name}") is None
    assert library.resolve(f"..\\{outside.name}") is None


def test_remove_unused_keeps_referenced_files(tmp_path: Path) -> None:
    first_source = write_sound(tmp_path / "first.mp3", b"first")
    second_source = write_sound(tmp_path / "second.wav", b"second")
    generated_ids = iter(("keep", "remove"))
    library = SoundLibrary(tmp_path / "library", id_factory=generated_ids.__next__)
    kept = library.import_file(first_source)
    removed = library.import_file(second_source)

    removed_ids = library.remove_unused({kept.sound_id})

    assert removed_ids == (removed.sound_id,)
    assert kept.path.exists()
    assert library.resolve(kept.sound_id) == kept.path
    assert not removed.path.exists()


def test_remove_unused_compares_references_case_insensitively(
    tmp_path: Path,
) -> None:
    source = write_sound(tmp_path / "effect.mp3")
    library = SoundLibrary(tmp_path / "library", id_factory=lambda: "abcdef")
    imported = library.import_file(source)

    assert library.resolve("ABCDEF.MP3") is not None

    removed_ids = library.remove_unused({"ABCDEF.MP3"})

    assert removed_ids == ()
    assert imported.path.exists()
