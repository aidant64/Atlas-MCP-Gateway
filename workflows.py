import os
import re
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
    1. Assess Risk via Modal SLM (Llama-3.1-8B fine-tuned on NIST AI RMF).
    2. If High Risk, wait for Human Approval via HITL Dashboard.
    3. Log Audit Trail.
    """
    event_data = ctx.event.data
    intent = event_data.get("intent")
    context = event_data.get("context")
    tool_name = event_data.get("tool_name")

    # Step 1: Risk Analysis via Modal SLM
    # Defined as a step so Inngest retries automatically on failure
    async def call_modal_slm():
        try:
            # --- Connect to the deployed Modal class ---
            # deploy_modal.py defines: app = modal.App("atlas-welfare-v1")
            # with a class called Model that has a .generate() method
            Model = modal.Cls.from_name("atlas-welfare-v1", "Model")
            model = Model()

            # --- Build the Alpaca-format prompt ---
            # The ATLAS-NIST-Measure model was fine-tuned on this exact format.
            # Must match atlas_welfare_risk_api.py's format_prompt() exactly.
            instruction = f"Evaluate the risk for the following action: {intent}"
            input_data = {
                "structured_inputs": context,
                "decision_context": {
                    "case_id": context.get("beneficiary_id", "UNKNOWN") if isinstance(context, dict) else "UNKNOWN",
                    "tool_name": tool_name,
                    "timestamp": datetime.now().isoformat()
                }
            }

            prompt = f"""Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Input:
{json.dumps(input_data, indent=2)}

### Response:
"""

            # --- Call Modal with individual args (not a dict) ---
            # Model.generate(self, prompt: str, max_tokens: int, temperature: float)
            response_text = model.generate.remote(prompt, 256, 0.1)

            # --- Parse risk score from model output ---
            risk_score = 0
            risk_label = "ROUTINE"

            # Try to find an explicit numeric score in the output
            score_match = re.search(r"(?:Risk\s*Score|Score)\s*[:\-]\s*(\d+)", response_text, re.IGNORECASE)
            if score_match:
                risk_score = min(int(score_match.group(1)), 100)

            # Keyword-based fallback if no numeric score found
            if risk_score == 0:
                lower_text = response_text.lower()
                if any(w in lower_text for w in ["block", "deny", "denied", "critical risk"]):
                    risk_score = 95
                elif any(w in lower_text for w in ["high risk", "escalate", "manual review", "flag"]):
                    risk_score = 85
                elif any(w in lower_text for w in ["medium risk", "moderate"]):
                    risk_score = 55
                elif any(w in lower_text for w in ["low risk", "approve", "routine"]):
                    risk_score = 20

            # Derive label from score
            if risk_score >= 90:
                risk_label = "BLOCK"
            elif risk_score >= 70:
                risk_label = "ESCALATE"
            else:
                risk_label = "ROUTINE"

            return {
                "risk_score": risk_score,
                "risk_label": risk_label,
                "rationale": response_text.strip()[:500],
            }
        except Exception as e:
            # Fail safe -> always escalate to human review on error
            return {
                "risk_score": 100,
                "risk_label": "BLOCK",
                "rationale": f"System Error/Timeout: {str(e)}"
            }

    risk_assessment = await step.run("assess_risk", call_modal_slm)

    # Step 2: Decision Branch
    risk_score = risk_assessment["risk_score"]
    risk_label = risk_assessment.get("risk_label", "ROUTINE")

    if risk_score < 70:
        # LOW RISK -> Auto Approve
        await step.run("log_approval", lambda: print(f"✅ Auto-Approved: {intent} (score: {risk_score}, label: {risk_label})"))
        return {"status": "APPROVED", "risk_score": risk_score, "risk_label": risk_label}

    # HIGH RISK -> Wait for Human decision from HITL Dashboard
    # The dashboard POSTs to /webhook/approval which fires atlas/sarah.decision
    approval_event = await step.wait_for_event(
        "wait_for_sarah",
        event="atlas/sarah.decision",
        timeout="72h",
    )

    # Handle timeout (no reviewer responded within 72h)
    if approval_event is None:
        await step.run("log_expired", lambda: print(f"⏰ EXPIRED: {intent} — no reviewer responded in 72h"))
        return {"status": "EXPIRED", "risk_score": risk_score, "risk_label": risk_label}

    decision = approval_event.data.get("decision", "REJECTED")
    approver = approval_event.data.get("approver", "Sarah")
    note = approval_event.data.get("note", "")

    # Step 3: Final Audit Log
    await step.run("audit_log", lambda: print(
        f"📝 Final Decision for {intent}: {decision} by {approver}"
        + (f" — note: {note}" if note else "")
    ))

    return {
        "status": decision,
        "risk_score": risk_score,
        "risk_label": risk_label,
        "reviewer": approver,
    }
