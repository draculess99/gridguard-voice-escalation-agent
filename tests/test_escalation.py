import pytest
from unittest.mock import patch, MagicMock
from backend.call_e_integration import dispatch_escalation

def test_dry_run_mode():
    """Test that dry_run mode returns fixture data without attempting any network calls."""
    res = dispatch_escalation(goal="Test goal", dry_run=True)
    assert res["status"] == "escalation_completed"
    assert res["acknowledgement"] is True
    assert res["availability"] == "Available"
    assert "MOCK TRANSCRIPT" in res["transcript_summary"]

@patch.dict("os.environ", clear=True)
def test_live_mode_missing_api_key():
    """Test that live mode fails closed if CALLE_API_KEY is missing."""
    with pytest.raises(ValueError, match="Missing CALLE_API_KEY"):
        dispatch_escalation(goal="Test goal", dry_run=False)

@patch.dict("os.environ", {"CALLE_API_KEY": "fake_key"})
def test_live_mode_missing_test_number():
    """Test that live mode fails closed if CALLE_AUTHORIZED_TEST_NUMBER is missing."""
    with pytest.raises(ValueError, match="Missing CALLE_AUTHORIZED_TEST_NUMBER"):
        dispatch_escalation(goal="Test goal", dry_run=False)

@patch.dict("os.environ", {"CALLE_API_KEY": "fake_key", "CALLE_AUTHORIZED_TEST_NUMBER": "12345"})
def test_live_mode_invalid_test_number():
    """Test that live mode fails closed if CALLE_AUTHORIZED_TEST_NUMBER is not valid E.164."""
    with pytest.raises(ValueError, match="Invalid E.164 phone number configured"):
        dispatch_escalation(goal="Test goal", dry_run=False)

@patch("backend.call_e_integration.CalleClient")
@patch.dict("os.environ", {"CALLE_API_KEY": "fake_key", "CALLE_AUTHORIZED_TEST_NUMBER": "+15550199999"})
def test_live_mode_successful_call(mock_calle_client):
    """Test the successful execution and parsing of a live call using the SDK mock."""
    mock_client = MagicMock()
    mock_calle_client.return_value = mock_client
    
    mock_client.calls.create.return_value = {"id": "call_123"}
    
    mock_client.calls.wait_for_result.return_value = {
        "status": "completed",
        "attempts": [
            {
                "transcript_summary": "Real operator acknowledged test.",
                "structured_result": {
                    "test_acknowledged": True,
                    "recipient_response": "test acknowledgement received",
                    "test_completed": True
                }
            }
        ]
    }
    
    res = dispatch_escalation(goal="Critical Risk", dry_run=False)
    
    assert res["status"] == "escalation_completed"
    assert res["test_acknowledged"] is True
    assert res["recipient_response"] == "test acknowledgement received"
    assert res["test_completed"] is True
    assert "Real operator" in res["transcript_summary"]
    
    # Verify SDK was called correctly
    mock_client.calls.create.assert_called_once()
    call_kwargs = mock_client.calls.create.call_args.kwargs
    
    # Verify the goal is the safe live goal, NOT the critical risk string
    assert "Critical Risk" not in call_kwargs["task"]
    assert "critical" not in call_kwargs["task"].lower()
    assert "availability" not in call_kwargs["task"].lower()
    assert "not an emergency" in call_kwargs["task"].lower()
    assert "This is a disclosed GridGuard demonstration call" in call_kwargs["task"]
    assert "test acknowledgement received" in call_kwargs["task"]
    
    assert call_kwargs["recipients"][0]["phones"] == ["+15550199999"]
    assert "idempotency_key" in call_kwargs
    assert call_kwargs["result_schema"]["type"] == "object"
    assert "test_acknowledged" in call_kwargs["recipient_result_schema"]["properties"]
    
    mock_client.calls.wait_for_result.assert_called_once_with("call_123")

@patch("backend.call_e_integration.CalleClient")
@patch.dict("os.environ", {"CALLE_API_KEY": "fake_key", "CALLE_AUTHORIZED_TEST_NUMBER": "+15550199999"})
def test_idempotency_keys_are_unique_per_call(mock_calle_client):
    """Test that two separate live-dispatch attempts generate different idempotency keys."""
    mock_client = MagicMock()
    mock_calle_client.return_value = mock_client
    
    mock_client.calls.create.return_value = {"id": "call_123"}
    mock_client.calls.wait_for_result.return_value = {
        "status": "completed",
        "attempts": [{"structured_result": {"test_acknowledged": True, "recipient_response": "test", "test_completed": True}}]
    }
    
    dispatch_escalation(goal="Critical Risk", dry_run=False)
    call1_kwargs = mock_client.calls.create.call_args_list[0].kwargs
    key1 = call1_kwargs["idempotency_key"]
    
    dispatch_escalation(goal="Critical Risk", dry_run=False)
    call2_kwargs = mock_client.calls.create.call_args_list[1].kwargs
    key2 = call2_kwargs["idempotency_key"]
    
    assert key1 != key2, "Idempotency keys must be unique per live dispatch attempt."

@patch("backend.call_e_integration.CalleClient")
@patch.dict("os.environ", {"CALLE_API_KEY": "fake_key", "CALLE_AUTHORIZED_TEST_NUMBER": "+15550199999"})
def test_live_mode_task_creation_failure(mock_calle_client):
    """Test safe diagnostic output when task creation fails."""
    mock_client = MagicMock()
    mock_calle_client.return_value = mock_client
    
    # Simulate SDK raising an exception on create
    mock_client.calls.create.side_effect = Exception("API rate limit exceeded")
    
    res = dispatch_escalation(goal="Critical Risk", dry_run=False)
    
    assert res["status"] == "failed"
    assert res["creation_succeeded"] is False
    assert res["failure_reason"] == "Exception"
    assert "API rate limit exceeded" in res["message"]
    # Ensure secrets/numbers aren't leaked in diagnostic wrapper
    assert "fake_key" not in str(res)
    assert "+15550199999" not in str(res)

@patch("backend.call_e_integration.CalleClient")
@patch.dict("os.environ", {"CALLE_API_KEY": "fake_key", "CALLE_AUTHORIZED_TEST_NUMBER": "+15550199999"})
def test_live_mode_task_wait_failure(mock_calle_client):
    """Test safe diagnostic output when a created task fails in wait_for_result."""
    mock_client = MagicMock()
    mock_calle_client.return_value = mock_client
    
    mock_client.calls.create.return_value = {"id": "call_123", "created_at": "2026-09-03"}
    
    mock_client.calls.wait_for_result.return_value = {
        "status": "failed",
        "error": "Recipient blocked",
        "error_code": 403,
        "message": "Call blocked by recipient network."
    }
    
    res = dispatch_escalation(goal="Critical Risk", dry_run=False)
    
    assert res["status"] == "failed"
    assert res["creation_succeeded"] is True
    assert res["call_id"] == "call_123"
    assert res["failure_reason"] == "Recipient blocked"
    assert res["error_code"] == 403
    # Ensure secrets/numbers aren't leaked in diagnostic wrapper
    assert "fake_key" not in str(res)
    assert "+15550199999" not in str(res)
