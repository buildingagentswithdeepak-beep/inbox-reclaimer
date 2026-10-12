import pytest

from inbox_reclaimer.models import Identity, Inventory, Message, ReadFailure
from inbox_reclaimer.mime import inspect_mime, parse_parts


def test_nested_mime_names_sizes_are_advisory_without_body_access():
    observations = parse_parts(
        "m1",
        {
            "partId": "0",
            "parts": [
                {"partId": "1", "filename": "<script>invoice.pdf</script>", "body": {"size": 2_000_000}},
                {
                    "partId": "2",
                    "parts": [{"partId": "2.1", "filename": "photo.jpg", "body": {"size": 3_000_000}}],
                },
            ],
        },
    )
    assert [o.part_id for o in observations] == ["1", "2.1"]
    assert all(o.sha256 is None for o in observations)
    assert observations[0].filename.startswith("<script>")


def test_malformed_or_unbounded_mime_fails_closed():
    with pytest.raises(ReadFailure):
        parse_parts("m", {"partId": "1", "filename": "file", "body": {"size": -1}})
    with pytest.raises(ReadFailure):
        parse_parts("m", {"partId": "1", "parts": [{}] * 10001})


def test_mime_opt_in_pass_accounts_partial_coverage_and_identity():
    identity = Identity("owner@example.test", "client")
    messages = tuple(Message(str(i), str(i), 1, 20_000_000, frozenset(), "x@example.test") for i in range(3))
    inventory = Inventory(identity.account_id, "gen", "H0", "start", "end", True, (), messages)

    class Reader:
        def resolve_identity(self):
            return identity

        def get_mime(self, message_id):
            if message_id == "1":
                raise ReadFailure("synthetic transport failure")
            return {"partId": "1", "filename": "same.pdf", "body": {"size": 3_000_000}}

    result = inspect_mime(Reader(), inventory, max_messages=2)
    assert result["advisory_only"] is True
    assert result["coverage"]["inspected"] == 1
    assert result["coverage"]["failed"] == 1
    assert result["coverage"]["limited"] == 1
    assert "deletable_bytes" not in result
