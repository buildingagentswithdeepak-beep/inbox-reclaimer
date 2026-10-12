from io import BytesIO
import hashlib

import pytest

from inbox_reclaimer.attachments import AttachmentObservation, attachment_findings, hash_stream


def test_filename_size_is_only_possible_match():
    observations = [
        AttachmentObservation("m1", "part1", "invoice.pdf", 6),
        AttachmentObservation("m2", "part2", "invoice.pdf", 6),
    ]
    result = attachment_findings(observations)
    assert len(result["possible_matches"]) == 1
    assert not result["equal_content"]
    assert result["advisory_only"] is True
    assert "deletable_bytes" not in result and "batches" not in result
    assert "not duplicate messages" in result["warning"]


def test_different_content_and_equal_content_never_recommend_deletion():
    h1 = hash_stream(BytesIO(b"aaaaaa"), max_bytes=6)
    h2 = hash_stream(BytesIO(b"bbbbbb"), max_bytes=6)
    different = [
        AttachmentObservation("m1", "p", "a.pdf", 6, h1),
        AttachmentObservation("m2", "p", "a.pdf", 6, h2),
    ]
    assert not attachment_findings(different)["equal_content"]
    # Matching attachments do not compare bodies or additional attachments.
    same = different + [
        AttachmentObservation("m3", "p", "other-name.pdf", 6, h1),
        AttachmentObservation("m3", "extra", "extra.txt", 6, h2),
    ]
    result = attachment_findings(same)
    assert len(result["equal_content"]) == 2
    assert result["advisory_only"]
    assert all("action" not in item for item in result["equal_content"])


def test_hash_bounded_reads_and_limit_failure(tmp_path):
    class Bounded(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 3
            return super().read(size)

    assert hash_stream(Bounded(b"abcdef"), max_bytes=6, chunk_size=3) == hashlib.sha256(b"abcdef").hexdigest()
    with pytest.raises(ValueError, match="limit"):
        hash_stream(Bounded(b"abcdefg"), max_bytes=6, chunk_size=3)
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError):
        hash_stream(BytesIO(), max_bytes=-1)


def test_observations_validate_and_deduplicate():
    with pytest.raises(ValueError):
        AttachmentObservation("m1", "p", "a", -1)
    with pytest.raises(ValueError):
        AttachmentObservation("m1", "p", "a", 1, "not a sha256")
    a = AttachmentObservation("m1", "p", "a", 1)
    assert attachment_findings([a, a])["possible_matches"] == []
    with pytest.raises(ValueError, match="conflicting"):
        attachment_findings([a, AttachmentObservation("m1", "p", "different", 1)])


def test_hash_empty_and_failed_stream_do_not_return_partial_digest():
    assert hash_stream(BytesIO(), max_bytes=0) == hashlib.sha256(b"").hexdigest()

    class Broken:
        def read(self, size):
            raise OSError("read failed")

    with pytest.raises(OSError):
        hash_stream(Broken())
    with pytest.raises(TypeError):
        from io import StringIO

        hash_stream(StringIO("text"))
