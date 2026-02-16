import httpx
from fastmcp import FastMCP
from gateway import mcp

# Check redirect
try:
    with httpx.Client(follow_redirects=False) as client:
        resp = client.get("http://localhost:8000/mcp")
        print(f"Redirect Location: {resp.headers.get('location')}")
except Exception as e:
    print(f"Check failed: {e}")

# Inspect mcp object
print("\n--- dir(mcp) ---")
print([d for d in dir(mcp) if 'app' in d or 'sse' in d or 'http' in d])

# Check what http_app actually returns
print("\n--- mcp.http_app type ---")
app_instance = mcp.http_app() if callable(mcp.http_app) else mcp.http_app
print(type(app_instance))
print(dir(app_instance))
