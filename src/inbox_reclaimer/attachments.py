"""Opt-in local attachment observations; deliberately no transport or deletion API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import BinaryIO, Iterable


@dataclass(frozen=True)
class AttachmentObservation:
    message_id: str
    part_id: str
    filename: str
    decoded_size: int
    sha256: str | None = None

    def __post_init__(self):
        if not isinstance(self.message_id, str) or not self.message_id:
            raise ValueError("message_id is required")
        if not isinstance(self.part_id, str) or not self.part_id:
            raise ValueError("part_id is required")
        if not isinstance(self.filename, str):
            raise ValueError("filename must be text")
        if type(self.decoded_size) is not int or self.decoded_size < 0:
            raise ValueError("decoded_size must be a nonnegative integer")
        if self.sha256 is not None and (
            not isinstance(self.sha256, str) or re.fullmatch("[0-9a-f]{64}", self.sha256) is None
        ):
            raise ValueError("sha256 must be a lowercase SHA-256 hex digest")


def hash_stream(stream: BinaryIO, *, max_bytes: int = 25_000_000, chunk_size: int = 65536) -> str:
    """Hash already decoded bytes with bounded reads; caller owns/closes stream.

    No temporary file or whole-body buffer is created. Read one extra byte to
    detect overflow; exceeding the bound raises without returning a partial hash.
    A transport adapter must separately bound its encoded/download response.
    """
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("max_bytes must be a nonnegative limit")
    if type(chunk_size) is not int or not 1 <= chunk_size <= 1_048_576:
        raise ValueError("chunk_size must be between 1 and 1048576")
    digest = hashlib.sha256()
    consumed = 0
    while True:
        requested = min(chunk_size, max_bytes - consumed + 1)
        chunk = stream.read(requested)
        if not isinstance(chunk, bytes):
            raise TypeError("stream must return decoded bytes")
        if len(chunk) > requested:
            raise ValueError("stream exceeded requested read limit")
        consumed += len(chunk)
        if consumed > max_bytes:
            raise ValueError("attachment exceeds byte limit")
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def attachment_findings(observations: Iterable[AttachmentObservation]) -> dict:
    """Group exact filename/decoded-size candidates and independently equal hashes.

    Identity is (message_id, part_id), never attachment-ID-as-content. Conflicting
    duplicate observations fail rather than silently supplying false evidence.
    """
    unique: dict[tuple[str, str], AttachmentObservation] = {}
    for observation in observations:
        key = (observation.message_id, observation.part_id)
        if key in unique and unique[key] != observation:
            raise ValueError("conflicting observations for one message part")
        unique[key] = observation
    possible: dict[tuple[str, int], list] = {}
    equal: dict[tuple[str, int], list] = {}
    for observation in unique.values():
        if observation.filename:
            possible.setdefault((observation.filename, observation.decoded_size), []).append(observation)
        if observation.sha256:
            equal.setdefault((observation.sha256, observation.decoded_size), []).append(observation)

    def members(values):
        return [asdict(value) for value in sorted(values, key=lambda v: (v.message_id, v.part_id))]

    return {
        "advisory_only": True,
        "observed_parts": len(unique),
        "possible_matches": [
            {"filename": name, "decoded_size": size, "members": members(values)}
            for (name, size), values in sorted(possible.items())
            if len(values) > 1
        ],
        "equal_content": [
            {"sha256": digest, "decoded_size": size, "members": members(values)}
            for (digest, size), values in sorted(equal.items())
            if len(values) > 1
        ],
        "warning": "Filename and decoded size indicate possible matches only. Equal SHA-256 confirms equal "
        "attachment content, not duplicate messages. Bodies and other attachments may differ. "
        "Deleting a message removes its body and all attachments. Advisory only; no deletion batches "
        "or reclaimable-byte totals are produced.",
    }
