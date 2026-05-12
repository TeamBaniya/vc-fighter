# test_pytgcalls_simple.py
from pytgcalls import GroupCallFactory

# Just check if imports work
print("✓ GroupCallFactory imported successfully")

# Check available methods without creating a real client
print("\nAvailable classes in pytgcalls:")
import pytgcalls
for item in dir(pytgcalls):
    if not item.startswith('_'):
        print(f"  - {item}")

print("\n✓ pytgcalls is working!")
