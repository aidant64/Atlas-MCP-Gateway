from gateway import mcp, app
import json

print("\n--- FastMCP Settings ---")
try:
    print(mcp.settings)
except:
    print("No settings attribute")

print("\n--- FastMCP Routes (Internal App) ---")
try:
    mcp_app = mcp.http_app() if callable(mcp.http_app) else mcp.http_app
    for route in mcp_app.routes:
        print(f"Path: {route.path}, Name: {route.name}, Methods: {route.methods if hasattr(route, 'methods') else 'N/A'}")
except Exception as e:
    print(f"Error inspecting internal app: {e}")
