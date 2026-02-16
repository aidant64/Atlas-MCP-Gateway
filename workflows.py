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
    # We define this as a step so it's retried automatically on failure
    async def call_modal_slm():
        try:
            f = modal.Function.from_name("atlas-welfare-v1", "inference")
            # Format prompt similar to gateway (simplified here for brevity/reuse)
            # In a real app, share the format_prompt logic
            instruction = f"Evaluate the risk for the following action: {intent}"
            input_data = {
                "structured_inputs": context,
                "decision_context": {"timestamp": datetime.now().isoformat()}
            }
            prompt = f"Instruction: {instruction}\nInput: {json.dumps(input_data)}\nResponse:"
            
            # Modal call
            result = f.call({"prompt": prompt, "max_tokens": 256, "temperature": 0.1})
            
            response_text = result if isinstance(result, str) else result.get("generated_text", "")
            
            risk_score = 0
            if "high risk" in response_text.lower() or "escalate" in response_text.lower():
                risk_score = 85
            else:
                # Try to parse
                import re
                match = re.search(r"Risk Score:\s*(\d+)", response_text, re.IGNORECASE)
                if match:
                    risk_score = int(match.group(1))
            
            return {"risk_score": risk_score, "rationale": response_text}
        except Exception as e:
            return {"risk_score": 100, "rationale": f"System Error: {str(e)}"}

    risk_assessment = await step.run("assess_risk", call_modal_slm)
    
    # Step 2: Decision Branch
    risk_score = risk_assessment["risk_score"]
    
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
