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
