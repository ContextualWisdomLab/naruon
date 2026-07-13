import os
import zipfile
import pytest
import asyncio
import services.archive as archive_module

from services.exceptions import (
    InvalidArchiveError,
    ArchiveSizeExceededError,
    ArchiveFileCountExceededError,
)


def test_extract_backup_success(tmp_path):
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("test.eml", b"Subject: Test Email")
        z.writestr("folder/", b"")
        z.writestr("folder/test2.eml", b"Subject: Test Email 2")

    out_dir = tmp_path / "output"
    extracted_files = archive_module.extract_backup(zip_path, out_dir)

    # Check only files are returned, not directories
    assert len(extracted_files) == 2
    assert any(f.name == "test.eml" for f in extracted_files)
    assert any(f.name == "test2.eml" for f in extracted_files)
    assert not any(f.name == "folder" for f in extracted_files)

    for f in extracted_files:
        assert f.exists()
        assert f.is_file()


def test_extract_backup_file_not_found(tmp_path):
    with pytest.raises(InvalidArchiveError, match="Failed to extract archive"):
        archive_module.extract_backup(tmp_path / "missing.zip", tmp_path / "output")


def test_extract_backup_bad_zip_file(tmp_path):
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_text("This is not a zip file")

    with pytest.raises(InvalidArchiveError, match="Failed to extract archive"):
        archive_module.extract_backup(bad_zip, tmp_path / "output")


def test_extract_backup_size_exceeded(tmp_path, monkeypatch):
    monkeypatch.setattr(archive_module, "MAX_EXTRACT_SIZE", 10)  # 10 bytes limit

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("large.txt", b"A" * 20)  # 20 bytes

    with pytest.raises(
        ArchiveSizeExceededError,
        match="Archive exceeds maximum allowed extraction size",
    ):
        archive_module.extract_backup(zip_path, tmp_path / "output")


def test_extract_backup_malformed_path(tmp_path):
    zip_path = tmp_path / "malformed.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        # Create a file with a relative path trying to escape directory
        z.writestr("../malformed.eml", b"Subject: Malformed Email")

    with pytest.raises(InvalidArchiveError, match="Unsafe archive path"):
        archive_module.extract_backup(zip_path, tmp_path / "output")

    assert not (tmp_path / "malformed.eml").exists()


def test_extract_backup_rejects_absolute_path(tmp_path):
    zip_path = tmp_path / "absolute.zip"
    escaped_path = tmp_path / "absolute-escape.eml"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(str(escaped_path), b"Subject: Absolute Email")

    with pytest.raises(InvalidArchiveError, match="Unsafe archive path"):
        archive_module.extract_backup(zip_path, tmp_path / "output")

    assert not escaped_path.exists()


def test_extract_backup_rejects_symlink_zip_entry(tmp_path):
    zip_path = tmp_path / "symlink.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        link_info = zipfile.ZipInfo("folder/link_to_tmp")
        link_info.create_system = 3
        link_info.external_attr = 0o120000 << 16
        z.writestr(link_info, "../..")

    with pytest.raises(InvalidArchiveError, match="Unsafe archive path"):
        archive_module.extract_backup(zip_path, tmp_path / "output")


def test_extract_backup_rejects_preexisting_symlink_escape(tmp_path):
    zip_path = tmp_path / "preexisting-symlink.zip"
    out_dir = tmp_path / "output"
    outside_dir = tmp_path / "outside"
    out_dir.mkdir()
    outside_dir.mkdir()
    os.symlink(outside_dir, out_dir / "link")
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("link/escaped.eml", b"Subject: Escaped Email")

    with pytest.raises(InvalidArchiveError, match="Unsafe archive path"):
        archive_module.extract_backup(zip_path, out_dir)

    assert not (outside_dir / "escaped.eml").exists()


def test_extract_backup_file_count_exceeded(tmp_path, monkeypatch):
    monkeypatch.setattr(archive_module, "MAX_FILE_COUNT", 2)

    zip_path = tmp_path / "test_count.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("file1.txt", b"1")
        z.writestr("file2.txt", b"2")
        z.writestr("file3.txt", b"3")

    with pytest.raises(
        ArchiveFileCountExceededError,
        match="Archive exceeds maximum allowed file count",
    ):
        archive_module.extract_backup(zip_path, tmp_path / "output")


def test_extract_backup_async(tmp_path):
    zip_path = tmp_path / "test_async.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("test.eml", b"Subject: Test Email")

    out_dir = tmp_path / "output"
    extracted_files = asyncio.run(archive_module.extract_backup_async(zip_path, out_dir))

    assert len(extracted_files) == 1
    assert extracted_files[0].name == "test.eml"
    assert extracted_files[0].exists()


@pytest.mark.asyncio
async def test_extract_backup_async_calls_to_thread(tmp_path, monkeypatch):
    called = False
    passed_args = ()

    async def mock_to_thread(func, *args, **kwargs):
        nonlocal called, passed_args
        called = True
        passed_args = (func, *args)
        return [tmp_path / "dummy.txt"]

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)

    zip_path = tmp_path / "test.zip"
    out_dir = tmp_path / "output"

    result = await archive_module.extract_backup_async(zip_path, out_dir)

    assert called is True
    assert passed_args == (archive_module.extract_backup, zip_path, out_dir)
    assert result == [tmp_path / "dummy.txt"]
