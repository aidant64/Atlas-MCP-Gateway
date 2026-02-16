import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pathlib import Path

from fastmcp import FastMCP, Context
import modal

# Configuration
MODAL_FUNCTION_NAME = "nislam-mics/ATLAS-NIST-Measure"
AUDIT_LOG_FILE = "audit_log.jsonl"
RISK_THRESHOLD = 70

# Initialize FastMCP Server
mcp = FastMCP("ATLAS_Hub")

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ATLAS_Hub")


class Decision(Enum):
    APPROVED = "APPROVED"
    PAUSED = "PAUSED"
    DENIED = "DENIED"


class PendingAction:
    def __init__(self, intent: str, context: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]):
        self.id = f"action_{int(time.time())}"
        self.intent = intent
        self.context = context
        self.tool_name = tool_name
        self.arguments = arguments
        self.status = "PENDING"
        self.timestamp = datetime.now().isoformat()

# Simple in-memory queue for pending actions (mocking a database/persistent queue)
pending_actions: Dict[str, PendingAction] = {}


def log_audit(entry: Dict[str, Any]):
    """Appends an entry to the immutable audit log."""
    with open(AUDIT_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def call_slm_risk_engine(intent: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls the remote Modal.com SLM to evaluate risk.
    Handles 'Cold Start' with a 10-second timeout.
    """
    try:
        # Mocking the actual Modal call for now as we might not have access to the deployed function
        # f = modal.Function.lookup(MODAL_FUNCTION_NAME, "score")
        # result = f.call(intent, context, timeout=10) 
        
        # Simulating Modal logic for demonstration
        # In production, uncomment the lines above and remove the simulation below
        
        logger.info(f"Connecting to Modal SLM: {MODAL_FUNCTION_NAME}...")
        time.sleep(1) # Simulate network 
        
        # Simulated SLM Logic
        if "extension" in intent.lower() or "modify" in intent.lower():
            return {"decision": "ESCALATE", "risk_score": 85, "rationale": "High-risk financial modification requested."}
        else:
            return {"decision": "APPROVE", "risk_score": 10, "rationale": "Low-risk informational query."}

    except Exception as e:
        logger.error(f"Modal SLM Call Failed: {e}")
        return {"decision": "MANUAL_REVIEW", "risk_score": 100, "rationale": f"System Error/Timeout: {str(e)}"}


async def gatekeeper(intent: str, context: Dict[str, Any], tool_name: str, arguments: Dict[str, Any], ctx: Context = None) -> str:
    """
    Middleware that evaluates intent vs. policy using the SLM.
    Returns the tool output if approved, or a 'PAUSED' message if escalated.
    """
    logger.info(f"Gatekeeper evaluating: {intent}")
    
    # 1. Evaluate Risk
    slm_result = call_slm_risk_engine(intent, context)
    risk_score = slm_result.get("risk_score", 0)
    decision = slm_result.get("decision", "ESCALATE")
    
    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent_intent": intent,
        "user_context": context,
        "tool_name": tool_name,
        "arguments": arguments,
        "slm_rationale": slm_result.get("rationale"),
        "risk_score": risk_score,
        "slm_decision": decision,
        "final_outcome": "",
    }

    # 2. Threshold Logic
    if decision == "ESCALATE" or risk_score > RISK_THRESHOLD:
        # 3. Sarah's Intervention (Queue)
        action = PendingAction(intent, context, tool_name, arguments)
        pending_actions[action.id] = action
        
        audit_entry["final_outcome"] = "PAUSED_FOR_REVIEW"
        audit_entry["action_id"] = action.id
        log_audit(audit_entry)

        if ctx:
            ctx.info(f"Action paused. Risk Score: {risk_score}. Queued as {action.id}")

        return (
            f"⚠️ ACTION PAUSED: This request has been flagged (Risk Score: {risk_score}) "
            f"and escalated to Sarah (Case Officer) for review per Article 14 of the EU AI Act. "
            f"Reference ID: {action.id}. Please inform Alex."
        )

    # 4. Approved Execution (Mock execution logic here since we wrap the tool)
    audit_entry["final_outcome"] = "EXECUTED"
    log_audit(audit_entry)
    
    return "APPROVED"


# --- Tool Definitions ---

@mcp.tool()
async def check_payment_status(beneficiary_id: str, ctx: Context = None) -> str:
    """Check the payment status for a beneficiary. Low risk."""
    # In a real middleware, we'd pass the intent/context from the agent. 
    # For this demo, we infer or require it. FastMCP context can be used to pass metadata.
    # Here we simulate the gatekeeper check inside the tool for simplicity, 
    # but ideally, the agent calls a 'request_action' tool that wraps this.
    
    # Context extraction (simulated)
    user_context = {"user": "Alex", "role": "beneficiary"}
    intent = f"Check payment status for {beneficiary_id}"
    
    approval = await gatekeeper(intent, user_context, "check_payment_status", {"beneficiary_id": beneficiary_id}, ctx)
    if approval != "APPROVED":
        return approval
        
    return f"Payment status for {beneficiary_id}: PROCESSED. Amount: €450. Date: 2023-10-25."


@mcp.tool()
async def request_payment_extension(beneficiary_id: str, reason: str, ctx: Context = None) -> str:
    """Request a payment extension. High risk."""
    user_context = {"user": "Alex", "role": "beneficiary"}
    intent = f"Request payment extension for {beneficiary_id} because {reason}"
    
    approval = await gatekeeper(intent, user_context, "request_payment_extension", {"beneficiary_id": beneficiary_id, "reason": reason}, ctx)
    if approval != "APPROVED":
        return approval

    return f"Extension request for {beneficiary_id} submitted successfully."


@mcp.tool()
async def modify_welfare_record(beneficiary_id: str, changes: Dict[str, Any], ctx: Context = None) -> str:
    """Modify a welfare record. Very High risk."""
    user_context = {"user": "Alex", "role": "beneficiary"}
    intent = f"Modify welfare record for {beneficiary_id}: {changes}"
    
    approval = await gatekeeper(intent, user_context, "modify_welfare_record", {"beneficiary_id": beneficiary_id, "changes": changes}, ctx)
    if approval != "APPROVED":
        return approval

    return f"Record for {beneficiary_id} updated."


@mcp.tool()
async def get_pending_action_status(action_id: str) -> str:
    """Check the status of a pending action."""
    action = pending_actions.get(action_id)
    if not action:
        return "Action ID not found."
    return f"Action {action_id} status: {action.status}"


if __name__ == "__main__":
    mcp.run()
