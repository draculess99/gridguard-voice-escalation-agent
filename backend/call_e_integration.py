import os
import hashlib
from datetime import datetime, timezone
from calle import CalleClient

def get_calle_client() -> CalleClient | None:
    api_key = os.environ.get("CALLE_API_KEY")
    if not api_key:
        return None
    return CalleClient(api_key=api_key)

def dispatch_escalation(goal: str, test_number: str = "+15550100000", dry_run: bool = True) -> dict:
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
    if test_number != "+15550100000":
        raise ValueError(f"Live mode only authorized for test number +15550100000, got {test_number}")

    # 3. Generate a stable idempotency key (hourly stable per goal)
    current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    base_string = f"{goal}-{test_number}-{current_hour}"
    idempotency_key = hashlib.sha256(base_string.encode('utf-8')).hexdigest()

    # 4. Use CalleClient and create
    try:
        schema = {
            "type": "object",
            "properties": {
                "acknowledgement": {"type": "boolean"},
                "availability": {"type": "string"},
                "eta_minutes": {"type": "integer"},
                "escalation_status": {"type": "string"}
            },
            "required": ["acknowledgement", "availability", "eta_minutes", "escalation_status"]
        }

        created = client.calls.create(
            task=goal,
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
            "acknowledgement": structured.get("acknowledgement", False),
            "availability": structured.get("availability", "Unknown"),
            "eta_minutes": structured.get("eta_minutes", None),
            "human_approval_decision": structured.get("escalation_status", "Pending"),
            "transcript_summary": last_attempt.get("transcript_summary", "")
        }
    except Exception as e:
        raise RuntimeError(f"CALL-E SDK Error: {str(e)}")
