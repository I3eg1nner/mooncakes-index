import io
import os
import posixpath
import zipfile


def _safe_name(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return False
    if "\\" in name:
        return False
    if len(name) > 1 and name[1] == ":":
        return False
    norm = posixpath.normpath(name)
    return not norm.startswith("..") and not norm.startswith("/")


def safe_extract(data: bytes, dest: str, max_bytes: int = 50_000_000, max_files: int = 5_000) -> None:
    if len(data) > max_bytes:
        raise ValueError(f"archive too large: {len(data)}")
    z = zipfile.ZipFile(io.BytesIO(data))
    infos = z.infolist()
    if len(infos) > max_files:
        raise ValueError(f"too many entries: {len(infos)}")
    if sum(i.file_size for i in infos) > max_bytes:
        raise ValueError("uncompressed size exceeds cap")
    for info in infos:
        if not _safe_name(info.filename):
            raise ValueError(f"unsafe path in archive: {info.filename}")
    os.makedirs(dest, exist_ok=True)
    for info in infos:
        target = os.path.join(dest, info.filename)
        if info.filename.endswith("/"):
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
        with z.open(info) as src, open(target, "wb") as out:
            out.write(src.read())
