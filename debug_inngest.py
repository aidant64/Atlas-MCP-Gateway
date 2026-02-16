import inngest
print("--- dir(inngest) ---")
print(dir(inngest))

print("\n--- dir(inngest.Inngest) ---")
try:
    print(dir(inngest.Inngest))
except Exception as e:
    print(e)
    
print("\n--- Checking for create_function ---")
if hasattr(inngest, "create_function"):
    print("inngest.create_function exists")
else:
    print("inngest.create_function DOES NOT exist")

client = inngest.Inngest(app_id="test")
print("\n--- dir(client) ---")
print(dir(client))

if hasattr(client, "create_function"):
    print("client.create_function exists")
else:
    print("client.create_function DOES NOT exist")
