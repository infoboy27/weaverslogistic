"""Atomic, locked writes for the data files.

The dashboard (two users) and the daily scan write the same CSVs. Each write goes to a
temp file in the same folder and is renamed over the target (readers never see half a file),
under an exclusive lock on <file>.lock so two writers don't interleave. On Windows (local
development) there is no fcntl and the lock is skipped; the rename is still atomic.
"""
import contextlib
import os
import tempfile
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


@contextlib.contextmanager
def locked(path: os.PathLike):
    path = Path(path)
    if fcntl is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def write_text(path: os.PathLike, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise


def write_csv(df, path: os.PathLike, **kwargs) -> None:
    kwargs.setdefault("index", False)
    write_text(path, df.to_csv(**kwargs))
