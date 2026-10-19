"""Private originals with opaque references and leases for safe reconciliation."""

import fcntl
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

REFERENCE = re.compile(r"[a-f0-9]{32}")
DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "storage" / "originals"


class SourceLease:
    def __init__(self, root, reference, stream):
        self.root, self.reference, self.stream = root, reference, stream

    def write(self, data: bytes):
        self.stream.write(data)

    def finish(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def discard(self):
        (self.root / self.reference).unlink(missing_ok=True)


class PrivateSources:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.environ.get("VISION_SOURCE_ROOT", str(DEFAULT_ROOT)))
        if self.root.is_symlink():
            raise ValueError("Source root must not be a symlink")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.root.is_dir() or self.root.stat().st_mode & 0o077:
            raise ValueError("Source root must be a private directory")

    def path(self, reference: str) -> Path:
        if not REFERENCE.fullmatch(reference):
            raise ValueError("Invalid source reference")
        return self.root / reference

    @contextmanager
    def create(self):
        reference = uuid.uuid4().hex
        descriptor = os.open(self.path(reference), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield SourceLease(self.root, reference, stream)

    def read(self, reference: str, max_bytes: int = 8 * 1024 * 1024) -> bytes:
        descriptor = os.open(self.path(reference), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Stored source exceeds input budget")
        return data
