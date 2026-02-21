import os
import inngest
import modal
import json
from datetime import datetime

# Logic Attribution: Anna Ko <anna_ko@berkeley.edu>

# Configuration
MODAL_FUNCTION_NAME = os.getenv("MODAL_FUNCTION_NAME", "nislam-mics/ATLAS-NIST-Measure")

# Initialize Inngest Client
# INNGEST_EVENT_KEY is required for production (sending events to Inngest Cloud)
inngest_client = inngest.Inngest(
    app_id="atlas_governance",
    event_key=os.getenv("INNGEST_EVENT_KEY"),
    signing_key=os.getenv("INNGEST_SIGNING_KEY")
)

@inngest_client.create_function(
    fn_id="governance-workflow",
    trigger=inngest.TriggerEvent(event="atlas/tool.execution_requested"),
)
async def handle_governance(ctx: inngest.Context, step: inngest.Step):
    """
    Durable workflow for governance.
    1. Assess Risk via Modal.
    2. If High Risk, wait for Human Approval.
    3. Log Audit Trail.
    """
    event_data = ctx.event.data
    intent = event_data.get("intent")
    context = event_data.get("context")
    tool_name = event_data.get("tool_name")
    
    # Step 1: Risk Analysis
    # We use the pre-computed risk from the API gateway to avoid double SLM calls
    pre_computed_risk = event_data.get("pre_computed_risk")
    
    if pre_computed_risk:
        risk_assessment = pre_computed_risk
        # Log that we received it
        await step.run("log_risk_received", lambda: print(f"Received pre-computed risk: {risk_assessment['risk_score']}"))
    else:
        # Fallback if workflow triggered without pre-computed risk (e.g. from tests)
        async def call_modal_slm_fallback():
            return {"risk_score": 100, "rationale": "Fallback triggered without pre_computed_risk. Escalate to manual review."}

        risk_assessment = await step.run("assess_risk_fallback", call_modal_slm_fallback)
    
    # Step 2: Decision Branch
    risk_score = risk_assessment.get("risk_score", 100)
    
    if risk_score < 70:
        # LOW RISK -> Auto Approve
        await step.run("log_approval", lambda: print(f"✅ Auto-Approved: {intent}"))
        return {"status": "APPROVED", "risk_score": risk_score}
    
    # HIGH RISK -> Wait for Human
    # This will sleep until the event is received
    approval_event = await step.wait_for_event(
        "wait_for_sarah", 
        event="atlas/sarah.decision",
        timeout="24h", # Wait up to 24 hours
        if_timeout="fail" # Fail if no decision
    )
    
    decision = approval_event.data.get("decision")
    
    # Step 3: Final Audit Log
    await step.run("audit_log", lambda: print(f"📝 Final Decision for {intent}: {decision}"))
    
    return {"status": decision, "risk_score": risk_score, "reviewer": "Sarah"}
