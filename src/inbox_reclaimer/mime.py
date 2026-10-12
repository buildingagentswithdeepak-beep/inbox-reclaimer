"""Explicitly opt-in MIME metadata inspection. No bodies/downloads or deletion rationale."""

from __future__ import annotations

from .attachments import AttachmentObservation, attachment_findings
from .models import IdentityMismatch, MissingMessage, ReadFailure


class GoogleMimeReader:
    """Narrow composition over the same authenticated, paced read session."""

    def __init__(self, adapter):
        self.adapter = adapter

    def resolve_identity(self):
        return self.adapter.resolve_identity()

    def get_mime(self, message_id):
        # Gmail partial-response fields suppress headers, body.data and attachment IDs.
        fields = "partId,filename,body/size"
        for _ in range(20):
            fields = f"partId,filename,body/size,parts({fields})"
        data = self.adapter._read(
            "get",
            lambda: self.adapter._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full", fields=f"id,payload({fields})"),
        )
        if data.get("id") != message_id or not isinstance(data.get("payload"), dict):
            raise ReadFailure("Invalid MIME metadata response")
        return data["payload"]


class DemoMimeReader:
    def __init__(self, adapter):
        self.adapter = adapter

    def resolve_identity(self):
        return self.adapter.resolve_identity()

    def get_mime(self, message_id):
        self.adapter.get_metadata(message_id)
        return (
            {
                "partId": "0",
                "parts": [
                    {"partId": "1", "filename": "synthetic-newsletter.pdf", "body": {"size": 2_000_000}}
                ],
            }
            if message_id.startswith("newsletter-")
            else {"partId": "0"}
        )


def parse_parts(message_id: str, payload: dict, *, min_bytes: int = 1_000_000) -> list[AttachmentObservation]:
    observations = []
    pending = [(payload, 0)]
    count = 0
    seen_parts = set()
    while pending:
        part, depth = pending.pop()
        count += 1
        if count > 10000 or depth > 20 or not isinstance(part, dict):
            raise ReadFailure("MIME metadata exceeds safe complexity limits")
        filename = part.get("filename", "")
        if not isinstance(filename, str):
            raise ReadFailure("Malformed MIME attachment name")
        if filename:
            part_id = part.get("partId")
            body = part.get("body", {})
            size = body.get("size") if isinstance(body, dict) else None
            if not isinstance(part_id, str) or not part_id or type(size) is not int or size < 0:
                raise ReadFailure("Malformed MIME attachment metadata")
            if part_id in seen_parts:
                raise ReadFailure("Ambiguous duplicate MIME part identity")
            seen_parts.add(part_id)
            if size >= min_bytes:
                observations.append(AttachmentObservation(message_id, part_id, filename, size))
        children = part.get("parts", [])
        if not isinstance(children, list) or len(children) + count > 10000:
            raise ReadFailure("Invalid or oversized MIME child list")
        pending.extend((child, depth + 1) for child in reversed(children))
    return observations


def inspect_mime(reader, inventory, *, max_messages: int = 1000, min_message_bytes: int = 5_000_000) -> dict:
    if type(max_messages) is not int or not 1 <= max_messages <= 10000:
        raise ValueError("MIME pass requires a bounded message limit (1..10000)")
    observations = []
    candidates = sorted(
        (
            m
            for m in inventory.messages
            if type(m.size_estimate) is int and m.size_estimate > min_message_bytes
        ),
        key=lambda m: m.id,
    )
    inspected = failed = 0
    for message in candidates[:max_messages]:
        if reader.resolve_identity().account_id != inventory.account_id:
            raise IdentityMismatch("Account changed during attachment inspection")
        try:
            observations.extend(parse_parts(message.id, reader.get_mime(message.id)))
            inspected += 1
        except (ReadFailure, MissingMessage):
            failed += 1
    if reader.resolve_identity().account_id != inventory.account_id:
        raise IdentityMismatch("Account changed during attachment inspection")
    result = attachment_findings(observations)
    result["coverage"] = {
        "candidate_messages": len(candidates),
        "inspected": inspected,
        "failed": failed,
        "limited": max(0, len(candidates) - max_messages),
        "body_bytes_downloaded": 0,
    }
    result["warning"] += (
        " MIME traversal is limited to 20 nesting levels; metadata observations are not a complete content comparison."
    )
    return result
