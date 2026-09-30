"""Runtime tools shared by the Mod Loader and Mod Creator.

The applications are distributed as one-file binaries, while development runs
directly from this repository.  This module keeps the audio helper in one
well-known cache location in both cases and never downloads a replacement.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import warnings

from .worker.variables import MODLOADER_CACHE_PATH


LOGGER = logging.getLogger(__name__)
RUNTIME_AUDIO_TOOL_NAME = "wwiseutil.exe"
RUNTIME_AUDIO_TOOL_PATH = os.path.join(MODLOADER_CACHE_PATH, RUNTIME_AUDIO_TOOL_NAME)


def get_runtime_audio_tool_path() -> str:
    """Return the only path used by audio operations for ``wwiseutil.exe``."""

    return RUNTIME_AUDIO_TOOL_PATH


def is_runtime_audio_tool_available() -> bool:
    """Return whether a usable cached copy is currently present."""

    return _is_valid_file(Path(RUNTIME_AUDIO_TOOL_PATH))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_valid_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _source_candidates() -> list[Path]:
    """Yield packaged resources before the repository development copy."""

    package_dir = Path(__file__).resolve().parent
    candidates: list[Path] = [package_dir / "tools" / RUNTIME_AUDIO_TOOL_NAME]

    # PyInstaller and similar loaders expose their extracted payload here.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = Path(meipass)
        candidates.extend([
            meipass_path / "core" / "tools" / RUNTIME_AUDIO_TOOL_NAME,
            meipass_path / "tools" / RUNTIME_AUDIO_TOOL_NAME,
        ])

    # Nuitka one-file payloads and standalone runs may place data next to the
    # executable rather than beside the Python package.
    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend([
        executable_dir / "core" / "tools" / RUNTIME_AUDIO_TOOL_NAME,
        executable_dir / "tools" / RUNTIME_AUDIO_TOOL_NAME,
    ])

    # ``core`` is a junction to BhModLoaderCore/core in the source checkout;
    # its third parent is the repository root containing the source resource.
    candidates.append(package_dir.parent.parent / RUNTIME_AUDIO_TOOL_NAME)
    candidates.append(Path.cwd() / RUNTIME_AUDIO_TOOL_NAME)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(os.fspath(candidate)))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _find_source() -> Path | None:
    for candidate in _source_candidates():
        if _is_valid_file(candidate):
            return candidate
    return None


def _missing_tool_warning() -> None:
    message = (
        "wwiseutil.exe was not found.\n"
        "Full banks and external WEM files remain available,\n"
        "but internal WEM files cannot be processed until the tool is restored.\n"
        "Expected cache path: %APPDATA%\\BModloader\\wwiseutil.exe\n"
        f"Resolved path: {RUNTIME_AUDIO_TOOL_PATH}"
    )
    LOGGER.warning(message)
    warnings.warn(message, RuntimeWarning, stacklevel=2)


def ensure_runtime_audio_tool() -> str | None:
    """Install or refresh the shared cached audio helper atomically.

    The packaged copy is preferred, followed by the development copy in the
    repository root.  A valid existing cache remains usable if the source is
    unavailable or Windows temporarily refuses to replace the file.
    """

    cache_path = Path(RUNTIME_AUDIO_TOOL_PATH)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOGGER.warning("Could not create the audio tool cache %s: %s", cache_path.parent, exc)
        if _is_valid_file(cache_path):
            return os.fspath(cache_path)
        _missing_tool_warning()
        return None

    source_path = _find_source()
    if source_path is None:
        if _is_valid_file(cache_path):
            return os.fspath(cache_path)
        _missing_tool_warning()
        return None

    try:
        if source_path.resolve() == cache_path.resolve():
            return os.fspath(cache_path)
    except OSError:
        pass

    try:
        if _is_valid_file(cache_path) and _sha256(source_path) == _sha256(cache_path):
            return os.fspath(cache_path)
    except OSError as exc:
        LOGGER.warning("Could not verify the wwiseutil.exe cache: %s", exc)

    temp_path: Path | None = None
    try:
        # Keep the temporary file in the destination directory so os.replace is
        # atomic even when APPDATA and the system temp directory are different.
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{RUNTIME_AUDIO_TOOL_NAME}.",
            suffix=f".{os.getpid()}.{threading.get_ident()}.tmp",
            dir=os.fspath(cache_path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        with source_path.open("rb") as source, temp_path.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        os.replace(os.fspath(temp_path), os.fspath(cache_path))
        temp_path = None
        return os.fspath(cache_path)
    except OSError as exc:
        # Antivirus scanners or an active audio operation can briefly hold the
        # destination.  Never destroy a valid previous copy in that situation.
        if _is_valid_file(cache_path):
            LOGGER.warning("Could not update wwiseutil.exe; keeping the valid existing copy: %s", exc)
            return os.fspath(cache_path)
        LOGGER.warning("Could not install wwiseutil.exe at %s: %s", cache_path, exc)
        _missing_tool_warning()
        return None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
