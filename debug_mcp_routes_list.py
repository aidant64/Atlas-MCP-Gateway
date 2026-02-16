from gateway import mcp

# Get the app instance exactly as gateway.py does
app_instance = mcp.http_app() if callable(mcp.http_app) else mcp.http_app

print("\n--- FastMCP App Routes ---")
# Starlette apps usually have .routes
if hasattr(app_instance, "routes"):
    for route in app_instance.routes:
        print(f"Path: {route.path}, Name: {route.name}, Methods: {route.methods if hasattr(route, 'methods') else 'N/A'}")
else:
    print("No routes attribute on app_instance")
