import os
import re
import hashlib
from datetime import datetime, timezone
from calle import CalleClient

def get_calle_client() -> CalleClient | None:
    api_key = os.environ.get("CALLE_API_KEY")
    if not api_key:
        return None
    return CalleClient(api_key=api_key)

def dispatch_escalation(goal: str, dry_run: bool = True) -> dict:
    """
    Dispatches a voice escalation call via the CALL-E Python SDK.
    """
    if dry_run:
        # Fixture / mock behavior
        return {
            "status": "escalation_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledgement": True,
            "availability": "Available",
            "eta_minutes": 15,
            "human_approval_decision": "Approved emergency protocol",
            "transcript_summary": f"MOCK TRANSCRIPT: Operator acknowledged grid risk. Goal: {goal[:50]}..."
        }

    # Live Mode
    # 1. Validate API Key
    client = get_calle_client()
    if not client:
        raise ValueError("Missing CALLE_API_KEY for live mode.")

    # 2. Strict E.164 lock check
    test_number = os.environ.get("CALLE_AUTHORIZED_TEST_NUMBER")
    if not test_number:
        raise ValueError("Missing CALLE_AUTHORIZED_TEST_NUMBER for live mode.")
    
    if not re.match(r'^\+[1-9]\d{1,14}$', test_number):
        raise ValueError(f"Invalid E.164 phone number configured for CALLE_AUTHORIZED_TEST_NUMBER.")

    # 3. Generate a stable idempotency key (hourly stable per goal)
    current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    base_string = f"{goal}-{test_number}-{current_hour}"
    idempotency_key = hashlib.sha256(base_string.encode('utf-8')).hexdigest()

    # 4. Use CalleClient and create
    try:
        live_goal = "This is a disclosed GridGuard demonstration call to an authorized test recipient. This is not an emergency. No grid action, dispatch, emergency response, or operational decision is requested. Please confirm that you received this test call and say 'test acknowledgement received.'"
        
        schema = {
            "type": "object",
            "properties": {
                "test_acknowledged": {"type": "boolean"},
                "recipient_response": {"type": "string"},
                "test_completed": {"type": "boolean"}
            },
            "required": ["test_acknowledged", "recipient_response", "test_completed"]
        }

        created = client.calls.create(
            task=live_goal,
            recipients=[
                {
                    "phones": [test_number],
                    "region": "US",
                    "locale": "en-US",
                }
            ],
            result_schema={"type": "object", "properties": {"overall_status": {"type": "string"}}},
            recipient_result_schema=schema,
            idempotency_key=idempotency_key,
        )
        
        completed = client.calls.wait_for_result(created["id"])
        
        # 5. Parse the result and fail closed on non-terminal
        if completed.get("status") != "completed":
            raise RuntimeError(f"Call did not complete successfully. Status: {completed.get('status')}")

        # The attempt results contain the structured data
        attempts = completed.get("attempts", [])
        if not attempts:
            raise RuntimeError("No call attempts were returned.")
        
        last_attempt = attempts[-1]
        structured = last_attempt.get("structured_result", {})
        
        return {
            "status": "escalation_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_acknowledged": structured.get("test_acknowledged", False),
            "recipient_response": structured.get("recipient_response", "Unknown"),
            "test_completed": structured.get("test_completed", False),
            "transcript_summary": last_attempt.get("transcript_summary", "")
        }
    except Exception as e:
        raise RuntimeError(f"CALL-E SDK Error: {str(e)}")
