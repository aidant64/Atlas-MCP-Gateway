import asyncio
import httpx
import json
import time

# Simulation of the End-to-End Handshake
# 1. Agent calls Gateway (via logic function directly or API if running)
# 2. Gateway returns "PENDING"
# 3. Test script simulates "Sarah" approving via Webhook
# 4. Inngest workflow runs (we can't easily assert the internal inngest state here without a real Inngest server, 
#    but we can verify the webhook returns success and the gateway returns PENDING)

from gateway import request_payment_extension_logic

async def run_test():
    print(">>> Starting Inngest Handshake Test <<<")
    
    # 1. Simulate Agent Request
    print("\n[1] Agent requests payment extension...")
    response = await request_payment_extension_logic("BEN-123", "I lost my job")
    print(f"Agent received: {response}")
    
    assert "PENDING REVIEW" in response, "Failed: Did not receive PENDING status from Gateway"
    print("✅ Gateway passed governance check (returned PENDING).")
    
    # 2. Simulate Sarah's Approval (Webhook)
    print("\n[2] Simulating Sarah's Approval via Webhook...")
    # We need the FastAPI app running to hit the webhook. 
    # Since we are running this script standalone, we can't hit localhost:8000 unless we start the server.
    # For this test logic, we will assume the Inngest event was sent.
    # To properly test the webhook *code*, we can import the app and use TestClient.
    
    from fastapi.testclient import TestClient
    from gateway import app
    
    client = TestClient(app)
    
    webhook_payload = {
        "decision": "APPROVED",
        "event_id": "test_event_123"
    }
    
    wh_response = client.post("/webhook/approval", json=webhook_payload)
    print(f"Webhook Status: {wh_response.status_code}")
    print(f"Webhook Response: {wh_response.json()}")
    
    assert wh_response.status_code == 200, "Webhook failed"
    assert wh_response.json()["status"] == "Signal Sent", "Webhook did not send signal"
    
    print("✅ Webhook successfully processed approval.")
    print("\n>>> Test Complete: Handshake Logic Verified <<<")

if __name__ == "__main__":
    asyncio.run(run_test())
