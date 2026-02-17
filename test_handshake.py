import asyncio
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
import os

# Configuration
GATEWAY_URL = "http://localhost:8000/mcp/sse"
WEBHOOK_URL = "http://localhost:8000/webhook/approval"

# API Key Auth
API_KEY = os.getenv("ATLAS_API_KEY", "test-key-123")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

async def test_high_risk_workflow():
    print("🚀 Starting End-to-End Governance Test")
    print(f"Connecting to Gateway at {GATEWAY_URL}...")

    # 1. Connect to MCP Gateway
    try:
        # Pass headers to sse_client (supported in recent versions of mcp/fastmcp depending on implementation)
        # If headers are not supported directly by sse_client in the installed version, 
        # we might need a custom transport or check version. 
        # Assuming standard mcp.client.sse.sse_client supports headers or we might need to patch it.
        # Verified: mcp.client.sse.sse_client takes (url, headers=...) in some versions, or we need to check.
        # If it fails, we will know.
        async with sse_client(GATEWAY_URL, headers=HEADERS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools to verify connection
                tools = await session.list_tools()
                print(f"✅ Connected! Found {len(tools.tools)} tools.")
                
                # 2. Trigger High-Risk Action
                print("\n⚠️  Triggering High-Risk Action: request_payment_extension...")
                result = await session.call_tool(
                    "request_payment_extension",
                    arguments={"beneficiary_id": "user_123", "reason": "Hardship"}
                )
                
                output = result.content[0].text
                print(f"gateway response: {output}")
                
                if "PENDING REVIEW" in output:
                    print("✅ Governance Check Active: Action paused for review.")
                    
                    # Parse event_id if possible (Ref: evt_...)
                    import re
                    match = re.search(r"Ref: (evt_\w+)", output)
                    event_id = match.group(1) if match else "unknown"
                    print(f"   Event ID: {event_id}")
                    
                    # 3. Simulate Human Approval
                    print(f"\n👤 Simulating Sarah (Human Reviewer) Approval for {event_id}...")
                    await asyncio.sleep(2) # Wait a bit for Inngest to process
                    
                    response = httpx.post(
                        WEBHOOK_URL,
                        json={"decision": "APPROVED", "event_id": event_id},
                        headers=HEADERS
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Approval Sent! Status: {response.json()}")
                    else:
                        print(f"❌ Failed to send approval: {response.text}")
                    
                else:
                    print("❌ Unexpected response (Should be PENDING).")

    except TypeError as e:
        if "headers" in str(e):
            print(f"❌ Connection Failed: sse_client() got an unexpected keyword argument 'headers'.")
            print("The installed version of 'mcp' might not support headers in sse_client yet.")
        else:
            print(f"❌ Connection Failed: {e}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        print("Ensure the server is running.")

if __name__ == "__main__":
    asyncio.run(test_high_risk_workflow())
