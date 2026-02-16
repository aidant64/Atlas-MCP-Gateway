from gateway import app
import json

print("--- Registered Routes ---")
for route in app.routes:
    print(f"Path: {route.path}, Name: {route.name}, Methods: {route.methods if hasattr(route, 'methods') else 'N/A'}")

print("\n--- Testing Mount ---")
# Try to inspect the mounted app's routes if possible
for route in app.routes:
    if route.path == "/mcp":
        print(f"Found mount at /mcp: {route.app}")
        if hasattr(route.app, "routes"):
            print("  Sub-routes:")
            for sub in route.app.routes:
                print(f"  - {sub.path}")
