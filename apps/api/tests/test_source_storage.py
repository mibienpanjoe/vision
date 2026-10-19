import os

import pytest
from app.core.errors import PublicError
from app.core.storage import DEFAULT_ROOT, PrivateSources
from app.services.ingestion.inputs import validate_text_source


def test_original_is_exact_private_and_opaque(tmp_path):
    store = PrivateSources(tmp_path / "originals")
    payload = "é🦊é\r\nThe captain wore blue.".encode()
    with store.create() as source:
        source.write(payload)
        source.finish()
        reference = source.reference
        assert store.read(reference) == payload
    assert len(reference) == 32
    assert os.stat(store.root).st_mode & 0o777 == 0o700
    assert os.stat(store.root / reference).st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        store.read("../secret")


def test_symlink_sources_and_shared_directory_fail_closed(tmp_path):
    root = tmp_path / "originals"
    store = PrivateSources(root)
    victim = tmp_path / "private"
    victim.write_bytes(b"do not read")
    (root / ("a" * 32)).symlink_to(victim)
    with pytest.raises(OSError):
        store.read("a" * 32)
    root.chmod(0o755)
    with pytest.raises(ValueError):
        PrivateSources(root)


@pytest.mark.parametrize("data", [b"", b" \n", b"\xff", b"a\x00b", b"%PDF-1.7\npretending to be text", b"PK\x03\x04archive"])
def test_invalid_or_disguised_text_rejected(data):
    with pytest.raises(PublicError) as error:
        validate_text_source(data)
    assert error.value.code == "INVALID_SOURCE"


def test_unicode_original_is_not_normalized():
    data = "é🦊é\r\n".encode()
    assert validate_text_source(data) == data.decode("utf-8")


def test_failed_write_can_be_removed_without_following_links(tmp_path):
    store = PrivateSources(tmp_path / "originals")
    with store.create() as source:
        reference = source.reference
        source.write(b"partial")
        source.discard()
    assert not (store.root / reference).exists()


def test_default_sources_stay_in_ignored_project_storage():
    from pathlib import Path

    assert DEFAULT_ROOT == Path(__file__).resolve().parents[3] / "storage" / "originals"
