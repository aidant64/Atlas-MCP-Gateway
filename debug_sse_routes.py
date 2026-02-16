from gateway import mcp, app
import sys

print("--- FastMCP Transport Mode ---")
# We don't have easy access to the transport mode property on the instance, 
# but we can check the app type or routes.

print("\n--- FastMCP App Routes (Internal) ---")
try:
    # This matches the code in gateway.py
    mcp_app = mcp.http_app(transport="sse")
    print(f"App Type: {type(mcp_app)}")
    if hasattr(mcp_app, "routes"):
        for route in mcp_app.routes:
            print(f"Path: {route.path}, Name: {route.name}, Methods: {route.methods if hasattr(route, 'methods') else 'N/A'}")
    else:
        print("No routes attribute on mcp_app")
except Exception as e:
    print(f"Error inspecting internal app: {e}")

print("\n--- Main FastAPI Routes ---")
for route in app.routes:
    print(f"Path: {route.path}, Name: {route.name}")
