# ATLAS Governance Gateway (Phase 2)

**Inngest-Powered Governance Architecture**

The **ATLAS Governance Gateway** is a centralized hub that intercepts AI Agent tool calls, evaluates potential risks using a Modal.com SLM, and manages "Human-in-the-Loop" (HITL) escalations via durable **Inngest** workflows.

> **Logic Attribution**: The governance logic and dataset design are attributed to **Anna Ko <anna_ko@berkeley.edu>** (UC Berkeley). This implementation strictly follows the "approve -> auto_approve" deterministic flow for low-risk actions per project v3.0 findings.

## 🚀 Key Features

* **Durable Governance**: Uses **Inngest** to manage long-running human review workflows that survive server restarts.
* **FastMCP + FastAPI**: Exposes MCP tools via a robust web server.
* **Risk Evaluation**: Real-time checking against EU AI Act standards via `atlas-welfare-v1` on Modal.
* **Compliance**: Enforces Article 14 by pausing high-risk actions until human approval is received.

---

## 🛠️ Architecture

1. **Gateway (`gateway.py`)**: A **FastAPI** application that:
    * Hosts the **FastMCP** server.
    * Serves the **Inngest** endpoint (`/api/inngest`).
    * Receives **Webhooks** from the Sarah Portal (`/webhook/approval`).
2. **Workflows (`workflows.py`)**: Defines the Inngest functions.
    * `handle_governance`: Assesses risk -> Auto-approves LOW risk -> Waits for event `atlas/sarah.decision` for HIGH risk.
3. **Agent (`agent.py`)**:
    * configured to handle "PENDING REVIEW" responses gracefully.

---

## 📦 Installation

1. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

2. **Setup Environment**:
    Create a `.env` file for **Inngest Cloud** (Production):

    ```bash
    export OPENAI_API_KEY="sk-..."       
    export MODAL_TOKEN_ID="..."          
    export MODAL_TOKEN_SECRET="..."
    
    # Required for Inngest Cloud
    export INNGEST_EVENT_KEY="cn-..."    
    export INNGEST_SIGNING_KEY="sign-..." 
    ```

3. **Start the Gateway**:
    * **Production**: Just run `python gateway.py`. The app will connect to Inngest Cloud.
    * **Local Dev**: Run `npx inngest-cli@latest dev` in a separate terminal, then run `python gateway.py`.

---

## 🧪 How to Test (End-to-End Handshake)

We have a script `test_handshake.py` that simulates the full asynchronous flow:

1. **Agent Request**: Simulates calling `request_payment_extension`.
2. **Gateway Response**: Returns `PENDING REVIEW` (Action Paused).
3. **Governance Workflow**: Inngest triggers, checks risk (High), and waits.
4. **Sarah's Approval**: The script posts to `/webhook/approval`.
5. **Completion**: The workflow completes (check Inngest dashboard).

Run it:

```bash
# Ensure gateway.py is running in another terminal!
python test_handshake.py
```

---

## 📂 Project Structure

* `gateway.py`: FastAPI app with FastMCP and Inngest.
* `workflows.py`: Inngest workflow definitions.
* `agent.py`: LangChain Agent.
* `test_handshake.py`: Verification script.
