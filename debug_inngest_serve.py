import inspect
try:
    from inngest.fastapi import serve
    print("Imported from inngest.fastapi")
except ImportError:
    try:
        from inngest.fast_api import serve
        print("Imported from inngest.fast_api")
    except ImportError:
        print("Could not import serve")
        exit(1)

print("\n--- serve() signature ---")
print(inspect.signature(serve))

import inngest
print("\n--- Inngest() signature ---")
print(inspect.signature(inngest.Inngest))
