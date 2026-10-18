"""Immutable checksummed gzip JSON-lines segments (format 1)."""

import gzip
import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pp_atlas.index.postings import Positions, positions
from pp_atlas.ingest.tokenizer import TOKENIZER_VERSION, tokenize
from pp_atlas.models import Document


class CorruptSegment(RuntimeError):
    """An immutable referenced file failed integrity or format validation."""


@dataclass(frozen=True)
class Record:
    id: str
    revision: str
    title: str
    text: str
    length: int
    positions: Positions


def make_record(document: Document) -> Record:
    tokens = tokenize(document.text)
    return Record(
        document.id, uuid.uuid4().hex, document.title, document.text, len(tokens), positions(tokens)
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_segment(directory: Path, records: Iterable[Record]) -> tuple[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jsonl.gz"
    temporary = directory / f".{name}.tmp"
    target = directory / name
    try:
        with temporary.open("xb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
                stream.write(
                    (json.dumps({"format": 1, "tokenizer": TOKENIZER_VERSION}) + "\n").encode()
                )
                for record in records:
                    value = [
                        record.id,
                        record.revision,
                        record.title,
                        record.text,
                        record.length,
                        record.positions,
                    ]
                    stream.write(
                        (
                            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
                        ).encode()
                    )
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(temporary, target)
        # Directory durability is supported on the required Linux failure-test platform.
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return name, sha256(target)
    finally:
        temporary.unlink(missing_ok=True)


def read_segment(path: Path, expected: str) -> Iterator[Record]:
    try:
        if sha256(path) != expected:
            raise CorruptSegment(f"checksum mismatch: {path.name}")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            header: object = json.loads(stream.readline(4096))
            if header != {"format": 1, "tokenizer": TOKENIZER_VERSION}:
                raise CorruptSegment("unsupported segment/tokenizer version")
            while line := stream.readline(32_000_001):
                if len(line) > 32_000_000:
                    raise CorruptSegment("oversized segment record")
                value: object = json.loads(line)
                if not isinstance(value, list) or len(value) != 6:
                    raise CorruptSegment("invalid segment record")
                ident, revision, title, text, length, raw_positions = value
                if not all(isinstance(item, str) for item in (ident, revision, title, text)):
                    raise CorruptSegment("invalid string fields")
                if type(length) is not int or length < 0 or not isinstance(raw_positions, dict):
                    raise CorruptSegment("invalid length or postings")
                postings: Positions = {}
                for term, values in raw_positions.items():
                    if not isinstance(term, str) or not isinstance(values, list):
                        raise CorruptSegment("invalid posting")
                    if any(type(p) is not int or p < 0 or p >= length for p in values):
                        raise CorruptSegment("invalid positions")
                    if values != sorted(set(values)):
                        raise CorruptSegment("unordered positions")
                    postings[term] = tuple(values)
                yield Record(
                    cast(str, ident),
                    cast(str, revision),
                    cast(str, title),
                    cast(str, text),
                    length,
                    postings,
                )
    except (OSError, ValueError, EOFError) as error:
        raise CorruptSegment(f"unreadable segment {path.name}: {error}") from error
