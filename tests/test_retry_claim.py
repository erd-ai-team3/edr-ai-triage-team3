
from unittest.mock import MagicMock

from opensearchpy.exceptions import ConflictError

from soc.alerts import claim_retry


def make_client(status="failed", attempts=0):
    client = MagicMock()
    client.get.return_value = {
        "_seq_no": 5,
        "_primary_term": 1,
        "_source": {
            "alert_id": "al-test",
            "status": status,
            "attempts": attempts,
        },
    }
    return client


def test_claim_retry_success():
    client = make_client()

    result = claim_retry("al-test", client=client)

    assert result is not None
    assert result["resumed"] is True
    assert result["attempts"] == 1

    kwargs = client.update.call_args.kwargs

    assert kwargs["if_seq_no"] == 5
    assert kwargs["if_primary_term"] == 1
    assert kwargs["body"]["doc"]["status"] == "in_progress"


def test_claim_retry_completed_blocked():
    client = make_client(status="completed")

    result = claim_retry("al-test", client=client)

    assert result is None
    client.update.assert_not_called()


def test_claim_retry_pending_blocked():
    client = make_client(status="pending_approval")

    result = claim_retry("al-test", client=client)

    assert result is None
    client.update.assert_not_called()


def test_claim_retry_version_conflict():
    client = make_client()

    client.update.side_effect = ConflictError(
        409,
        "version_conflict_engine_exception",
        {"error": {"type": "version_conflict_engine_exception"}},
    )

    result = claim_retry("al-test", client=client)

    assert result is None
    assert client.update.call_count == 1
