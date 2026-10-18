"""Persistent format: SHA256(canonical UTF-8 [namespace,key]), first 8 bytes big endian."""

import hashlib


def bucket(key: bytes, count: int) -> int:
    if count < 1 or count > 4096:
        raise ValueError("bucket count must be 1..4096; changing it requires migration")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % count
