import asyncio
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZipInfo

from .exceptions import (
    InvalidArchiveError,
    ArchiveSizeExceededError,
    ArchiveFileCountExceededError,
)

MAX_EXTRACT_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
MAX_FILE_COUNT = 100000
ZIP_UNIX_FILE_TYPE_MASK = 0o170000
ZIP_UNIX_SYMLINK_TYPE = 0o120000


def _is_zipinfo_symlink(info: ZipInfo) -> bool:
    return (info.external_attr >> 16) & ZIP_UNIX_FILE_TYPE_MASK == ZIP_UNIX_SYMLINK_TYPE


def _resolve_safe_archive_member(output_dir: Path, info: ZipInfo) -> Path:
    normalized_name = info.filename.replace("\\", "/")
    if (
        not normalized_name
        or normalized_name.startswith("/")
        or _is_zipinfo_symlink(info)
    ):
        raise InvalidArchiveError("Unsafe archive path")

    parts = normalized_name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise InvalidArchiveError("Unsafe archive path")
    if parts and parts[0].endswith(":"):
        raise InvalidArchiveError("Unsafe archive path")

    target_path = output_dir.joinpath(*parts).resolve(strict=False)
    try:
        target_path.relative_to(output_dir)
    except ValueError as exc:
        raise InvalidArchiveError("Unsafe archive path") from exc

    return target_path


def extract_backup(zip_path: str | Path, output_dir: str | Path) -> list[Path]:
    """
    Extracts a zip archive to the specified output directory.

    WARNING: This function performs blocking I/O operations. When called from
    an async web layer (e.g. FastAPI), it must be executed in a thread pool using
    `fastapi.concurrency.run_in_threadpool` or `asyncio.to_thread()`.

    Args:
        zip_path: The path to the zip archive to extract.
        output_dir: The directory where the contents should be extracted.

    Returns:
        A list of Path objects for the extracted files (excluding directories).

    Raises:
        InvalidArchiveError: If the zip file is not found or corrupted.
        ArchiveSizeExceededError: If the uncompressed size exceeds the maximum allowed limit.
        ArchiveFileCountExceededError: If the archive exceeds the maximum allowed file count.
    """
    zip_path = Path(zip_path)
    output_dir = Path(output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_paths = []

    try:
        with ZipFile(zip_path, "r") as z:
            total_size = 0
            file_count = 0

            for info in z.infolist():
                if info.is_dir():
                    continue

                file_count += 1
                if file_count > MAX_FILE_COUNT:
                    raise ArchiveFileCountExceededError(
                        f"Archive exceeds maximum allowed file count of {MAX_FILE_COUNT}."
                    )

                target_path = _resolve_safe_archive_member(output_dir, info)

                target_path.parent.mkdir(parents=True, exist_ok=True)

                with z.open(info) as source, open(target_path, "wb") as target:
                    while chunk := source.read(8192):
                        total_size += len(chunk)
                        if total_size > MAX_EXTRACT_SIZE:
                            raise ArchiveSizeExceededError(
                                f"Archive exceeds maximum allowed extraction size of {MAX_EXTRACT_SIZE} bytes."
                            )
                        target.write(chunk)

                extracted_paths.append(target_path)

    except (BadZipFile, FileNotFoundError) as e:
        raise InvalidArchiveError(f"Failed to extract archive: {e}") from e

    return extracted_paths


async def extract_backup_async(
    zip_path: str | Path, output_dir: str | Path
) -> list[Path]:
    """
    Async wrapper for extract_backup to be used safely in async contexts.
    """
    return await asyncio.to_thread(extract_backup, zip_path, output_dir)
