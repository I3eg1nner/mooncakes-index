# indexer/api.py
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np

GLM_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
RETRY_DELAYS = (0.5, 1.0, 2.0)


class MissingKeyError(RuntimeError):
    pass


class Embedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


def _post(url: str, payload: dict, key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    last: Exception | None = None
    for i in range(len(RETRY_DELAYS) + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if not (e.code == 429 or 500 <= e.code <= 599):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
        if i < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[i])
    raise last


def _l2norm(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return np.divide(v, norms, out=np.zeros_like(v), where=norms > 0)


class GlmEmbedder(Embedder):
    def __init__(self, dims: int = 1024, batch_size: int = 16, rate_limit: float = 0.5):
        self.key = os.environ.get("ZHIPUAI_API_KEY")
        if not self.key:
            raise MissingKeyError("set ZHIPUAI_API_KEY (https://open.bigmodel.cn)")
        self.dims, self.batch_size, self.rate_limit = dims, batch_size, rate_limit
        self._last = 0.0

    def embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            wait = self.rate_limit - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            resp = _post(
                GLM_URL,
                {"model": "embedding-3", "input": batch, "dimensions": self.dims},
                self.key,
            )
            ordered = sorted(resp["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in ordered)
        return _l2norm(np.asarray(out, dtype=np.float32))
