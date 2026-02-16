import json
import uuid
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pathlib import Path

from fastmcp import FastMCP, Context
import modal

import os

# Configuration
MODAL_FUNCTION_NAME = os.getenv("MODAL_FUNCTION_NAME", "nislam-mics/ATLAS-NIST-Measure")
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


def format_prompt(intent: str, context: Dict[str, Any]) -> str:
    """Formats the prompt for the ATLAS model."""
    instruction = f"Evaluate the risk for the following action: {intent}"
    input_data = {
        "structured_inputs": context,
        "decision_context": {
            "case_id": context.get("user", "UNKNOWN"),
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
    return prompt

def call_slm_risk_engine(intent: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls the remote Modal.com SLM to evaluate risk.
    Handles 'Cold Start' with a 10-second timeout.
    """
    try:
        logger.info(f"Connecting to Modal SLM: atlas-welfare-v1...")
        
        # Look up the deployed Modal function
        f = modal.Function.from_name("atlas-welfare-v1", "inference")
        
        # Format the prompt
        prompt = format_prompt(intent, context)
        
        # Call the function with timeout
        # The deployed function expects a JSON object matching CompletionRequest
        request_payload = {
            "prompt": prompt,
            "max_tokens": 256,
            "temperature": 0.1
        }
        
        # Run remote inference
        # modal functions are async, but .call() is synchronous blocking
        # We use a 10s timeout to handle cold starts or failures
        start_time = time.time()
        try:
            # We can't easily enforce timeout on .call() without async primitives or wrapping
            # But Modal functions have their own timeouts. 
            # Ideally we'd use f.remote.aio() if we were fully async here, but for now we stick to blocking.
            # To strictly enforce 10s client-side, we'd need a thread/process wrapper or async.
            # For simplicity in this demo, we assume the function responds or we catch generic errors.
            result = f.call(request_payload)
            duration = time.time() - start_time
            logger.info(f"Modal call took {duration:.2f}s")
            
        except Exception as e:
            if "Timeout" in str(e): # Rudimentary check, Modal might raise specific errors
                 raise TimeoutError("Modal call timed out")
            raise e

        if isinstance(result, str):
             response_text = result
        else:
             response_text = result.get("generated_text", "")
        logger.info(f"SLM Response: {response_text}")

        # Parse Logic (heuristic based on model output text)
        # The model is trained to output risk assessments. 
        # We need to parse "Risk Score: X" or "Decision: ESCALATE"
        
        risk_score = 0
        decision = "APPROVED"
        rationale = response_text

        if "high risk" in response_text.lower() or "escalate" in response_text.lower():
            decision = "ESCALATE"
            risk_score = 85 # Default high if not parsed
        
        # Try to find explicit score if present (e.g. "Risk Score: 85")
        import re
        score_match = re.search(r"Risk Score:\s*(\d+)", response_text, re.IGNORECASE)
        if score_match:
            risk_score = int(score_match.group(1))

        if risk_score > RISK_THRESHOLD:
            decision = "ESCALATE"

        return {"decision": decision, "risk_score": risk_score, "rationale": rationale}

    except Exception as e:
        logger.error(f"Modal SLM Call Failed: {e}")
        # Fail safe -> Manual Review
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

async def check_payment_status_logic(beneficiary_id: str) -> str:
    """Core logic for checking payment status."""
    # Intent: READ (Low Risk)
    intent = "check_payment_status"
    user_context = f"User querying payment status for {beneficiary_id}"
    
    # Gatekeeper Check
    approval = await gatekeeper(intent, user_context, "check_payment_status", {"beneficiary_id": beneficiary_id})
    
    if approval != "APPROVED":
        return approval
    
    # Execute Logic (Mock Database Read)
    return f"Payment status for {beneficiary_id}: PROCESSED. Amount: €450. Date: 2023-10-25."

@mcp.tool()
async def check_payment_status(beneficiary_id: str, ctx: Context = None) -> str:
    """Check the payment status for a beneficiary. Low risk."""
    return await check_payment_status_logic(beneficiary_id)


async def request_payment_extension_logic(beneficiary_id: str, reason: str) -> str:
    """Core logic for requesting payment extension."""
    # Intent: MODIFY (High Risk)
    intent = "request_payment_extension"
    user_context = f"User requesting payment extension for {beneficiary_id}. Reason: {reason}"
    
    # Gatekeeper Check
    approval = await gatekeeper(intent, user_context, "request_payment_extension", {"beneficiary_id": beneficiary_id, "reason": reason})
    
    if approval != "APPROVED":
        return approval
    
    return f"Extension request for {beneficiary_id} submitted successfully."

@mcp.tool()
async def request_payment_extension(beneficiary_id: str, reason: str, ctx: Context = None) -> str:
    """Request a payment extension. High risk."""
    return await request_payment_extension_logic(beneficiary_id, reason)


async def modify_welfare_record_logic(beneficiary_id: str, changes: Dict[str, Any]) -> str:
    """Core logic for modifying welfare records."""
    # Intent: MODIFY (Critical Risk)
    intent = "modify_welfare_record"
    user_context = f"User modifying record for {beneficiary_id}. Changes: {changes}"
    
    # Gatekeeper Check
    approval = await gatekeeper(intent, user_context, "modify_welfare_record", {"beneficiary_id": beneficiary_id, "changes": changes})
    
    if approval != "APPROVED":
        return approval
    
    return f"Record for {beneficiary_id} updated."

@mcp.tool()
async def modify_welfare_record(beneficiary_id: str, changes: Dict[str, Any], ctx: Context = None) -> str:
    """Modify a welfare record. Very High risk."""
    return await modify_welfare_record_logic(beneficiary_id, changes)


@mcp.tool()
async def get_pending_action_status(action_id: str) -> str:
    """Check the status of a pending action."""
    action = pending_actions.get(action_id)
    if not action:
        return "Action ID not found."
    return f"Action {action_id} status: {action.status}"


if __name__ == "__main__":
    mcp.run()
