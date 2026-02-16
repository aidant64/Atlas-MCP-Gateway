import asyncio
import os
import json
import logging
# Ensure we can import from current directory
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from agent import create_atlas_agent
from gateway import pending_actions, AUDIT_LOG_FILE

async def run_test_scenario():
    print(">>> Starting ATLAS Governance Gateway Test Scenario <<<")
    
    # 1. Setup Environment
    # Verify API Key exists or mock it for the test if possible (LangChain needs real key usually)
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY is missing. Agent will attempt to use Local LLM (Ollama).")


    # 2. Initialize Agent
    print("\n[1] Initializing Agent...")
    agent_executor = create_atlas_agent()
    
    # 3. Simulate "Alex" Request
    # Explicit instruction to ensure smaller local models trigger the tool
    user_input = "Request a payment extension for beneficiary ID BEN-123. The reason is: I lost my job."
    print(f"\n[2] User (Alex) says: \"{user_input}\"")
    
    print("\n[3] Agent processing (Intercepted by Gateway)...")
    try:
        from langchain_core.messages import HumanMessage
        # Invoke the graph with the initial state (list of messages)
        response = await agent_executor.ainvoke({"messages": [HumanMessage(content=user_input)]})
        
        # Get the last message from the AI
        final_message = response["messages"][-1]
        print(f"\n[4] Agent Response:\n{final_message.content}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Agent Execution Failed: {e}")

    # 4. Verification
    print("\n[5] Verifying Audit Log and Pending Actions...")
    
    # Check Audit Log
    found_log = False
    if os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, "r") as f:
            for line in f:
                entry = json.loads(line)
                if "request_payment_extension" in str(entry):
                    print(f"✅ Audit Log Entry Found: {entry['final_outcome']} | Risk Score: {entry['risk_score']}")
                    found_log = True
                    break
    
    if not found_log:
        print("❌ Verification Failed: No relevant audit log entry found.")
    
    # Check Pending Queue
    if len(pending_actions) > 0:
        print(f"✅ Escalation Queue: {len(pending_actions)} action(s) pending review.")
        for pid, action in pending_actions.items():
            print(f"   - Pending Action ID: {pid} | Intent: {action.intent}")
    else:
        print("❌ Verification Failed: No actions in pending queue (Expected Escalation).")

if __name__ == "__main__":
    asyncio.run(run_test_scenario())
