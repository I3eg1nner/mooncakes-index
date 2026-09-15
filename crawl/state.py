import json
import os
import tempfile
import threading


class CrawlState:
    def __init__(self, path: str, data: dict | None = None):
        self.path = path
        self.data = data or {}
        self.data.setdefault("done", {})
        self.data.setdefault("failed", {})
        self._lock = threading.Lock()

    @classmethod
    def load(cls, path: str) -> "CrawlState":
        if os.path.exists(path):
            with open(path) as f:
                return cls(path, json.load(f))
        return cls(path)

    def done(self, name: str) -> bool:
        return name in self.data["done"]

    def mark(self, name: str, status: str) -> None:
        with self._lock:
            if status == "ok":
                self.data["done"][name] = True
                self.data["failed"].pop(name, None)
            else:
                self.data["failed"][name] = status

    def failures(self) -> list[str]:
        return sorted(self.data["failed"])

    def save(self) -> None:
        with self._lock:
            directory = os.path.dirname(self.path) or "."
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory)
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.data, f, indent=1)
                os.replace(tmp, self.path)
            except BaseException:
                os.unlink(tmp)
                raise
