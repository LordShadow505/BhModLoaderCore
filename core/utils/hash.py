import os
import hashlib


def HashFromBytes(bytes_: bytes) -> str:
    return hashlib.sha256(bytes_).hexdigest()


def RandomHash() -> str:
    return HashFromBytes(os.urandom(2**12))


def HashFile(path: str) -> str:
    hash_ = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hash_.update(chunk)
    return hash_.hexdigest()
