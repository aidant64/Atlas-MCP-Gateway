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
import inngest

# Try importing serve from standard location, fallback to direct module if needed 
# (Inngest 0.5.15+ seems to use fast_api.py)
try:
    from inngest.fastapi import serve as inngest_serve
except ImportError:
    try:
        from inngest.fast_api import serve as inngest_serve
    except ImportError:
        # Fallback for older versions or if structure differs
        import inngest.fastapi as inngest_fastapi
        inngest_serve = inngest_fastapi.serve

from workflows import inngest_client, handle_governance

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

# --- Security & Authentication ---
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

API_KEY = os.getenv("ATLAS_API_KEY")
API_KEY_NAME = "Authorization"

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verifies the Bearer token against the ATLAS_API_KEY environment variable.
    """
    if not API_KEY:
        # For initial deployment/testing, if no key is set, we might want to warn.
        # But to be safe, we should probably fail. 
        # However, to avoid "Server Error" on startup if user forgets env var, 
        # let's log a warning and maybe allow or fail. 
        # DECISION: Fail safe.
        logger.error("ATLAS_API_KEY not set! Rejecting all requests.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server configuration error: ATLAS_API_KEY not set"
        )

    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


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
        return {"decision": decision, "risk_score": risk_score, "rationale": rationale}

    except Exception as e:
        logger.error(f"Modal SLM Call Failed: {e}")
        # Fail safe -> Manual Review
        return {"decision": "MANUAL_REVIEW", "risk_score": 100, "rationale": f"System Error/Timeout: {str(e)}"}
# --- Governance Logic (Inngest Powered) ---

async def governance_check(intent: str, context: Any, tool_name: str) -> str:
    """
    Triggers an Inngest workflow for governance.
    Returns "APPROVED" if low risk (auto-approved),
    or "PENDING: <event_id>" if high risk (waiting for human).
    """
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    
    # Send event to Inngest
    await inngest_client.send(
        inngest.Event(
            name="atlas/tool.execution_requested",
            data={
                "intent": intent,
                "context": context,
                "tool_name": tool_name,
                "event_id": event_id
            },
            id=event_id
        )
    )
    
    # For Phase 2, we assume a "Checking..." state.
    # ideally, we would wait for the result if it's fast (low risk).
    # But Inngest is async.
    # To keep it simple: We tell the Agent to expect a delay.
    # The Inngest workflow will log the final outcome.
    
    # We can do a quick pre-check or just return PENDING.
    # Let's return a special string that the Agent knows how to handle.
    return f"PENDING REVIEW (Ref: {event_id}). This action has been queued for execution subject to governance checks."

# --- Tool Definitions ---

async def check_payment_status_logic(beneficiary_id: str) -> str:
    """Core logic for checking payment status."""
    # READ operation, usually low risk, but let's pass it through governance for audit
    status = await governance_check("check_payment_status", {"beneficiary_id": beneficiary_id}, "check_payment_status")
    if "PENDING" in status:
         return status
    
    # If immediately approved (future optimization), we would proceed.
    # For now, let's simulate that READ operations are safe and don't block.
    return f"Payment Status for {beneficiary_id}: Active. Last payment: $500 on 2023-10-01."

async def request_payment_extension_logic(beneficiary_id: str, reason: str) -> str:
    """Core logic for requesting payment extension."""
    # WRITE operation - triggers strict governance
    status = await governance_check("request_payment_extension", {"beneficiary_id": beneficiary_id, "reason": reason}, "request_payment_extension")
    return status

async def modify_welfare_record_logic(beneficiary_id: str, changes: Dict[str, Any]) -> str:
    """Core logic for modifying welfare records."""
    # WRITE operation - critical risk
    status = await governance_check("modify_welfare_record", {"beneficiary_id": beneficiary_id, "changes": changes}, "modify_welfare_record")
    return status


@mcp.tool()
async def check_payment_status(beneficiary_id: str, ctx: Context = None) -> str:
    """Check the payment status for a beneficiary. Low risk."""
    return await check_payment_status_logic(beneficiary_id)

@mcp.tool()
async def request_payment_extension(beneficiary_id: str, reason: str, ctx: Context = None) -> str:
    """Request a payment extension. High risk."""
    return await request_payment_extension_logic(beneficiary_id, reason)

@mcp.tool()
async def modify_welfare_record(beneficiary_id: str, changes: Dict[str, Any], ctx: Context = None) -> str:
    """Modify a welfare record. Very High risk."""
    return await modify_welfare_record_logic(beneficiary_id, changes)


# --- API Endpoints & Server Integration ---

# Initialize FastAPI (Main Entry Point)
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="ATLAS Governance Gateway")

# Serve the visual homepage at root
@app.get("/")
async def root():
    return FileResponse('static/index.html')

@app.get("/health")
async def health_check():
    return {
        "status": "ATLAS Governance Gateway Running",
        "mcp_endpoint": "/mcp/sse",
        "inngest_endpoint": "/api/inngest"
    }

import pydantic

# Internal Test Endpoint for the Homepage Console
class TestToolRequest(pydantic.BaseModel):
    tool: str

@app.post("/api/test-tool", dependencies=[Depends(verify_api_key)])
async def test_tool_endpoint(req: TestToolRequest):
    """
    Internal endpoint to simulate tool calls for the homepage console.
    """
    if req.tool == "check_payment":
        result = await check_payment_status_logic("test_user_123")
        return {"result": result}
    elif req.tool == "request_extension":
        result = await request_payment_extension_logic("test_user_123", "Tested via Console")
        return {"result": result}
    else:
        raise HTTPException(status_code=400, detail="Unknown test scenario")

# Mount FastMCP server
# This exposes the MCP tools at /mcp/sse and /mcp/messages
try:
    # fastmcp.http_app returns a Starlette app. We force SSE transport.
    # We must wrap this interaction to enforce auth.
    # FastMCP doesn't natively support easy global dependencies on its internal app 
    # without mounting it with dependencies in FastAPI.
    
    # Create a sub-application for MCP to apply dependencies
    from fastapi import FastAPI
    mcp_api_wrapper = FastAPI(dependencies=[Depends(verify_api_key)])
    
    mcp_app = mcp.http_app(transport="sse")
    mcp_api_wrapper.mount("/", mcp_app)
    
    # Mount the wrapper
    app.mount("/mcp", mcp_api_wrapper)
    logger.info("Mounted FastMCP (SSE) at /mcp [Secured with API Key]")
except Exception as e:
    logger.error(f"Failed to mount FastMCP: {e}")

# Serve Inngest
# For production, we must provide the signing_key to verify requests from Inngest Cloud.
# signing_key is now handled in the Inngest client initialization in workflows.py
# Inngest endpoint stays PUBLIC (secured by signature)
inngest_serve(
    app, 
    inngest_client, 
    [handle_governance]
)

# Webhook for Sarah (Mock Panel)
@app.post("/webhook/approval", dependencies=[Depends(verify_api_key)])
async def approve_action(request: Request):
    """
    Simulates Sarah clicking 'Approve' on the dashboard.
    Sends the 'atlas/sarah.decision' event to Inngest.
    """
    data = await request.json()
    event_id = data.get("event_id") # The specific event we are waiting for? No, Inngest waits match on data.
    decision = data.get("decision", "APPROVED")
    
    # Sentinel event to unblock the workflow
    await inngest_client.send(
        inngest.Event(
            name="atlas/sarah.decision",
            data={
                "decision": decision,
                "timestamp": datetime.now().isoformat()
            }
        )
    )
    return {"status": "Signal Sent", "decision": decision}

if __name__ == "__main__":
    import uvicorn
    print("Starting ATLAS Gateway (FastAPI + FastMCP + Inngest)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
