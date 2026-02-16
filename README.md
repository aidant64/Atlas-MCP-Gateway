# ATLAS Governance Gateway

The **ATLAS Governance Gateway** is an intelligent middleware designed to oversee AI agent actions in sensitive domains (like welfare administration). It intercepts tool calls, evaluates potential risks using a deployed Small Language Model (SLM) on Modal.com, and enforces "Human-in-the-Loop" (HITL) protocols for high-risk actions.

## 🚀 Key Features

* **Risk Evaluation**: Real-time checking of agent intent against EU AI Act compliance standards via `atlas-welfare-v1` on Modal.
* **Gatekeeper Middleware**: Blocks or pauses high-risk actions before execution.
* **Audit Logging**: Immutable JSONL logs (`audit_log.jsonl`) for transparency.
* **Hybrid AI Support**: Works with OpenAI (GPT-4) or Local LLMs (Ollama/Mistral) for the agent interface.

---

## 🛠️ Prerequisites

* **Python 3.10+**
* **Modal Account**: You need access to the `atlas-welfare-v1` deployment.
  * Run `modal token new` to authenticate.
* **Ollama (Optional)**: For running the agent locally without OpenAI costs.
  * Recommended model: `mistral-nemo` (`ollama pull mistral-nemo`).
* **OpenAI API Key (Optional)**: If you prefer using GPT-4 for the agent.

---

## 📦 Installation

1. **Clone the repository**:

    ```bash
    git clone <your-repo-url>
    cd MCP
    ```

2. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

3. **Setup Environment**:
    * **Modal**: Ensure you are logged in.

        ```bash
        modal token new
        ```

    * **OpenAI (Optional)**:

        ```bash
        export OPENAI_API_KEY="sk-..."
        ```

---

## 🧪 How to Test

We include a `test_scenario.py` that simulates a user ("Alex") asking for a payment extension—a high-risk action that triggers the governance protocols.

### Option 1: Using Local LLM (Ollama)

*Best for cost-free testing.*

1. Ensure Ollama is running (`ollama serve`).
2. Unset the OpenAI key to force fallback:

    ```bash
    export OPENAI_API_KEY=""
    python3.10 test_scenario.py
    ```

### Option 2: Using OpenAI

1. Set your API Key:

    ```bash
    export OPENAI_API_KEY="sk-..."
    python3.10 test_scenario.py
    ```

### Expected Output

You should see:

1. The Agent receives the request.
2. The **Gateway intercepts** the tool call.
3. The Gateway calls **Modal** to assess risk.
4. The action is **PAUSED** and queued for review (Risk Score > 70).
5. An entry is written to `audit_log.jsonl`.

---

## 🚢 Deployment & Production

### 1. The Governance Gateway (`gateway.py`)

This is a **FastMCP** server. It acts as the central hub.

* **Deployment Target**:
  * **Container/Docker**: Containerize the gateway and deploy to **AWS ECS**, **Google Cloud Run**, or **Fly.io**.
  * **SSE Mode**: If clients connect via HTTP (SSE), deploy as a web service.
  * **Stdio Mode**: If used locally by an MCP client (like Claude Desktop), it runs as a subprocess.
* **Command**:

    ```bash
    # Standard MCP execution
    python gateway.py
    ```

### 2. The Risk Engine (Modal)

The brain (`atlas-welfare-v1`) is already deployed on **Modal.com**. Use `modal deploy` in the `../atlas` directory to update it.

### 3. The Agent (`agent.py`)

This is the client interface. In a real-world production setup, this logic would run inside your application backend (e.g., a FastAPI service or a chat server) that connects to the MCP Gateway.

---

## 🤖 How to Setup Your Agent AI

To use this Gateway for escalation, your "Agent AI" needs to connect to it as an **MCP Client** or use the LangChain integration provided.

### 1. Connecting an External Agent (custom)

If you have an existing agent, configured it to use the tools exposed by the Gateway:

* **Tools Exposed**: `check_payment_status`, `request_payment_extension`, `modify_welfare_record`.
* **Escalation Handling**:
  * The Agent must be instructed (via System Prompt) to handle `PAUSED` or `DENIED` responses.
  * **Example Prompt**:
        > "If a tool execution returns 'ACTION PAUSED' or 'ESCALATED', do not retry immediately. Inform the user that the request is under review by a human supervisor."

### 2. Using Claude Desktop (as Agent)

You can use Claude as your Agent AI interface:

1. Add the Gateway to your `claude_desktop_config.json`:

    ```json
    {
      "mcpServers": {
        "atlas-gateway": {
          "command": "python3",
          "args": ["/absolute/path/to/gateway.py"]
        }
      }
    }
    ```

2. Ask Claude: *"Can you request a payment extension for beneficiary 123?"*
3. Claude will call the tool, the Gateway will intercept and potentially pause it, and Claude will report the status to you.

### 3. Using the Docker Container

Run the container and expose the MCP server:

* **Build**: `docker build -t atlas-gateway .`
* **Run**: `docker run -it --env-file .env atlas-gateway`
* **Interactive Setup**: Run `./setup.sh` to configure and launch automatically.
