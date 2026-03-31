"""单 work_dir 互斥锁（fcntl），满足实施手册 P0-2。"""

from __future__ import annotations

import errno
import os


class WorkdirLock:
    """非阻塞尝试或阻塞等待独占锁。"""

    def __init__(self, work_dir: str, name: str = ".autoloop-runner.lock"):
        self.path = os.path.join(os.path.abspath(work_dir), name)
        self._fp = None

    def acquire(self, blocking: bool = True) -> bool:
        import fcntl

        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._fp = open(self.path, "a+", encoding="utf-8")
        flags = fcntl.LOCK_EX
        if not blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._fp.fileno(), flags)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EACCES):
                if self._fp:
                    self._fp.close()
                    self._fp = None
                return False
            raise
        return True

    def release(self) -> None:
        import fcntl

        if self._fp is not None:
            try:
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
            finally:
                self._fp.close()
                self._fp = None

    def __enter__(self) -> WorkdirLock:
        if not self.acquire(blocking=True):
            raise RuntimeError("无法获取锁")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
